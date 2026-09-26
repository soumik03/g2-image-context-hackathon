"""Build the golden dataset deterministically. Makes NO API calls.

Source types (never mixed up):
  real_gemini_output  image produced by Gemini; observations recorded from the live evaluator
  edited_fixture      deterministic Pillow edit of a real image; observations hand-authored
  hypothetical        no image; hand-authored observations that test the rules only

Expected outcomes below are written by hand from the approved policy. They are
never computed by the evaluator rules; tests/test_golden.py checks the rules
reproduce them.

Usage: python scripts/build_golden.py
"""

import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = PROJECT_ROOT / "golden"
REAL_RUN_NAME = "sneaker-tokyo-winter_20260926T060958_761600Z"
REAL_DIR = GOLDEN / "real" / REAL_RUN_NAME
ORIGINAL_RUN = PROJECT_ROOT / "outputs" / "sneaker-tokyo-winter" / "20260926T060958_761600Z"
SPEC = {"geography": "Tokyo, Japan", "season": "Winter", "required_text": "Step Into Winter"}
# Real composite-strategy PASS (bounded run, Interaction 28): accepted attempt-02.
COMPOSITE_RUN_NAME = "sneaker-tokyo-winter_20260926T093146_984333Z_attempt-02"
COMPOSITE_DIR = GOLDEN / "real" / COMPOSITE_RUN_NAME
ORIGINAL_COMPOSITE = PROJECT_ROOT / "outputs" / "sneaker-tokyo-winter" / "20260926T093146_984333Z" / "attempt-02"
COMPOSITE_JSON_COPIES = ("metadata.json", "evaluation.json", "attempt.json")

REAL_BASELINE_REASONS = [
    "PRODUCT_COLOR_MATERIAL_ALTERED", "PRODUCT_MARK_ALTERED", "PRODUCT_BRANDING_DISTORTED",
    "PRODUCT_DESIGN_DEVIATION", "CONTEXT_GEO_WEAK", "CONTEXT_SEASON_CONTRADICTORY", "CONTEXT_SEASON_CONFLICT",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


# ---------------- real Gemini output (copied, paths sanitized) ----------------

JSON_COPIES = ("metadata.json", "evaluation.json")
USER_PATH_PATTERN = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]|/Users/|/home/", re.IGNORECASE)


def _sanitize(value, where: str, changed: list):
    """Make absolute paths inside the project project-relative; refuse any other user path."""
    if isinstance(value, dict):
        return {k: _sanitize(v, f"{where}.{k}", changed) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v, f"{where}[{i}]", changed) for i, v in enumerate(value)]
    if isinstance(value, str):
        path = Path(value)
        if path.is_absolute():
            try:
                relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
            except ValueError:
                sys.exit(f"Absolute path outside the project at {where}; refusing to commit it.")
            changed.append(where)
            return relative
        if USER_PATH_PATTERN.search(value):
            sys.exit(f"User-specific path embedded at {where}; refusing to commit it.")
    return value


