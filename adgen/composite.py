"""Composite strategy: Gemini generates the advertising scene + headline; the exact product pixels
come from the human-approved cutout and are composited locally with Pillow.

The scene call receives ONLY a text prompt built from geography, season, required_text and
layout/camera constraints: no reference image, no cutout, no profile, no product description.

Pixel invariant: the cutout is pasted at native scale (never resampled). Every fully opaque cutout
pixel must be identical in the composed canvas and in the saved PNG, else CompositeInvariantError.

Interior backing: transparent regions fully enclosed by the product (e.g. a shoe opening where packing
tissue was removed from the reference photo) would show the generated scene through the product. A
deterministic, soft, dark-neutral backing layer is drawn BEHIND the cutout in those regions only. The
cutout asset is never modified, and the backing can never replace an opaque product pixel.

Layer order: scene -> contact shadow -> interior backing -> exact cutout.
"""

import io
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import google.genai
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from adgen import config
from adgen.cutout import Cutout
from adgen.errors import GenerationError, NoImageReturnedError, OutputProcessingError, redact
from adgen.generator import _call_gemini
from adgen.image_io import decode_base64_image, finalize_dir, load_reference_image
from adgen.spec import GenerationSpec, spec_warnings

CANVAS = 1024                 # final square canvas (1:1 request, long edge <= 1024)
HEADLINE_BAND = 0.22          # top share of the canvas reserved for the headline
BOTTOM_MARGIN = 0.02
MIN_PRODUCT_HEIGHT = 0.45     # product must span >= 45% of canvas height (readability); never upscaled
SHADOW = {"offset_x": 0, "offset_y": 10, "blur_radius": 14, "opacity": 0.45}
# Interior backing for enclosed non-product cavities (see module docstring).
BACKING = {
    "cavity_rule": "cutout pixels with alpha < 128 not connected to the cutout border (enclosed by the product)",
    "min_cavity_pixels": 64,      # smaller enclosed specks are ignored
    "grow_px": 2,                 # extend under the cavity's soft rim so it blends onto the backing, not the scene
    "colour_top": [34, 32, 30],   # vertical dark-neutral gradient across the cavity's bounding box
    "colour_bottom": [68, 64, 60],
}

VIEW_PHRASES = {
    "overhead": "a top-down flat-lay photograph shot from directly above",
    "near_overhead": "a high-angle photograph shot from almost directly above",
    "eye_level": "an eye-level photograph",
}

SCENE_PROMPT_TEMPLATE = """Create the background scene for a professional display advertisement: {view_phrase}.

CONTEXT
- Target geography: {geography}
- Season: {season}
- Reflect this geography and season naturally through the setting, surface materials, lighting, props and atmosphere, using several location-specific visual cues.

LAYOUT (important)
- Top band (roughly the top fifth of the image): render the headline text described below.
- Everything below the top band: a clean, flat, uncluttered surface seen from the same camera angle, leaving a large empty central area where a product will be placed later. Place contextual props only near the edges of the image.
- Do not include any product, merchandise, packaging or logos in the empty central area.

TEXT
- Render the following text exactly as written, character for character, exactly once, in the top band:
  "{required_text}"
- Use a clean, highly legible typeface with strong contrast.
- Do not add any other text, slogans, prices, claims, logos or watermarks.

STYLE
- Polished commercial advertising photography with soft, even lighting."""


class CompositeInvariantError(Exception):
    """A pipeline-composed image violated the exact-pixel product invariant (internal error)."""


@dataclass(frozen=True)
class CompositeResult:
    run_dir: Path
    image_path: Path
    metadata_path: Path
    metadata: dict
    finalization: str = "rename"   # "rename" or "copy" (verified copy fallback), see image_io.finalize_dir


def build_scene_prompt(spec: GenerationSpec, view: str) -> str:
    return SCENE_PROMPT_TEMPLATE.format(
        view_phrase=VIEW_PHRASES[view], geography=spec.geography, season=spec.season,
        required_text=spec.required_text,
    )


