"""Exact-pixel product cutouts for the composite strategy.

Workflow (mirrors the reference profile):
  reference image + HUMAN-MADE mask  --build-->  cutouts/<name>.draft.png/.json (human_verified=false)
  human reviews the draft            --approve--> cutouts/<name>.png/.json      (human_verified=true)
  pipeline preflight                 --load-->    only approved cutouts whose lineage re-verifies

Mask convention: grayscale, same pixel size as the reference; white (255) = keep product,
black (0) = remove; intermediate values = partial edge alpha. The cutout's RGB channels are
copied byte-for-byte from the reference; the mask only supplies the alpha channel.
The cutout is a derived artifact of the single reference image, not an extra input.
"""

import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, UnidentifiedImageError

from adgen import config
from adgen.errors import CutoutError

VIEWS = ("overhead", "near_overhead", "eye_level")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
DRAFT = ".draft"
MIN_KEEP_FRACTION = 0.01  # a mask keeping <1% of the image is almost certainly wrong
MAX_KEEP_FRACTION = 0.95  # a mask keeping >95% has not removed the background


@dataclass(frozen=True)
class Cutout:
    image: Image.Image  # RGBA, cropped to the mask's bounding box
    metadata: dict
    path: Path


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(Path(path).read_bytes())


def _rel(path: Path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _open(path: Path, what: str) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
        return img
    except FileNotFoundError:
        raise CutoutError(f"{what} not found: {path}") from None
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        raise CutoutError(f"{what} is not a readable image: {path} ({e})") from None


def load_mask(mask_path: Path, reference_size: tuple[int, int]) -> Image.Image:
    """Validate a human-made mask and return it as mode 'L' (white = keep)."""
    mask = _open(mask_path, "Mask")
    if mask.size != reference_size:
        raise CutoutError(f"Mask is {mask.size[0]}x{mask.size[1]} but the reference is "
                          f"{reference_size[0]}x{reference_size[1]}; they must match exactly.")
    if mask.mode in ("1", "L"):
        mask = mask.convert("L")
    elif mask.mode == "RGB":
        r, g, b = mask.split()
        if ImageChops.difference(r, g).getbbox() or ImageChops.difference(r, b).getbbox():
            raise CutoutError("Mask must be grayscale (black/white); it contains colored pixels.")
        mask = r
    else:
        raise CutoutError(f"Unsupported mask mode {mask.mode!r}; save it as a grayscale PNG (no transparency).")

    histogram = mask.histogram()
    total = reference_size[0] * reference_size[1]
    keep = sum(count * value for value, count in enumerate(histogram)) / 255 / total
    if keep < MIN_KEEP_FRACTION:
        raise CutoutError(f"Mask keeps only {keep:.1%} of the image; is white the product?")
    if keep > MAX_KEEP_FRACTION:
        raise CutoutError(f"Mask keeps {keep:.1%} of the image; the background was not removed.")
    return mask


def make_cutout(reference: Image.Image, mask: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """RGB copied exactly from the reference, alpha from the mask, cropped to the mask bbox."""
    bbox = mask.getbbox()
    rgba = reference.convert("RGB").copy()
    rgba.putalpha(mask)
    return rgba.crop(bbox), bbox


def build_draft(reference_path: Path, mask_path: Path, name: str, view: str = "overhead",
                cutouts_dir: Path = config.CUTOUTS_DIR, mask_source: str = "manual") -> Path:
    """Create cutouts/<name>.draft.png + .draft.json (human_verified=false). Never overwrites."""
    if not NAME_PATTERN.match(name):
        raise CutoutError("Cutout name may only contain letters, digits, '-' and '_'.")
    if view not in VIEWS:
        raise CutoutError(f"view must be one of {VIEWS}")
    cutouts_dir = Path(cutouts_dir)
    png_path, json_path = cutouts_dir / f"{name}{DRAFT}.png", cutouts_dir / f"{name}{DRAFT}.json"
    if png_path.exists() or json_path.exists():
        raise CutoutError(f"Draft {png_path.name} already exists; not overwriting.")

    reference = _open(reference_path, "Reference image")
    if reference.mode != "RGB":
        raise CutoutError(f"Reference image must be RGB, got {reference.mode}.")
    mask = load_mask(mask_path, reference.size)
    cutout, bbox = make_cutout(reference, mask)

    buf = io.BytesIO()
    cutout.save(buf, format="PNG")
    alpha_hist = cutout.getchannel("A").histogram()
    metadata = {
        "cutout_version": 1,
        "human_verified": False,
        "verified_by": "",
        "verified_at": "",
        "reference_image": _rel(reference_path),
        "reference_image_sha256": _sha_file(reference_path),
        "reference_size": list(reference.size),
        "mask_file": _rel(mask_path),
        "mask_sha256": _sha_file(mask_path),
        "mask_source": mask_source,
        "cutout_file": png_path.name,
        "cutout_sha256": _sha_bytes(buf.getvalue()),
        "crop_box": list(bbox),
        "cutout_size": list(cutout.size),
        "opaque_pixels": alpha_hist[255],
        "partial_alpha_pixels": sum(alpha_hist[1:255]),
        "view": view,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "review_notes": [
            f"DRAFT built from mask_file (source: {mask_source}). Not trusted until a human reviews it.",
            "Check that only the product is kept (no shoe box, floor or shadows) and edges are clean.",
            "Check that 'view' describes the camera angle of the reference photo.",
        ],
    }
    cutouts_dir.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(buf.getvalue())
    _write_json(json_path, metadata)
    return png_path


def approve(name: str, verified_by: str, cutouts_dir: Path = config.CUTOUTS_DIR) -> Path:
    """Human approval: copy the reviewed draft to cutouts/<name>.png/.json with human_verified=true."""
    if not verified_by.strip():
        raise CutoutError("verified_by is required for approval.")
    cutouts_dir = Path(cutouts_dir)
    draft_png, draft_json = cutouts_dir / f"{name}{DRAFT}.png", cutouts_dir / f"{name}{DRAFT}.json"
    if not draft_png.is_file() or not draft_json.is_file():
        raise CutoutError(f"No draft for {name!r} in {cutouts_dir}.")
    metadata = json.loads(draft_json.read_text(encoding="utf-8"))
    if _sha_file(draft_png) != metadata["cutout_sha256"]:
        raise CutoutError("Draft PNG does not match its recorded SHA-256; rebuild the draft.")
    png_path, json_path = cutouts_dir / f"{name}.png", cutouts_dir / f"{name}.json"
    if png_path.exists() or json_path.exists():
        raise CutoutError(f"Approved cutout {png_path.name} already exists; not overwriting.")

    png_path.write_bytes(draft_png.read_bytes())
    metadata.update(
        human_verified=True, verified_by=verified_by.strip(),
        verified_at=datetime.now(timezone.utc).date().isoformat(),
        cutout_file=png_path.name, derived_from_draft=draft_json.name,
    )
    metadata["review_notes"] = [f"Approved by {verified_by.strip()} after visual review of {draft_png.name}."]
    _write_json(json_path, metadata)
    return png_path


def load_approved_cutout(reference_path: Path, cutouts_dir: Path = config.CUTOUTS_DIR) -> Cutout:
    """Preflight: the approved cutout for this reference image, with lineage re-verified pixel by pixel."""
    reference_sha = _sha_file(reference_path)
    matches = []
    for path in sorted(Path(cutouts_dir).glob("*.json")):
        if path.name.endswith(f"{DRAFT}.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise CutoutError(f"Cannot read cutout metadata {path.name}: {e}") from None
        if isinstance(data, dict) and data.get("reference_image_sha256") == reference_sha:
            matches.append((path, data))
    if not matches:
        raise CutoutError(f"No approved cutout for reference sha256={reference_sha[:12]}... in {cutouts_dir}.")
    if len(matches) > 1:
        raise CutoutError(f"Several cutouts match this reference: {[p.name for p, _ in matches]}")

    path, meta = matches[0]
    if meta.get("human_verified") is not True:
        raise CutoutError(f"Cutout {path.name} is not human_verified; it cannot be used.")
    if meta.get("view") not in VIEWS:
        raise CutoutError(f"Cutout {path.name} has an invalid view {meta.get('view')!r}.")
    png_path = path.with_name(meta.get("cutout_file", ""))
    if not png_path.is_file() or _sha_file(png_path) != meta.get("cutout_sha256"):
        raise CutoutError(f"Cutout image for {path.name} is missing or does not match its SHA-256.")

    cutout = _open(png_path, "Cutout")
    if cutout.mode != "RGBA":
        raise CutoutError(f"Cutout must be RGBA, got {cutout.mode}.")
    reference = _open(reference_path, "Reference image").convert("RGB")
    verify_lineage(cutout, reference, tuple(meta["crop_box"]))
    return Cutout(image=cutout, metadata=meta, path=png_path)


def verify_lineage(cutout: Image.Image, reference: Image.Image, crop_box: tuple) -> None:
    """Every non-transparent cutout pixel must equal the reference pixel at the same position."""
    region = reference.crop(crop_box)
    if region.size != cutout.size:
        raise CutoutError("Cutout size does not match its recorded crop box.")
    visible = cutout.getchannel("A").point(lambda a: 255 if a > 0 else 0)
    diff = ImageChops.difference(cutout.convert("RGB"), region)
    blank = Image.new("RGB", cutout.size)
    if Image.composite(diff, blank, visible).getbbox() is not None:
        raise CutoutError("Cutout RGB pixels differ from the reference image; lineage check failed.")


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
