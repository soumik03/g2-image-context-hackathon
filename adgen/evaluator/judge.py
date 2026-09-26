"""The evaluator's only network code: request building, the Flash-Lite call, JSON parsing.

Request fields are limited to ones verified by the SDK and live usage so far:
model, input, response_format, store. No seed, no delivery.
"""

import json

from google.genai import errors as genai_errors

from adgen import config
from adgen.errors import redact
from adgen.evaluator import EvaluationError
from adgen.evaluator.prompts import PROFILE_DRAFT_PROMPT, build_evaluator_prompt
from adgen.evaluator.schemas import PROFILE_DRAFT_SCHEMA, build_response_schema
from adgen.image_io import ReferenceImage


def _json_format(schema: dict) -> dict:
    return {"type": "text", "mime_type": "application/json", "schema": schema}


def build_evaluation_request(
    reference: ReferenceImage, generated: ReferenceImage, profile: dict, geography: str, season: str
) -> dict:
    return {
        "model": config.EVALUATOR_MODEL,
        "input": [
            {"type": "text", "text": build_evaluator_prompt(profile, geography, season)},
            {"type": "text", "text": "REFERENCE IMAGE:"},
            reference.to_input_part(),
            {"type": "text", "text": "GENERATED ADVERTISEMENT:"},
            generated.to_input_part(),
        ],
        "response_format": _json_format(build_response_schema(profile)),
        "store": False,
    }


def build_profile_draft_request(reference: ReferenceImage) -> dict:
    return {
        "model": config.EVALUATOR_MODEL,
        "input": [{"type": "text", "text": PROFILE_DRAFT_PROMPT}, reference.to_input_part()],
        "response_format": _json_format(PROFILE_DRAFT_SCHEMA),
        "store": False,
    }


def request_summary(request: dict) -> dict:
    """Auditable copy of a request with base64 image data replaced by its length."""
    parts = []
    for part in request["input"]:
        if part.get("type") == "image":
            parts.append({"type": "image", "mime_type": part["mime_type"], "base64_chars": len(part["data"])})
        else:
            parts.append(part)
    return {**request, "input": parts}


def call_model(client, request: dict, secret: str | None) -> str:
    """Call the model and return its raw text output."""
    try:
        interaction = client.interactions.create(**request)
    except genai_errors.APIError as e:
        raise EvaluationError(
            "EVAL_API_ERROR", redact(f"Gemini API error {e.code} {e.status}: {e.message}", secret)
        ) from None
    except Exception as e:  # transport errors, including SDK errors not wrapped as APIError
        raise EvaluationError(
            "EVAL_API_ERROR", redact(f"Gemini request failed: {type(e).__name__}: {e}", secret)
        ) from None

    status = str(getattr(interaction, "status", None))
    if status != "completed":
        raise EvaluationError("EVAL_API_ERROR", f"Evaluator interaction not completed (status={status}).")
    return redact(getattr(interaction, "output_text", None) or "", secret)


def parse_json(raw_text: str):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise EvaluationError("EVAL_MALFORMED_RESPONSE", f"Evaluator output is not valid JSON: {e}") from None
