"""Bounded regeneration pipeline, driven by deterministic scripted fake clients (no network)."""

import base64
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from adgen import config
from adgen import pipeline as st
from adgen.pipeline import cli as pipeline_cli
from adgen.pipeline import orchestrator
from adgen.pipeline.orchestrator import run_pipeline
from adgen.prompt import build_prompt
from adgen.spec import spec_from_dict
from conftest import jpeg_bytes

FAKE_KEY = "AIzaFAKE-pipeline-key-555"


class OverBudget(BaseException):
    """Raised if the pipeline asks for more calls than scripted (BaseException: not swallowed)."""


class ScriptedClient:
    """One client for both models; answers are consumed in order, calls are counted."""

    def __init__(self, generations, evaluations):
        self.generations, self.evaluations = list(generations), list(evaluations)
        self.gen_calls, self.eval_calls = [], []
        self.interactions = self

    def create(self, **kwargs):
        if kwargs["model"] == config.GENERATOR_MODEL:
            self.gen_calls.append(kwargs)
            if not self.generations:
                raise OverBudget("generator")
            item = self.generations.pop(0)
            if isinstance(item, Exception):
                raise item
            return SimpleNamespace(id="", status="completed", output_text="",
                                   output_image=SimpleNamespace(data=base64.b64encode(item).decode(), mime_type="image/jpeg"))
        self.eval_calls.append(kwargs)
        if not self.evaluations:
            raise OverBudget("evaluator")
        item = self.evaluations.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(id="", status="completed", output_text=item)


@pytest.fixture
def pipe(tmp_path, profile, good_response):
    ref = tmp_path / "sneaker.jpg"
    ref.write_bytes(jpeg_bytes((64, 48), "skyblue"))
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    approved = copy.deepcopy(profile)
    approved["reference_image_sha256"] = hashlib.sha256(ref.read_bytes()).hexdigest()
    (profiles_dir / "sneaker.json").write_text(json.dumps(approved), encoding="utf-8")
    spec = spec_from_dict({"id": "sneaker-tokyo-winter", "product_image": str(ref), "geography": "Tokyo, Japan",
                           "season": "Winter", "required_text": "Step Into Winter"})

    def variant(mutate=None):
        r = copy.deepcopy(good_response)
        if mutate:
            mutate(r)
        return json.dumps(r)

    def run(generations, evaluations, **kwargs):
        client = ScriptedClient(generations, evaluations)
        result = run_pipeline(spec, client, output_root=tmp_path / "outputs", profiles_dir=profiles_dir, **kwargs)
        return result, client

    return SimpleNamespace(spec=spec, ref=ref, profiles_dir=profiles_dir, variant=variant, run=run, tmp=tmp_path)


IMG = jpeg_bytes((1024, 1024), "white")


def emblem_altered(r):
    r["product"]["attributes"][3].update(status="altered", evidence="five-pointed star on side")


def weak_geo(r):
    r["context"]["geography"].update(rating="weak", cues=["generic street"])


def misspelled(r):
    r["text"]["items"][0]["text"] = "Step Into Wintr"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# 1. first attempt PASS
def test_first_attempt_pass(pipe):
    result, client = pipe.run([IMG], [pipe.variant()])
    assert result.status == st.PASS
    assert result.final["accepted_attempt"] == "attempt-01"
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 1)
    assert result.final["api_calls"] == {"generator": 1, "evaluator": 1}
    assert not (result.run_dir / "attempt-02").exists()
    assert load(result.run_dir / "final.json") == result.final


# 2 + 3. FAIL -> retry -> PASS
def test_fail_then_retry_pass(pipe):
    result, client = pipe.run([IMG, IMG], [pipe.variant(emblem_altered), pipe.variant()])
    assert result.status == st.PASS and result.final["accepted_attempt"] == "attempt-02"
    assert (len(client.gen_calls), len(client.eval_calls)) == (2, 2)
    base = build_prompt(pipe.spec)
    first, second = (c["input"][1]["text"] for c in client.gen_calls)
    assert first == base
    correction = load(result.run_dir / "attempt-02" / "attempt.json")["correction"]["text"]
    assert second == base + "\n\n" + correction
    assert "five-pointed star on side" in correction


# 4. exhaustion (codes change each time, so no early stop)
def test_max_attempts_exhausted(pipe):
    result, client = pipe.run([IMG] * 3, [pipe.variant(emblem_altered), pipe.variant(weak_geo),
                                          pipe.variant(misspelled)])
    assert result.status == st.FAIL_EXHAUSTED and result.final["final_verdict"] == "FAIL"
    assert result.final["accepted_attempt"] is None
    assert (len(client.gen_calls), len(client.eval_calls)) == (3, 3)
    assert result.final["reason_history"] == [["PRODUCT_MARK_ALTERED"], ["CONTEXT_GEO_WEAK"], ["TEXT_MISMATCH"]]


