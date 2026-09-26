"""Command line: bounded regeneration for one spec.

Usage:
    python -m adgen.pipeline.cli specs/example.json [--max-attempts N]
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from adgen import config
from adgen import pipeline as status
from adgen.errors import GenerationError, redact
from adgen.spec import load_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate, evaluate and (boundedly) regenerate one ad.")
    parser.add_argument("spec", help="Path to a generation spec JSON file")
    parser.add_argument("--max-attempts", type=int, default=config.MAX_ATTEMPTS,
                        help=f"Maximum attempts (default {config.MAX_ATTEMPTS})")
    parser.add_argument("--strategy", choices=("redraw", "composite"), default="redraw",
                        help="redraw = baseline (Gemini draws the whole ad); composite = exact-pixel product "
                             "cutout composited into a Gemini-generated scene (needs an approved cutout)")
    args = parser.parse_args(argv)
    if args.max_attempts < 1:
        parser.error("--max-attempts must be >= 1")

    try:
        spec = load_spec(args.spec)
    except GenerationError as e:
        print(f"{status.ERROR_PREFLIGHT}: {e}", file=sys.stderr)
        return 1
    load_dotenv(config.PROJECT_ROOT / ".env")
    api_key = os.environ.get(config.API_KEY_ENV, "").strip()
    if not api_key:
        print(f"{status.ERROR_PREFLIGHT}: {config.API_KEY_ENV} is not set. Add it to .env.", file=sys.stderr)
        return 1

    from google import genai
    from adgen.pipeline.orchestrator import run_pipeline

    try:
        result = run_pipeline(spec, genai.Client(api_key=api_key), max_attempts=args.max_attempts,
                              secret=api_key, strategy=args.strategy)
    except OSError as e:  # last resort: even the run records could not be written
        message = redact(f"{type(e).__name__}: {e}", api_key)
        print(f"{status.ERROR_INTERNAL}: filesystem failure, run records may be incomplete: {message}",
              file=sys.stderr)
        return 1
    final = result.final
    print(f"STATUS: {result.status}  (accepted: {final['accepted_attempt']})")
    for a in final["attempts"]:
        print(f"  {a['dir']}: {a['verdict']} {a['reasons']}")
    print(f"API calls: {final['api_calls']}")
    if final["error"]:
        print(f"  error: {final['error']}")
    print(f"Written: {result.run_dir / 'final.json'}")
    return 0 if result.status == status.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
