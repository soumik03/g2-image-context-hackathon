"""Command line for the evaluator.

Usage:
    python -m adgen.evaluator.cli draft-profile inputs/products/sneaker.jpg [--name sneaker]
    python -m adgen.evaluator.cli evaluate outputs/<id>/<run> [--overwrite]
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from adgen import config
from adgen.errors import ConfigError, GenerationError, redact
from adgen.evaluator import EvaluationError


def _client():
    load_dotenv(config.PROJECT_ROOT / ".env")
    api_key = os.environ.get(config.API_KEY_ENV, "").strip()
    if not api_key:
        raise ConfigError(f"{config.API_KEY_ENV} is not set. Add it to .env (see .env.example).")
    from google import genai

    return genai.Client(api_key=api_key), api_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluator for generated ads.")
    sub = parser.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("draft-profile", help="One-time model draft of a reference profile (needs human review)")
    draft.add_argument("image", help="Reference product image")
    draft.add_argument("--name", help="Profile name (default: image file stem)")
    ev = sub.add_parser("evaluate", help="Evaluate one generation run directory")
    ev.add_argument("run_dir")
    ev.add_argument("--overwrite", action="store_true", help="Replace an existing evaluation.json")
    args = parser.parse_args(argv)

    secret = None
    try:
        from adgen.evaluator.evaluate import evaluate_run
        from adgen.evaluator.profile import create_profile_draft

        if args.command == "draft-profile":
            image = Path(args.image)
            if not image.is_file():
                raise ConfigError(f"Reference image not found: {image}")
            client, secret = _client()
            path = create_profile_draft(image, client, args.name or image.stem, secret=secret)
            print(f"DRAFT written: {path}")
            print("It is NOT trusted: review it, then save an approved copy with human_verified=true.")
            return 0

        client, secret = _client()
        record = evaluate_run(Path(args.run_dir), client, secret=secret, overwrite=args.overwrite)
        print(f"VERDICT: {record['verdict']}")
        for code in record["reasons"]:
            print(f"  - {code}")
        if record["error"]:
            print(f"  error: {record['error']}")
        print(f"Written: {Path(args.run_dir) / 'evaluation.json'}")
        return 0 if record["verdict"] == "PASS" else 1
    except (GenerationError, EvaluationError) as e:
        print(f"ERROR ({getattr(e, 'code', type(e).__name__)}): {redact(str(e), secret)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
