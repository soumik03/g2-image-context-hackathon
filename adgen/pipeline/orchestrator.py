"""Bounded quality-controlled regeneration for ONE generation spec.

generate -> evaluate -> deterministic gate -> PASS: accept | FAIL: targeted correction -> ...
Bounded by a for-loop over max_attempts (default config.MAX_ATTEMPTS = 3): at most
max_attempts generator calls and max_attempts evaluator calls. No hidden retries;
every error terminates the run. Every run starts with a fresh attempt-01 generation.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import google.genai

from adgen import config
from adgen import pipeline as status
from adgen.errors import FinalizationError, GenerationError, redact
from adgen.evaluator import EvaluationError
from adgen.evaluator.evaluate import evaluate_run
from adgen.evaluator.policy import RULES_VERSION
from adgen.evaluator.profile import load_approved_profile
from adgen.generator import generate
from adgen.image_io import load_reference_image
from adgen.composite import CompositeInvariantError, build_scene_prompt, generate_composite
from adgen.cutout import load_approved_cutout
from adgen.pipeline.correction import ALL_SECTIONS, build_correction
from adgen.prompt import build_prompt
from adgen.spec import GenerationSpec

STRATEGIES = ("redraw", "composite")
COMPOSITE_SECTIONS = ("TEXT", "CONTEXT")  # the scene model never draws the product


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    status: str
    final: dict


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _signature(evaluation: dict) -> list[str]:
    """Failing reasons as code[:id], sorted: the unit of 'progress' between attempts."""
    items = set()
    for section in ("text", "product", "context"):
        for r in evaluation["checks"].get(section, {}).get("reasons", []):
            items.add(f"{r['code']}:{r['id']}" if r.get("id") else r["code"])
    return sorted(items)


def run_pipeline(
    spec: GenerationSpec,
    client,
    output_root: Path = config.OUTPUT_DIR,
    profiles_dir: Path = config.PROFILES_DIR,
    max_attempts: int = config.MAX_ATTEMPTS,
    secret: str | None = None,
    strategy: str = "redraw",
    cutouts_dir: Path = config.CUTOUTS_DIR,
) -> RunResult:
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")

    started = _now()
    run_id = started.strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir = Path(output_root) / spec.id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)  # always a fresh run; never reuses old evaluations

    spec_values = {"id": spec.id, "product_image": _rel(spec.product_image), "geography": spec.geography,
                   "season": spec.season, "required_text": spec.required_text}
    spec_sha = _sha(json.dumps(spec_values, sort_keys=True, ensure_ascii=False))
    base_prompt_sha = _sha(build_prompt(spec)) if strategy == "redraw" else None  # composite: set after preflight
    calls = {"generator": 0, "evaluator": 0}
    final = {
        "schema_version": 1, "run_id": run_id, "strategy": strategy, "cutout": None,
        "status": None, "final_verdict": None, "accepted_attempt": None,
        "stop_reason": None, "spec": spec_values, "spec_sha256": spec_sha, "reference_image_sha256": None,
        "base_prompt_sha256": base_prompt_sha, "profile": None, "generator_model": config.GENERATOR_MODEL,
        "evaluator_model": config.EVALUATOR_MODEL, "rules_version": RULES_VERSION, "max_attempts": max_attempts,
        "attempts": [], "reason_history": [], "api_calls": calls, "error": None,
        "started_utc": _iso(started), "finished_utc": None, "duration_seconds": None,
        "sdk_version": google.genai.__version__,
    }

    def finish(run_status: str, verdict: str, stop_reason: str, error: str | None = None) -> RunResult:
        ended = _now()
        final.update(status=run_status, final_verdict=verdict, stop_reason=stop_reason,
                     error=redact(error, secret) if error else None,
                     finished_utc=_iso(ended), duration_seconds=round((ended - started).total_seconds(), 3))
        _write_json(run_dir / "final.json", final)
        return RunResult(run_dir, run_status, final)

    # Preflight: nothing is generated unless the output can be evaluated.
    cutout = None
    try:
        reference = load_reference_image(spec.product_image)
        profile, profile_path = load_approved_profile(reference.sha256, profiles_dir)
        if strategy == "composite":
            cutout = load_approved_cutout(spec.product_image, cutouts_dir)  # human_verified + pixel lineage
    except (GenerationError, EvaluationError) as e:
        return finish(status.ERROR_PREFLIGHT, "ERROR", "preflight_error", str(e))
    final["reference_image_sha256"] = reference.sha256
    final["profile"] = {"file": profile_path.name, "verified_by": profile.get("verified_by", "")}
    if cutout is not None:
        base_prompt_sha = _sha(build_scene_prompt(spec, cutout.metadata["view"]))
        final["base_prompt_sha256"] = base_prompt_sha
        final["cutout"] = {"file": cutout.path.name, "sha256": cutout.metadata["cutout_sha256"],
                           "view": cutout.metadata["view"], "verified_by": cutout.metadata.get("verified_by", "")}
    sections = ALL_SECTIONS if strategy == "redraw" else COMPOSITE_SECTIONS

    history: list[list[str]] = []   # failing codes per attempt (for persistence notes)
    previous_eval = None
    previous_signature = None
    previous_body = None

    for attempt in range(1, max_attempts + 1):
        attempt_dir = run_dir / f"attempt-{attempt:02d}"
        attempt_started = _now()
        correction = None
        if previous_eval is not None:
            correction = build_correction(previous_eval, spec, attempt, max_attempts, history, sections)
            if not correction.lines:  # e.g. composite mode with only product failures: nothing actionable
                return finish(status.FAIL_NO_PROGRESS, "FAIL", "no_actionable_correction")
            if correction.body == previous_body:  # identical request guard
                return finish(status.FAIL_NO_PROGRESS, "FAIL", "no_progress")

        record = {
            "run_id": run_id, "attempt": attempt, "attempt_id": f"{spec.id}/{run_id}/attempt-{attempt:02d}",
            "parent_attempt": f"attempt-{attempt - 1:02d}" if attempt > 1 else None,
            "spec_sha256": spec_sha, "reference_image_sha256": reference.sha256,
            "generator_model": config.GENERATOR_MODEL, "evaluator_model": config.EVALUATOR_MODEL,
            "base_prompt_sha256": base_prompt_sha, "prompt_sha256": None,
            "correction": None if correction is None else {
                "derived_from": f"attempt-{attempt - 1:02d}/evaluation.json",
                "codes": [c for line in correction.lines for c in line["codes"]],
                "suppressed_codes": correction.suppressed,
                "excluded_codes_not_sent": correction.excluded,
                "persisting_codes": correction.persisting,
                "text": correction.text,
            },
            "outcome": None, "started_utc": _iso(attempt_started), "finished_utc": None,
        }
        summary = {"attempt": attempt, "dir": attempt_dir.name, "parent": record["parent_attempt"],
                   "correction_applied": correction is not None, "verdict": None, "reasons": [], "error": None}
        final["attempts"].append(summary)

        def close(verdict, reasons, error=None, regressions=None):
            record["outcome"] = {"verdict": verdict, "reasons": reasons,
                                 "error": redact(error, secret) if error else None,
                                 "regressions": regressions or []}
            record["finished_utc"] = _iso(_now())
            summary.update(verdict=verdict, reasons=reasons, error=record["outcome"]["error"])
            _write_json(attempt_dir / "attempt.json", record)

        # Generation (1 call).
        calls["generator"] += 1
        correction_text = correction.text if correction else None
        try:
            if strategy == "composite":
                result = generate_composite(spec, client, cutout, attempt_dir, correction_text, secret)
            else:
                result = generate(spec, client, secret=secret, target_dir=attempt_dir, correction=correction_text)
        except CompositeInvariantError as e:
            close("ERROR", [], f"CompositeInvariantError: {e}")
            return finish(status.ERROR_INTERNAL, "ERROR", "internal_error", str(e))
        except (FinalizationError, OSError) as e:  # filesystem failure after the generator call
            close("ERROR", [], f"{type(e).__name__}: {e}")
            return finish(status.ERROR_INTERNAL, "ERROR", "filesystem_error", f"{type(e).__name__}: {e}")
        except GenerationError as e:
            close("ERROR", [], f"{type(e).__name__}: {e}")
            return finish(status.ERROR_GENERATOR, "ERROR", "generator_error", str(e))
        record["prompt_sha256"] = _sha(result.metadata["prompt"])
        record["finalization"] = getattr(result, "finalization", "rename")

        # Evaluation (at most 1 call; none if the technical check fails).
        try:
            evaluation = evaluate_run(attempt_dir, client, profiles_dir=profiles_dir, secret=secret,
                                      cutouts_dir=cutouts_dir)
        except EvaluationError as e:
            close("ERROR", [e.code], str(e))
            return finish(status.ERROR_INTERNAL, "ERROR", "internal_error", str(e))
        except OSError as e:  # e.g. evaluation.json could not be written; the model call may already have run
            calls["evaluator"] += 1  # counted as an upper bound, never under-reported
            close("ERROR", [], f"{type(e).__name__}: {e}")
            return finish(status.ERROR_INTERNAL, "ERROR", "filesystem_error",
                          f"{type(e).__name__}: {e} (evaluator call count is an upper bound)")
        if evaluation.get("request_summary") is not None:
            calls["evaluator"] += 1

        if evaluation["checks"]["technical"]["verdict"] == "FAIL":
            close("ERROR", evaluation["reasons"], "technical invariant violated by a pipeline-generated artifact")
            return finish(status.ERROR_INTERNAL, "ERROR", "internal_error",
                          f"technical FAIL on {attempt_dir.name}: {evaluation['reasons']}")
        if evaluation["verdict"] == "ERROR":
            close("ERROR", evaluation["reasons"], evaluation.get("error"))
            return finish(status.ERROR_EVALUATOR, "ERROR", "evaluator_error", evaluation.get("error"))
        if evaluation["verdict"] == "PASS":
            close("PASS", [])
            final["reason_history"].append([])
            final["accepted_attempt"] = attempt_dir.name
            return finish(status.PASS, "PASS", "passed")

        # FAIL: decide whether another attempt is justified.
        signature = _signature(evaluation)
        regressions = sorted(set(signature) - set(previous_signature or signature))
        close("FAIL", evaluation["reasons"], regressions=regressions)
        history.append(list(evaluation["reasons"]))
        final["reason_history"].append(list(evaluation["reasons"]))

        if previous_signature is not None and signature == previous_signature:
            return finish(status.FAIL_NO_PROGRESS, "FAIL", "no_progress")
        if attempt == max_attempts:
            return finish(status.FAIL_EXHAUSTED, "FAIL", "max_attempts_reached")
        previous_eval, previous_signature = evaluation, signature
        previous_body = correction.body if correction else None

    raise AssertionError("unreachable: the loop always returns")  # pragma: no cover
