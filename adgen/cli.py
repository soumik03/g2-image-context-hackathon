"""Command line: generate one ad from a spec file.

Usage:
    python -m adgen.cli specs/example.json
    python -m adgen.cli specs/example.json --dry-run   # validate only, no API call
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from adgen import config
from adgen.errors import ConfigError, GenerationError
from adgen.image_io import load_reference_image
from adgen.prompt import build_prompt
from adgen.spec import load_spec, spec_warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate one display ad from a spec file.")
    parser.add_argument("spec", help="Path to a generation spec JSON file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate spec and build the prompt without calling Gemini"
    )
    args = parser.parse_args(argv)

    try:
        # Offline validation first: spec fields and reference image.
        spec = load_spec(args.spec)
        reference = load_reference_image(spec.product_image)
        for warning in spec_warnings(spec):
            print(f"WARNING: {warning}")

        if args.dry_run:
            print(f"Spec OK: {spec.id} (reference {reference.mime_type}, {reference.size[0]}x{reference.size[1]})")
            print(f"Model: {config.GENERATOR_MODEL}, image_size={config.IMAGE_SIZE}, aspect_ratio={config.ASPECT_RATIO}")
            print("Prompt:\n" + build_prompt(spec))
            print("DRY RUN: no API call made.")
            return 0

        load_dotenv(config.PROJECT_ROOT / ".env")
        api_key = os.environ.get(config.API_KEY_ENV, "").strip()
        if not api_key:
            raise ConfigError(f"{config.API_KEY_ENV} is not set. Add it to .env (see .env.example).")

        # Imported here so --dry-run and validation errors never need the SDK client.
        from google import genai
        from adgen.generator import generate

        client = genai.Client(api_key=api_key)
        result = generate(spec, client, secret=api_key)
    except GenerationError as e:
        print(f"ERROR ({type(e).__name__}): {e}", file=sys.stderr)
        return 1

    w, h = result.metadata["output"]["saved_resolution"]
    print(f"OK {spec.id} -> {result.image_path} ({w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
