import base64
import hashlib
import io
import json

import pytest
from PIL import Image

from adgen.errors import OutputProcessingError, SpecError
from adgen.image_io import (
    ProcessedImage,
    decode_base64_image,
    enforce_long_edge,
    load_reference_image,
    save_run,
)


def image_bytes(size, fmt="PNG", color="blue"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_reference_image_to_base64_part(tmp_path, fmt, mime):
    raw = image_bytes((40, 30), fmt)
    path = tmp_path / f"ref.{fmt.lower()}"
    path.write_bytes(raw)

    ref = load_reference_image(path)
    part = ref.to_input_part()

    assert part["type"] == "image"
    assert part["mime_type"] == mime
    assert base64.b64decode(part["data"]) == raw  # original bytes preserved exactly
    assert ref.sha256 == hashlib.sha256(raw).hexdigest()
    assert ref.size == (40, 30)


def test_mime_comes_from_content_not_extension(tmp_path):
    path = tmp_path / "looks_like.png"
    path.write_bytes(image_bytes((10, 10), "JPEG"))
    assert load_reference_image(path).mime_type == "image/jpeg"


def test_corrupt_reference_image_rejected(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"this is not an image")
    with pytest.raises(SpecError, match="not a valid image"):
        load_reference_image(path)


def test_unsupported_reference_format_rejected(tmp_path):
    path = tmp_path / "ref.bmp"
    path.write_bytes(image_bytes((10, 10), "BMP"))
    with pytest.raises(SpecError, match="Unsupported"):
        load_reference_image(path)


def test_oversized_image_resized_proportionally():
    result = enforce_long_edge(image_bytes((1376, 768), "JPEG"), 1024)
    assert result.raw_size == (1376, 768)
    assert result.saved_size == (1024, 571)
    assert result.downscaled is True
    with Image.open(io.BytesIO(result.data)) as img:
        assert img.size == (1024, 571)
        assert img.format == "JPEG"


def test_portrait_image_resized_on_long_edge():
    result = enforce_long_edge(image_bytes((768, 1376)), 1024)
    assert result.saved_size == (571, 1024)


def test_image_within_limit_unchanged():
    raw = image_bytes((1024, 1024), "JPEG")
    result = enforce_long_edge(raw, 1024)
    assert result.downscaled is False
    assert result.saved_size == (1024, 1024)
    assert result.data == raw  # byte-for-byte identical


def test_corrupt_output_image_rejected():
    with pytest.raises(OutputProcessingError, match="could not be decoded"):
        enforce_long_edge(b"\x89PNG garbage", 1024)


def test_invalid_base64_rejected():
    with pytest.raises(OutputProcessingError, match="base64"):
        decode_base64_image("not base64 !!!")


def test_save_run_writes_both_files_and_no_temp_dir(tmp_path):
    image = ProcessedImage(image_bytes((8, 8)), "PNG", (8, 8), (8, 8), False)
    run_dir = tmp_path / "prod" / "run1"
    image_path, meta_path = save_run(run_dir, image, {"hello": "world"})

    assert image_path == run_dir / "ad.png"
    assert image_path.read_bytes() == image.data
    assert json.loads(meta_path.read_text(encoding="utf-8")) == {"hello": "world"}
    assert sorted(p.name for p in (tmp_path / "prod").iterdir()) == ["run1"]


def test_save_run_refuses_existing_dir(tmp_path):
    image = ProcessedImage(image_bytes((8, 8)), "PNG", (8, 8), (8, 8), False)
    (tmp_path / "run1").mkdir()
    with pytest.raises(OutputProcessingError, match="already exists"):
        save_run(tmp_path / "run1", image, {})
