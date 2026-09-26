"""Deterministic rule tests: the evaluator must separate passing from failing outputs."""

import pytest

from adgen.evaluator.rules import CheckResult, context_rules, gate, product_rules, text_rules
from adgen.evaluator.schemas import validate_response

REQUIRED = "Step Into Winter"


def run_rules(response, profile, required=REQUIRED):
    validate_response(response, profile)
    checks = {
        "technical": CheckResult(),
        "text": text_rules(response["text"], required),
        "product": product_rules(response["product"], profile),
        "context": context_rules(response["context"]),
    }
    verdict, codes = gate(checks)
    return verdict, codes, checks


def set_attr(response, attr_id, status, evidence="changed"):
    for obs in response["product"]["attributes"]:
        if obs["id"] == attr_id:
            obs["status"], obs["evidence"] = status, evidence


def set_brand(response, brand_id, status, observed_text):
    for obs in response["product"]["branding"]:
        if obs["id"] == brand_id:
            obs["status"], obs["observed_text"] = status, observed_text


def set_ad_text(response, *texts):
    branding = [i for i in response["text"]["items"] if i["role"] != "headline_or_ad_text"]
    response["text"]["items"] = [
        {"text": t, "role": "headline_or_ad_text", "location": "top"} for t in texts
    ] + branding


def codes_of(check):
    return [r["code"] for r in check.reasons]


# 1. known-good
def test_known_good_passes(good_response, profile):
    verdict, codes, checks = run_rules(good_response, profile)
    assert verdict == "PASS" and codes == []
    assert all(c.verdict == "PASS" for c in checks.values())


# ---------------- product ----------------

# 2. altered emblem
def test_altered_emblem_is_mark_altered_not_added(good_response, profile):
    set_attr(good_response, "side_emblem", "altered", "five-pointed star with lightning bolt")
    verdict, codes, checks = run_rules(good_response, profile)
    assert verdict == "FAIL"
    assert codes_of(checks["product"]) == ["PRODUCT_MARK_ALTERED"]
    assert "PRODUCT_BRANDING_ADDED" not in codes


# 2b. altered emblem also listed as an "added" mark with a counterpart -> counted once, as altered
def test_added_mark_with_counterpart_reclassified(good_response, profile):
    set_attr(good_response, "side_emblem", "altered")
    good_response["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "star-and-bolt logo", "location": "side", "possible_reference_counterpart_id": "side_emblem"}
    ]
    _, codes, checks = run_rules(good_response, profile)
    assert codes_of(checks["product"]) == ["PRODUCT_MARK_ALTERED"]
    assert checks["product"].details["reclassified"][0]["counted_as_altered"] == "side_emblem"


def test_added_mark_with_counterpart_overrides_preserved_status(good_response, profile):
    good_response["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "odd star", "location": "side", "possible_reference_counterpart_id": "side_emblem"}
    ]
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_MARK_ALTERED"]


def test_missing_emblem(good_response, profile):
    set_attr(good_response, "side_emblem", "missing", "plain side panel")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_MARK_MISSING"]


# 3. distorted COMET
def test_distorted_branding(good_response, profile):
    set_brand(good_response, "tongue_label", "illegible_or_garbled", "ZOMET")
    _, codes, checks = run_rules(good_response, profile)
    assert codes == ["PRODUCT_BRANDING_DISTORTED"]
    assert checks["product"].reasons[0]["observed_text"] == "ZOMET"


def test_legible_different_branding(good_response, profile):
    set_brand(good_response, "tongue_label", "legible_different", "COMIT")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_BRANDING_DISTORTED"]


def test_legible_correct_but_text_differs_is_distorted(good_response, profile):
    set_brand(good_response, "tongue_label", "legible_correct", "ZOMET")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_BRANDING_DISTORTED"]


def test_branding_case_difference_is_not_distortion(good_response, profile):
    set_brand(good_response, "tongue_label", "legible_correct", "CoMeT")
    verdict, _, _ = run_rules(good_response, profile)
    assert verdict == "PASS"


# 4. genuinely new logo
def test_genuinely_added_logo(good_response, profile):
    good_response["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "red swoosh-like logo on the heel", "location": "heel", "possible_reference_counterpart_id": ""}
    ]
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_BRANDING_ADDED"]


def test_added_mark_pointing_at_non_mark_attribute_counts_as_added(good_response, profile):
    good_response["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "logo printed on sole", "location": "sole", "possible_reference_counterpart_id": "sole"}
    ]
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_BRANDING_ADDED"]


def test_same_product_partially_fails(good_response, profile):
    good_response["product"]["same_product"] = "partially"
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_DESIGN_DEVIATION"]


def test_same_product_no_fails(good_response, profile):
    good_response["product"]["same_product"] = "no"
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_REPLACED"]


def test_critical_color_change_fails(good_response, profile):
    set_attr(good_response, "upper", "altered", "red upper")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_COLOR_MATERIAL_ALTERED"]


def test_non_critical_deviation_is_recorded_only(good_response, profile):
    set_attr(good_response, "laces", "altered", "white laces")
    verdict, _, checks = run_rules(good_response, profile)
    assert verdict == "PASS"
    assert {"code": "PRODUCT_MINOR_DEVIATION", "id": "laces", "status": "altered",
            "evidence": "white laces"} in checks["product"].details["recorded"]


def test_not_visible_non_critical_branding_does_not_fail(good_response, profile):
    verdict, _, checks = run_rules(good_response, profile)  # insole_logo is not_visible in good_response
    assert verdict == "PASS"
    assert {"code": "PRODUCT_NOT_VISIBLE", "id": "insole_logo"} in checks["product"].details["recorded"]


