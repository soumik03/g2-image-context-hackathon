"""The ~20-output evaluation experiment for the composite strategy (one reference product, 20 contexts).

    python scripts/run_experiment.py build      # write the 20 specs + manifest (no API call)
    python scripts/run_experiment.py check      # validate specs/manifest/preflight (no API call)
    python scripts/run_experiment.py run        # LIVE: per case 1 generation + 1 evaluation (max_attempts=1)
    python scripts/run_experiment.py recompute  # OFFLINE: re-apply current rules to the stored raw evaluator responses
    python scripts/run_experiment.py report     # aggregate report from the recorded artifacts (no API call)

Budget: at most 20 generator + 20 evaluator calls. No retries: a FAIL or ERROR is recorded as the result.
A case already recorded in the manifest is never run again. The run aborts (remaining cases recorded as
"not_run") after 3 consecutive generator/API errors, so a systemic outage cannot burn the budget.
"""

import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adgen import config  # noqa: E402
from adgen import pipeline as status  # noqa: E402
from adgen.spec import load_spec  # noqa: E402

EXP_DIR = ROOT / "experiments" / "composite20"
SPECS_DIR = EXP_DIR / "specs"
MANIFEST = EXP_DIR / "manifest.json"
REPORT_JSON = EXP_DIR / "report.json"
REPORT_MD = EXP_DIR / "report.md"
REFERENCE = "inputs/products/sneaker.jpg"
STRATEGY = "composite"
MAX_ATTEMPTS = 1
MAX_CONSECUTIVE_API_ERRORS = 3

GEOGRAPHIES = [("tokyo", "Tokyo, Japan"), ("paris", "Paris, France"), ("newyork", "New York, USA"),
               ("london", "London, United Kingdom"), ("seoul", "Seoul, South Korea")]
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
# Short, product-agnostic, one per case (fixed order = case order).
REQUIRED_TEXTS = [
    "Warm Steps Ahead", "Bloom In Motion", "Light On Your Feet", "Fall Into Comfort",
    "Winter Walks Await", "Fresh Starts Daily", "Made For Sunny Days", "Golden Days Ahead",
    "Own The Cold", "New Season New Pace", "Keep It Moving", "Step Into Autumn",
    "Cozy City Miles", "Rain Or Shine", "Long Days Easy Steps", "Walk The Season",
    "Stay Warm Stay Bold", "Spring Into Style", "Cool Summer Moves", "Autumn Starts Here",
]


