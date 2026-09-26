"""Deterministic evaluation rules and the overall gate.

Each check is an independent function. Inputs are already-validated model
observations (see schemas.validate_response); settings come from policy.py.
A check's verdict is derived from its reasons: FAIL if and only if it has at
least one reason, so every failure always carries a reason code.
"""

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageChops, UnidentifiedImageError

from adgen import config
from adgen.cutout import load_approved_cutout
from adgen.errors import GenerationError
from adgen.evaluator.policy import POLICY


@dataclass
class CheckResult:
    reasons: list = field(default_factory=list)  # [{"code": ..., ...details}]
    details: dict = field(default_factory=dict)
    skipped: bool = False

    @property
    def verdict(self) -> str:
        if self.skipped:
            return "SKIPPED"
        return "FAIL" if self.reasons else "PASS"

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "reasons": self.reasons, **self.details}


def _reason(code: str, **details) -> dict:
    return {"code": code, **details}


# ---------------- technical ----------------

REQUIRED_INPUT_FIELDS = ("product_image", "product_image_sha256", "geography", "season", "required_text")


def technical_check(run_dir: Path) -> tuple[CheckResult, dict | None, Path | None]:
    """Metadata completeness, image readability, long edge <= limit. No model involved."""
    result = CheckResult()
    run_dir = Path(run_dir)
    metadata = None
    try:
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        inputs = metadata["inputs"]
        missing = [f for f in REQUIRED_INPUT_FIELDS if not isinstance(inputs.get(f), str) or not inputs.get(f)]
        image_path = run_dir / metadata["output"]["image_file"]
        if missing:
            raise KeyError(", ".join(missing))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        result.reasons.append(_reason("TECH_METADATA_INVALID", detail=f"metadata.json missing or incomplete: {e}"))
        return result, None, None

    try:
        with Image.open(image_path) as img:
            img.load()
            size = img.size
    except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as e:
        result.reasons.append(_reason("TECH_IMAGE_UNREADABLE", detail=str(e)))
        return result, metadata, image_path

    result.details["resolution"] = list(size)
    if max(size) > config.MAX_LONG_EDGE:
        result.reasons.append(_reason("TECH_OVERSIZE", long_edge=max(size), limit=config.MAX_LONG_EDGE))
    return result, metadata, image_path


# ---------------- text ----------------

def _ws(text: str) -> str:
    return " ".join(text.split())


def text_rules(text_section: dict, required_text: str) -> CheckResult:
    policy = POLICY["text"]
    fold = (lambda s: s) if policy["case_sensitive"] else str.casefold

    ad_items = [_ws(i["text"]) for i in text_section["items"] if i["role"] == "headline_or_ad_text"]
    ad_text = _ws(" ".join(ad_items))
    required = _ws(required_text)
    occurrences = fold(ad_text).count(fold(required)) if required else 0

    result = CheckResult(details={
        "required": required,
        "ad_text": ad_text,
        "occurrences": occurrences,
        "extra_ad_copy": "",
        "similarity": 0.0,
    })
    if not ad_items:
        result.reasons.append(_reason("TEXT_MISSING"))
        return result

    if occurrences == 0:
        candidates = ad_items + [ad_text]
        result.details["similarity"] = round(
            max(SequenceMatcher(None, required, c).ratio() for c in candidates), 3
        )
        result.reasons.append(_reason("TEXT_MISMATCH", found=ad_text))
        return result  # extra copy is not computed: the mismatched headline would count as "extra"

    result.details["similarity"] = 1.0
    if occurrences > policy["required_occurrences"]:
        result.reasons.append(_reason("TEXT_DUPLICATED", occurrences=occurrences))

    remainder = _ws(re.sub(re.escape(fold(required)), " ", fold(ad_text)))
    if remainder and not re.sub(r"[\W_]+", "", remainder):
        # Only punctuation left over (e.g. a trailing "!"): punctuation counts, so the text is not exact.
        result.details["similarity"] = round(SequenceMatcher(None, required, ad_text).ratio(), 3)
        result.reasons.append(_reason("TEXT_MISMATCH", found=ad_text))
    elif remainder and policy["fail_on_extra_ad_copy"]:
        result.details["extra_ad_copy"] = remainder
        result.reasons.append(_reason("TEXT_EXTRA_AD_COPY", extra=remainder))
    return result


# ---------------- product ----------------

def _brand_norm(text: str) -> str:
    return "".join(text.split()).casefold()


