"""Reference profiles: drafts are never trusted; only human-verified profiles are used."""

import json

import pytest

from adgen.evaluator import EvaluationError
from adgen.evaluator.profile import create_profile_draft, load_approved_profile
from conftest import FakeClient, jpeg_bytes

DRAFT_OUTPUT = {
    "product_category": "pair of low-top sneakers",
    "attributes": [
        {"id": "Side Emblem", "kind": "mark", "description": "yellow elongated four-pointed star"},
        {"id": "upper", "kind": "color_material", "description": "light-blue patent upper"},
        {"id": "toe holes", "kind": "detail", "description": "perforated toe"},
    ],
    "branding": [
        {"id": "tongue", "text": "COMET", "location": "tongue label"},
        {"id": "blank", "text": "  ", "location": "heel"},
    ],
}


def test_load_approved_profile_by_sha(run_setup):
    sha = run_setup.metadata["inputs"]["product_image_sha256"]
    profile, path = load_approved_profile(sha, run_setup.profiles_dir)
    assert path.name == "sneaker.json" and profile["human_verified"] is True


def test_no_profile_for_sha(run_setup):
    with pytest.raises(EvaluationError) as exc_info:
        load_approved_profile("f" * 64, run_setup.profiles_dir)
    assert exc_info.value.code == "EVAL_NO_APPROVED_PROFILE"


def test_create_draft_is_unverified(tmp_path):
    image = tmp_path / "sneaker.jpg"
    image.write_bytes(jpeg_bytes((64, 48)))
    client = FakeClient(json.dumps(DRAFT_OUTPUT))
    path = create_profile_draft(image, client, "sneaker", profiles_dir=tmp_path / "profiles")

    assert path.name == "sneaker.draft.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    assert draft["human_verified"] is False
    assert [a["id"] for a in draft["attributes"]] == ["side_emblem", "upper", "toe_holes"]
    assert [a["critical"] for a in draft["attributes"]] == [True, True, False]  # proposed defaults
    assert [b["id"] for b in draft["branding"]] == ["tongue"]  # empty-text entry dropped
    assert any("Dropped branding entry" in n for n in draft["review_notes"])
    assert draft["draft_source"]["raw_model_output"] == json.dumps(DRAFT_OUTPUT)

    (request,) = client.interactions.calls
    assert set(request) == {"model", "input", "response_format", "store"}
    assert request["model"] == "gemini-3.1-flash-lite"

    # A draft is never usable for evaluation.
    with pytest.raises(EvaluationError) as exc_info:
        load_approved_profile(draft["reference_image_sha256"], tmp_path / "profiles")
    assert exc_info.value.code == "EVAL_NO_APPROVED_PROFILE"


def test_draft_not_overwritten(tmp_path):
    image = tmp_path / "sneaker.jpg"
    image.write_bytes(jpeg_bytes((64, 48)))
    create_profile_draft(image, FakeClient(json.dumps(DRAFT_OUTPUT)), "sneaker", profiles_dir=tmp_path)
    client = FakeClient(json.dumps(DRAFT_OUTPUT))
    with pytest.raises(EvaluationError) as exc_info:
        create_profile_draft(image, client, "sneaker", profiles_dir=tmp_path)
    assert exc_info.value.code == "EVAL_DRAFT_EXISTS"
    assert client.interactions.calls == []  # refused before any call


def test_malformed_draft_output_writes_nothing(tmp_path):
    image = tmp_path / "sneaker.jpg"
    image.write_bytes(jpeg_bytes((64, 48)))
    with pytest.raises(EvaluationError) as exc_info:
        create_profile_draft(image, FakeClient("not json"), "sneaker", profiles_dir=tmp_path / "p")
    assert exc_info.value.code == "EVAL_MALFORMED_RESPONSE"
    assert not (tmp_path / "p").exists()