# 5. no-progress stop
def test_same_failure_twice_stops_early(pipe):
    result, client = pipe.run([IMG] * 3, [pipe.variant(weak_geo)] * 3)
    assert result.status == st.FAIL_NO_PROGRESS and result.final["stop_reason"] == "no_progress"
    assert (len(client.gen_calls), len(client.eval_calls)) == (2, 2)
    assert not (result.run_dir / "attempt-03").exists()


def test_regressions_are_recorded(pipe):
    result, _ = pipe.run([IMG] * 3, [pipe.variant(emblem_altered), pipe.variant(weak_geo), pipe.variant()])
    assert result.status == st.PASS
    assert load(result.run_dir / "attempt-02" / "attempt.json")["outcome"]["regressions"] == ["CONTEXT_GEO_WEAK"]


# 6. evaluator ERROR terminates without retry
@pytest.mark.parametrize("bad", [
    "this is not json",
    genai_errors.APIError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}),
])
def test_evaluator_error_terminates(pipe, bad):
    result, client = pipe.run([IMG, IMG], [bad])
    assert result.status == st.ERROR_EVALUATOR and result.final["accepted_attempt"] is None
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 1)
    assert load(result.run_dir / "attempt-01" / "attempt.json")["outcome"]["verdict"] == "ERROR"


# 7. generator ERROR terminates without retry
def test_generator_error_first_attempt(pipe):
    err = genai_errors.APIError(400, {"error": {"code": 400, "message": f"bad {FAKE_KEY}", "status": "INVALID"}})
    client = ScriptedClient([err], [])
    result = run_pipeline(pipe.spec, client, output_root=pipe.tmp / "outputs", profiles_dir=pipe.profiles_dir,
                          secret=FAKE_KEY)
    assert result.status == st.ERROR_GENERATOR
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 0)
    attempt = load(result.run_dir / "attempt-01" / "attempt.json")
    assert attempt["outcome"]["verdict"] == "ERROR" and "GenerationAPIError" in attempt["outcome"]["error"]
    assert not (result.run_dir / "attempt-01" / "ad.jpg").exists()


def test_generator_error_on_retry(pipe):
    result, client = pipe.run([IMG, ConnectionError("offline")], [pipe.variant(emblem_altered)])
    assert result.status == st.ERROR_GENERATOR
    assert (len(client.gen_calls), len(client.eval_calls)) == (2, 1)
    assert [a["verdict"] for a in result.final["attempts"]] == ["FAIL", "ERROR"]


# 10. input immutability
def test_inputs_identical_across_attempts(pipe):
    result, client = pipe.run([IMG] * 3, [pipe.variant(emblem_altered), pipe.variant(weak_geo),
                                          pipe.variant(misspelled)])
    base = build_prompt(pipe.spec)
    base_sha = hashlib.sha256(base.encode()).hexdigest()
    records = [load(result.run_dir / f"attempt-0{i}" / "attempt.json") for i in (1, 2, 3)]
    metas = [load(result.run_dir / f"attempt-0{i}" / "metadata.json") for i in (1, 2, 3)]
    assert len({r["spec_sha256"] for r in records}) == 1
    assert {r["reference_image_sha256"] for r in records} == {hashlib.sha256(pipe.ref.read_bytes()).hexdigest()}
    assert {r["base_prompt_sha256"] for r in records} == {base_sha}
    for m in metas:
        assert (m["inputs"]["geography"], m["inputs"]["season"], m["inputs"]["required_text"]) == \
               ("Tokyo, Japan", "Winter", "Step Into Winter")
        assert m["inputs"]["product_image_sha256"] == records[0]["reference_image_sha256"]
        assert m["prompt"].startswith(base)
    for m, r in zip(metas, records):  # only the appended correction differs
        suffix = m["prompt"][len(base):]
        assert suffix == ("" if r["correction"] is None else "\n\n" + r["correction"]["text"])


# 11. lineage
def test_attempt_lineage(pipe):
    result, _ = pipe.run([IMG] * 3, [pipe.variant(emblem_altered), pipe.variant(weak_geo), pipe.variant()])
    records = [load(result.run_dir / f"attempt-0{i}" / "attempt.json") for i in (1, 2, 3)]
    assert [r["parent_attempt"] for r in records] == [None, "attempt-01", "attempt-02"]
    assert records[0]["correction"] is None
    assert records[1]["correction"]["derived_from"] == "attempt-01/evaluation.json"
    assert records[2]["correction"]["derived_from"] == "attempt-02/evaluation.json"
    for r in records:
        assert r["generator_model"] == config.GENERATOR_MODEL and r["evaluator_model"] == config.EVALUATOR_MODEL
        assert r["run_id"] == result.final["run_id"] and r["started_utc"] and r["finished_utc"]
        assert r["prompt_sha256"]
    assert records[1]["correction"]["codes"] == ["PRODUCT_MARK_ALTERED"]