def product_rules(product: dict, profile: dict) -> CheckResult:
    policy = POLICY["product"]
    attrs = {a["id"]: a for a in profile["attributes"]}
    observed = {o["id"]: o for o in product["attributes"]}
    branding_obs = {o["id"]: o for o in product["branding"]}
    result = CheckResult(details={
        "same_product": product["same_product"],
        "attributes": {},
        "branding": {},
        "recorded": [],
        "reclassified": [],
    })
    reasons, recorded = result.reasons, result.details["recorded"]

    # Added marks: a counterpart that names a profile mark is an alteration, not an addition.
    altered_by_added = set()
    for mark in product["genuinely_added_marks_or_logos"]:
        counterpart = mark["possible_reference_counterpart_id"]
        if counterpart and attrs[counterpart]["kind"] == "mark":
            altered_by_added.add(counterpart)
            result.details["reclassified"].append(
                {"added_mark": mark["description"], "counted_as_altered": counterpart}
            )
        else:
            reasons.append(_reason("PRODUCT_BRANDING_ADDED", evidence=mark["description"], location=mark["location"]))

    # Attribute-level checks (primary evidence), in profile order.
    for attr_id, attr in attrs.items():
        obs = observed[attr_id]
        status = obs["status"]
        if attr_id in altered_by_added and status in ("preserved", "not_visible"):
            status = "altered"
        result.details["attributes"][attr_id] = status
        if status in ("altered", "missing"):
            if attr["critical"]:
                code = policy["critical_attribute_codes"][attr["kind"]][status]
                reasons.append(_reason(code, id=attr_id, evidence=obs["evidence"]))
            else:
                recorded.append({"code": "PRODUCT_MINOR_DEVIATION", "id": attr_id, "status": status,
                                 "evidence": obs["evidence"]})
        elif status == "not_visible":
            recorded.append({"code": "PRODUCT_NOT_VISIBLE", "id": attr_id})

    # Branding checks.
    for brand in profile["branding"]:
        obs = branding_obs[brand["id"]]
        status = obs["status"]
        result.details["branding"][brand["id"]] = status
        if status in policy["branding_fail_statuses"]:
            reasons.append(_reason("PRODUCT_BRANDING_DISTORTED", id=brand["id"], expected=brand["text"],
                                   observed_text=obs["observed_text"], evidence=obs["evidence"]))
        elif status == "legible_correct" and _brand_norm(obs["observed_text"]) != _brand_norm(brand["text"]):
            reasons.append(_reason("PRODUCT_BRANDING_DISTORTED", id=brand["id"], expected=brand["text"],
                                   observed_text=obs["observed_text"],
                                   evidence="model said legible_correct but the observed text differs"))
        elif status == "not_visible":
            recorded.append({"code": "PRODUCT_NOT_VISIBLE", "id": brand["id"]})

    # Safety net on overall identity.
    same_code = policy["same_product_fail_codes"].get(product["same_product"])
    if same_code:
        reasons.append(_reason(same_code, evidence=product["same_product_evidence"]))

    # Not enough visible evidence to judge fidelity at all.
    critical_statuses = [result.details["attributes"][a["id"]] for a in profile["attributes"] if a["critical"]]
    critical_statuses += [result.details["branding"][b["id"]] for b in profile["branding"] if b["critical"]]
    if (policy["fail_when_all_critical_not_visible"] and critical_statuses
            and all(s == "not_visible" for s in critical_statuses)):
        reasons.append(_reason("PRODUCT_INSUFFICIENT_EVIDENCE"))
    return result


# ---------------- composite product preservation (deterministic, rules v2) ----------------

def composite_pixel_identity(metadata: dict, image_path: Path, cutouts_dir: Path = config.CUTOUTS_DIR) -> dict:
    """Independently re-verify, from files on disk, that the approved cutout's pixels are intact in the ad.

    Does not trust the generator's own pixel_identity claim: it loads the approved, human-verified cutout
    for the reference (lineage re-checked), confirms it is the cutout recorded in the metadata, and
    compares every fully opaque cutout pixel with the saved ad at the recorded placement.
    """
    evidence = {"passed": False, "checked_opaque_pixels": 0, "mismatches": None,
                "expected_opaque_pixels": None, "cutout_sha256": None, "detail": ""}
    try:
        cutout = load_approved_cutout(Path(metadata["inputs"]["product_image"]), cutouts_dir)
        evidence["cutout_sha256"] = cutout.metadata["cutout_sha256"]
        evidence["expected_opaque_pixels"] = cutout.metadata["opaque_pixels"]
        if cutout.metadata["cutout_sha256"] != metadata["cutout"]["sha256"]:
            evidence["detail"] = "approved cutout differs from the cutout recorded in the ad metadata"
            return evidence
        x, y = metadata["composite"]["placement"]["x"], metadata["composite"]["placement"]["y"]
        w, h = cutout.image.size
        with Image.open(image_path) as img:
            region = img.convert("RGB").crop((x, y, x + w, y + h))
        opaque = cutout.image.getchannel("A").point(lambda a: 255 if a == 255 else 0)
        r, g, b = ImageChops.difference(region, cutout.image.convert("RGB")).split()
        differs = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v else 0)
        evidence["checked_opaque_pixels"] = opaque.histogram()[255]
        evidence["mismatches"] = ImageChops.multiply(differs, opaque).histogram()[255]
    except (GenerationError, KeyError, TypeError, ValueError, OSError, UnidentifiedImageError) as e:
        evidence["detail"] = f"pixel identity could not be verified: {type(e).__name__}: {e}"
        return evidence
    evidence["passed"] = (evidence["mismatches"] == 0 and evidence["checked_opaque_pixels"] > 0
                          and evidence["checked_opaque_pixels"] == evidence["expected_opaque_pixels"])
    evidence["detail"] = ("all fully opaque approved-cutout pixels are identical in the ad" if evidence["passed"]
                          else "product pixels differ from the approved cutout")
    return evidence