def build_scene_request(prompt: str) -> dict:
    """Text-only scene request: the product image is never sent."""
    return {
        "model": config.GENERATOR_MODEL,
        "input": [{"type": "text", "text": prompt}],
        "response_modalities": list(config.RESPONSE_MODALITIES),
        "response_format": {"type": "image", "image_size": config.IMAGE_SIZE, "aspect_ratio": config.ASPECT_RATIO},
        "store": False,
    }


def placement(cutout_size: tuple[int, int], canvas: int = CANVAS) -> tuple[int, int]:
    """Deterministic top-left position: horizontally centred, bottom-aligned below the headline band."""
    w, h = cutout_size
    zone_top = round(canvas * HEADLINE_BAND)
    zone_bottom = canvas - round(canvas * BOTTOM_MARGIN)
    if w > canvas or h > zone_bottom - zone_top:
        raise OutputProcessingError(f"Cutout {w}x{h} does not fit the product zone at native scale "
                                    f"({canvas}x{zone_bottom - zone_top}); resampling the product is not allowed.")
    if h < canvas * MIN_PRODUCT_HEIGHT:
        raise OutputProcessingError(f"Cutout height {h}px is below the minimum readable size "
                                    f"({MIN_PRODUCT_HEIGHT:.0%} of {canvas}px); upscaling is not allowed.")
    return (canvas - w) // 2, zone_bottom - h


def cavity_mask(cutout: Image.Image) -> Image.Image:
    """Enclosed cavities of the cutout (255 = cavity), grown by BACKING['grow_px']. Deterministic."""
    product = cutout.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    padded = ImageOps.expand(product, 1, 0)
    ImageDraw.floodfill(padded, (0, 0), 128)  # everything reachable from outside the product
    w, h = product.size
    holes = padded.crop((1, 1, w + 1, h + 1)).point(lambda v: 255 if v == 0 else 0)

    kept = Image.new("L", holes.size, 0)
    work = holes.copy()
    while (box := work.getbbox()) is not None:  # one enclosed component per iteration; bounded by pixel count
        seed = next((x, box[1]) for x in range(box[0], box[2]) if work.getpixel((x, box[1])) == 255)
        ImageDraw.floodfill(work, seed, 100)
        component = work.point(lambda v: 255 if v == 100 else 0)
        work = work.point(lambda v: 255 if v == 255 else 0)  # drop the component just measured
        if component.histogram()[255] >= BACKING["min_cavity_pixels"]:
            kept = ImageChops.lighter(kept, component)
    grow = BACKING["grow_px"]
    return kept.filter(ImageFilter.MaxFilter(2 * grow + 1)) if grow else kept


