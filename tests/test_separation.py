"""Generation and evaluation must stay separate: the generator never imports the evaluator."""

import subprocess
import sys
from pathlib import Path

from adgen import config

GENERATOR_MODULES = ["config", "errors", "spec", "prompt", "image_io", "generator", "cli"]


def test_generator_import_does_not_load_evaluator():
    code = (
        "import sys, adgen.generator, adgen.cli; "
        "print(sorted(m for m in sys.modules if m.startswith(('adgen.evaluator', 'adgen.pipeline'))))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=config.PROJECT_ROOT, check=True).stdout.strip()
    assert out == "[]"


def test_generator_sources_do_not_reference_evaluator_or_profiles():
    for name in GENERATOR_MODULES:
        source = (Path(config.PROJECT_ROOT) / "adgen" / f"{name}.py").read_text(encoding="utf-8")
        assert "from adgen.evaluator" not in source and "import adgen.evaluator" not in source, name
        assert "adgen.pipeline" not in source, name
        if name != "config":  # config only defines the evaluator settings
            assert "PROFILES_DIR" not in source and "EVALUATOR_MODEL" not in source, name
