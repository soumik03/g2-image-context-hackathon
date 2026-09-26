"""JSON schemas sent to the evaluator model, and strict local validators.

The API-side schema guides the model; the local validators are what we trust.
Any structural problem raises EvaluationError (-> overall ERROR, never PASS).
"""

import re

from adgen.evaluator import EvaluationError

TEXT_ROLES = ("headline_or_ad_text", "product_branding", "background_incidental")
ATTRIBUTE_STATUSES = ("preserved", "altered", "missing", "not_visible")
BRANDING_STATUSES = ("legible_correct", "legible_different", "illegible_or_garbled", "not_visible")
SAME_PRODUCT_VALUES = ("yes", "partially", "no")
RATINGS = ("strong", "weak", "absent", "contradictory")
PROMINENCE = ("prominent", "minor")
ATTRIBUTE_KINDS = ("shape", "color_material", "mark", "detail")

RESPONSE_SCHEMA_VERSION = 1
PROFILE_VERSION = 1
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

MALFORMED = "EVAL_MALFORMED_RESPONSE"
MISSING_SECTION = "EVAL_MISSING_SECTION"
INCOMPLETE_COVERAGE = "EVAL_INCOMPLETE_COVERAGE"
INVALID_PROFILE = "EVAL_INVALID_PROFILE"


# ---------- schemas sent to the API (only widely supported keywords) ----------

def _s():
    return {"type": "string"}


def _enum(values):
    return {"type": "string", "enum": list(values)}


def _obj(props):
    return {"type": "object", "properties": props, "required": list(props)}


def _arr(items):
    return {"type": "array", "items": items}


def build_response_schema(profile: dict) -> dict:
    attr_ids = [a["id"] for a in profile["attributes"]]
    brand_ids = [b["id"] for b in profile["branding"]]
    return _obj({
        "schema_version": {"type": "integer"},
        "text": _obj({
            "items": _arr(_obj({"text": _s(), "role": _enum(TEXT_ROLES), "location": _s()})),
        }),
        "product": _obj({
            "attributes": _arr(_obj({
                "id": _enum(attr_ids), "evidence": _s(), "status": _enum(ATTRIBUTE_STATUSES),
            })),
            "branding": _arr(_obj({
                "id": _enum(brand_ids) if brand_ids else _s(),
                "observed_text": _s(), "evidence": _s(), "status": _enum(BRANDING_STATUSES),
            })),
            "genuinely_added_marks_or_logos": _arr(_obj({
                "description": _s(), "location": _s(), "possible_reference_counterpart_id": _s(),
            })),
            "same_product_evidence": _s(),
            "same_product": _enum(SAME_PRODUCT_VALUES),
        }),
        "context": _obj({
            "geography": _obj({
                "cues": _arr(_s()), "contradicting_cues": _arr(_s()), "rating": _enum(RATINGS),
            }),
            "season": _obj({
                "cues": _arr(_s()),
                "conflicting_cues": _arr(_obj({
                    "cue": _s(), "prominence": _enum(PROMINENCE), "reason": _s(),
                })),
                "rating": _enum(RATINGS),
            }),
        }),
    })


PROFILE_DRAFT_SCHEMA = _obj({
    "product_category": _s(),
    "attributes": _arr(_obj({"id": _s(), "kind": _enum(ATTRIBUTE_KINDS), "description": _s()})),
    "branding": _arr(_obj({"id": _s(), "text": _s(), "location": _s()})),
})


# ---------- small validation helpers ----------

def _fail(code, message):
    raise EvaluationError(code, message)


def _dict(value, path, code=MALFORMED):
    if not isinstance(value, dict):
        _fail(code, f"{path} must be an object")
    return value


def _list(value, path, code=MALFORMED):
    if not isinstance(value, list):
        _fail(code, f"{path} must be a list")
    return value


def _str(value, path, nonempty=False, code=MALFORMED):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _fail(code, f"{path} must be a {'non-empty ' if nonempty else ''}string")
    return value


def _enum_value(value, allowed, path, code=MALFORMED):
    if value not in allowed:
        _fail(code, f"{path} must be one of {list(allowed)}, got {value!r}")
    return value


