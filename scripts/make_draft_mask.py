"""Create a DRAFT product mask from the reference image with deterministic, Pillow-only color segmentation.

No ML model, no API call. The result is only a draft: it must be reviewed by a human
before the cutout built from it may be approved (adgen.cutout_cli approve).

Rule (HSV, Pillow 0-255 scale):
  keep  light-blue upper   H 136-162, S >= 82, V >= 150
        pale lining        H 136-147, S >= 45, V >= 150     (box top is H >= 149: excluded)
        saturated blue     H 136-165, S >= 170, V >= 90     (laces, sole)
        yellow emblem/tab  H 22-46,   S >= 110, V >= 150
  then  morphological close -> fill enclosed holes (insole, tissue, lettering) -> open
        -> remove packing tissue -> keep large regions -> 1px soft edge

Packing tissue (not part of the product) sits inside the left shoe and is swallowed by the hole fill.
Human review located it, so it is removed only inside the reviewer-directed box TISSUE_BOX:
  tissue    S <= 64, 35 <= V <= 215  (white/grey paper; blue laces, lining and tongue are S >= 82)
  then      close -> fill enclosed creases -> open -> put back any pixel with S >= 80 (laces, lining)

Usage: python scripts/make_draft_mask.py inputs/products/sneaker.jpg inputs/masks/sneaker_mask.png
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Reference-pixel box (left, top, right, bottom) around the packing tissue in the left shoe,
# located during human review of the first draft cutout. Stops above the insole's COMET print.
TISSUE_BOX = (112, 728, 292, 820)


def band_range(band: Image.Image, lo: int, hi: int) -> Image.Image:
    return band.point(lambda v: 255 if lo <= v <= hi else 0)


def draft_mask(reference: Image.Image, close: int = 9, open_: int = 7) -> Image.Image:
    h, s, v = reference.convert("HSV").split()
    light_blue = ImageChops.multiply(ImageChops.multiply(band_range(h, 136, 162), band_range(s, 82, 255)),
                                     band_range(v, 150, 255))
    # Paler, slightly greener lining; the grey-blue box top sits at H >= 149 and is excluded.
    lining = ImageChops.multiply(ImageChops.multiply(band_range(h, 136, 147), band_range(s, 45, 255)),
                                 band_range(v, 150, 255))
    light_blue = ImageChops.lighter(light_blue, lining)
    deep_blue = ImageChops.multiply(ImageChops.multiply(band_range(h, 136, 165), band_range(s, 170, 255)),
                                    band_range(v, 90, 255))
    yellow = ImageChops.multiply(ImageChops.multiply(band_range(h, 22, 46), band_range(s, 110, 255)),
                                 band_range(v, 150, 255))
    mask = ImageChops.lighter(ImageChops.lighter(light_blue, deep_blue), yellow)

    # Close small gaps (stitching, lace shadows), then fill holes enclosed by the product.
    mask = mask.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    mask = fill_holes(mask)

    # Remove thin attachments and specks, keep only large connected regions, then a 1-pixel soft edge.
    mask = mask.filter(ImageFilter.MinFilter(open_)).filter(ImageFilter.MaxFilter(open_))
    mask = ImageChops.subtract(mask, tissue_mask(s, v))
    mask = keep_large_components(mask)
    return mask.filter(ImageFilter.GaussianBlur(1))


def fill_holes(mask: Image.Image) -> Image.Image:
    background = mask.copy()
    ImageDraw.floodfill(background, (0, 0), 128)  # mark outside region reachable from a corner
    return background.point(lambda p: 0 if p == 128 else 255)


def tissue_mask(s: Image.Image, v: Image.Image, box: tuple[int, int, int, int] = TISSUE_BOX) -> Image.Image:
    """Low-saturation packing tissue inside `box` (255 = remove). Saturated product pixels are never removed."""
    region = Image.new("L", s.size, 0)
    region.paste(255, box)
    tissue = ImageChops.multiply(ImageChops.multiply(band_range(s, 0, 64), band_range(v, 35, 215)), region)
    tissue = fill_holes(tissue.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9)))
    tissue = tissue.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return ImageChops.multiply(ImageChops.multiply(tissue, region), band_range(s, 0, 79))


def keep_large_components(mask: Image.Image, min_share: float = 0.05, step: int = 4) -> Image.Image:
    """Keep connected regions whose area is >= min_share of the largest one (deterministic scan order)."""
    labeled = mask.point(lambda p: 255 if p >= 128 else 0)
    px = labeled.load()
    w, h = labeled.size
    label = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            if px[x, y] == 255 and label < 250:
                label += 1
                ImageDraw.floodfill(labeled, (x, y), label)
    sizes = labeled.histogram()[1:label + 1]
    if not sizes:
        return labeled.point(lambda p: 0)
    keep = {i + 1 for i, n in enumerate(sizes) if n >= min_share * max(sizes)}
    return labeled.point(lambda p: 255 if p in keep else 0)


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    reference_path, out_path = Path(argv[0]), Path(argv[1])
    reference = Image.open(reference_path).convert("RGB")
    mask = draft_mask(reference)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(out_path, format="PNG")
    keep = sum(i * c for i, c in enumerate(mask.histogram())) / 255 / (mask.size[0] * mask.size[1])
    print(f"DRAFT mask written: {out_path} ({mask.size[0]}x{mask.size[1]}, mode {mask.mode}, keeps {keep:.1%})")


if __name__ == "__main__":
    main(sys.argv[1:])