# 12. API bound
@pytest.mark.parametrize("max_attempts", [1, 2, 3])
def test_api_calls_never_exceed_bound(pipe, max_attempts):
    failing = [pipe.variant(emblem_altered), pipe.variant(weak_geo), pipe.variant(misspelled)]
    result, client = pipe.run([IMG] * 5, failing + failing, max_attempts=max_attempts)
    assert len(client.gen_calls) == len(client.eval_calls) == max_attempts
    assert result.status == st.FAIL_EXHAUSTED


def test_invalid_max_attempts_rejected(pipe):
    with pytest.raises(ValueError):
        pipe.run([], [], max_attempts=0)


def test_default_budget_is_three():
    assert config.MAX_ATTEMPTS == 3


# 13. preflight: zero calls
def test_no_approved_profile_is_preflight_error(pipe):
    (pipe.profiles_dir / "sneaker.json").rename(pipe.profiles_dir / "sneaker.draft.json")
    result, client = pipe.run([IMG], [pipe.variant()])
    assert result.status == st.ERROR_PREFLIGHT
    assert (len(client.gen_calls), len(client.eval_calls)) == (0, 0)
    assert (result.run_dir / "final.json").is_file() and result.final["attempts"] == []


def test_corrupt_reference_is_preflight_error(pipe):
    pipe.ref.write_bytes(b"not an image")
    result, client = pipe.run([IMG], [pipe.variant()])
    assert result.status == st.ERROR_PREFLIGHT and len(client.gen_calls) == 0


def test_cli_preflight_errors_make_no_client(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert pipeline_cli.main([str(bad)]) == 1
    assert "ERROR_PREFLIGHT" in capsys.readouterr().err

    ref = tmp_path / "r.jpg"
    ref.write_bytes(jpeg_bytes((10, 10)))
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"id": "x", "product_image": str(ref), "geography": "g", "season": "s",
                                "required_text": "t"}), encoding="utf-8")
    monkeypatch.setenv(config.API_KEY_ENV, "")
    assert pipeline_cli.main([str(good)]) == 1
    assert "GEMINI_API_KEY is not set" in capsys.readouterr().err


# 14. technical invariant -> ERROR_INTERNAL, no evaluator call
def test_technical_invariant_violation_is_internal_error(pipe, monkeypatch):
    real_generate = orchestrator.generate

    def corrupting_generate(*args, **kwargs):
        result = real_generate(*args, **kwargs)
        result.image_path.write_bytes(b"corrupted after generation")
        return result

    monkeypatch.setattr(orchestrator, "generate", corrupting_generate)
    result, client = pipe.run([IMG], [pipe.variant()])
    assert result.status == st.ERROR_INTERNAL
    assert len(client.eval_calls) == 0
    assert result.final["api_calls"]["evaluator"] == 0


# 15. artifact completeness
def test_artifacts_complete_and_key_free(pipe):
    client = ScriptedClient([IMG, IMG], [pipe.variant(emblem_altered), pipe.variant()])
    result = run_pipeline(pipe.spec, client, output_root=pipe.tmp / "outputs", profiles_dir=pipe.profiles_dir,
                          secret=FAKE_KEY)
    for name in ("attempt-01", "attempt-02"):
        files = sorted(p.name for p in (result.run_dir / name).iterdir())
        assert files == ["ad.jpg", "attempt.json", "evaluation.json", "metadata.json"]
    final = load(result.run_dir / "final.json")
    for key in ("run_id", "status", "final_verdict", "accepted_attempt", "spec", "spec_sha256",
                "reference_image_sha256", "base_prompt_sha256", "profile", "generator_model", "evaluator_model",
                "rules_version", "max_attempts", "attempts", "reason_history", "stop_reason", "api_calls",
                "started_utc", "finished_utc", "duration_seconds", "sdk_version"):
        assert key in final, key
    assert not list(result.run_dir.rglob("*.tmp"))
    for path in result.run_dir.rglob("*"):
        if path.is_file():
            assert FAKE_KEY.encode() not in path.read_bytes()


def test_every_run_starts_fresh(pipe):
    first, _ = pipe.run([IMG], [pipe.variant(weak_geo)], max_attempts=1)
    second, client = pipe.run([IMG], [pipe.variant()])
    assert first.run_dir != second.run_dir
    assert len(client.gen_calls) == 1  # new attempt-01 generation, never a reused evaluation
    assert load(first.run_dir / "final.json")["status"] == st.FAIL_EXHAUSTED  # earlier run untouched
