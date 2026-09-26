"""Single source of configuration for the generation pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Approved generator model (see CLAUDE.md). Verified by scripts/check_api.py.
GENERATOR_MODEL = "gemini-3.1-flash-image"

# Requested output format.
IMAGE_SIZE = "1K"
ASPECT_RATIO = "1:1"  # global setting, deliberately not a spec input
RESPONSE_MODALITIES = ["image", "text"]  # text lets the model explain a refusal

# Official constraint: long edge <= 1024 px (enforced locally after generation).
MAX_LONG_EDGE = 1024

# Long required text is allowed; above this length we only record a warning.
LONG_TEXT_WARNING_CHARS = 80

API_KEY_ENV = "GEMINI_API_KEY"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Regeneration pipeline (ENGINEERING DECISIONS, approved 2026-09-26).
# Worst case per spec: MAX_ATTEMPTS generator calls + MAX_ATTEMPTS evaluator calls.
MAX_ATTEMPTS = 3
MAX_EVIDENCE_CHARS = 200  # cap per evidence quote in a correction section

# Composite strategy: human-approved exact-pixel product cutouts derived from the reference image.
CUTOUTS_DIR = PROJECT_ROOT / "cutouts"
MASKS_DIR = PROJECT_ROOT / "inputs" / "masks"

# Evaluator (used only by adgen.evaluator; the generator never reads these).
EVALUATOR_MODEL = "gemini-3.1-flash-lite"
PROFILES_DIR = PROJECT_ROOT / "profiles"
