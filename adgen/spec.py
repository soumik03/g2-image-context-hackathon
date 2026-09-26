"""Generation spec: the four official pipeline inputs plus an id."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from adgen import config
from adgen.errors import SpecError

FIELDS = ("id", "product_image", "geography", "season", "required_text")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")  # safe to use as a directory name


@dataclass(frozen=True)
class GenerationSpec:
    id: str
    product_image: Path
    geography: str
    season: str
    required_text: str


def spec_from_dict(data: dict, base_dir: Path = config.PROJECT_ROOT) -> GenerationSpec:
    """Validate a dict and build a spec. Relative image paths resolve against base_dir."""
    if not isinstance(data, dict):
        raise SpecError("Spec must be a JSON object.")

    missing = [f for f in FIELDS if f not in data]
    unknown = sorted(set(data) - set(FIELDS))
    if missing:
        raise SpecError(f"Spec is missing required field(s): {', '.join(missing)}")
    if unknown:
        raise SpecError(f"Spec has unknown field(s): {', '.join(unknown)}")

    for field in FIELDS:
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            raise SpecError(f"Spec field '{field}' must be a non-empty string.")

    if not _ID_PATTERN.match(data["id"]):
        raise SpecError("Spec field 'id' may only contain letters, digits, '-' and '_'.")

    image_path = Path(data["product_image"])
    if not image_path.is_absolute():
        image_path = base_dir / image_path
    if not image_path.is_file():
        raise SpecError(f"Reference product image not found: {image_path}")

    # Text values are kept exactly as given; required_text must be rendered verbatim.
    return GenerationSpec(
        id=data["id"],
        product_image=image_path,
        geography=data["geography"],
        season=data["season"],
        required_text=data["required_text"],
    )


def load_spec(path: Path, base_dir: Path = config.PROJECT_ROOT) -> GenerationSpec:
    """Load and validate a spec from a JSON file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpecError(f"Spec file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise SpecError(f"Spec file is not valid JSON: {path} ({e})") from None
    return spec_from_dict(data, base_dir)


def spec_warnings(spec: GenerationSpec) -> list[str]:
    """Non-fatal observations about a spec. Never blocks generation."""
    warnings = []
    if len(spec.required_text) > config.LONG_TEXT_WARNING_CHARS:
        warnings.append(
            f"required_text is {len(spec.required_text)} characters; "
            "long text is more likely to be rendered imperfectly."
        )
    return warnings
