"""The correction builder: pure, deterministic, deduplicated, evidence framed as previous-output observation."""

import copy
from pathlib import Path

from adgen import config
from adgen.evaluator.rules import context_rules, product_rules, text_rules
from adgen.pipeline.correction import OBSERVED, build_correction
from adgen.spec import GenerationSpec

SPEC = GenerationSpec(id="sneaker-tokyo-winter", product_image=Path("unused.jpg"),
                      geography="Tokyo, Japan", season="Winter", required_text="Step Into Winter")


def evaluation_from(response, profile, required="Step Into Winter"):
    """A realistic evaluation record: checks produced by the real deterministic rules."""
    return {"checks": {
        "text": text_rules(response["text"], required).to_dict(),
        "product": product_rules(response["product"], profile).to_dict(),
        "context": context_rules(response["context"]).to_dict(),
    }}


def sneaker_failure(smoke):
    """The current real sneaker failure combination (season rated contradictory, as observed live)."""
    response = copy.deepcopy(smoke["response"])
    response["context"]["season"]["rating"] = "contradictory"
    return response


def test_sneaker_failure_combination_is_concise(smoke, profile):
    evaluation = evaluation_from(sneaker_failure(smoke), profile)
    codes = [r["code"] for s in ("text", "product", "context") for r in evaluation["checks"][s]["reasons"]]
    assert codes == ["PRODUCT_MARK_ALTERED", "PRODUCT_BRANDING_DISTORTED", "PRODUCT_DESIGN_DEVIATION",
                     "CONTEXT_GEO_WEAK", "CONTEXT_SEASON_CONTRADICTORY", "CONTEXT_SEASON_CONFLICT"]

    c = build_correction(evaluation, SPEC, attempt=2, max_attempts=3, history=[codes])
    lines = c.body.splitlines()
    assert [line.split("]")[0] + "]" for line in lines] == ["- [PRODUCT]", "- [PRODUCT]", "- [CONTEXT]", "- [CONTEXT]"]
    assert sorted(c.suppressed) == ["CONTEXT_SEASON_CONTRADICTORY", "PRODUCT_DESIGN_DEVIATION"]
    assert "design differed" not in c.text                     # generic line suppressed
    assert sum("season" in line.lower() for line in lines) == 1  # one consolidated seasonal line
    assert "cherry blossoms" in c.text and "Winter must read clearly throughout" in c.text
    assert "Tokyo, Japan" in c.text
    assert "[TEXT]" not in c.text                               # text passed; nothing to correct
    assert c.text.startswith("CORRECTIONS FROM PREVIOUS ATTEMPT (attempt 2 of 3)")
    assert len(c.body) < 1500


def test_evidence_is_framed_as_previous_output_observation(smoke, profile):
    c = build_correction(evaluation_from(sneaker_failure(smoke), profile), SPEC, 2, 3, [])
    for line in c.body.splitlines():
        assert OBSERVED in line, line
    assert "five-pointed star with a lightning-bolt tail" in c.text
    assert "ZOMET" in c.text


def test_no_profile_content_or_flags_leak(smoke, profile):
    c = build_correction(evaluation_from(sneaker_failure(smoke), profile), SPEC, 2, 3, [])
    assert "critical" not in c.text.lower() and "human_verified" not in c.text
    for attr in profile["attributes"]:
        assert attr["description"] not in c.text
        assert attr["id"] not in c.text
    for brand in profile["branding"]:
        assert brand["location"] not in c.text


def test_correction_is_pure_and_deterministic(smoke, profile):
    evaluation = evaluation_from(sneaker_failure(smoke), profile)
    snapshot = copy.deepcopy(evaluation)
    history = [["CONTEXT_GEO_WEAK"], ["CONTEXT_GEO_WEAK", "PRODUCT_MARK_ALTERED"]]
    a = build_correction(evaluation, SPEC, 3, 3, history)
    b = build_correction(copy.deepcopy(evaluation), SPEC, 3, 3, copy.deepcopy(history))
    assert a == b
    assert evaluation == snapshot  # inputs not mutated


