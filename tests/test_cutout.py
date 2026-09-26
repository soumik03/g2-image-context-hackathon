"""Cutout workflow: human mask -> draft -> human approval -> preflight with pixel lineage. Offline only."""

import hashlib
import json

import pytest
from PIL import Image, ImageChops, ImageDraw

from adgen import config, cutout_cli
from adgen.cutout import approve, build_draft, load_approved_cutout, load_mask
from adgen.errors import CutoutError

W, H = 60, 40
BOX = (15, 10, 45, 30)  # product area in the synthetic mask


@pytest.fixture
def files(tmp_path):
    ref = Image.new("RGB", (W, H))
    ref.putdata([((x * 7) % 256, (y * 11) % 256, (x * y) % 256) for y in range(H) for x in range(W)])
    ref_path = tmp_path / "ref.jpg"
    ref.save(ref_path, format="JPEG", quality=95)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle((BOX[0], BOX[1], BOX[2] - 1, BOX[3] - 1), fill=255)
    mask.putpixel((BOX[0], BOX[1]), 128)  # one anti-aliased edge pixel
    mask_path = tmp_path / "mask.png"
    mask.save(mask_path)
    return tmp_path, ref_path, mask_path, tmp_path / "cutouts"


def build_and_approve(files, name="sneaker"):
    tmp, ref, mask, cdir = files
    build_draft(ref, mask, name, cutouts_dir=cdir)
    approve(name, "Test Reviewer", cutouts_dir=cdir)
    return cdir


def test_real_reference_pixel_grid_for_the_mask():
    """Documents the exact mask specification for inputs/products/sneaker.jpg."""
    with Image.open(config.PROJECT_ROOT / "inputs" / "products" / "sneaker.jpg") as img:
        assert (img.format, img.mode, img.size) == ("JPEG", "RGB", (720, 1280))
        assert img.getexif().get(274) in (None, 1)  # no EXIF rotation: editor view == pixel grid