def _bool(value, path, code):
    if not isinstance(value, bool):
        _fail(code, f"{path} must be true or false")
    return value


def _key(obj, key, path, code=MALFORMED):
    if key not in obj:
        _fail(code, f"{path}.{key} is missing")
    return obj[key]


def _coverage(observed_ids, expected_ids, path):
    if sorted(observed_ids) != sorted(expected_ids):
        missing = sorted(set(expected_ids) - set(observed_ids))
        unknown = sorted(set(observed_ids) - set(expected_ids))
        dupes = sorted({i for i in observed_ids if observed_ids.count(i) > 1})
        _fail(INCOMPLETE_COVERAGE,
              f"{path} must cover each profile id exactly once "
              f"(missing={missing}, unknown={unknown}, duplicated={dupes})")


# ---------- evaluator response ----------

def validate_response(data, profile: dict) -> dict:
    _dict(data, "response")
    if data.get("schema_version") != RESPONSE_SCHEMA_VERSION:
        _fail(MALFORMED, f"response.schema_version must be {RESPONSE_SCHEMA_VERSION}")
    for section in ("text", "product", "context"):
        _dict(_key(data, section, "response", code=MISSING_SECTION), f"response.{section}")

    # text
    for i, item in enumerate(_list(_key(data["text"], "items", "text"), "text.items")):
        p = f"text.items[{i}]"
        _dict(item, p)
        _str(_key(item, "text", p), f"{p}.text", nonempty=True)
        _enum_value(_key(item, "role", p), TEXT_ROLES, f"{p}.role")
        _str(_key(item, "location", p), f"{p}.location")

    # product
    product = data["product"]
    attr_ids = [a["id"] for a in profile["attributes"]]
    brand_ids = [b["id"] for b in profile["branding"]]
    observed = []
    for i, obs in enumerate(_list(_key(product, "attributes", "product"), "product.attributes")):
        p = f"product.attributes[{i}]"
        _dict(obs, p)
        observed.append(_str(_key(obs, "id", p), f"{p}.id", nonempty=True))
        _str(_key(obs, "evidence", p), f"{p}.evidence", nonempty=True)
        _enum_value(_key(obs, "status", p), ATTRIBUTE_STATUSES, f"{p}.status")
    _coverage(observed, attr_ids, "product.attributes")

    observed = []
    for i, obs in enumerate(_list(_key(product, "branding", "product"), "product.branding")):
        p = f"product.branding[{i}]"
        _dict(obs, p)
        observed.append(_str(_key(obs, "id", p), f"{p}.id", nonempty=True))
        _str(_key(obs, "observed_text", p), f"{p}.observed_text")
        _str(_key(obs, "evidence", p), f"{p}.evidence", nonempty=True)
        _enum_value(_key(obs, "status", p), BRANDING_STATUSES, f"{p}.status")
    _coverage(observed, brand_ids, "product.branding")

    added = _key(product, "genuinely_added_marks_or_logos", "product")
    for i, mark in enumerate(_list(added, "product.genuinely_added_marks_or_logos")):
        p = f"product.genuinely_added_marks_or_logos[{i}]"
        _dict(mark, p)
        _str(_key(mark, "description", p), f"{p}.description", nonempty=True)
        _str(_key(mark, "location", p), f"{p}.location")
        counterpart = _str(_key(mark, "possible_reference_counterpart_id", p), f"{p}.possible_reference_counterpart_id")
        if counterpart and counterpart not in attr_ids:
            _fail(MALFORMED, f"{p}.possible_reference_counterpart_id {counterpart!r} is not a profile attribute id")

    _enum_value(_key(product, "same_product", "product"), SAME_PRODUCT_VALUES, "product.same_product")
    _str(_key(product, "same_product_evidence", "product"), "product.same_product_evidence", nonempty=True)

    # context
    context = data["context"]
    geo = _dict(_key(context, "geography", "context"), "context.geography")
    for field in ("cues", "contradicting_cues"):
        for i, cue in enumerate(_list(_key(geo, field, "context.geography"), f"context.geography.{field}")):
            _str(cue, f"context.geography.{field}[{i}]", nonempty=True)
    _enum_value(_key(geo, "rating", "context.geography"), RATINGS, "context.geography.rating")

    season = _dict(_key(context, "season", "context"), "context.season")
    for i, cue in enumerate(_list(_key(season, "cues", "context.season"), "context.season.cues")):
        _str(cue, f"context.season.cues[{i}]", nonempty=True)
    conflicts = _list(_key(season, "conflicting_cues", "context.season"), "context.season.conflicting_cues")
    for i, c in enumerate(conflicts):
        p = f"context.season.conflicting_cues[{i}]"
        _dict(c, p)
        _str(_key(c, "cue", p), f"{p}.cue", nonempty=True)
        _enum_value(_key(c, "prominence", p), PROMINENCE, f"{p}.prominence")
        _str(_key(c, "reason", p), f"{p}.reason")
    _enum_value(_key(season, "rating", "context.season"), RATINGS, "context.season.rating")
    return data


