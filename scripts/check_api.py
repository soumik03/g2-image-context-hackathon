"""Read-only check that the configured Gemini models are accessible.

Retrieves model metadata only (models.get). Makes no generation request.
Usage: python scripts/check_api.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors

# Approved model IDs (see CLAUDE.md). Never substituted automatically.
GENERATOR_MODEL = "gemini-3.1-flash-image"
EVALUATOR_MODEL = "gemini-3.1-flash-lite"

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def redact(text: str, secret: str) -> str:
    """Remove the key from any text before printing, as a safety net."""
    return text.replace(secret, "[REDACTED]") if secret else text


def check_model(client: genai.Client, model_id: str, api_key: str) -> bool:
    try:
        model = client.models.get(model=model_id)
    except errors.APIError as e:
        print(f"[FAIL] {model_id}: HTTP {e.code} {e.status} - {redact(str(e.message), api_key)}")
        return False
    except Exception as e:  # network errors etc.
        print(f"[FAIL] {model_id}: {type(e).__name__} - {redact(str(e), api_key)}")
        return False
    actions = ", ".join(model.supported_actions or []) or "n/a"
    print(f"[OK]   {model_id}: name={model.name}, supported_actions={actions}")
    return True


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print(f"ERROR: GEMINI_API_KEY is not set. Add it to {PROJECT_ROOT / '.env'} (see .env.example).")
        print("RESULT: FAILURE")
        return 1

    client = genai.Client(api_key=api_key)
    results = [check_model(client, m, api_key) for m in (GENERATOR_MODEL, EVALUATOR_MODEL)]

    if all(results):
        print("RESULT: SUCCESS")
        return 0
    print("One or more configured model IDs are not accessible. No fallback model was substituted.")
    print("RESULT: FAILURE")
    return 1


if __name__ == "__main__":
    sys.exit(main())
