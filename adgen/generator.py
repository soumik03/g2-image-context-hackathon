"""Single-shot ad generation with Gemini (Interactions API).

The only module that talks to the network. The client is passed in, so tests
can substitute a fake. No evaluation and no retries happen here.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import google.genai
from google.genai import errors as genai_errors

from adgen import config
from adgen.errors import GenerationAPIError, NoImageReturnedError, redact
from adgen.image_io import (
    ReferenceImage,
    decode_base64_image,
    enforce_long_edge,
    load_reference_image,
    save_run,
)
from adgen.prompt import build_prompt
from adgen.spec import GenerationSpec, spec_warnings


@dataclass(frozen=True)
class GenerationResult:
    run_dir: Path
    image_path: Path
    metadata_path: Path
    metadata: dict


def build_request(reference: ReferenceImage, prompt: str) -> dict:
    """Keyword arguments for client.interactions.create()."""
    return {
        "model": config.GENERATOR_MODEL,
        "input": [reference.to_input_part(), {"type": "text", "text": prompt}],
        "response_modalities": list(config.RESPONSE_MODALITIES),
        "response_format": {
            "type": "image",
            "image_size": config.IMAGE_SIZE,
            "aspect_ratio": config.ASPECT_RATIO,
            # No "delivery" field: the live API rejects it (400 "Image delivery
            # mode is not supported."); images are returned inline by default.
        },
        "store": False,
    }


def _call_gemini(client, request: dict, secret: str | None):
    try:
        return client.interactions.create(**request)
    except genai_errors.APIError as e:
        message = redact(f"Gemini API error {e.code} {e.status}: {e.message}", secret)
        raise GenerationAPIError(message, code=e.code, status=e.status) from None
    except Exception as e:  # network failures and other transport errors
        message = redact(f"Gemini request failed: {type(e).__name__}: {e}", secret)
        raise GenerationAPIError(message) from None


def generate(
    spec: GenerationSpec,
    client,
    output_root: Path = config.OUTPUT_DIR,
    secret: str | None = None,
    *,
    target_dir: Path | None = None,
    correction: str | None = None,
) -> GenerationResult:
    """Generate one ad for the spec and save image + metadata.

    `secret` (the API key) is used only to redact error messages.
    Optional, used by the regeneration pipeline (defaults keep single-shot behavior):
      target_dir  exact output directory (must not exist) instead of output_root/<id>/<timestamp>
      correction  section appended after the unchanged base prompt
    """
    reference = load_reference_image(spec.product_image)  # validated before the API call
    prompt = build_prompt(spec)
    if correction:
        prompt = f"{prompt}\n\n{correction}"
    request = build_request(reference, prompt)

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    interaction = _call_gemini(client, request, secret)
    duration = time.perf_counter() - t0

    status = str(getattr(interaction, "status", None))
    model_text = getattr(interaction, "output_text", None) or ""
    output_image = getattr(interaction, "output_image", None)
    if status != "completed" or output_image is None or not getattr(output_image, "data", None):
        detail = f" Model text: {model_text!r}" if model_text else ""
        raise NoImageReturnedError(
            redact(f"Gemini returned no image (status={status}).{detail}", secret)
        )

    image = enforce_long_edge(decode_base64_image(output_image.data), config.MAX_LONG_EDGE)

    metadata = {
        "schema_version": 1,
        "spec_id": spec.id,
        "inputs": {
            "product_image": str(spec.product_image),
            "product_image_sha256": reference.sha256,
            "product_image_mime_type": reference.mime_type,
            "geography": spec.geography,
            "season": spec.season,
            "required_text": spec.required_text,
        },
        "prompt": prompt,
        "model": config.GENERATOR_MODEL,
        "request": {
            "api": "interactions.create",
            "image_size": config.IMAGE_SIZE,
            "aspect_ratio": config.ASPECT_RATIO,
            "response_modalities": list(config.RESPONSE_MODALITIES),
            "store": False,
        },
        "response": {
            "interaction_id": getattr(interaction, "id", None),
            "status": status,
            "mime_type": getattr(output_image, "mime_type", None),
            "model_text": redact(model_text, secret),
        },
        "output": {
            "image_file": "ad" + image.extension,
            "format": image.format,
            "raw_resolution": list(image.raw_size),
            "saved_resolution": list(image.saved_size),
            "downscaled": image.downscaled,
            "max_long_edge": config.MAX_LONG_EDGE,
        },
        "warnings": spec_warnings(spec),
        "timestamp_utc": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "duration_seconds": round(duration, 3),
        "sdk_version": google.genai.__version__,
    }

    if target_dir is not None:
        run_dir = Path(target_dir)
    else:
        run_dir = Path(output_root) / spec.id / started.strftime("%Y%m%dT%H%M%S_%fZ")
    image_path, metadata_path = save_run(run_dir, image, metadata)
    return GenerationResult(run_dir, image_path, metadata_path, metadata)