# ---------- reference profile ----------

def validate_profile(data) -> dict:
    """Structural validation of a profile file (draft or approved)."""
    code = INVALID_PROFILE
    _dict(data, "profile", code)
    if data.get("profile_version") != PROFILE_VERSION:
        _fail(code, f"profile.profile_version must be {PROFILE_VERSION}")
    _str(_key(data, "reference_image", "profile", code), "profile.reference_image", True, code)
    sha = _str(_key(data, "reference_image_sha256", "profile", code), "profile.reference_image_sha256", True, code)
    if not SHA256_PATTERN.match(sha):
        _fail(code, "profile.reference_image_sha256 must be a lowercase hex SHA-256")
    _bool(_key(data, "human_verified", "profile", code), "profile.human_verified", code)
    _str(_key(data, "product_category", "profile", code), "profile.product_category", True, code)

    ids = []
    attributes = _list(_key(data, "attributes", "profile", code), "profile.attributes", code)
    if not attributes:
        _fail(code, "profile.attributes must not be empty")
    for i, a in enumerate(attributes):
        p = f"profile.attributes[{i}]"
        _dict(a, p, code)
        ids.append(_str(_key(a, "id", p, code), f"{p}.id", True, code))
        _enum_value(_key(a, "kind", p, code), ATTRIBUTE_KINDS, f"{p}.kind", code)
        _str(_key(a, "description", p, code), f"{p}.description", True, code)
        _bool(_key(a, "critical", p, code), f"{p}.critical", code)
    for i, b in enumerate(_list(_key(data, "branding", "profile", code), "profile.branding", code)):
        p = f"profile.branding[{i}]"
        _dict(b, p, code)
        ids.append(_str(_key(b, "id", p, code), f"{p}.id", True, code))
        _str(_key(b, "text", p, code), f"{p}.text", True, code)
        _str(_key(b, "location", p, code), f"{p}.location", False, code)
        _bool(_key(b, "critical", p, code), f"{p}.critical", code)

    bad = [i for i in ids if not ID_PATTERN.match(i)]
    if bad:
        _fail(code, f"profile ids must match [a-z0-9_]+: {bad}")
    if len(set(ids)) != len(ids):
        _fail(code, "profile attribute and branding ids must be unique")
    return data


def validate_profile_draft_output(data) -> dict:
    """Validate the raw model output of the profile-draft call."""
    _dict(data, "draft")
    _str(_key(data, "product_category", "draft"), "draft.product_category", nonempty=True)
    attributes = _list(_key(data, "attributes", "draft"), "draft.attributes")
    if not attributes:
        _fail(MALFORMED, "draft.attributes must not be empty")
    for i, a in enumerate(attributes):
        p = f"draft.attributes[{i}]"
        _dict(a, p)
        _str(_key(a, "id", p), f"{p}.id", nonempty=True)
        _enum_value(_key(a, "kind", p), ATTRIBUTE_KINDS, f"{p}.kind")
        _str(_key(a, "description", p), f"{p}.description", nonempty=True)
    for i, b in enumerate(_list(_key(data, "branding", "draft"), "draft.branding")):
        p = f"draft.branding[{i}]"
        _dict(b, p)
        _str(_key(b, "id", p), f"{p}.id", nonempty=True)
        _str(_key(b, "text", p), f"{p}.text")  # empty entries are dropped when building the draft
        _str(_key(b, "location", p), f"{p}.location")
    return data
