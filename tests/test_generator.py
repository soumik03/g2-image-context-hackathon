import base64
import io
import json
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from PIL import Image

from adgen import cli, config
from adgen.errors import GenerationAPIError, NoImageReturnedError, OutputProcessingError
from adgen.generator import generate
from adgen.prompt import build_prompt
from adgen.spec import spec_from_dict

FAKE_KEY = "AIzaFAKE-test-key-1234567890"


def image_bytes(size, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", size, "green").save(buf, format=fmt)
    return buf.getvalue()


class FakeInteractions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.interactions = FakeInteractions(response, error)


def completed_response(data: bytes, mime="image/jpeg"):
    return SimpleNamespace(
        id="interaction-123",
        status="completed",
        output_image=SimpleNamespace(data=base64.b64encode(data).decode("ascii"), mime_type=mime),
        output_text="",
    )


@pytest.fixture
def spec(tmp_path):
    ref = tmp_path / "product.png"
    ref.write_bytes(image_bytes((50, 40)))
    return spec_from_dict({
        "id": "prod-01",
        "product_image": str(ref),
        "geography": "Tokyo, Japan",
        "season": "Winter",
        "required_text": "Step Into Winter",
    })


def test_request_shape(spec, tmp_path):
    client = FakeClient(completed_response(image_bytes((1024, 1024), "JPEG")))
    generate(spec, client, output_root=tmp_path / "out")

    (call,) = client.interactions.calls
    assert call["model"] == "gemini-3.1-flash-image"
    image_part, text_part = call["input"]
    assert image_part["type"] == "image"
    assert image_part["mime_type"] == "image/png"
    assert base64.b64decode(image_part["data"]) == spec.product_image.read_bytes()
    assert text_part == {"type": "text", "text": build_prompt(spec)}
    assert call["response_format"]["image_size"] == "1K"
    assert call["response_format"]["aspect_ratio"] == "1:1"


def test_successful_generation_saves_image_and_metadata(spec, tmp_path):
    returned = image_bytes((1024, 1024), "JPEG")
    result = generate(spec, FakeClient(completed_response(returned)), output_root=tmp_path / "out")

    assert result.image_path.name == "ad.jpg"
    assert result.image_path.read_bytes() == returned
    meta = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert meta["inputs"]["geography"] == "Tokyo, Japan"
    assert meta["inputs"]["season"] == "Winter"
    assert meta["inputs"]["required_text"] == "Step Into Winter"
    assert len(meta["inputs"]["product_image_sha256"]) == 64
    assert meta["prompt"] == build_prompt(spec)
    assert meta["model"] == config.GENERATOR_MODEL
    assert meta["request"]["image_size"] == "1K"
    assert meta["output"]["raw_resolution"] == [1024, 1024]
    assert meta["output"]["saved_resolution"] == [1024, 1024]
    assert meta["output"]["downscaled"] is False
    assert meta["response"]["interaction_id"] == "interaction-123"
    for key in ("timestamp_utc", "duration_seconds", "sdk_version"):
        assert meta[key] is not None


def test_oversized_output_is_downscaled(spec, tmp_path):
    client = FakeClient(completed_response(image_bytes((1376, 768), "JPEG")))
    result = generate(spec, client, output_root=tmp_path / "out")
    assert result.metadata["output"]["raw_resolution"] == [1376, 768]
    assert result.metadata["output"]["saved_resolution"] == [1024, 571]
    with Image.open(result.image_path) as img:
        assert max(img.size) <= 1024


@pytest.mark.parametrize("response", [
    SimpleNamespace(id="x", status="completed", output_image=None, output_text="I can't do that."),
    SimpleNamespace(id="x", status="failed", output_image=None, output_text=""),
    SimpleNamespace(id="x", status="completed", output_image=SimpleNamespace(data=None, mime_type=None), output_text=""),
])
def test_missing_image_raises(spec, tmp_path, response):
    with pytest.raises(NoImageReturnedError, match="no image"):
        generate(spec, FakeClient(response), output_root=tmp_path / "out")
    assert not (tmp_path / "out").exists()  # nothing saved on failure


def test_api_error_translated(spec, tmp_path):
    error = genai_errors.APIError(
        403, {"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}}
    )
    with pytest.raises(GenerationAPIError) as exc_info:
        generate(spec, FakeClient(error=error), output_root=tmp_path / "out")
    assert exc_info.value.code == 403
    assert exc_info.value.status == "PERMISSION_DENIED"
    assert "Permission denied" in str(exc_info.value)


def test_transport_error_translated(spec, tmp_path):
    with pytest.raises(GenerationAPIError, match="ConnectionError"):
        generate(spec, FakeClient(error=ConnectionError("offline")), output_root=tmp_path / "out")


def test_corrupt_returned_image_raises(spec, tmp_path):
    with pytest.raises(OutputProcessingError):
        generate(spec, FakeClient(completed_response(b"not an image")), output_root=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_api_key_redacted_from_api_error(spec, tmp_path):
    error = genai_errors.APIError(
        400, {"error": {"code": 400, "message": f"API key {FAKE_KEY} not valid", "status": "INVALID_ARGUMENT"}}
    )
    with pytest.raises(GenerationAPIError) as exc_info:
        generate(spec, FakeClient(error=error), output_root=tmp_path / "out", secret=FAKE_KEY)
    assert FAKE_KEY not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_api_key_redacted_from_no_image_error(spec, tmp_path):
    response = SimpleNamespace(id="x", status="completed", output_image=None, output_text=f"echo {FAKE_KEY}")
    with pytest.raises(NoImageReturnedError) as exc_info:
        generate(spec, FakeClient(response), output_root=tmp_path / "out", secret=FAKE_KEY)
    assert FAKE_KEY not in str(exc_info.value)


def test_api_key_never_in_output_files(spec, tmp_path):
    response = completed_response(image_bytes((1024, 1024), "JPEG"))
    response.output_text = f"model echoed {FAKE_KEY}"
    result = generate(spec, FakeClient(response), output_root=tmp_path / "out", secret=FAKE_KEY)
    for path in result.run_dir.iterdir():
        assert FAKE_KEY.encode() not in path.read_bytes()


EXPECTED_METADATA_KEYS = {
    "schema_version", "spec_id", "inputs", "prompt", "model", "request", "response", "output",
    "warnings", "timestamp_utc", "duration_seconds", "sdk_version",
}


def test_default_call_is_backward_compatible(spec, tmp_path):
    """generate(spec, client) keeps the original prompt, layout and metadata schema."""
    client = FakeClient(completed_response(image_bytes((1024, 1024), "JPEG")))
    result = generate(spec, client, output_root=tmp_path / "out")
    (call,) = client.interactions.calls
    assert call["input"][1]["text"] == build_prompt(spec)  # no correction appended
    assert result.metadata["prompt"] == build_prompt(spec)
    assert set(result.metadata) == EXPECTED_METADATA_KEYS
    assert result.run_dir.parent == tmp_path / "out" / spec.id  # outputs/<id>/<timestamp>/


def test_correction_is_appended_after_unchanged_base_prompt(spec, tmp_path):
    client = FakeClient(completed_response(image_bytes((1024, 1024), "JPEG")))
    target = tmp_path / "run" / "attempt-02"
    result = generate(spec, client, target_dir=target, correction="CORRECTIONS FROM PREVIOUS ATTEMPT\n- fix")
    sent = client.interactions.calls[0]["input"][1]["text"]
    assert sent == build_prompt(spec) + "\n\n" + "CORRECTIONS FROM PREVIOUS ATTEMPT\n- fix"
    assert result.metadata["prompt"] == sent
    assert result.run_dir == target and (target / "ad.jpg").is_file()
    assert set(result.metadata) == EXPECTED_METADATA_KEYS


def test_cli_missing_key_fails_before_any_call(spec, tmp_path, monkeypatch, capsys):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({
        "id": spec.id, "product_image": str(spec.product_image), "geography": spec.geography,
        "season": spec.season, "required_text": spec.required_text,
    }), encoding="utf-8")
    monkeypatch.setenv(config.API_KEY_ENV, "")  # an existing (empty) var is not overridden by .env
    assert cli.main([str(spec_file)]) == 1
    assert "GEMINI_API_KEY is not set" in capsys.readouterr().err


def test_cli_dry_run_needs_no_key(spec, tmp_path, monkeypatch, capsys):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps({
        "id": spec.id, "product_image": str(spec.product_image), "geography": spec.geography,
        "season": spec.season, "required_text": spec.required_text,
    }), encoding="utf-8")
    monkeypatch.setenv(config.API_KEY_ENV, "")
    assert cli.main([str(spec_file), "--dry-run"]) == 0
    assert "DRY RUN: no API call made." in capsys.readouterr().out
