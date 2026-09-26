"""Shared fixtures for evaluator tests. Nothing here touches the network."""

import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

FIXTURES = Path(__file__).parent / "fixtures"
REQUIRED_TEXT = "Step Into Winter"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def jpeg_bytes(size, color="blue"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


class FakeInteractions:
    def __init__(self, output_text=None, error=None, status="completed"):
        self.output_text, self.error, self.status = output_text, error, status
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(id="", status=self.status, output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text=None, error=None, status="completed"):
        self.interactions = FakeInteractions(output_text, error, status)


@pytest.fixture
def profile():
    return _load("sneaker_profile_test.json")


@pytest.fixture
def smoke():
    return _load("smoke_test_observations.json")


@pytest.fixture
def good_response(profile):
    """A known-good evaluator response for the test profile."""
    return {
        "schema_version": 1,
        "text": {"items": [
            {"text": REQUIRED_TEXT, "role": "headline_or_ad_text", "location": "top right"},
            {"text": "COMET", "role": "product_branding", "location": "tongue label"},
        ]},
        "product": {
            "attributes": [
                {"id": a["id"], "evidence": f"{a['id']} matches the reference", "status": "preserved"}
                for a in profile["attributes"]
            ],
            "branding": [
                {"id": "tongue_label", "observed_text": "COMET", "evidence": "clear tongue label",
                 "status": "legible_correct"},
                {"id": "insole_logo", "observed_text": "", "evidence": "insole hidden by angle",
                 "status": "not_visible"},
            ],
            "genuinely_added_marks_or_logos": [],
            "same_product_evidence": "same patent upper, four-pointed side emblem and blue cupsole",
            "same_product": "yes",
        },
        "context": {
            "geography": {"cues": ["Japanese-script shop signage", "narrow Tokyo side street with overhead wires"],
                          "contradicting_cues": [], "rating": "strong"},
            "season": {"cues": ["falling snow", "snow on rooftops"], "conflicting_cues": [], "rating": "strong"},
        },
    }


@pytest.fixture
def run_setup(tmp_path, profile):
    """A generation run dir + reference image + profiles dir holding an approved profile for it."""
    ref_bytes = jpeg_bytes((64, 48), "skyblue")
    ref_path = tmp_path / "sneaker.jpg"
    ref_path.write_bytes(ref_bytes)
    sha = hashlib.sha256(ref_bytes).hexdigest()

    run_dir = tmp_path / "outputs" / "sneaker-tokyo-winter" / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / "ad.jpg").write_bytes(jpeg_bytes((1024, 1024), "white"))
    metadata = {
        "spec_id": "sneaker-tokyo-winter",
        "inputs": {"product_image": str(ref_path), "product_image_sha256": sha,
                   "geography": "Tokyo, Japan", "season": "Winter", "required_text": REQUIRED_TEXT},
        "output": {"image_file": "ad.jpg"},
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    approved = copy.deepcopy(profile)
    approved["reference_image_sha256"] = sha
    (profiles_dir / "sneaker.json").write_text(json.dumps(approved), encoding="utf-8")
    return SimpleNamespace(run_dir=run_dir, profiles_dir=profiles_dir, profile=approved,
                           ref_path=ref_path, metadata=metadata)