def test_mark_altered_suppresses_design_deviation(good_response, profile):
    good_response["product"]["attributes"][3].update(status="altered", evidence="five-pointed star")
    good_response["product"]["same_product"] = "partially"
    c = build_correction(evaluation_from(good_response, profile), SPEC, 2, 3, [])
    assert c.suppressed == ["PRODUCT_DESIGN_DEVIATION"]
    assert len(c.lines) == 1 and c.lines[0]["codes"] == ["PRODUCT_MARK_ALTERED"]


def test_design_deviation_alone_is_kept(good_response, profile):
    good_response["product"]["same_product"] = "partially"
    good_response["product"]["same_product_evidence"] = "overall proportions look bulkier"
    c = build_correction(evaluation_from(good_response, profile), SPEC, 2, 3, [])
    assert c.suppressed == []
    assert "design differed" in c.text and "overall proportions look bulkier" in c.text


def test_season_conflict_alone_and_rating_alone(good_response, profile):
    r = copy.deepcopy(good_response)
    r["context"]["season"]["conflicting_cues"] = [{"cue": "blossoms", "prominence": "prominent", "reason": "spring"}]
    c = build_correction(evaluation_from(r, profile), SPEC, 2, 3, [])
    assert c.lines[0]["codes"] == ["CONTEXT_SEASON_CONFLICT"] and "throughout" not in c.text

    r = copy.deepcopy(good_response)
    r["context"]["season"]["rating"] = "weak"
    c = build_correction(evaluation_from(r, profile), SPEC, 2, 3, [])
    assert c.lines[0]["codes"] == ["CONTEXT_SEASON_WEAK"] and "did not read clearly as Winter" in c.text


def test_text_corrections_use_spec_values(good_response, profile):
    r = copy.deepcopy(good_response)
    r["text"]["items"][0]["text"] = "Step Into Wintr"
    c = build_correction(evaluation_from(r, profile), SPEC, 2, 3, [])
    assert '"Step Into Wintr"' in c.text and 'Render exactly "Step Into Winter"' in c.text

    r = copy.deepcopy(good_response)
    r["text"]["items"].insert(1, {"text": "50% OFF", "role": "headline_or_ad_text", "location": "badge"})
    c = build_correction(evaluation_from(r, profile), SPEC, 2, 3, [])
    assert '"50% OFF"' in c.text and "Remove it" in c.text


def test_recorded_only_items_are_not_corrected(good_response, profile):
    good_response["product"]["attributes"][4].update(status="altered", evidence="white laces")  # non-critical
    good_response["context"]["season"]["conflicting_cues"] = [{"cue": "plant", "prominence": "minor", "reason": "x"}]
    c = build_correction(evaluation_from(good_response, profile), SPEC, 2, 3, [])
    assert c.lines == [] and "white laces" not in c.text and "plant" not in c.text


def test_persisting_codes_are_marked(smoke, profile):
    evaluation = evaluation_from(sneaker_failure(smoke), profile)
    history = [["CONTEXT_GEO_WEAK", "TEXT_MISMATCH"], ["CONTEXT_GEO_WEAK", "PRODUCT_MARK_ALTERED"]]
    c = build_correction(evaluation, SPEC, 3, 3, history)
    assert c.persisting == {"CONTEXT_GEO_WEAK": 1}
    geo_line = next(line for line in c.body.splitlines() if "Tokyo" in line)
    assert "STILL UNRESOLVED since attempt 1" in geo_line


def test_long_evidence_is_capped(good_response, profile):
    good_response["product"]["attributes"][3].update(status="altered", evidence="x" * 1000)
    c = build_correction(evaluation_from(good_response, profile), SPEC, 2, 3, [])
    assert "x" * config.MAX_EVIDENCE_CHARS not in c.text
    assert "x" * (config.MAX_EVIDENCE_CHARS - 1) in c.text or "…" in c.text
