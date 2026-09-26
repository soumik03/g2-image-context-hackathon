"""Golden dataset: every case has an explicit expected outcome, and the deterministic
rules reproduce it offline from the case's observations. No API calls."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from adgen import config
from adgen.evaluator.rules import CheckResult, context_rules, gate, product_rules, text_rules
from adgen.evaluator.schemas import validate_profile, validate_response

ROOT = config.PROJECT_ROOT
MANIFEST = json.loads((ROOT / "golden" / "manifest.json").read_text(encoding="utf-8"))
PROFILE = json.loads((ROOT / MANIFEST["profile"]).read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]
BY_ID = {c["id"]: c for c in CASES}
SOURCE_TYPES = {"real_gemini_output", "edited_fixture", "hypothetical"}
REQUIRED_MODES = {"known_good", "real_output", "altered_emblem", "garbled_branding", "misspelled_text",
                  "extra_ad_copy", "weak_geography", "conflicting_season", "multiple_failures"}


def load(rel_path):
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def sha256(rel_path):
    return hashlib.sha256((ROOT / rel_path).read_bytes()).hexdigest()


def replay(case):
    """Run the deterministic pipeline on a case's observations (technical from the image if any)."""
    obs = validate_response(load(case["observations"]), PROFILE)
    technical = CheckResult()
    if case["image"]:
        with Image.open(ROOT / case["image"]) as img:
            img.load()
            if max(img.size) > config.MAX_LONG_EDGE:
                technical.reasons.append({"code": "TECH_OVERSIZE"})
    checks = {
        "technical": technical,
        "text": text_rules(obs["text"], case["spec"]["required_text"]),
        "product": product_rules(obs["product"], PROFILE),
        "context": context_rules(obs["context"]),
    }
    verdict, reasons = gate(checks)
    return verdict, reasons, checks


# ---------------- manifest integrity ----------------

def test_profile_is_the_trusted_one():
    validate_profile(PROFILE)
    assert PROFILE["human_verified"] is True


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_has_explicit_expected_outcome(case):
    assert case["source_type"] in SOURCE_TYPES
    exp = case["expected"]
    assert exp["overall"] in ("PASS", "FAIL")
    assert set(exp["checks"]) == {"technical", "text", "product", "context"}
    assert (exp["overall"] == "PASS") == (exp["reasons"] == [])
    assert (ROOT / case["observations"]).is_file()
    assert case["observations_source"] in ("recorded_live_evaluator", "hand_authored")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_image_presence_matches_source_type(case):
    if case["source_type"] == "hypothetical":
        assert case["image"] is None and case["image_provenance"] is None
        assert case["expected"]["checks"]["technical"] == "not_applicable"
    else:
        with Image.open(ROOT / case["image"]) as img:
            assert max(img.size) <= config.MAX_LONG_EDGE
        assert case["expected"]["checks"]["technical"] == "PASS"


# ---------------- the core claim: rules reproduce every expected outcome ----------------

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_rules_reproduce_expected_outcome(case):
    verdict, reasons, checks = replay(case)
    exp = case["expected"]
    assert verdict == exp["overall"]
    assert reasons == exp["reasons"]  # all reasons retained, in gate order
    for name in ("text", "product", "context"):
        assert checks[name].verdict == exp["checks"][name], name
    if case["image"]:
        assert checks["technical"].verdict == exp["checks"]["technical"]


def test_pass_and_fail_both_represented():
    outcomes = {c["expected"]["overall"] for c in CASES}
    assert outcomes == {"PASS", "FAIL"}


def test_multiple_failure_reasons_are_retained():
    multi = [c for c in CASES if "multiple_failures" in c["failure_modes"]]
    assert multi
    for case in multi:
        _, reasons, checks = replay(case)
        failed = [n for n, c in checks.items() if c.verdict == "FAIL"]
        assert len(reasons) >= 3 and len(failed) >= 2, case["id"]


def test_required_failure_modes_covered():
    covered = {m for c in CASES for m in c["failure_modes"]}
    assert REQUIRED_MODES <= covered


# ---------------- provenance honesty ----------------

def test_only_recorded_live_cases_claim_to_be_real():
    real = [c["id"] for c in CASES if c["source_type"] == "real_gemini_output"]
    assert real == ["real_baseline", "real_composite_pass"]
    for case in CASES:
        if case["source_type"] != "real_gemini_output":
            assert case["observations_source"] == "hand_authored"


def test_real_baseline_provenance():
    case = BY_ID["real_baseline"]
    assert case["observations_source"] == "recorded_live_evaluator"
    prov = case["image_provenance"]
    assert prov["generator_model"] == "gemini-3.1-flash-image"
    assert sha256(case["image"]) == prov["sha256"]

    real_dir = Path(case["image"]).parent
    metadata = load(real_dir / "metadata.json")
    evaluation = load(real_dir / "evaluation.json")
    assert metadata["model"] == "gemini-3.1-flash-image"
    # Observations are exactly the recorded live evaluator response...
    assert load(case["observations"]) == json.loads(evaluation["raw_response"])
    # ...and replaying them reproduces the historical live verdict.
    verdict, reasons, _ = replay(case)
    assert (verdict, reasons) == (evaluation["verdict"], evaluation["reasons"])