def backing_layer(mask: Image.Image) -> Image.Image | None:
    """Dark-neutral vertical gradient over the cavity bounding box, clipped to `mask`. None if no cavity."""
    box = mask.getbbox()
    if box is None:
        return None
    top, bottom = BACKING["colour_top"], BACKING["colour_bottom"]
    span = max(1, box[3] - box[1] - 1)
    column = Image.new("RGB", (1, mask.size[1]), tuple(top))
    for yy in range(box[1], box[3]):
        t = (yy - box[1]) / span
        column.putpixel((0, yy), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    for yy in range(box[3], mask.size[1]):
        column.putpixel((0, yy), tuple(bottom))
    return column.resize(mask.size, Image.Resampling.NEAREST)


def compose(scene: Image.Image, cutout: Image.Image, canvas: int = CANVAS) -> tuple[Image.Image, dict]:
    """Scene fitted to the canvas + contact shadow + interior backing + exact cutout pixels (deterministic)."""
    base = scene.convert("RGB")
    scene_resized = base.size != (canvas, canvas)
    if scene_resized:
        base = base.resize((canvas, canvas), Image.Resampling.LANCZOS)  # scene only, never the product
    x, y = placement(cutout.size, canvas)

    alpha = cutout.getchannel("A")
    shadow_alpha = Image.new("L", (canvas, canvas), 0)
    shadow_alpha.paste(alpha, (x + SHADOW["offset_x"], y + SHADOW["offset_y"]))
    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(SHADOW["blur_radius"]))
    shadow_alpha = shadow_alpha.point(lambda a: round(a * SHADOW["opacity"]))
    out = Image.composite(Image.new("RGB", (canvas, canvas), (0, 0, 0)), base, shadow_alpha)

    cavity = cavity_mask(cutout)
    backing = backing_layer(cavity)
    if backing is not None:
        out.paste(backing, (x, y), cavity)  # behind the product: the cutout is pasted over it next
    out.paste(cutout.convert("RGB"), (x, y), alpha)

    verify_pixel_identity(out, cutout, (x, y))
    cavity_pixels = cavity.histogram()[255]
    info = {
        "canvas": [canvas, canvas], "scene_raw_resolution": list(scene.size), "scene_resized": scene_resized,
        "placement": {"x": x, "y": y, "width": cutout.size[0], "height": cutout.size[1]},
        "product_scale": 1.0, "final_resize_factor": 1.0, "shadow": dict(SHADOW),
        "interior_backing": {
            "used": backing is not None,
            "note": ("All preserved opaque product pixels come directly from the reference cutout; a deterministic "
                     "interior backing fills the reference photo's non-product cavity where packing tissue was "
                     "removed.") if backing is not None else "no enclosed cavity in the cutout",
            "cavity_pixels_including_rim": cavity_pixels,
            "cavity_bbox_in_cutout": list(cavity.getbbox()) if backing is not None else None,
            "parameters": dict(BACKING),
        },
    }
    return out, info


def verify_pixel_identity(image: Image.Image, cutout: Image.Image, position: tuple[int, int]) -> int:
    """Every fully opaque cutout pixel must be identical in `image`. Returns the number checked."""
    x, y = position
    region = image.convert("RGB").crop((x, y, x + cutout.size[0], y + cutout.size[1]))
    opaque = cutout.getchannel("A").point(lambda a: 255 if a == 255 else 0)
    diff = ImageChops.difference(region, cutout.convert("RGB"))
    if Image.composite(diff, Image.new("RGB", cutout.size), opaque).getbbox() is not None:
        raise CompositeInvariantError("Composited product pixels differ from the approved cutout.")
    return opaque.histogram()[255]


def integration_observation(ad: Image.Image, cutout: Image.Image, position: tuple[int, int]) -> dict:
    """SUPPLEMENTARY, NON-GATING deterministic proxies for visual integration (engineering metric).

    Not part of the official PASS/FAIL gate and not a visual judgment: simple measurements that make
    obvious mismatches visible (brightness / colour-cast gap between product and surroundings).
    """
    x, y = position
    w, h = cutout.size
    alpha = cutout.getchannel("A")
    product_stat = ImageStat.Stat(cutout.convert("RGB"), alpha)
    ring = Image.new("L", ad.size, 0)
    ring.paste(alpha, (x, y))
    ring = ImageChops.subtract(ring.filter(ImageFilter.MaxFilter(41)), ring)
    surround_stat = ImageStat.Stat(ad.convert("RGB"), ring)

    def luma(m):
        return 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]

    hist = alpha.histogram()
    return {
        "gating": False,
        "kind": "supplementary engineering metric (deterministic proxies, not a visual judgment)",
        "lighting_brightness_gap": round(abs(luma(product_stat.mean) - luma(surround_stat.mean)), 1),
        "colour_cast_gap_red_minus_blue": round(abs((product_stat.mean[0] - product_stat.mean[2])
                                                    - (surround_stat.mean[0] - surround_stat.mean[2])), 1),
        "product_height_share": round(h / ad.size[1], 3),
        "edge_soft_pixel_share": round(sum(hist[1:255]) / max(1, sum(hist[1:])), 4),
        "shadow": dict(SHADOW),
        "perspective_note": "cutout view is recorded; scene prompt requests the same camera angle",
    }