def _rel(path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def case_list() -> list[dict]:
    cases = []
    for gi, (slug, geography) in enumerate(GEOGRAPHIES):
        for si, season in enumerate(SEASONS):
            n = gi * len(SEASONS) + si + 1
            cases.append({"case_id": f"exp20-{n:02d}-{slug}-{season.lower()}", "geography": geography,
                          "season": season, "required_text": REQUIRED_TEXTS[n - 1]})
    return cases


def build() -> None:
    if MANIFEST.exists():
        sys.exit(f"{_rel(MANIFEST)} already exists; refusing to overwrite recorded results.")
    entries = []
    for c in case_list():
        spec = {"id": c["case_id"], "product_image": REFERENCE, "geography": c["geography"],
                "season": c["season"], "required_text": c["required_text"]}
        spec_path = SPECS_DIR / f"{c['case_id']}.json"
        _write_json(spec_path, spec)
        entries.append({
            **c, "reference_product": REFERENCE, "spec_file": _rel(spec_path),
            "source": "composite20 experiment: deterministic spec from scripts/run_experiment.py (same product, varied context/text)",
            "expected_official_inputs": {"product_image": REFERENCE, "geography": c["geography"],
                                         "season": c["season"], "required_text": c["required_text"]},
            "run_dir": None, "generation_result": None, "evaluation_result": None, "status": "pending",
        })
    reference_sha = hashlib.sha256((ROOT / REFERENCE).read_bytes()).hexdigest()
    _write_json(MANIFEST, {
        "manifest_version": 1, "experiment": "composite20",
        "description": "~20-output evaluation of the final composite strategy: one approved reference product, "
                       "20 geography/season/required_text contexts, max_attempts=1 (no retries).",
        "strategy": STRATEGY, "max_attempts": MAX_ATTEMPTS, "reference_product": REFERENCE,
        "reference_image_sha256": reference_sha, "generator_model": config.GENERATOR_MODEL,
        "evaluator_model": config.EVALUATOR_MODEL, "budget": {"generator_calls_max": 20, "evaluator_calls_max": 20},
        "cases": entries,
    })
    print(f"Wrote {len(entries)} specs to {_rel(SPECS_DIR)} and {_rel(MANIFEST)}")


def check() -> dict:
    """Offline validation before any live call. Exits non-zero on any problem."""
    from adgen.cutout import load_approved_cutout
    from adgen.evaluator.profile import load_approved_profile
    from adgen.image_io import load_reference_image

    problems = []
    manifest = _load(MANIFEST)
    cases = manifest["cases"]
    spec_files = sorted(SPECS_DIR.glob("*.json"))
    if len(cases) != 20 or len(spec_files) != 20:
        problems.append(f"expected exactly 20 cases/specs, found {len(cases)}/{len(spec_files)}")
    if len({c["case_id"] for c in cases}) != len(cases) or len({c["required_text"] for c in cases}) != len(cases):
        problems.append("case ids or required_text values are not unique")
    combos = {(c["geography"], c["season"]) for c in cases}
    if len(combos) != 20:
        problems.append("geography/season combinations are not 20 distinct pairs")
    for c in cases:
        spec = load_spec(ROOT / c["spec_file"])
        if (spec.geography, spec.season, spec.required_text) != (c["geography"], c["season"], c["required_text"]):
            problems.append(f"{c['case_id']}: spec file does not match manifest")
        if _rel(spec.product_image) != REFERENCE:
            problems.append(f"{c['case_id']}: unexpected reference {spec.product_image}")
        raw = (ROOT / c["spec_file"]).read_text(encoding="utf-8")
        if ":\\" in raw or raw.count(":/") or "Users" in raw:
            problems.append(f"{c['case_id']}: absolute path in spec")
        if c["status"] == "pending" and (config.OUTPUT_DIR / c["case_id"]).exists():
            problems.append(f"{c['case_id']}: output directory already exists")
    manifest_raw = MANIFEST.read_text(encoding="utf-8")
    if "Users" in manifest_raw or ":\\" in manifest_raw:
        problems.append("absolute local path in manifest")
    key = os.environ.get(config.API_KEY_ENV, "")
    if key and any(key in p.read_text(encoding="utf-8") for p in [MANIFEST, *spec_files]):
        problems.append("API key found in experiment files")
    reference = load_reference_image(ROOT / REFERENCE)
    load_approved_profile(reference.sha256, config.PROFILES_DIR)
    cutout = load_approved_cutout(ROOT / REFERENCE, config.CUTOUTS_DIR)
    free_mb = shutil.disk_usage(config.OUTPUT_DIR.parent).free / 2**20
    if free_mb < 500:
        problems.append(f"only {free_mb:.0f} MB free for outputs")
    result = {"cases": len(cases), "spec_files": len(spec_files), "pending": sum(c["status"] == "pending" for c in cases),
              "free_disk_mb": round(free_mb), "cutout_sha256": cutout.metadata["cutout_sha256"],
              "cutout_view": cutout.metadata["view"], "problems": problems}
    print(json.dumps(result, indent=2))
    if problems:
        sys.exit(1)
    return result


def _summarize(case: dict, res) -> None:
    final = res.final
    case["run_dir"] = _rel(res.run_dir)
    case["status"] = res.status
    case["api_calls"] = dict(final["api_calls"])
    attempt_dir = res.run_dir / "attempt-01"
    meta_path, eval_path = attempt_dir / "metadata.json", attempt_dir / "evaluation.json"
    if meta_path.is_file():
        meta = _load(meta_path)
        case["generation_result"] = {
            "result": "success", "image_file": _rel(attempt_dir / meta["output"]["image_file"]),
            "saved_resolution": meta["output"]["saved_resolution"], "duration_seconds": meta["duration_seconds"],
            "pixel_identity_mismatches": meta["pixel_identity"]["mismatches"],
            "interior_backing_used": meta["composite"]["interior_backing"]["used"],
            "integration_observation": {k: meta["integration_observation"][k] for k in (
                "lighting_brightness_gap", "colour_cast_gap_red_minus_blue", "product_height_share")},
        }
    else:
        case["generation_result"] = {"result": "error", "error": final["error"]}
    if eval_path.is_file():
        ev = _load(eval_path)
        case["evaluation_result"] = {
            "verdict": ev["verdict"], "reasons": ev["reasons"], "error": ev["error"],
            "checks": {k: v["verdict"] for k, v in ev["checks"].items()},
            "duration_seconds": ev["duration_seconds"], "evaluation_file": _rel(eval_path),
        }
    else:
        case["evaluation_result"] = {"verdict": None, "error": "not evaluated", "reasons": []}
    case["final_error"] = final["error"]


def run() -> None:
    from dotenv import load_dotenv
    from google import genai
    from adgen.pipeline.orchestrator import run_pipeline

    check()
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get(config.API_KEY_ENV, "").strip()
    if not api_key:
        sys.exit(f"{config.API_KEY_ENV} is not set.")
    client = genai.Client(api_key=api_key)
    manifest = _load(MANIFEST)
    calls = Counter()
    consecutive_api_errors = 0
    for case in manifest["cases"]:
        if case["status"] != "pending":
            continue  # never re-run a recorded case
        if consecutive_api_errors >= MAX_CONSECUTIVE_API_ERRORS:
            case["status"] = "not_run"
            case["final_error"] = f"aborted after {MAX_CONSECUTIVE_API_ERRORS} consecutive generator errors"
            _write_json(MANIFEST, manifest)
            continue
        if calls["generator"] >= 20 or calls["evaluator"] >= 20:
            raise AssertionError("call budget exhausted")  # unreachable with 20 cases x 1 attempt
        spec = load_spec(ROOT / case["spec_file"])
        case["started_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            res = run_pipeline(spec, client, max_attempts=MAX_ATTEMPTS, secret=api_key, strategy=STRATEGY)
        except Exception as e:  # recorded, never retried
            case["status"] = "ERROR_UNHANDLED"
            case["final_error"] = f"{type(e).__name__}: {e}".replace(api_key, "[REDACTED]")
            _write_json(MANIFEST, manifest)
            print(f"{case['case_id']}: ERROR_UNHANDLED {case['final_error']}")
            continue
        _summarize(case, res)
        calls.update(res.final["api_calls"])
        consecutive_api_errors = consecutive_api_errors + 1 if res.status == status.ERROR_GENERATOR else 0
        _write_json(MANIFEST, manifest)
        print(f"{case['case_id']}: {res.status} {case['evaluation_result'].get('reasons')} calls={dict(calls)}")
    manifest["total_api_calls"] = dict(calls)
    _write_json(MANIFEST, manifest)
    print(f"TOTAL API calls: {dict(calls)}")


RECOMPUTED_LABEL = ("Recomputed offline from the same 20 live experiment artifacts after deterministic composite "
                    "product-preservation rule.")


def recompute() -> None:
    """OFFLINE: re-apply the current rules to each case's STORED raw evaluator response. No API call.

    Writes attempt-01/evaluation.recomputed.json (a new file; evaluation.json is never touched) and
    records the result under each case's "recomputed_evaluation" in the manifest.
    """
    from adgen.evaluator.evaluate import recompute_evaluation

    manifest = _load(MANIFEST)
    for case in manifest["cases"]:
        ev = case.get("evaluation_result") or {}
        if not ev.get("evaluation_file"):
            case["recomputed_evaluation"] = None
            continue
        eval_path = ROOT / ev["evaluation_file"]
        before = hashlib.sha256(eval_path.read_bytes()).hexdigest()
        rec = recompute_evaluation(eval_path.parent)
        rec["run_dir"] = _rel(eval_path.parent)
        out = eval_path.parent / "evaluation.recomputed.json"
        _write_json(out, rec)
        assert hashlib.sha256(eval_path.read_bytes()).hexdigest() == before, "stored evaluation changed"
        case["recomputed_evaluation"] = {
            "label": RECOMPUTED_LABEL, "rules_version": rec["rules_version"], "model_call": False,
            "verdict": rec["verdict"], "reasons": rec["reasons"], "error": rec["error"],
            "checks": {k: v["verdict"] for k, v in rec["checks"].items()},
            "evaluator_disagreements": [
                {"code": d["code"], "check": d["check"], "ai_codes": [r["code"] for r in d["ai_reasons"]]}
                for d in rec["evaluator_disagreements"]],
            "pixel_identity": rec["checks"]["product"].get("pixel_identity"),
            "evaluation_file": _rel(out), "source_evaluation_sha256": before,
        }
        print(f"{case['case_id']}: live {ev['verdict']} {ev['reasons']} -> recomputed {rec['verdict']} "
              f"{rec['reasons']} disagreements={[d['code'] for d in rec['evaluator_disagreements']]}")
    manifest["recomputation"] = {"label": RECOMPUTED_LABEL, "api_calls": {"generator": 0, "evaluator": 0},
                                 "images_changed": False}
    _write_json(MANIFEST, manifest)


def _rate(n: int, d: int):
    return None if d == 0 else round(n / d, 3)


def _stats(cases: list[dict], key: str) -> dict:
    """Aggregate one result view ("evaluation_result" = live, "recomputed_evaluation" = offline rules v2)."""
    total = len(cases)
    res = {c["case_id"]: (c.get(key) or {}) for c in cases}
    evaluated = [c for c in cases if res[c["case_id"]].get("verdict") in ("PASS", "FAIL", "ERROR")]
    eval_ok = [c for c in evaluated if res[c["case_id"]]["verdict"] in ("PASS", "FAIL")]
    passes = [c for c in eval_ok if res[c["case_id"]]["verdict"] == "PASS"]
    fails = [c for c in eval_ok if res[c["case_id"]]["verdict"] == "FAIL"]
    errors = [c for c in cases if c not in passes and c not in fails]

    def check_counts(name):
        cnt = Counter(res[c["case_id"]]["checks"].get(name) for c in eval_ok)
        return {"PASS": cnt.get("PASS", 0), "FAIL": cnt.get("FAIL", 0), "evaluated": len(eval_ok)}

    reasons = Counter(code for c in fails for code in res[c["case_id"]]["reasons"])
    by = {"geography": defaultdict(Counter), "season": defaultdict(Counter)}
    for c in cases:
        verdict = res[c["case_id"]].get("verdict") if c in eval_ok else "ERROR"
        by["geography"][c["geography"]][verdict] += 1
        by["season"][c["season"]][verdict] += 1
    sections = Counter()
    for c in fails:
        for section in {code.split("_")[0] for code in res[c["case_id"]]["reasons"]}:
            sections[section] += 1
    disagreements = [{"case_id": c["case_id"], **d} for c in eval_ok
                     for d in res[c["case_id"]].get("evaluator_disagreements", [])]
    return {
        "evaluation": {"success": len(eval_ok), "error": len(evaluated) - len(eval_ok),
                       "not_evaluated": total - len(evaluated)},
        "overall": {"PASS": len(passes), "FAIL": len(fails), "ERROR": len(errors),
                    "pass_rate_of_all": _rate(len(passes), total), "fail_rate_of_all": _rate(len(fails), total),
                    "pass_rate_of_evaluated": _rate(len(passes), len(eval_ok))},
        "checks": {name: check_counts(name) for name in ("technical", "product", "context", "text")},
        "failure_reason_counts": dict(reasons.most_common()),
        "failed_cases_by_section": dict(sections),
        "evaluator_disagreements": {"count": len(disagreements), "cases": disagreements},
        "per_geography": {k: dict(v) for k, v in by["geography"].items()},
        "per_season": {k: dict(v) for k, v in by["season"].items()},
        "pass_cases": [c["case_id"] for c in passes],
        "fail_cases": [{"case_id": c["case_id"], "reasons": res[c["case_id"]]["reasons"]} for c in fails],
        "error_cases": [{"case_id": c["case_id"], "status": c["status"], "error": c.get("final_error")} for c in errors],
    }


def report() -> None:
    manifest = _load(MANIFEST)
    cases = manifest["cases"]
    total = len(cases)
    gen_ok = [c for c in cases if (c.get("generation_result") or {}).get("result") == "success"]
    gen_d = [c["generation_result"]["duration_seconds"] for c in gen_ok]
    ev_d = [c["evaluation_result"]["duration_seconds"] for c in cases
            if (c.get("evaluation_result") or {}).get("duration_seconds") is not None]
    calls = Counter()
    for c in cases:
        calls.update(c.get("api_calls") or {})
    # Audit: branding transcriptions of the (pixel-identical) product and pixel identity per case.
    insole_reads, product_fail_audit = Counter(), []
    for c in cases:
        ev_file = (c.get("evaluation_result") or {}).get("evaluation_file")
        if not ev_file:
            continue
        ev = _load(ROOT / ev_file)
        branding = {b["id"]: b for b in json.loads(ev["raw_response"])["product"]["branding"]}
        insole = branding.get("insole_text", {})
        insole_reads[f"{insole.get('observed_text')} -> {insole.get('status')}"] += 1
        if c["evaluation_result"]["checks"].get("product") == "FAIL":
            product_fail_audit.append({
                "case_id": c["case_id"],
                "pixel_identity_mismatches": c["generation_result"]["pixel_identity_mismatches"],
                "product_reasons": list(ev["checks"]["product"]["reasons"]),
            })
    data = {
        "experiment": manifest["experiment"], "strategy": manifest["strategy"], "max_attempts": manifest["max_attempts"],
        "total_outputs": total,
        "generation": {"success": len(gen_ok), "error": total - len(gen_ok)},
        "api_calls_live_experiment": {"generator": calls.get("generator", 0), "evaluator": calls.get("evaluator", 0)},
        "avg_generation_seconds": round(sum(gen_d) / len(gen_d), 3) if gen_d else None,
        "avg_evaluation_seconds": round(sum(ev_d) / len(ev_d), 3) if ev_d else None,
        "pixel_identity_mismatches_total": sum(c["generation_result"]["pixel_identity_mismatches"] for c in gen_ok),
        "insole_branding_transcriptions": dict(insole_reads.most_common()),
        "original_live_results": {
            "label": "Original live results (evaluator rules v1, as recorded during the live experiment).",
            **_stats(cases, "evaluation_result"),
            "product_fail_audit": product_fail_audit,
        },
    }
    if all(c.get("recomputed_evaluation") for c in cases):
        data["recomputed_offline_results"] = {
            "label": RECOMPUTED_LABEL, "rules_version": cases[0]["recomputed_evaluation"]["rules_version"],
            "api_calls": {"generator": 0, "evaluator": 0}, "images_changed": False,
            **_stats(cases, "recomputed_evaluation"),
        }
    _write_json(REPORT_JSON, data)
    REPORT_MD.write_text(_markdown(data, cases), encoding="utf-8")
    print(json.dumps({k: v for k, v in data.items() if k not in ("original_live_results",)}, indent=2,
                     ensure_ascii=False)[:6000])


def _view_md(v: dict, heading: str) -> list[str]:
    o = v["overall"]
    lines = [f"## {heading}", "", f"*{v['label']}*", "",
             "| Measure | Value |", "|---|---|",
             f"| Evaluation success / error / not evaluated | {v['evaluation']['success']} / "
             f"{v['evaluation']['error']} / {v['evaluation']['not_evaluated']} |",
             f"| Overall PASS | {o['PASS']} ({o['pass_rate_of_all']}) |",
             f"| Overall FAIL (quality) | {o['FAIL']} ({o['fail_rate_of_all']}) |",
             f"| ERROR (not a quality verdict) | {o['ERROR']} |",
             f"| Evaluator disagreements (recorded, non-gating) | {v['evaluator_disagreements']['count']} |",
             "", "| Check | PASS | FAIL |", "|---|---|---|"]
    lines += [f"| {k} | {c['PASS']} | {c['FAIL']} |" for k, c in v["checks"].items()]
    lines += ["", "| Failure reason code | Count |", "|---|---|"]
    lines += [f"| `{k}` | {n} |" for k, n in v["failure_reason_counts"].items()] or ["| none | 0 |"]
    lines += ["", "| Geography | PASS | FAIL | ERROR |", "|---|---|---|---|"]
    lines += [f"| {k} | {g.get('PASS', 0)} | {g.get('FAIL', 0)} | {g.get('ERROR', 0)} |"
              for k, g in v["per_geography"].items()]
    lines += ["", "| Season | PASS | FAIL | ERROR |", "|---|---|---|---|"]
    lines += [f"| {k} | {g.get('PASS', 0)} | {g.get('FAIL', 0)} | {g.get('ERROR', 0)} |"
              for k, g in v["per_season"].items()]
    return lines + [""]


def _markdown(d: dict, cases: list[dict]) -> str:
    lines = [
        "# Composite strategy: 20-output experiment report", "",
        f"Strategy `{d['strategy']}`, `max_attempts = {d['max_attempts']}` (no retries), one approved reference "
        "product, 20 geography/season/required-text contexts. Generated by `scripts/run_experiment.py report` from "
        "the recorded artifacts; no value is estimated.", "",
        "| Live experiment facts | Value |", "|---|---|",
        f"| Total outputs | {d['total_outputs']} |",
        f"| Generation success / error | {d['generation']['success']} / {d['generation']['error']} |",
        f"| API calls in the live experiment (generator / evaluator) | {d['api_calls_live_experiment']['generator']} / "
        f"{d['api_calls_live_experiment']['evaluator']} |",
        f"| Avg generation / evaluation seconds | {d['avg_generation_seconds']} / {d['avg_evaluation_seconds']} |",
        f"| Pixel-identity mismatches across all composited product pixels | {d['pixel_identity_mismatches_total']} |",
        "",
    ]
    rec = d.get("recomputed_offline_results")
    if rec:
        lines += _view_md(rec, "Recomputed results (rules v2, offline, 0 API calls)")
        lines += ["Evaluator disagreements (AI product reasons overridden by exact pixel identity; the AI "
                  "observations stay stored in each evaluation file):", "",
                  "| Case | AI product codes |", "|---|---|"]
        lines += [f"| {x['case_id']} | {', '.join(x['ai_codes'])} |" for x in rec["evaluator_disagreements"]["cases"]]
        lines += [""]
    lines += _view_md(d["original_live_results"], "Original live results (rules v1)")
    lines += ["### Product-failure audit (original live results)", "",
              "The product region is byte-identical to the approved cutout in every output, so each original "
              "product FAIL reflects the evaluator's observation, not a change to the product.", "",
              "Evaluator transcriptions of the (identical) insole print, with the status it assigned:", "",
              "| Observed text -> status | Count |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in d["insole_branding_transcriptions"].items()]
    lines += ["", "## Cases", "",
              "| Case | Required text | Live verdict | Live reasons | Recomputed verdict | Recomputed reasons | "
              "Disagreement |", "|---|---|---|---|---|---|---|"]
    for c in cases:
        ev = c.get("evaluation_result") or {}
        rc = c.get("recomputed_evaluation") or {}
        dis = ", ".join(x["code"] for x in rc.get("evaluator_disagreements", [])) or "-"
        lines.append(f"| {c['case_id']} | {c['required_text']} | {ev.get('verdict', '-')} | "
                     f"{', '.join(ev.get('reasons') or []) or '-'} | {rc.get('verdict', '-')} | "
                     f"{', '.join(rc.get('reasons') or []) or '-'} | {dis} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    commands = {"build": build, "check": check, "run": run, "recompute": recompute, "report": report}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
