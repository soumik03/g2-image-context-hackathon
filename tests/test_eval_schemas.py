"""Strict validation: malformed or incomplete evaluator output must become ERROR."""

import copy

import pytest

from adgen.evaluator import EvaluationError
from adgen.evaluator.judge import parse_json
from adgen.evaluator.schemas import (
    build_response_schema,
    validate_profile,
    validate_profile_draft_output,
    validate_response,
)


def error_code(fn, *args):
    with pytest.raises(EvaluationError) as exc_info:
        fn(*args)
    return exc_info.value.code


def test_good_response_validates(good_response, profile):
    assert validate_response(good_response, profile) is good_response


# 13. missing metric
@pytest.mark.parametrize("section", ["text", "product", "context"])
def test_missing_section(good_response, profile, section):
    del good_response[section]
    assert error_code(validate_response, good_response, profile) == "EVAL_MISSING_SECTION"


def test_missing_profile_attribute_id(good_response, profile):
    good_response["product"]["attributes"].pop()
    assert error_code(validate_response, good_response, profile) == "EVAL_INCOMPLETE_COVERAGE"


def test_duplicate_attribute_id(good_response, profile):
    good_response["product"]["attributes"].append(copy.deepcopy(good_response["product"]["attributes"][0]))
    assert error_code(validate_response, good_response, profile) == "EVAL_INCOMPLETE_COVERAGE"


def test_unknown_branding_id(good_response, profile):
    good_response["product"]["branding"][0]["id"] = "heel_logo"
    assert error_code(validate_response, good_response, profile) == "EVAL_INCOMPLETE_COVERAGE"


# 14. malformed structured response
def test_non_json_output():
    assert error_code(parse_json, "Sure! Here is my analysis: the ad looks great.") == "EVAL_MALFORMED_RESPONSE"


@pytest.mark.parametrize("mutate", [
    lambda r: r["product"]["attributes"][0].update(status="mostly_fine"),
    lambda r: r["product"].update(same_product="maybe"),
    lambda r: r["context"]["geography"].update(rating="ok"),
    lambda r: r["context"]["season"]["conflicting_cues"].append({"cue": "x", "prominence": "huge", "reason": ""}),
    lambda r: r["text"]["items"][0].update(role="slogan"),
    lambda r: r["product"]["attributes"][0].update(evidence=""),
    lambda r: r["product"].pop("same_product"),
    lambda r: r.update(schema_version=2),
    lambda r: r.update(text=["not", "an", "object"]),
    lambda r: r["product"]["genuinely_added_marks_or_logos"].append(
        {"description": "logo", "location": "heel", "possible_reference_counterpart_id": "not_in_profile"}),
])
def test_malformed_values(good_response, profile, mutate):
    mutate(good_response)
    assert error_code(validate_response, good_response, profile) == "EVAL_MALFORMED_RESPONSE"


def test_response_is_not_an_object(profile):
    assert error_code(validate_response, [1, 2, 3], profile) == "EVAL_MALFORMED_RESPONSE"


def test_response_schema_uses_profile_ids_and_no_critical_flags(profile):
    schema = build_response_schema(profile)
    attr_id_schema = schema["properties"]["product"]["properties"]["attributes"]["items"]["properties"]["id"]
    assert attr_id_schema["enum"] == [a["id"] for a in profile["attributes"]]
    assert "critical" not in str(schema)


def test_profile_validation(profile):
    assert validate_profile(profile) is profile
    broken = copy.deepcopy(profile)
    broken["attributes"][0]["critical"] = "yes"
    assert error_code(validate_profile, broken) == "EVAL_INVALID_PROFILE"
    broken = copy.deepcopy(profile)
    broken["branding"][0]["id"] = broken["attributes"][0]["id"]
    assert error_code(validate_profile, broken) == "EVAL_INVALID_PROFILE"


def test_profile_draft_output_validation():
    good = {"product_category": "sneaker",
            "attributes": [{"id": "emblem", "kind": "mark", "description": "yellow star"}],
            "branding": [{"id": "tongue", "text": "COMET", "location": "tongue"}]}
    assert validate_profile_draft_output(good) is good
    bad = copy.deepcopy(good)
    bad["attributes"][0]["kind"] = "logo"
    assert error_code(validate_profile_draft_output, bad) == "EVAL_MALFORMED_RESPONSE"
