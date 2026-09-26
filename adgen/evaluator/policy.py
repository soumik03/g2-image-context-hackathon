"""Versioned evaluation policy.

Every setting here is an ENGINEERING DECISION made for this project, not an
official hackathon requirement (the only official numeric constraint, the
1024 px long edge, lives in adgen.config). Settings are expected to be
calibrated against the golden dataset; bump RULES_VERSION on any change.
Each evaluation.json records RULES_VERSION and a snapshot of this policy.
"""

import copy

RULES_VERSION = "2"  # v2 (2026-09-26): composite-mode product preservation rule

POLICY = {
    "text": {
        # Exact comparison after whitespace normalization; punctuation always counts.
        "case_sensitive": True,
        "required_occurrences": 1,
        "fail_on_extra_ad_copy": True,
    },
    "product": {
        # Safety net on top of the attribute-level rules (approved 2026-09-26).
        "same_product_fail_codes": {
            "partially": "PRODUCT_DESIGN_DEVIATION",
            "no": "PRODUCT_REPLACED",
        },
        # Applied to attributes marked critical in the human-verified profile.
        "critical_attribute_codes": {
            "mark": {"altered": "PRODUCT_MARK_ALTERED", "missing": "PRODUCT_MARK_MISSING"},
            "color_material": {
                "altered": "PRODUCT_COLOR_MATERIAL_ALTERED",
                "missing": "PRODUCT_COLOR_MATERIAL_ALTERED",
            },
            "shape": {"altered": "PRODUCT_SHAPE_ALTERED", "missing": "PRODUCT_SHAPE_ALTERED"},
            "detail": {"altered": "PRODUCT_DETAIL_ALTERED", "missing": "PRODUCT_DETAIL_ALTERED"},
        },
        # Applied to every visible branding item, critical or not.
        "branding_fail_statuses": ["legible_different", "illegible_or_garbled"],
        "fail_when_all_critical_not_visible": True,
        # Composite mode only (v2). The evaluator independently re-verifies that every fully opaque
        # pixel of the approved cutout is present unchanged in the ad. When it is, that deterministic
        # evidence is authoritative for the PRESERVED PRODUCT PIXELS: AI reasons about those pixels
        # become a recorded PRODUCT_EVALUATOR_DISAGREEMENT instead of a FAIL. AI reasons that pixel
        # identity cannot rule out (something ADDED around the product) stay gating. If identity is
        # not verified, the product FAILS (PRODUCT_PIXEL_IDENTITY_FAIL) and all AI reasons stay gating.
        # Redraw mode is unaffected.
        "composite_pixel_identity": {
            "authoritative_for_preserved_product_pixels": True,
            "codes_not_covered_by_pixel_identity": ["PRODUCT_BRANDING_ADDED"],
        },
    },
    "context": {
        # Only "strong" passes; a landmark is not required (several cues suffice).
        "geography_pass_ratings": ["strong"],
        "season_pass_ratings": ["strong"],
        "season_conflict_fail_prominence": ["prominent"],
    },
}


def snapshot() -> dict:
    return {"rules_version": RULES_VERSION, **copy.deepcopy(POLICY)}
