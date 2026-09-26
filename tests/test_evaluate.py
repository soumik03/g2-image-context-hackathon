"""End-to-end evaluator tests on a temporary run dir with a fake Gemini client."""

import json

import pytest
from google.genai import errors as genai_errors

from adgen import config
from adgen.evaluator import EvaluationError, policy
from adgen.evaluator.evaluate import evaluate_run
from conftest import FakeClient, jpeg_bytes

FAKE_KEY = "AIzaFAKE-eval-key-0987654321"


def run(setup, client, **kwargs):
    return evaluate_run(setup.run_dir, client, profiles_dir=setup.profiles_dir, **kwargs)


def test_pass_writes_auditable_record(run_setup, good_response):
    raw = json.dumps(good_response)
    client = FakeClient(raw)
    record = run(run_setup, client)

    assert record["verdict"] == "PASS" and record["reasons"] == []
    assert len(client.interactions.calls) == 1  # one combined call
    saved = json.loads((run_setup.run_dir / "evaluation.json").read_text(encoding="utf-8"))
    assert saved == record
    assert saved["raw_response"] == raw
    assert saved["rules_version"] == policy.RULES_VERSION
    assert saved["policy_snapshot"]["product"]["same_product_fail_codes"]["partially"] == "PRODUCT_DESIGN_DEVIATION"
    assert saved["profile"]["human_verified"] is True
    assert saved["evaluator_model"] == "gemini-3.1-flash-lite"
    assert set(saved["checks"]) == {"technical", "text", "product", "context"}


def test_smoke_pattern_end_to_end(run_setup, smoke):
    record = run(run_setup, FakeClient(json.dumps(smoke["response"])))
    assert record["verdict"] == "FAIL"
    assert record["reasons"] == smoke["expected_reasons"]


def test_request_shape_and_hidden_fields(run_setup, good_response):
    client = FakeClient(json.dumps(good_response))
    run(run_setup, client)
    (request,) = client.interactions.calls
    dumped = json.dumps(request)

    assert request["model"] == config.EVALUATOR_MODEL
    assert set(request) == {"model", "input", "response_format", "store"}  # no seed, no delivery
    assert request["response_format"]["type"] == "text"
    assert request["response_format"]["mime_type"] == "application/json"
    assert [p["type"] for p in request["input"]] == ["text", "text", "image", "text", "image"]
    assert "Target geography: Tokyo, Japan" in request["input"][0]["text"]
    assert "Target season: Winter" in request["input"][0]["text"]
    # Must NOT be sent to the evaluator model:
    assert "Step Into Winter" not in dumped
    assert "critical" not in dumped
    assert "human_verified" not in dumped and "verified_by" not in dumped


def test_oversized_image_fails_with_zero_model_calls(run_setup, good_response):
    (run_setup.run_dir / "ad.jpg").write_bytes(jpeg_bytes((1376, 768)))
    client = FakeClient(json.dumps(good_response))
    record = run(run_setup, client)
    assert record["verdict"] == "FAIL"
    assert record["reasons"] == ["TECH_OVERSIZE"]
    assert client.interactions.calls == []
    assert record["checks"]["text"]["verdict"] == "SKIPPED"


def test_unreadable_image_fails_without_call(run_setup, good_response):
    (run_setup.run_dir / "ad.jpg").write_bytes(b"not an image")
    client = FakeClient(json.dumps(good_response))
    assert run(run_setup, client)["reasons"] == ["TECH_IMAGE_UNREADABLE"]
    assert client.interactions.calls == []


def test_unverified_profile_is_error_without_call(run_setup, good_response):
    run_setup.profile["human_verified"] = False
    (run_setup.profiles_dir / "sneaker.json").write_text(json.dumps(run_setup.profile), encoding="utf-8")
    client = FakeClient(json.dumps(good_response))
    record = run(run_setup, client)
    assert record["verdict"] == "ERROR"
    assert record["reasons"] == ["EVAL_NO_APPROVED_PROFILE"]
    assert client.interactions.calls == []


def test_draft_profile_is_never_used(run_setup, good_response):
    (run_setup.profiles_dir / "sneaker.json").rename(run_setup.profiles_dir / "sneaker.draft.json")
    record = run(run_setup, FakeClient(json.dumps(good_response)))
    assert record["reasons"] == ["EVAL_NO_APPROVED_PROFILE"]


def test_malformed_output_is_error_and_raw_is_kept(run_setup):
    record = run(run_setup, FakeClient("I think the ad is great!"))
    assert record["verdict"] == "ERROR"
    assert record["reasons"] == ["EVAL_MALFORMED_RESPONSE"]
    assert record["raw_response"] == "I think the ad is great!"


def test_missing_section_is_error(run_setup, good_response):
    del good_response["context"]
    record = run(run_setup, FakeClient(json.dumps(good_response)))
    assert record["verdict"] == "ERROR"
    assert record["reasons"] == ["EVAL_MISSING_SECTION"]


def test_api_error_is_error(run_setup):
    err = genai_errors.APIError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
    record = run(run_setup, FakeClient(error=err))
    assert record["verdict"] == "ERROR"
    assert record["reasons"] == ["EVAL_API_ERROR"]


def test_incomplete_interaction_is_error(run_setup, good_response):
    record = run(run_setup, FakeClient(json.dumps(good_response), status="failed"))
    assert record["reasons"] == ["EVAL_API_ERROR"]


def test_api_key_never_in_evaluation_file(run_setup):
    err = genai_errors.APIError(400, {"error": {"code": 400, "message": f"bad key {FAKE_KEY}", "status": "X"}})
    record = run(run_setup, FakeClient(error=err), secret=FAKE_KEY)
    text = (run_setup.run_dir / "evaluation.json").read_text(encoding="utf-8")
    assert FAKE_KEY not in text
    assert "[REDACTED]" in record["error"]


def test_existing_evaluation_not_overwritten(run_setup, good_response):
    run(run_setup, FakeClient(json.dumps(good_response)))
    with pytest.raises(EvaluationError) as exc_info:
        run(run_setup, FakeClient(json.dumps(good_response)))
    assert exc_info.value.code == "EVAL_ALREADY_EXISTS"
    assert run(run_setup, FakeClient(json.dumps(good_response)), overwrite=True)["verdict"] == "PASS"


def test_reference_changed_on_disk_is_error(run_setup, good_response):
    run_setup.ref_path.write_bytes(jpeg_bytes((64, 48), "red"))
    client = FakeClient(json.dumps(good_response))
    assert run(run_setup, client)["reasons"] == ["EVAL_REFERENCE_INVALID"]
    assert client.interactions.calls == []