def composite_product_rules(ai: CheckResult, identity: dict) -> CheckResult:
    """Composite-mode product verdict from deterministic pixel identity plus the AI observation.

    `ai` is the unchanged product_rules() result on the evaluator's observations; it is always stored.
    """
    not_covered = set(POLICY["product"]["composite_pixel_identity"]["codes_not_covered_by_pixel_identity"])
    details = {
        "mode": "composite",
        "same_product": ai.details["same_product"],
        "attributes": ai.details["attributes"],
        "branding": ai.details["branding"],
        "recorded": ai.details["recorded"],
        "reclassified": ai.details["reclassified"],
        "pixel_identity": identity,
        "deterministic_evidence": [],
        "ai_observation": ai.to_dict(),  # the AI product verdict and reasons under the unchanged rules
        "evaluator_disagreement": None,
    }
    if not identity["passed"]:
        fail = _reason("PRODUCT_PIXEL_IDENTITY_FAIL", detail=identity["detail"], mismatches=identity["mismatches"],
                       checked_opaque_pixels=identity["checked_opaque_pixels"])
        return CheckResult(reasons=[fail, *ai.reasons], details=details)

    details["deterministic_evidence"].append({
        "code": "PRODUCT_PIXEL_IDENTITY_PASS", "checked_opaque_pixels": identity["checked_opaque_pixels"],
        "cutout_sha256": identity["cutout_sha256"]})
    gating = [r for r in ai.reasons if r["code"] in not_covered]
    overridden = [r for r in ai.reasons if r["code"] not in not_covered]
    if overridden:
        details["evaluator_disagreement"] = {
            "code": "PRODUCT_EVALUATOR_DISAGREEMENT",
            "ai_reasons": overridden,
            "resolution": "exact pixel identity with the approved cutout is authoritative for the preserved "
                          "product pixels; the AI observation is retained, not used as ground truth",
        }
    return CheckResult(reasons=gating, details=details)


# ---------------- context ----------------

def context_rules(context: dict) -> CheckResult:
    policy = POLICY["context"]
    geo, season = context["geography"], context["season"]
    result = CheckResult(details={
        "geography": {"rating": geo["rating"], "cues": geo["cues"], "contradicting_cues": geo["contradicting_cues"]},
        "season": {"rating": season["rating"], "cues": season["cues"], "conflicting_cues": season["conflicting_cues"]},
        "recorded": [],
    })
    if geo["rating"] not in policy["geography_pass_ratings"]:
        result.reasons.append(_reason(f"CONTEXT_GEO_{geo['rating'].upper()}", cues=geo["cues"],
                                      contradicting_cues=geo["contradicting_cues"]))
    if season["rating"] not in policy["season_pass_ratings"]:
        result.reasons.append(_reason(f"CONTEXT_SEASON_{season['rating'].upper()}", cues=season["cues"]))
    for conflict in season["conflicting_cues"]:
        if conflict["prominence"] in policy["season_conflict_fail_prominence"]:
            result.reasons.append(_reason("CONTEXT_SEASON_CONFLICT", cue=conflict["cue"], reason=conflict["reason"]))
        else:
            result.details["recorded"].append({"minor_season_conflict": conflict["cue"]})
    return result


# ---------------- gate ----------------

def gate(checks: dict[str, CheckResult]) -> tuple[str, list[str]]:
    """Overall PASS only if every check passed; reason codes in first-seen order."""
    codes = []
    for check in checks.values():
        for reason in check.reasons:
            if reason["code"] not in codes:
                codes.append(reason["code"])
    verdict = "PASS" if all(c.verdict == "PASS" for c in checks.values()) else "FAIL"
    return verdict, codes
