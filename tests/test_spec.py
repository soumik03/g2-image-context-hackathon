import json

import pytest
from PIL import Image

from adgen import config
from adgen.errors import SpecError
from adgen.spec import load_spec, spec_from_dict, spec_warnings


@pytest.fixture
def valid_data(tmp_path):
    image = tmp_path / "product.png"
    Image.new("RGB", (64, 48), "red").save(image)
    return {
        "id": "prod-01",
        "product_image": str(image),
        "geography": "Tokyo, Japan",
        "season": "Winter",
        "required_text": "Step Into Winter",
    }


def test_valid_spec_loads(valid_data):
    spec = spec_from_dict(valid_data)
    assert spec.id == "prod-01"
    assert spec.geography == "Tokyo, Japan"
    assert spec.season == "Winter"
    assert spec.required_text == "Step Into Winter"


def test_load_spec_from_file_resolves_relative_image(tmp_path, valid_data):
    valid_data["product_image"] = "product.png"
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(valid_data), encoding="utf-8")
    spec = load_spec(spec_file, base_dir=tmp_path)
    assert spec.product_image == tmp_path / "product.png"


@pytest.mark.parametrize("field", ["id", "product_image", "geography", "season", "required_text"])
def test_missing_field_rejected(valid_data, field):
    del valid_data[field]
    with pytest.raises(SpecError, match=field):
        spec_from_dict(valid_data)


@pytest.mark.parametrize("field", ["id", "geography", "season", "required_text"])
@pytest.mark.parametrize("value", ["", "   ", None, 42])
def test_empty_or_non_string_field_rejected(valid_data, field, value):
    valid_data[field] = value
    with pytest.raises(SpecError, match=field):
        spec_from_dict(valid_data)


def test_unknown_field_rejected(valid_data):
    valid_data["aspect_ratio"] = "16:9"
    with pytest.raises(SpecError, match="unknown"):
        spec_from_dict(valid_data)


def test_missing_reference_image_rejected(valid_data, tmp_path):
    valid_data["product_image"] = str(tmp_path / "does_not_exist.png")
    with pytest.raises(SpecError, match="not found"):
        spec_from_dict(valid_data)


def test_unsafe_id_rejected(valid_data):
    valid_data["id"] = "../escape"
    with pytest.raises(SpecError, match="id"):
        spec_from_dict(valid_data)


def test_invalid_json_file_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SpecError, match="not valid JSON"):
        load_spec(bad)


def test_missing_spec_file_rejected(tmp_path):
    with pytest.raises(SpecError, match="not found"):
        load_spec(tmp_path / "nope.json")


def test_long_required_text_is_accepted_with_warning(valid_data):
    valid_data["required_text"] = "A" * (config.LONG_TEXT_WARNING_CHARS + 50)
    spec = spec_from_dict(valid_data)  # must not raise
    assert spec.required_text == valid_data["required_text"]
    assert len(spec_warnings(spec)) == 1


def test_required_text_kept_exactly(valid_data):
    valid_data["required_text"] = "  Sale: 50% off {today}!  "
    assert spec_from_dict(valid_data).required_text == "  Sale: 50% off {today}!  "