def test_all_critical_not_visible_is_insufficient_evidence(good_response, profile):
    for a in profile["attributes"]:
        if a["critical"]:
            set_attr(good_response, a["id"], "not_visible", "cropped")
    set_brand(good_response, "tongue_label", "not_visible", "")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["PRODUCT_INSUFFICIENT_EVIDENCE"]


# ---------------- text ----------------

# 5. misspelling
def test_misspelled_text(good_response, profile):
    set_ad_text(good_response, "Step Into Wintr")
    _, codes, checks = run_rules(good_response, profile)
    assert codes == ["TEXT_MISMATCH"]
    assert 0.9 < checks["text"].details["similarity"] < 1.0


def test_case_difference_is_mismatch(good_response, profile):
    set_ad_text(good_response, "STEP INTO WINTER")
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["TEXT_MISMATCH"]


@pytest.mark.parametrize("rendered", ["Step Into Winter!", "Step-Into Winter", "Step Into Winter."])
def test_punctuation_difference_is_mismatch(good_response, profile, rendered):
    set_ad_text(good_response, rendered)
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["TEXT_MISMATCH"]


def test_line_break_and_split_items_are_normalized(good_response, profile):
    set_ad_text(good_response, "Step Into\nWinter")
    assert run_rules(good_response, profile)[0] == "PASS"
    set_ad_text(good_response, "Step Into", "Winter")
    assert run_rules(good_response, profile)[0] == "PASS"


def test_no_ad_text_is_missing(good_response, profile):
    set_ad_text(good_response)
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["TEXT_MISSING"]


# 6. duplicated
def test_duplicated_text(good_response, profile):
    set_ad_text(good_response, REQUIRED, REQUIRED)
    _, codes, checks = run_rules(good_response, profile)
    assert codes == ["TEXT_DUPLICATED"]
    assert checks["text"].details["occurrences"] == 2


# 7. extra ad copy
def test_extra_ad_copy(good_response, profile):
    set_ad_text(good_response, REQUIRED, "50% OFF")
    _, codes, checks = run_rules(good_response, profile)
    assert codes == ["TEXT_EXTRA_AD_COPY"]
    assert checks["text"].details["extra_ad_copy"] == "50% OFF"


def test_branding_and_background_text_are_not_ad_copy(good_response, profile):
    good_response["text"]["items"].append({"text": "渋谷", "role": "background_incidental", "location": "sign"})
    assert run_rules(good_response, profile)[0] == "PASS"


# ---------------- context ----------------

# 8. weak geography
def test_weak_geography(good_response, profile):
    good_response["context"]["geography"]["rating"] = "weak"
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["CONTEXT_GEO_WEAK"]


# 9. contradictory geography
def test_contradictory_geography(good_response, profile):
    good_response["context"]["geography"].update(rating="contradictory", contradicting_cues=["Eiffel Tower"])
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["CONTEXT_GEO_CONTRADICTORY"]


def test_absent_geography(good_response, profile):
    good_response["context"]["geography"].update(rating="absent", cues=[])
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["CONTEXT_GEO_ABSENT"]


@pytest.mark.parametrize("rating", ["weak", "absent", "contradictory"])
def test_season_below_strong_fails(good_response, profile, rating):
    good_response["context"]["season"]["rating"] = rating
    _, codes, _ = run_rules(good_response, profile)
    assert codes == [f"CONTEXT_SEASON_{rating.upper()}"]


# 10. prominent seasonal conflict
def test_prominent_season_conflict(good_response, profile):
    good_response["context"]["season"]["conflicting_cues"] = [
        {"cue": "blooming cherry blossoms", "prominence": "prominent", "reason": "spring flower"}
    ]
    _, codes, _ = run_rules(good_response, profile)
    assert codes == ["CONTEXT_SEASON_CONFLICT"]


# 11. minor seasonal conflict
def test_minor_season_conflict_is_recorded_only(good_response, profile):
    good_response["context"]["season"]["conflicting_cues"] = [
        {"cue": "small potted flower", "prominence": "minor", "reason": "spring-like"}
    ]
    verdict, _, checks = run_rules(good_response, profile)
    assert verdict == "PASS"
    assert checks["context"].details["recorded"] == [{"minor_season_conflict": "small potted flower"}]


# 12. multiple simultaneous failures
def test_multiple_failures_across_sections(good_response, profile):
    set_ad_text(good_response, "Step Into Wintr")
    set_attr(good_response, "side_emblem", "altered")
    set_brand(good_response, "tongue_label", "illegible_or_garbled", "C0M?T")
    good_response["context"]["geography"]["rating"] = "weak"
    verdict, codes, checks = run_rules(good_response, profile)
    assert verdict == "FAIL"
    assert codes == ["TEXT_MISMATCH", "PRODUCT_MARK_ALTERED", "PRODUCT_BRANDING_DISTORTED", "CONTEXT_GEO_WEAK"]
    assert [c.verdict for c in checks.values()] == ["PASS", "FAIL", "FAIL", "FAIL"]


# 15. the real smoke-test failure pattern
def test_smoke_test_failure_pattern(smoke, profile):
    verdict, codes, checks = run_rules(smoke["response"], profile)
    assert verdict == "FAIL"
    assert codes == smoke["expected_reasons"]
    assert checks["text"].verdict == "PASS"          # "Step Into Winter" was rendered correctly
    assert checks["product"].verdict == "FAIL"
    assert checks["context"].verdict == "FAIL"
    assert "PRODUCT_BRANDING_ADDED" not in codes      # the changed emblem is not double-counted
    assert codes.count("PRODUCT_MARK_ALTERED") == 1


def test_every_failed_check_has_reason_codes(smoke, profile):
    _, _, checks = run_rules(smoke["response"], profile)
    for check in checks.values():
        assert (check.verdict == "FAIL") == bool(check.reasons)