def test_real_composite_pass_provenance():
    case = BY_ID["real_composite_pass"]
    assert case["observations_source"] == "recorded_live_evaluator" and case["expected"]["overall"] == "PASS"
    prov = case["image_provenance"]
    assert prov["generator_model"] == "gemini-3.1-flash-image" and prov["strategy"] == "composite"
    assert sha256(case["image"]) == prov["sha256"] and prov["pixel_identity"]["mismatches"] == 0
    real_dir = Path(case["image"]).parent
    metadata = load(real_dir / "metadata.json")
    evaluation = load(real_dir / "evaluation.json")
    assert metadata["cutout"]["sha256"] == prov["cutout_sha256"]
    assert metadata["inputs"]["product_image_sha256"] == PROFILE["reference_image_sha256"]
    assert load(real_dir / "attempt.json")["outcome"]["verdict"] == "PASS"
    assert load(case["observations"]) == json.loads(evaluation["raw_response"])  # verbatim, not corrected
    verdict, reasons, _ = replay(case)
    assert (verdict, reasons) == (evaluation["verdict"], evaluation["reasons"]) == ("PASS", [])


def test_real_composite_pass_under_composite_rule_v2():
    """Rules v2: the evaluator's own pixel re-check on the golden composite image passes; no disagreement."""
    from adgen.evaluator.rules import composite_pixel_identity, composite_product_rules
    case = BY_ID["real_composite_pass"]
    real_dir = ROOT / Path(case["image"]).parent
    metadata = load(Path(case["image"]).parent / "metadata.json")
    identity = composite_pixel_identity(metadata, real_dir / "ad.png")
    assert identity["passed"] and identity["mismatches"] == 0
    obs = validate_response(load(case["observations"]), PROFILE)
    product = composite_product_rules(product_rules(obs["product"], PROFILE), identity)
    assert product.verdict == "PASS" and product.details["evaluator_disagreement"] is None
    assert product.details["deterministic_evidence"][0]["code"] == "PRODUCT_PIXEL_IDENTITY_PASS"


def test_real_composite_copy_matches_original_run_when_available():
    case = BY_ID["real_composite_pass"]
    original = ROOT / case["image_provenance"]["original_run_dir"]
    if not original.exists():
        pytest.skip("outputs/ is git-ignored; original run not present in this checkout")
    assert hashlib.sha256((original / "ad.png").read_bytes()).hexdigest() == case["image_provenance"]["sha256"]


def test_real_baseline_agrees_with_human_label_per_check():
    case = BY_ID["real_baseline"]
    human = case["human_label"]
    verdict, reasons, checks = replay(case)
    assert verdict == human["overall"]
    for name, label in human["checks"].items():
        assert checks[name].verdict == label, name
    assert set(human["expected_codes"]) <= set(reasons)


def test_real_copy_matches_original_run_when_available():
    original = ROOT / BY_ID["real_baseline"]["image_provenance"]["original_run_dir"]
    if not original.exists():
        pytest.skip("outputs/ is git-ignored; original run not present in this checkout")
    case = BY_ID["real_baseline"]
    assert hashlib.sha256((original / "ad.jpg").read_bytes()).hexdigest() == case["image_provenance"]["sha256"]


USER_PATH = re.compile(rb"[A-Za-z]:(\\\\|\\|/)+Users(\\\\|\\|/)|/Users/|/home/", re.IGNORECASE)
GOLDEN_FILES = sorted(p for p in (ROOT / "golden").rglob("*") if p.is_file())


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=[p.relative_to(ROOT).as_posix() for p in GOLDEN_FILES])
def test_golden_artifacts_contain_no_user_paths(path):
    assert not USER_PATH.search(path.read_bytes()), f"user-specific absolute path in {path.name}"


@pytest.mark.parametrize("path", [p for p in GOLDEN_FILES if p.suffix == ".json"],
                         ids=lambda p: p.relative_to(ROOT).as_posix())
def test_golden_json_contains_no_absolute_paths(path):
    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            assert not re.match(r"^([A-Za-z]:[\\/]|\\\\|/)", value), f"absolute path {value[:60]!r}"
    walk(json.loads(path.read_text(encoding="utf-8")))


def test_real_metadata_path_is_project_relative_and_provenance_kept():
    case = BY_ID["real_baseline"]
    metadata = load(Path(case["image"]).parent / "metadata.json")
    assert metadata["inputs"]["product_image"] == "inputs/products/sneaker.jpg"
    assert (ROOT / metadata["inputs"]["product_image"]).is_file()
    assert metadata["inputs"]["product_image_sha256"] == PROFILE["reference_image_sha256"]
    san = case["image_provenance"]["json_copy_sanitization"]
    assert "metadata.json.inputs.product_image" in san["fields_made_relative"]
    assert set(san["original_sha256"]) == {"metadata.json", "evaluation.json"}


@pytest.mark.parametrize("case", [c for c in CASES if c["source_type"] == "edited_fixture"],
                         ids=lambda c: c["id"])
def test_edited_fixture_provenance(case):
    prov = case["image_provenance"]
    assert prov["source_sha256"] == BY_ID["real_baseline"]["image_provenance"]["sha256"]
    assert prov["transformation"]["operation"]
    assert sha256(case["image"]) == prov["sha256"]
    assert "NOT a Gemini output" in case["description"]