def copy_real_baseline(previous: dict | None) -> tuple[dict, dict]:
    """Copy the real run into golden/ (outputs/ is git-ignored), sanitizing local paths.

    The original run is never modified. JSON copies are rewritten on every build, from the
    original when present, otherwise from the existing golden copy (sanitizing is idempotent).
    """
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    image = REAL_DIR / "ad.jpg"
    if not image.exists():
        if not (ORIGINAL_RUN / "ad.jpg").exists():
            sys.exit(f"Missing {ORIGINAL_RUN / 'ad.jpg'}; cannot build the real baseline case.")
        shutil.copy2(ORIGINAL_RUN / "ad.jpg", image)  # binary copy, SHA-256 preserved

    original_sha = dict((previous or {}).get("original_sha256", {}))
    changed: list = []
    for name in JSON_COPIES:
        source = ORIGINAL_RUN / name if (ORIGINAL_RUN / name).exists() else REAL_DIR / name
        if source.parent == ORIGINAL_RUN:
            original_sha[name] = sha256(source)
        data = _sanitize(json.loads(source.read_text(encoding="utf-8")), name, changed)
        (REAL_DIR / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    evaluation = json.loads((REAL_DIR / "evaluation.json").read_text(encoding="utf-8"))
    sanitization = {
        "note": "Absolute local paths in the JSON copies were made project-relative; nothing else changed.",
        "fields_made_relative": sorted(set(changed) | set((previous or {}).get("fields_made_relative", []))),
        "original_sha256": original_sha,  # SHA-256 of the unmodified originals in outputs/
    }
    return json.loads(evaluation["raw_response"]), sanitization  # recorded live evaluator observations


def copy_real_composite(previous: dict | None) -> tuple[dict, dict]:
    """Copy the real composite PASS attempt into golden/ exactly like the baseline (originals untouched)."""
    COMPOSITE_DIR.mkdir(parents=True, exist_ok=True)
    image = COMPOSITE_DIR / "ad.png"
    if not image.exists():
        if not (ORIGINAL_COMPOSITE / "ad.png").exists():
            sys.exit(f"Missing {ORIGINAL_COMPOSITE / 'ad.png'}; cannot build the real composite case.")
        shutil.copy2(ORIGINAL_COMPOSITE / "ad.png", image)  # binary copy, SHA-256 preserved

    original_sha = dict((previous or {}).get("original_sha256", {}))
    changed: list = []
    for name in COMPOSITE_JSON_COPIES:
        source = ORIGINAL_COMPOSITE / name if (ORIGINAL_COMPOSITE / name).exists() else COMPOSITE_DIR / name
        if source.parent == ORIGINAL_COMPOSITE:
            original_sha[name] = sha256(source)
        data = _sanitize(json.loads(source.read_text(encoding="utf-8")), name, changed)
        (COMPOSITE_DIR / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    evaluation = json.loads((COMPOSITE_DIR / "evaluation.json").read_text(encoding="utf-8"))
    sanitization = {
        "note": "Absolute local paths in the JSON copies were made project-relative; nothing else changed.",
        "fields_made_relative": sorted(set(changed) | set((previous or {}).get("fields_made_relative", []))),
        "original_sha256": original_sha,
    }
    return json.loads(evaluation["raw_response"]), sanitization


# ---------------- deterministic image edits ----------------

HEADLINE_BOX = (585, 50, 985, 255)  # "Step Into Winter" in the real baseline ad


def _font(size: int):
    return ImageFont.load_default(size=size)


def edit_misspelled_text(source: Path, target: Path) -> dict:
    img = Image.open(source).convert("RGB")
    region = img.crop(HEADLINE_BOX).filter(ImageFilter.GaussianBlur(28))
    img.paste(region, HEADLINE_BOX[:2])
    draw = ImageDraw.Draw(img)
    draw.text((605, 70), "Step Into", font=_font(78), fill=(245, 245, 245))
    draw.text((640, 160), "Wintr", font=_font(78), fill=(245, 245, 245))
    img.save(target, format="JPEG", quality=92)
    return {
        "operation": "blur original headline box, then draw misspelled headline",
        "headline_box": list(HEADLINE_BOX), "blur_radius": 28,
        "drawn_text": ["Step Into", "Wintr"], "font": "Pillow default font, size 78",
        "jpeg_quality": 92,
    }


def edit_extra_ad_copy(source: Path, target: Path) -> dict:
    img = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(img)
    box = (40, 890, 330, 990)
    draw.rectangle(box, fill=(200, 30, 40))
    draw.text((62, 905), "50% OFF", font=_font(64), fill=(255, 255, 255))
    img.save(target, format="JPEG", quality=92)
    return {
        "operation": "draw a red price badge with extra advertising copy; original headline untouched",
        "badge_box": list(box), "drawn_text": "50% OFF", "font": "Pillow default font, size 64",
        "jpeg_quality": 92,
    }


# ---------------- hand-authored observations ----------------

def known_good() -> dict:
    """Hypothetical ideal observations for profiles/sneaker.json."""
    return {
        "schema_version": 1,
        "text": {"items": [
            {"text": "Step Into Winter", "role": "headline_or_ad_text", "location": "upper right"},
            {"text": "COMET", "role": "product_branding", "location": "tongue label"},
        ]},
        "product": {
            "attributes": [
                {"id": "silhouette", "evidence": "low-top sneaker, rounded toe, thick flat cupsole", "status": "preserved"},
                {"id": "upper", "evidence": "light sky-blue glossy patent-like upper", "status": "preserved"},
                {"id": "sole", "evidence": "medium-to-dark blue rubber cupsole", "status": "preserved"},
                {"id": "laces", "evidence": "royal-blue flat laces", "status": "preserved"},
                {"id": "side_emblem", "evidence": "yellow asymmetric four-pointed emblem with long lower point", "status": "preserved"},
                {"id": "toe_perforations", "evidence": "rows of small holes on the toe box", "status": "preserved"},
                {"id": "tongue_tab", "evidence": "small yellow tab near top of tongue", "status": "preserved"},
                {"id": "sole_sidewall_texture", "evidence": "ribbed pattern along the sole sidewall", "status": "preserved"},
            ],
            "branding": [
                {"id": "tongue_label", "observed_text": "COMET", "evidence": "tongue patch reads COMET", "status": "legible_correct"},
                {"id": "insole_text", "observed_text": "", "evidence": "insole hidden by the camera angle", "status": "not_visible"},
            ],
            "genuinely_added_marks_or_logos": [],
            "same_product_evidence": "same colorway, silhouette, asymmetric emblem and COMET label",
            "same_product": "yes",
        },
        "context": {
            "geography": {"cues": ["Japanese-script shop signage", "narrow Tokyo side street with overhead wires",
                                   "vending machines on the pavement"],
                          "contradicting_cues": [], "rating": "strong"},
            "season": {"cues": ["falling snow", "snow on rooftops", "people in winter coats"],
                       "conflicting_cues": [], "rating": "strong"},
        },
    }


def _attr(obs, attr_id, status, evidence):
    for a in obs["product"]["attributes"]:
        if a["id"] == attr_id:
            a["status"], a["evidence"] = status, evidence


def _brand(obs, brand_id, status, text, evidence):
    for b in obs["product"]["branding"]:
        if b["id"] == brand_id:
            b["status"], b["observed_text"], b["evidence"] = status, text, evidence


def _headline(obs, *texts):
    others = [i for i in obs["text"]["items"] if i["role"] != "headline_or_ad_text"]
    obs["text"]["items"] = [{"text": t, "role": "headline_or_ad_text", "location": "upper right"} for t in texts] + others


def mut_altered_emblem(o):
    _attr(o, "side_emblem", "altered", "yellow symmetric five-pointed star on the side panel")
    o["product"]["same_product"] = "partially"
    o["product"]["same_product_evidence"] = "same colorway and silhouette but a different side emblem"


def mut_garbled_branding(o):
    _brand(o, "tongue_label", "illegible_or_garbled", "C0M?T", "tongue label letters smeared and malformed")


def mut_added_logo(o):
    o["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "red circular logo on the heel counter", "location": "heel",
         "possible_reference_counterpart_id": ""}]


def mut_weak_geography(o):
    o["context"]["geography"] = {"cues": ["generic city street at night"], "contradicting_cues": [], "rating": "weak"}


def mut_conflicting_season(o):
    o["context"]["season"]["conflicting_cues"] = [
        {"cue": "blooming cherry blossoms framing the scene", "prominence": "prominent",
         "reason": "cherry blossoms bloom in spring"}]


def mut_minor_season_conflict(o):
    o["context"]["season"]["conflicting_cues"] = [
        {"cue": "small potted green plant in a shop window", "prominence": "minor", "reason": "green foliage"}]


def mut_multiple(o):
    _headline(o, "Step Into Wintr")
    mut_altered_emblem(o)
    mut_garbled_branding(o)
    mut_weak_geography(o)
    mut_conflicting_season(o)


# ---------------- case table (expected outcomes are hand-written) ----------------

def build() -> dict:
    GOLDEN.mkdir(exist_ok=True)
    (GOLDEN / "edited").mkdir(exist_ok=True)
    obs_dir = GOLDEN / "observations"
    obs_dir.mkdir(exist_ok=True)

    previous = None
    if (GOLDEN / "manifest.json").exists():
        old = json.loads((GOLDEN / "manifest.json").read_text(encoding="utf-8"))
        old_real = next((c for c in old["cases"] if c["id"] == "real_baseline"), {})
        previous = (old_real.get("image_provenance") or {}).get("json_copy_sanitization")
        old_comp = next((c for c in old["cases"] if c["id"] == "real_composite_pass"), {})
        previous_comp = (old_comp.get("image_provenance") or {}).get("json_copy_sanitization")
    else:
        previous_comp = None
    recorded, sanitization = copy_real_baseline(previous)
    real_image = REAL_DIR / "ad.jpg"
    real_sha = sha256(real_image)
    real_meta = json.loads((REAL_DIR / "metadata.json").read_text(encoding="utf-8"))

    def write_obs(case_id, data):
        path = obs_dir / f"{case_id}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return rel(path)

    cases = []

    # 1. real Gemini output
    real_obs_path = obs_dir / "real_baseline.json"
    real_obs_path.write_text(json.dumps(recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cases.append({
        "id": "real_baseline",
        "source_type": "real_gemini_output",
        "description": "First real Gemini generation (smoke test). Natural real-world failure.",
        "failure_modes": ["real_output", "altered_emblem", "garbled_branding", "weak_geography",
                          "conflicting_season", "multiple_failures"],
        "image": rel(real_image),
        "image_provenance": {
            "generator_model": real_meta["model"], "original_run_dir": rel(ORIGINAL_RUN),
            "timestamp_utc": real_meta["timestamp_utc"], "sha256": real_sha,
            "copied_files": ["ad.jpg", "metadata.json", "evaluation.json"],
            "json_copy_sanitization": sanitization,
        },
        "observations": rel(real_obs_path),
        "observations_source": "recorded_live_evaluator",
        "observations_note": ("Verbatim raw_response from the historical live evaluation (Interaction 12). It was "
                              "recorded before the Interaction 13 sole-description correction; replaying it keeps "
                              "sole=altered as the model reported it then."),
        "spec": SPEC,
        "expected": {"overall": "FAIL",
                     "checks": {"technical": "PASS", "text": "PASS", "product": "FAIL", "context": "FAIL"},
                     "reasons": REAL_BASELINE_REASONS},
        "human_label": {
            "labelled_by": "Soumik Datta (AGENT_LOG Interaction 8)",
            "overall": "FAIL",
            "checks": {"text": "PASS", "product": "FAIL", "context": "FAIL"},
            "expected_codes": ["PRODUCT_MARK_ALTERED", "PRODUCT_BRANDING_DISTORTED",
                               "CONTEXT_GEO_WEAK", "CONTEXT_SEASON_CONFLICT"],
            "known_disagreements_with_recorded_evaluator": [
                "Evaluator reported sole=altered (ribbed sidewall), giving PRODUCT_COLOR_MATERIAL_ALTERED; the "
                "human baseline considered the sole reasonably preserved. The profile's sole description was "
                "corrected afterwards (Interaction 13).",
                "Evaluator rated the season 'contradictory' (CONTEXT_SEASON_CONTRADICTORY); the human saw strong "
                "winter cues plus a prominent conflicting cue.",
            ],
        },
    })

    # 1b. real composite-strategy PASS (appended to the real section; baseline entry above is unchanged)
    comp_recorded, comp_sanitization = copy_real_composite(previous_comp)
    comp_image = COMPOSITE_DIR / "ad.png"
    comp_meta = json.loads((COMPOSITE_DIR / "metadata.json").read_text(encoding="utf-8"))
    comp_obs_path = obs_dir / "real_composite_pass.json"
    comp_obs_path.write_text(json.dumps(comp_recorded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    composite_case = {
        "id": "real_composite_pass",
        "source_type": "real_gemini_output",
        "description": ("Real composite-strategy output: Gemini-generated scene and headline, product pixels "
                        "composited from the human-approved cutout. Accepted attempt 2 of the first bounded "
                        "composite run (attempt 1 failed CONTEXT_GEO_WEAK). Natural real-world PASS."),
        "failure_modes": ["real_output", "real_composite", "known_good"],
        "image": rel(comp_image),
        "image_provenance": {
            "generator_model": comp_meta["model"], "strategy": comp_meta["strategy"],
            "original_run_dir": rel(ORIGINAL_COMPOSITE), "timestamp_utc": comp_meta["timestamp_utc"],
            "sha256": sha256(comp_image), "cutout_sha256": comp_meta["cutout"]["sha256"],
            "pixel_identity": comp_meta["pixel_identity"],
            "copied_files": ["ad.png", *COMPOSITE_JSON_COPIES],
            "json_copy_sanitization": comp_sanitization,
        },
        "observations": rel(comp_obs_path),
        "observations_source": "recorded_live_evaluator",
        "observations_note": ("Verbatim raw_response from the live evaluation in the bounded run (Interaction 28). "
                              "Known evaluator transcription error, kept as recorded: the station sign's second line "
                              "appears in the image as '新宿丁駅' (三 and 目 missing) but was transcribed as '新宿三丁目駅'. "
                              "It is background_incidental text and does not affect the text gate."),
        "spec": SPEC,
        "expected": {"overall": "PASS",
                     "checks": {"technical": "PASS", "text": "PASS", "product": "PASS", "context": "PASS"},
                     "reasons": []},
    }
    cases.append(composite_case)

    # 2-3. edited fixtures derived from the real image
    baseline_codes = REAL_BASELINE_REASONS
    for case_id, editor, text_items, text_code, desc, mode in [
        ("edited_misspelled_text", edit_misspelled_text, ["Step Into Wintr"], "TEXT_MISMATCH",
         "Real baseline image with the headline replaced by a misspelling.", "misspelled_text"),
        ("edited_extra_ad_copy", edit_extra_ad_copy, ["Step Into Winter", "50% OFF"], "TEXT_EXTRA_AD_COPY",
         "Real baseline image with an added '50% OFF' price badge.", "extra_ad_copy"),
    ]:
        target = GOLDEN / "edited" / f"{case_id}.jpg"
        transformation = editor(real_image, target)
        obs = copy.deepcopy(recorded)
        branding_items = [i for i in obs["text"]["items"] if i["role"] != "headline_or_ad_text"]
        obs["text"]["items"] = [
            {"text": t, "role": "headline_or_ad_text", "location": "upper right" if i == 0 else "bottom-left badge"}
            for i, t in enumerate(text_items)] + branding_items
        cases.append({
            "id": case_id,
            "source_type": "edited_fixture",
            "description": desc + " NOT a Gemini output. Inherits every product/context defect of the real image.",
            "failure_modes": [mode, "multiple_failures"],
            "image": rel(target),
            "image_provenance": {"derived_from": rel(real_image), "source_sha256": real_sha,
                                 "transformation": transformation, "sha256": sha256(target)},
            "observations": write_obs(case_id, obs),
            "observations_source": "hand_authored",
            "observations_note": ("Product and context sections copied from the recorded real_baseline response "
                                  "(those image regions are unchanged); text section hand-edited to match the "
                                  "transformation."),
            "spec": SPEC,
            "expected": {"overall": "FAIL",
                         "checks": {"technical": "PASS", "text": "FAIL", "product": "FAIL", "context": "FAIL"},
                         "reasons": [text_code] + baseline_codes},
        })

    # 4+. hypothetical, observation-only cases
    na = "not_applicable"
    hypothetical = [
        ("hyp_known_good", None, ["known_good"], "PASS", {"text": "PASS", "product": "PASS", "context": "PASS"}, []),
        ("hyp_minor_season_conflict", mut_minor_season_conflict, ["known_good", "minor_season_conflict"], "PASS",
         {"text": "PASS", "product": "PASS", "context": "PASS"}, []),
        ("hyp_altered_emblem", mut_altered_emblem, ["altered_emblem"], "FAIL",
         {"text": "PASS", "product": "FAIL", "context": "PASS"}, ["PRODUCT_MARK_ALTERED", "PRODUCT_DESIGN_DEVIATION"]),
        ("hyp_garbled_branding", mut_garbled_branding, ["garbled_branding"], "FAIL",
         {"text": "PASS", "product": "FAIL", "context": "PASS"}, ["PRODUCT_BRANDING_DISTORTED"]),
        ("hyp_added_logo", mut_added_logo, ["added_logo"], "FAIL",
         {"text": "PASS", "product": "FAIL", "context": "PASS"}, ["PRODUCT_BRANDING_ADDED"]),
        ("hyp_misspelled_text", lambda o: _headline(o, "Step Into Wintr"), ["misspelled_text"], "FAIL",
         {"text": "FAIL", "product": "PASS", "context": "PASS"}, ["TEXT_MISMATCH"]),
        ("hyp_extra_ad_copy", lambda o: _headline(o, "Step Into Winter", "50% OFF"), ["extra_ad_copy"], "FAIL",
         {"text": "FAIL", "product": "PASS", "context": "PASS"}, ["TEXT_EXTRA_AD_COPY"]),
        ("hyp_weak_geography", mut_weak_geography, ["weak_geography"], "FAIL",
         {"text": "PASS", "product": "PASS", "context": "FAIL"}, ["CONTEXT_GEO_WEAK"]),
        ("hyp_conflicting_season", mut_conflicting_season, ["conflicting_season"], "FAIL",
         {"text": "PASS", "product": "PASS", "context": "FAIL"}, ["CONTEXT_SEASON_CONFLICT"]),
        ("hyp_multiple_failures", mut_multiple, ["multiple_failures"], "FAIL",
         {"text": "FAIL", "product": "FAIL", "context": "FAIL"},
         ["TEXT_MISMATCH", "PRODUCT_MARK_ALTERED", "PRODUCT_BRANDING_DISTORTED", "PRODUCT_DESIGN_DEVIATION",
          "CONTEXT_GEO_WEAK", "CONTEXT_SEASON_CONFLICT"]),
    ]
    for case_id, mutate, modes, overall, checks, reasons in hypothetical:
        obs = known_good()
        if mutate:
            mutate(obs)
        cases.append({
            "id": case_id,
            "source_type": "hypothetical",
            "description": "Hypothetical label: no image exists. Tests the deterministic rules only.",
            "failure_modes": modes,
            "image": None,
            "image_provenance": None,
            "observations": write_obs(case_id, obs),
            "observations_source": "hand_authored",
            "observations_note": "Written by the coding agent from the case definition; not model output.",
            "spec": SPEC,
            "expected": {"overall": overall, "checks": {"technical": na, **checks}, "reasons": reasons},
        })

    manifest = {
        "manifest_version": 1,
        "description": ("Golden dataset for evaluator validation. Expected outcomes are hand-written from "
                        "evaluator policy rules_version 1; tests/test_golden.py replays each case's observations "
                        "through the deterministic rules offline."),
        "profile": "profiles/sneaker.json",
        "rules_version": "1",
        "rules_version_note": {
            "golden_expected_outcomes_rules_version": "1",
            "current_evaluator_rules_version": "2",
            "explanation": ("Golden expected outcomes are authored against rules v1 and replayed with the v1 product, "
                            "text and context rules, which v2 leaves unchanged. Rules v2 only adds the composite-mode "
                            "product-preservation rule (pixel identity authoritative for preserved product pixels; "
                            "AI disagreement recorded); tests/test_golden.py checks real_composite_pass under it "
                            "separately. The v2 recomputation of the 20-output experiment "
                            "(experiments/composite20/) is separate from this golden fixture rule version."),
        },
        "source_types": {
            "real_gemini_output": "Image generated by Gemini; observations recorded from the live evaluator.",
            "edited_fixture": "Deterministic Pillow edit of a real image; NOT a Gemini output; observations hand-authored.",
            "hypothetical": "No image; hand-authored observations; tests rule logic only.",
        },
        "cases": cases,
    }
    (GOLDEN / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build()
    print(f"Golden dataset written: {len(m['cases'])} cases -> {rel(GOLDEN / 'manifest.json')}")