def generate_composite(
    spec: GenerationSpec,
    client,
    cutout: Cutout,
    target_dir: Path,
    correction: str | None = None,
    secret: str | None = None,
) -> CompositeResult:
    """One scene call + local composite. Writes scene.jpg, ad.png and metadata.json into target_dir."""
    reference = load_reference_image(spec.product_image)
    if reference.sha256 != cutout.metadata["reference_image_sha256"]:
        raise OutputProcessingError("Approved cutout does not belong to this reference image.")
    target_dir = Path(target_dir)
    if target_dir.exists():
        raise OutputProcessingError(f"Output directory already exists: {target_dir}")
    view = cutout.metadata["view"]
    base_prompt = build_scene_prompt(spec, view)
    prompt = f"{base_prompt}\n\n{correction}" if correction else base_prompt

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    interaction = _call_gemini(client, build_scene_request(prompt), secret)
    duration = time.perf_counter() - t0

    status = str(getattr(interaction, "status", None))
    model_text = getattr(interaction, "output_text", None) or ""
    output_image = getattr(interaction, "output_image", None)
    if status != "completed" or output_image is None or not getattr(output_image, "data", None):
        detail = f" Model text: {model_text!r}" if model_text else ""
        raise NoImageReturnedError(redact(f"Gemini returned no scene image (status={status}).{detail}", secret))

    scene_bytes = decode_base64_image(output_image.data)
    try:
        scene = Image.open(io.BytesIO(scene_bytes))
        scene.load()
    except Exception as e:
        raise OutputProcessingError(f"Returned scene could not be decoded: {e}") from None

    ad, info = compose(scene, cutout.image)
    position = (info["placement"]["x"], info["placement"]["y"])

    tmp = target_dir.with_name(target_dir.name + ".tmp")
    tmp.mkdir(parents=True)
    try:
        (tmp / "scene.jpg").write_bytes(scene_bytes)
        ad.save(tmp / "ad.png", format="PNG")  # lossless: product pixels stay exact
        with Image.open(tmp / "ad.png") as saved:
            checked = verify_pixel_identity(saved, cutout.image, position)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    metadata = {
        "schema_version": 1,
        "strategy": "composite",
        "spec_id": spec.id,
        "inputs": {
            "product_image": str(spec.product_image),
            "product_image_sha256": reference.sha256,
            "product_image_mime_type": reference.mime_type,
            "geography": spec.geography,
            "season": spec.season,
            "required_text": spec.required_text,
        },
        "prompt": prompt,
        "scene_prompt_sent_with_images": False,
        "model": config.GENERATOR_MODEL,
        "request": {"api": "interactions.create", "image_size": config.IMAGE_SIZE,
                    "aspect_ratio": config.ASPECT_RATIO, "response_modalities": list(config.RESPONSE_MODALITIES),
                    "store": False, "input_parts": ["text"]},
        "response": {"interaction_id": getattr(interaction, "id", None), "status": status,
                     "mime_type": getattr(output_image, "mime_type", None), "model_text": redact(model_text, secret)},
        "cutout": {"file": cutout.path.name, "sha256": cutout.metadata["cutout_sha256"],
                   "reference_image_sha256": cutout.metadata["reference_image_sha256"],
                   "view": view, "verified_by": cutout.metadata.get("verified_by", "")},
        "composite": info,
        "pixel_identity": {"checked_opaque_pixels": checked, "mismatches": 0, "verified_in_saved_png": True},
        "integration_observation": integration_observation(ad, cutout.image, position),
        "output": {"image_file": "ad.png", "scene_file": "scene.jpg", "format": "PNG",
                   "raw_resolution": list(scene.size), "saved_resolution": list(ad.size),
                   "downscaled": False, "max_long_edge": config.MAX_LONG_EDGE},
        "warnings": spec_warnings(spec),
        "timestamp_utc": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "duration_seconds": round(duration, 3),
        "sdk_version": google.genai.__version__,
    }
    (tmp / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    method = finalize_dir(tmp, target_dir)
    return CompositeResult(target_dir, target_dir / "ad.png", target_dir / "metadata.json", metadata, method)