def test_draft_preserves_reference_pixels_exactly(files):
    tmp, ref_path, mask_path, cdir = files
    png = build_draft(ref_path, mask_path, "sneaker", cutouts_dir=cdir)
    meta = json.loads((cdir / "sneaker.draft.json").read_text(encoding="utf-8"))
    cut = Image.open(png)
    ref = Image.open(ref_path).convert("RGB")

    assert cut.mode == "RGBA" and cut.size == (BOX[2] - BOX[0], BOX[3] - BOX[1])
    assert meta["crop_box"] == list(BOX) and meta["human_verified"] is False
    assert meta["reference_image_sha256"] == hashlib.sha256(ref_path.read_bytes()).hexdigest()
    assert meta["mask_sha256"] == hashlib.sha256(mask_path.read_bytes()).hexdigest()
    assert meta["cutout_sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert meta["view"] == "overhead" and meta["partial_alpha_pixels"] == 1
    # RGB identical to the reference crop; alpha identical to the mask crop.
    assert ImageChops.difference(cut.convert("RGB"), ref.crop(BOX)).getbbox() is None
    assert ImageChops.difference(cut.getchannel("A"), Image.open(mask_path).crop(BOX)).getbbox() is None


def test_draft_is_not_overwritten(files):
    tmp, ref, mask, cdir = files
    build_draft(ref, mask, "sneaker", cutouts_dir=cdir)
    with pytest.raises(CutoutError, match="already exists"):
        build_draft(ref, mask, "sneaker", cutouts_dir=cdir)


# ---------------- mask validation ----------------

def test_mask_wrong_size_rejected(files):
    tmp, ref, _, _ = files
    bad = tmp / "small.png"
    Image.new("L", (W - 1, H), 255).save(bad)
    with pytest.raises(CutoutError, match="must match exactly"):
        load_mask(bad, (W, H))


@pytest.mark.parametrize("mode,color", [("RGB", (255, 0, 0)), ("RGBA", (255, 255, 255, 255))])
def test_mask_color_or_transparency_rejected(files, mode, color):
    tmp = files[0]
    bad = tmp / "bad.png"
    img = Image.new(mode, (W, H), (0,) * len(color))
    ImageDraw.Draw(img).rectangle((10, 10, 40, 30), fill=color)
    img.save(bad)
    with pytest.raises(CutoutError):
        load_mask(bad, (W, H))


def test_grayscale_rgb_and_1bit_masks_accepted(files):
    tmp = files[0]
    for mode, white in (("RGB", (255, 255, 255)), ("1", 1)):
        path = tmp / f"ok_{mode}.png"
        img = Image.new(mode, (W, H), 0)
        ImageDraw.Draw(img).rectangle((10, 10, 40, 30), fill=white)
        img.save(path)
        assert load_mask(path, (W, H)).mode == "L"


@pytest.mark.parametrize("fill,match", [(0, "keeps only"), (255, "background was not removed")])
def test_empty_or_full_mask_rejected(files, fill, match):
    tmp = files[0]
    path = tmp / "m.png"
    Image.new("L", (W, H), fill).save(path)
    with pytest.raises(CutoutError, match=match):
        load_mask(path, (W, H))


# ---------------- approval and preflight ----------------

def test_unapproved_draft_is_rejected_by_preflight(files):
    tmp, ref, mask, cdir = files
    build_draft(ref, mask, "sneaker", cutouts_dir=cdir)
    with pytest.raises(CutoutError, match="No approved cutout"):
        load_approved_cutout(ref, cdir)


def test_approved_cutout_loads_with_lineage(files):
    cdir = build_and_approve(files)
    cut = load_approved_cutout(files[1], cdir)
    assert cut.metadata["human_verified"] is True and cut.metadata["verified_by"] == "Test Reviewer"
    assert cut.image.mode == "RGBA" and cut.path.name == "sneaker.png"
    assert (cdir / "sneaker.draft.json").is_file()  # draft kept as history


def test_human_verified_false_rejected(files):
    cdir = build_and_approve(files)
    meta = json.loads((cdir / "sneaker.json").read_text(encoding="utf-8"))
    meta["human_verified"] = False
    (cdir / "sneaker.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(CutoutError, match="not human_verified"):
        load_approved_cutout(files[1], cdir)


def test_wrong_reference_sha_rejected(files):
    tmp, ref, mask, _ = files
    cdir = build_and_approve(files)
    other = tmp / "other.jpg"
    Image.new("RGB", (W, H), "red").save(other)
    with pytest.raises(CutoutError, match="No approved cutout"):
        load_approved_cutout(other, cdir)


def test_tampered_png_rejected(files):
    cdir = build_and_approve(files)
    (cdir / "sneaker.png").write_bytes(b"not the cutout")
    with pytest.raises(CutoutError, match="does not match its SHA-256"):
        load_approved_cutout(files[1], cdir)


def test_modified_pixels_fail_lineage_even_with_updated_sha(files):
    cdir = build_and_approve(files)
    img = Image.open(cdir / "sneaker.png").copy()
    img.putpixel((5, 5), (0, 0, 0, 255))
    img.save(cdir / "sneaker.png")
    meta = json.loads((cdir / "sneaker.json").read_text(encoding="utf-8"))
    meta["cutout_sha256"] = hashlib.sha256((cdir / "sneaker.png").read_bytes()).hexdigest()
    (cdir / "sneaker.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(CutoutError, match="lineage check failed"):
        load_approved_cutout(files[1], cdir)


def test_non_rgba_cutout_rejected(files):
    cdir = build_and_approve(files)
    Image.open(cdir / "sneaker.png").convert("RGB").save(cdir / "sneaker.png")
    meta = json.loads((cdir / "sneaker.json").read_text(encoding="utf-8"))
    meta["cutout_sha256"] = hashlib.sha256((cdir / "sneaker.png").read_bytes()).hexdigest()
    (cdir / "sneaker.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(CutoutError, match="must be RGBA"):
        load_approved_cutout(files[1], cdir)


def test_invalid_view_rejected(files):
    tmp, ref, mask, cdir = files
    with pytest.raises(CutoutError, match="view"):
        build_draft(ref, mask, "sneaker", view="side", cutouts_dir=cdir)


def test_approve_requires_reviewer_and_draft(files):
    tmp, ref, mask, cdir = files
    with pytest.raises(CutoutError, match="No draft"):
        approve("sneaker", "Someone", cutouts_dir=cdir)
    build_draft(ref, mask, "sneaker", cutouts_dir=cdir)
    with pytest.raises(CutoutError, match="verified_by"):
        approve("sneaker", "  ", cutouts_dir=cdir)
    approve("sneaker", "Someone", cutouts_dir=cdir)
    with pytest.raises(CutoutError, match="already exists"):
        approve("sneaker", "Someone", cutouts_dir=cdir)


def test_approve_rejects_modified_draft(files):
    tmp, ref, mask, cdir = files
    build_draft(ref, mask, "sneaker", cutouts_dir=cdir)
    (cdir / "sneaker.draft.png").write_bytes(b"edited")
    with pytest.raises(CutoutError, match="does not match"):
        approve("sneaker", "Someone", cutouts_dir=cdir)


def test_cli_build_approve_check(files, capsys):
    tmp, ref, mask, cdir = files
    d = ["--cutouts-dir", str(cdir)]
    assert cutout_cli.main(d + ["check", str(ref)]) == 1
    assert "No approved cutout" in capsys.readouterr().err
    assert cutout_cli.main(d + ["build", str(ref), str(mask), "--name", "sneaker"]) == 0
    assert cutout_cli.main(d + ["check", str(ref)]) == 1  # draft alone is not usable
    assert cutout_cli.main(d + ["approve", "sneaker", "--verified-by", "Test Reviewer"]) == 0
    assert cutout_cli.main(d + ["check", str(ref)]) == 0
    assert "verified_by=Test Reviewer" in capsys.readouterr().out
