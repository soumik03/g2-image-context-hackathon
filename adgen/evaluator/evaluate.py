"""Evaluate one generation run directory and write evaluation.json next to it."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import google.genai

from adgen import config
from adgen.errors import GenerationError, redact
from adgen.evaluator import EvaluationError, judge, policy
from adgen.evaluator.profile import load_approved_profile
from adgen.evaluator.rules import (CheckResult, composite_pixel_identity, composite_product_rules, context_rules,
                                   gate, product_rules, technical_check, text_rules)
from adgen.evaluator.schemas import validate_response
from adgen.image_io import load_reference_image

EVALUATION_FILE = "evaluation.json"
SCHEMA_VERSION = 1


def evaluate_run(
    run_dir: Path,
    client,
    profiles_dir: Path = config.PROFILES_DIR,
    secret: str | None = None,
    overwrite: bool = False,
    cutouts_dir: Path = config.CUTOUTS_DIR,
) -> dict:
    """Evaluate a run: PASS / FAIL / ERROR. Always writes evaluation.json (unless it already exists)."""
    run_dir = Path(run_dir)
    out_path = run_dir / EVALUATION_FILE
    if out_path.exists() and not overwrite:
        raise EvaluationError("EVAL_ALREADY_EXISTS", f"{out_path} exists; pass overwrite=True to replace it.")

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    record = {
        "schema_version": SCHEMA_VERSION,
        "rules_version": policy.RULES_VERSION,
        "policy_snapshot": policy.snapshot(),
        "run_dir": str(run_dir),
        "evaluator_model": config.EVALUATOR_MODEL,
        "profile": None,
        "verdict": None,
        "reasons": [],
        "error": None,
        "checks": {},
        "evaluator_disagreements": [],
        "request_summary": None,
        "raw_response": None,
        "timestamp_utc": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "duration_seconds": None,
        "sdk_version": google.genai.__version__,
    }

    technical, metadata, image_path = technical_check(run_dir)
    record["checks"]["technical"] = technical.to_dict()

    if technical.verdict == "FAIL":
        # No model call: the output already fails a hard requirement.
        for name in ("text", "product", "context"):
            record["checks"][name] = CheckResult(skipped=True).to_dict()
        record["verdict"], record["reasons"] = gate({"technical": technical})
    else:
        try:
            inputs = metadata["inputs"]
            profile, profile_path = load_approved_profile(inputs["product_image_sha256"], profiles_dir)
            record["profile"] = {
                "file": profile_path.name,
                "reference_image_sha256": profile["reference_image_sha256"],
                "human_verified": profile["human_verified"],
                "verified_by": profile.get("verified_by", ""),
            }
            try:
                reference = load_reference_image(Path(inputs["product_image"]))
                generated = load_reference_image(image_path)
            except GenerationError as e:
                raise EvaluationError("EVAL_REFERENCE_INVALID", str(e)) from None
            if reference.sha256 != profile["reference_image_sha256"]:
                raise EvaluationError("EVAL_REFERENCE_INVALID",
                                      "Reference image on disk does not match the profile's SHA-256.")

            request = judge.build_evaluation_request(
                reference, generated, profile, inputs["geography"], inputs["season"]
            )
            record["request_summary"] = judge.request_summary(request)
            raw_text = judge.call_model(client, request, secret)
            record["raw_response"] = raw_text  # preserved verbatim for audit/replay, even if malformed
            decide(record, technical, metadata, image_path, raw_text, profile, cutouts_dir)
        except EvaluationError as e:
            record["verdict"] = "ERROR"
            record["reasons"] = [e.code]
            record["error"] = redact(str(e), secret)

    record["duration_seconds"] = round(time.perf_counter() - t0, 3)
    _write_json(out_path, record)
    return record


def decide(record: dict, technical: CheckResult, metadata: dict, image_path: Path, raw_text: str, profile: dict,
           cutouts_dir: Path = config.CUTOUTS_DIR) -> None:
    """Deterministic part of an evaluation: validate the raw observations and apply the rules + gate.

    Shared by live evaluation and offline recomputation, so both use exactly the same logic.
    """
    response = validate_response(judge.parse_json(raw_text), profile)
    checks = {
        "technical": technical,
        "text": text_rules(response["text"], metadata["inputs"]["required_text"]),
        "product": product_rules(response["product"], profile),
        "context": context_rules(response["context"]),
    }
    if metadata.get("strategy") == "composite":
        identity = composite_pixel_identity(metadata, image_path, cutouts_dir)
        checks["product"] = composite_product_rules(checks["product"], identity)
        disagreement = checks["product"].details["evaluator_disagreement"]
        record["evaluator_disagreements"] = [{"check": "product", **disagreement}] if disagreement else []
    record["checks"] = {name: check.to_dict() for name, check in checks.items()}
    record["verdict"], record["reasons"] = gate(checks)


def recompute_evaluation(run_dir: Path, profiles_dir: Path = config.PROFILES_DIR,
                         cutouts_dir: Path = config.CUTOUTS_DIR) -> dict:
    """Re-apply the CURRENT rules to a stored evaluation's raw model response. No model call; writes nothing."""
    run_dir = Path(run_dir)
    stored = json.loads((run_dir / EVALUATION_FILE).read_text(encoding="utf-8"))
    if not stored.get("raw_response"):
        raise EvaluationError("EVAL_NO_STORED_RESPONSE", f"{run_dir / EVALUATION_FILE} has no raw_response.")
    technical, metadata, image_path = technical_check(run_dir)
    profile, profile_path = load_approved_profile(metadata["inputs"]["product_image_sha256"], profiles_dir)
    record = {
        "schema_version": SCHEMA_VERSION, "rules_version": policy.RULES_VERSION,
        "policy_snapshot": policy.snapshot(), "run_dir": run_dir.as_posix(),
        "evaluator_model": stored["evaluator_model"],
        "profile": {"file": profile_path.name, "verified_by": profile.get("verified_by", "")},
        "verdict": None, "reasons": [], "error": None, "checks": {"technical": technical.to_dict()},
        "evaluator_disagreements": [], "raw_response": stored["raw_response"],
        "recomputed": {
            "note": "Recomputed offline from the stored raw evaluator response; no model call was made.",
            "model_call": False, "source_file": EVALUATION_FILE,
            "original_rules_version": stored["rules_version"], "original_verdict": stored["verdict"],
            "original_reasons": stored["reasons"], "original_timestamp_utc": stored["timestamp_utc"],
        },
    }
    try:
        decide(record, technical, metadata, image_path, stored["raw_response"], profile, cutouts_dir)
    except EvaluationError as e:
        record["verdict"], record["reasons"], record["error"] = "ERROR", [e.code], str(e)
    return record


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
