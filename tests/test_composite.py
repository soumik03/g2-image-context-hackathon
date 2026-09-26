"""Composite strategy: exact product pixels + Gemini scene. Fake clients only; no network."""

import base64
import copy
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from adgen import composite, config
from adgen import pipeline as st
from adgen.composite import (build_scene_prompt, build_scene_request, compose, generate_composite, placement,
                             verify_pixel_identity, CompositeInvariantError)
from adgen.cutout import approve, build_draft, load_approved_cutout
from adgen.errors import OutputProcessingError
from adgen.pipeline.orchestrator import run_pipeline
from adgen.spec import spec_from_dict
from conftest import jpeg_bytes
from test_pipeline import ScriptedClient

REAL_PROFILE = json.loads((config.PROJECT_ROOT / "profiles" / "sneaker.json").read_text(encoding="utf-8"))


@pytest.fixture
def comp(tmp_path, profile, good_response):
    ref = Image.new("RGB", (700, 900))
    ref.putdata([((x * 3) % 256, (y * 5) % 256, (x + y) % 256) for y in range(900) for x in range(700)])
    ref_path = tmp_path / "product.png"
    ref.save(ref_path)  # PNG reference keeps the synthetic pattern exact
    mask = Image.new("L", ref.size, 0)
    ImageDraw.Draw(mask).ellipse((100, 100, 599, 699), fill=255)
    mask_path = tmp_path / "mask.png"
    mask.save(mask_path)
    cdir = tmp_path / "cutouts"
    build_draft(ref_path, mask_path, "product", cutouts_dir=cdir)
    approve("product", "Test Reviewer", cutouts_dir=cdir)
    cut = load_approved_cutout(ref_path, cdir)

    pdir = tmp_path / "profiles"
    pdir.mkdir()
    prof = copy.deepcopy(profile)
    prof["reference_image_sha256"] = hashlib.sha256(ref_path.read_bytes()).hexdigest()
    (pdir / "p.json").write_text(json.dumps(prof), encoding="utf-8")
    spec = spec_from_dict({"id": "sneaker-tokyo-winter", "product_image": str(ref_path), "geography": "Tokyo, Japan",
                           "season": "Winter", "required_text": "Step Into Winter"})

    def variant(mutate=None):
        r = copy.deepcopy(good_response)
        if mutate:
            mutate(r)
        return json.dumps(r)

    def run(generations, evaluations, **kw):
        client = ScriptedClient(generations, evaluations)
        res = run_pipeline(spec, client, output_root=tmp_path / "outputs", profiles_dir=pdir,
                           cutouts_dir=cdir, strategy="composite", **kw)
        return res, client

    return SimpleNamespace(spec=spec, cutout=cut, cdir=cdir, pdir=pdir, variant=variant, run=run, tmp=tmp_path)


SCENE = jpeg_bytes((1024, 1024), "lightsteelblue")


# ---------------- scene prompt ----------------

def test_scene_prompt_has_spec_values_and_no_product_details(comp):
    prompt = build_scene_prompt(comp.spec, "overhead")
    for value in ("Tokyo, Japan", "Winter", '"Step Into Winter"', "top-down flat-lay", "empty central area"):
        assert value in prompt
    lowered = prompt.lower()
    for forbidden in ("comet", "emblem", "sneaker", "critical", "human_verified", "patent", "yellow"):
        assert forbidden not in lowered, forbidden
    for attr in REAL_PROFILE["attributes"]:
        assert attr["description"].lower() not in lowered


def test_scene_request_is_text_only(comp):
    request = build_scene_request(build_scene_prompt(comp.spec, "overhead"))
    assert [p["type"] for p in request["input"]] == ["text"]
    assert request["model"] == config.GENERATOR_MODEL
    assert set(request) == {"model", "input", "response_modalities", "response_format", "store"}
    assert "delivery" not in request["response_format"]


# ---------------- compositor ----------------

def test_compose_preserves_exact_product_pixels(comp):
    scene = Image.open(io.BytesIO(SCENE))
    ad, info = compose(scene, comp.cutout.image)
    assert ad.size == (1024, 1024) and info["product_scale"] == 1.0 and info["final_resize_factor"] == 1.0
    x, y = info["placement"]["x"], info["placement"]["y"]
    assert verify_pixel_identity(ad, comp.cutout.image, (x, y)) == comp.cutout.metadata["opaque_pixels"]


def test_compose_is_deterministic(comp):
    scene = Image.open(io.BytesIO(SCENE))
    a, ia = compose(scene, comp.cutout.image)
    b, ib = compose(scene, comp.cutout.image)
    assert a.tobytes() == b.tobytes() and ia == ib
    assert ia["shadow"] == composite.SHADOW


def test_placement_is_centred_below_headline_band(comp):
    w, h = comp.cutout.image.size
    x, y = placement((w, h))
    assert x == (1024 - w) // 2
    assert y >= round(1024 * composite.HEADLINE_BAND) and y + h <= 1024


def test_no_resampling_of_product(comp):
    with pytest.raises(OutputProcessingError, match="resampling the product is not allowed"):
        placement((1100, 600))
    with pytest.raises(OutputProcessingError, match="upscaling is not allowed"):
        placement((200, 200))


def test_non_square_scene_is_fitted_scene_only(comp):
    scene = Image.open(io.BytesIO(jpeg_bytes((1376, 768), "gray")))
    ad, info = compose(scene, comp.cutout.image)
    assert ad.size == (1024, 1024) and info["scene_resized"] is True and info["product_scale"] == 1.0


def test_pixel_identity_detects_tampering(comp):
    ad, info = compose(Image.open(io.BytesIO(SCENE)), comp.cutout.image)
    x, y = info["placement"]["x"], info["placement"]["y"]
    cx, cy = comp.cutout.image.size[0] // 2, comp.cutout.image.size[1] // 2
    original = ad.getpixel((x + cx, y + cy))
    ad.putpixel((x + cx, y + cy), tuple((c + 1) % 256 for c in original))
    with pytest.raises(CompositeInvariantError):
        verify_pixel_identity(ad, comp.cutout.image, (x, y))


def test_generate_composite_artifacts(comp):
    client = ScriptedClient([SCENE], [])
    res = generate_composite(comp.spec, client, comp.cutout, comp.tmp / "run" / "attempt-01")
    (call,) = client.gen_calls
    assert [p["type"] for p in call["input"]] == ["text"]  # no product image sent
    names = sorted(p.name for p in res.run_dir.iterdir())
    assert names == ["ad.png", "metadata.json", "scene.jpg"]
    meta = res.metadata
    assert meta["strategy"] == "composite" and meta["output"]["image_file"] == "ad.png"
    assert meta["cutout"]["sha256"] == comp.cutout.metadata["cutout_sha256"]
    assert meta["pixel_identity"]["mismatches"] == 0 and meta["pixel_identity"]["verified_in_saved_png"]
    obs = meta["integration_observation"]
    assert obs["gating"] is False and "lighting_brightness_gap" in obs and "product_height_share" in obs
    assert meta["scene_prompt_sent_with_images"] is False
    with Image.open(res.image_path) as saved:
        assert max(saved.size) <= config.MAX_LONG_EDGE
        p = meta["composite"]["placement"]
        verify_pixel_identity(saved, comp.cutout.image, (p["x"], p["y"]))


def test_cutout_from_other_reference_rejected_before_call(comp, tmp_path):
    other = tmp_path / "other.png"
    Image.new("RGB", (700, 900), "red").save(other)
    spec = spec_from_dict({"id": "x", "product_image": str(other), "geography": "g", "season": "s",
                           "required_text": "t"})
    client = ScriptedClient([SCENE], [])
    with pytest.raises(OutputProcessingError, match="does not belong"):
        generate_composite(spec, client, comp.cutout, tmp_path / "a")
    assert client.gen_calls == []


# ---------------- pipeline in composite mode ----------------

def weak_geo(r):
    r["context"]["geography"].update(rating="weak", cues=["generic street"])


def emblem_altered(r):
    r["product"]["attributes"][3].update(status="altered", evidence="five-pointed star")


def added_logo(r):  # the one product code pixel identity cannot rule out (something added AROUND the product)
    r["product"]["genuinely_added_marks_or_logos"] = [
        {"description": "red swoosh-like logo", "location": "next to the heel", "possible_reference_counterpart_id": ""}]


def tongue_case_variant(r):  # the composite20 false positive: capitalization variant of the branding
    r["product"]["branding"][0].update(observed_text="CoMeT", status="legible_different",
                                       evidence="mixed casing instead of COMET")


def test_composite_first_attempt_pass_and_evaluator_runs(comp):
    res, client = comp.run([SCENE], [comp.variant()])
    assert res.status == st.PASS and res.final["strategy"] == "composite"
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 1)
    assert res.final["cutout"]["verified_by"] == "Test Reviewer"
    eval_images = [p for p in client.eval_calls[0]["input"] if p["type"] == "image"]
    assert [p["mime_type"] for p in eval_images] == ["image/png", "image/png"]  # reference + composite ad
    assert (res.run_dir / "attempt-01" / "evaluation.json").is_file()


def test_composite_retry_sends_only_text_context_corrections(comp):
    both = lambda r: (added_logo(r), weak_geo(r))
    res, client = comp.run([SCENE, SCENE], [comp.variant(both), comp.variant()])
    assert res.status == st.PASS and (len(client.gen_calls), len(client.eval_calls)) == (2, 2)
    corr = json.loads((res.run_dir / "attempt-02" / "attempt.json").read_text(encoding="utf-8"))["correction"]
    assert "[CONTEXT]" in corr["text"] and "[PRODUCT]" not in corr["text"]
    assert "PRODUCT_BRANDING_ADDED" in corr["excluded_codes_not_sent"]
    sent = client.gen_calls[1]["input"][0]["text"]
    assert sent.endswith(corr["text"]) and "swoosh" not in sent
    assert "attached reference image" not in corr["text"]  # composite scene request has no attachment
    assert "The approved product reference remains the source of truth for the task." in corr["text"]


def test_composite_product_only_failure_stops_without_retry(comp):
    res, client = comp.run([SCENE, SCENE], [comp.variant(added_logo)])
    assert res.status == st.FAIL_NO_PROGRESS and res.final["stop_reason"] == "no_actionable_correction"
    assert res.final["final_verdict"] == "FAIL"  # product failure is never converted to PASS
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 1)


def test_composite_requires_approved_cutout(comp):
    (comp.cdir / "product.json").unlink()
    res, client = comp.run([SCENE], [comp.variant()])
    assert res.status == st.ERROR_PREFLIGHT and (len(client.gen_calls), len(client.eval_calls)) == (0, 0)


def test_composite_invariant_violation_is_internal_error(comp, monkeypatch):
    def broken(*a, **k):
        raise CompositeInvariantError("simulated mismatch")
    monkeypatch.setattr(composite, "verify_pixel_identity", broken)
    res, client = comp.run([SCENE], [comp.variant()])
    assert res.status == st.ERROR_INTERNAL and len(client.eval_calls) == 0


def test_composite_inputs_unchanged_and_bounded(comp):
    res, client = comp.run([SCENE] * 3, [comp.variant(weak_geo),
                                         comp.variant(lambda r: r["context"]["season"].update(rating="weak")),
                                         comp.variant(weak_geo)])
    assert len(client.gen_calls) <= 3 and len(client.eval_calls) <= 3
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(res.run_dir.glob("attempt-*/attempt.json"))]
    assert len({r["spec_sha256"] for r in records}) == 1 and len({r["base_prompt_sha256"] for r in records}) == 1
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(res.run_dir.glob("attempt-*/metadata.json"))]
    base = build_scene_prompt(comp.spec, "overhead")
    for m in metas:
        assert m["prompt"].startswith(base)
        assert (m["inputs"]["geography"], m["inputs"]["season"], m["inputs"]["required_text"]) == \
               ("Tokyo, Japan", "Winter", "Step Into Winter")


# ---------------- interior cavity backing ----------------

@pytest.fixture
def ring_cutout(tmp_path):
    """Approved cutout with one enclosed cavity (tissue-like hole) and one sub-threshold speck."""
    ref = Image.new("RGB", (700, 900))
    ref.putdata([((x * 7) % 256, (y * 3) % 256, (x * y) % 256) for y in range(900) for x in range(700)])
    ref_path = tmp_path / "ring.png"
    ref.save(ref_path)
    mask = Image.new("L", ref.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((100, 100, 599, 699), fill=255)
    draw.ellipse((250, 250, 449, 449), fill=0)     # enclosed cavity
    draw.rectangle((300, 600, 303, 603), fill=0)   # 16 px speck: below min_cavity_pixels
    mask_path = tmp_path / "ring_mask.png"
    mask.save(mask_path)
    cdir = tmp_path / "ring_cutouts"
    build_draft(ref_path, mask_path, "ring", cutouts_dir=cdir)
    approve("ring", "Test Reviewer", cutouts_dir=cdir)
    return load_approved_cutout(ref_path, cdir)


def _no_backing_compose(scene, cutout):
    """Reference composite without backing (same shadow and paste order)."""
    x, y = placement(cutout.size)
    base = scene.convert("RGB")
    alpha = cutout.getchannel("A")
    sh = Image.new("L", base.size, 0)
    sh.paste(alpha, (x + composite.SHADOW["offset_x"], y + composite.SHADOW["offset_y"]))
    sh = sh.filter(ImageFilter.GaussianBlur(composite.SHADOW["blur_radius"]))
    sh = sh.point(lambda a: round(a * composite.SHADOW["opacity"]))
    out = Image.composite(Image.new("RGB", base.size, (0, 0, 0)), base, sh)
    out.paste(cutout.convert("RGB"), (x, y), alpha)
    return out


def test_cavity_is_opaque_backing_not_scene(ring_cutout):
    scene = Image.new("RGB", (1024, 1024), (200, 150, 90))  # wood-like colour
    ad, info = compose(scene, ring_cutout.image)
    x, y = info["placement"]["x"], info["placement"]["y"]
    c = ad.getpixel((x + 250, y + 250))  # cavity centre (cutout crop starts at the mask bbox 100,100)
    assert c != (200, 150, 90)
    top, bottom = composite.BACKING["colour_top"], composite.BACKING["colour_bottom"]
    assert all(min(t, b) <= v <= max(t, b) for v, t, b in zip(c, top, bottom))
    assert info["interior_backing"]["used"] is True


def test_backing_keeps_opaque_pixels_identical_and_only_touches_cavity(ring_cutout):
    scene = Image.new("RGB", (1024, 1024), (200, 150, 90))
    ad, info = compose(scene, ring_cutout.image)
    x, y = info["placement"]["x"], info["placement"]["y"]
    assert verify_pixel_identity(ad, ring_cutout.image, (x, y)) == ring_cutout.metadata["opaque_pixels"]
    changed = ImageChops.difference(ad, _no_backing_compose(scene, ring_cutout.image)).convert("L")
    changed = changed.point(lambda v: 255 if v else 0)
    cavity = Image.new("L", ad.size, 0)
    cavity.paste(composite.cavity_mask(ring_cutout.image), (x, y))
    assert changed.getbbox() is not None
    assert ImageChops.subtract(changed, cavity).getbbox() is None  # differences only inside the cavity mask
    opaque = Image.new("L", ad.size, 0)
    opaque.paste(ring_cutout.image.getchannel("A").point(lambda a: 255 if a == 255 else 0), (x, y))
    assert ImageChops.multiply(changed, opaque).getbbox() is None  # never visible over product pixels


def test_backing_ignores_outside_and_small_specks(ring_cutout):
    mask = composite.cavity_mask(ring_cutout.image)
    assert mask.getpixel((0, 0)) == 0                      # outside the product is never backed
    assert mask.getpixel((201 + 1, 501 + 1)) == 0           # 16 px speck (cutout coords) stays transparent
    assert mask.getpixel((250, 250)) == 255


def test_backing_is_deterministic_and_recorded(ring_cutout):
    scene = Image.new("RGB", (1376, 768), (90, 90, 90))
    a, ia = compose(scene, ring_cutout.image)
    b, ib = compose(scene, ring_cutout.image)
    assert a.tobytes() == b.tobytes() and ia == ib
    assert max(a.size) <= config.MAX_LONG_EDGE
    rec = ia["interior_backing"]
    assert rec["parameters"] == composite.BACKING and rec["cavity_pixels_including_rim"] > 0
    assert "All preserved opaque product pixels come directly from the reference cutout" in rec["note"]


def test_no_cavity_means_no_backing(comp):
    ad, info = compose(Image.open(io.BytesIO(SCENE)), comp.cutout.image)
    assert info["interior_backing"]["used"] is False
    assert ad.tobytes() == _no_backing_compose(Image.open(io.BytesIO(SCENE)), comp.cutout.image).tobytes()


def test_backing_leaves_cutout_asset_and_lineage_unchanged(ring_cutout):
    before = hashlib.sha256(ring_cutout.path.read_bytes()).hexdigest()
    pixels = ring_cutout.image.tobytes()
    compose(Image.new("RGB", (1024, 1024), "white"), ring_cutout.image)
    assert hashlib.sha256(ring_cutout.path.read_bytes()).hexdigest() == before == ring_cutout.metadata["cutout_sha256"]
    assert ring_cutout.image.tobytes() == pixels


def test_approved_sneaker_cavity_is_the_left_shoe_opening():
    """The real approved cutout has exactly the tissue cavity, inside the reviewer-directed tissue box."""
    cut = Image.open(config.PROJECT_ROOT / "cutouts" / "sneaker.png")
    mask = composite.cavity_mask(cut)
    left, top, right, bottom = mask.getbbox()
    meta = json.loads((config.PROJECT_ROOT / "cutouts" / "sneaker.json").read_text(encoding="utf-8"))
    crop_x, crop_y = meta["crop_box"][:2]  # approved crop origin in the reference
    assert 112 - 3 <= left + crop_x and right + crop_x <= 292 + 3
    assert 728 - 3 <= top + crop_y and bottom + crop_y <= 820 + 3


# ---------------- filesystem finalization (Windows/OneDrive rename failures) ----------------

from adgen import image_io
from adgen.errors import FinalizationError
from adgen.pipeline import cli as pipeline_cli
from adgen.pipeline import orchestrator


def _locked_rename(src, dst):
    raise PermissionError(13, "Access is denied (simulated OneDrive lock)")


def _make_tmp(tmp_path):
    tmp = tmp_path / "attempt-01.tmp"
    tmp.mkdir()
    (tmp / "ad.png").write_bytes(b"\x89PNG fake bytes")
    (tmp / "metadata.json").write_text("{}", encoding="utf-8")
    return tmp


def test_finalize_dir_renames_when_possible(tmp_path):
    tmp = _make_tmp(tmp_path)
    assert image_io.finalize_dir(tmp, tmp_path / "attempt-01") == "rename"
    assert not tmp.exists() and sorted(p.name for p in (tmp_path / "attempt-01").iterdir()) == ["ad.png", "metadata.json"]


def test_finalize_dir_falls_back_to_verified_copy(tmp_path, monkeypatch):
    tmp = _make_tmp(tmp_path)
    originals = {p.name: p.read_bytes() for p in tmp.iterdir()}
    monkeypatch.setattr(image_io, "_rename", _locked_rename)
    assert image_io.finalize_dir(tmp, tmp_path / "attempt-01") == "copy"
    assert {p.name: p.read_bytes() for p in (tmp_path / "attempt-01").iterdir()} == originals


def test_finalize_dir_total_failure_raises_and_preserves_artifacts(tmp_path, monkeypatch):
    tmp = _make_tmp(tmp_path)
    monkeypatch.setattr(image_io, "_rename", _locked_rename)
    def broken_copy(src, dst):
        raise PermissionError(13, "Access is denied")
    monkeypatch.setattr(image_io.shutil, "copyfile", broken_copy)
    with pytest.raises(FinalizationError, match="preserved in attempt-01.tmp"):
        image_io.finalize_dir(tmp, tmp_path / "attempt-01")
    assert sorted(p.name for p in tmp.iterdir()) == ["ad.png", "metadata.json"]  # nothing deleted


def test_composite_pipeline_survives_locked_rename_via_copy(comp, monkeypatch):
    monkeypatch.setattr(image_io, "_rename", _locked_rename)
    res, client = comp.run([SCENE], [comp.variant()])
    assert res.status == st.PASS and (len(client.gen_calls), len(client.eval_calls)) == (1, 1)
    attempt = json.loads((res.run_dir / "attempt-01" / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["finalization"] == "copy"
    with Image.open(res.run_dir / "attempt-01" / "ad.png") as saved:  # copied PNG keeps exact product pixels
        meta = json.loads((res.run_dir / "attempt-01" / "metadata.json").read_text(encoding="utf-8"))
        p = meta["composite"]["placement"]
        verify_pixel_identity(saved, comp.cutout.image, (p["x"], p["y"]))


def test_finalization_failure_is_auditable_internal_error(comp, monkeypatch):
    monkeypatch.setattr(image_io, "_rename", _locked_rename)
    def broken_copy(src, dst):
        raise PermissionError(13, "Access is denied")
    monkeypatch.setattr(image_io.shutil, "copyfile", broken_copy)
    res, client = comp.run([SCENE, SCENE], [comp.variant(), comp.variant()])
    assert res.status == st.ERROR_INTERNAL and res.final["final_verdict"] == "ERROR"
    assert res.final["stop_reason"] == "filesystem_error" and "FinalizationError" in res.final["error"]
    assert (len(client.gen_calls), len(client.eval_calls)) == (1, 0)          # no hidden regeneration
    assert res.final["api_calls"] == {"generator": 1, "evaluator": 0}
    assert (res.run_dir / "final.json").is_file()
    assert (res.run_dir / "attempt-01.tmp" / "ad.png").is_file()               # generated artifact preserved


def test_oserror_during_evaluation_is_internal_error(comp, monkeypatch):
    def locked(*a, **k):
        raise PermissionError(13, "Access is denied: evaluation.json")
    monkeypatch.setattr(orchestrator, "evaluate_run", locked)
    res, client = comp.run([SCENE, SCENE], [])
    assert res.status == st.ERROR_INTERNAL and res.final["stop_reason"] == "filesystem_error"
    assert "upper bound" in res.final["error"] and len(client.gen_calls) == 1


def test_cli_reports_filesystem_failure_without_traceback(monkeypatch, capsys):
    monkeypatch.setenv(config.API_KEY_ENV, "test-key-not-real")
    monkeypatch.setattr("google.genai.Client", lambda api_key: object())
    def boom(*a, **k):
        raise PermissionError(13, "Access is denied: final.json")
    monkeypatch.setattr(orchestrator, "run_pipeline", boom)
    code = pipeline_cli.main(["specs/example.json", "--strategy", "composite", "--max-attempts", "1"])
    err = capsys.readouterr().err
    assert code == 1 and st.ERROR_INTERNAL in err and "test-key-not-real" not in err


# ---------------- rules v2: deterministic composite product preservation ----------------

from adgen.evaluator import policy as eval_policy
from adgen.evaluator.evaluate import recompute_evaluation
from adgen.evaluator.rules import (CheckResult, composite_pixel_identity, composite_product_rules, gate,
                                   product_rules)


def _evaluation(res, attempt="attempt-01"):
    return json.loads((res.run_dir / attempt / "evaluation.json").read_text(encoding="utf-8"))


def test_a_pixel_identity_overrides_branding_disagreement_and_records_it(comp):
    res, client = comp.run([SCENE], [comp.variant(tongue_case_variant)])
    ev = _evaluation(res)
    product = ev["checks"]["product"]
    assert res.status == st.PASS and ev["verdict"] == "PASS" and product["verdict"] == "PASS"
    assert product["deterministic_evidence"][0]["code"] == "PRODUCT_PIXEL_IDENTITY_PASS"
    assert product["pixel_identity"]["mismatches"] == 0 and product["pixel_identity"]["passed"] is True
    dis = product["evaluator_disagreement"]
    assert dis["code"] == "PRODUCT_EVALUATOR_DISAGREEMENT"
    assert [r["code"] for r in dis["ai_reasons"]] == ["PRODUCT_BRANDING_DISTORTED"]
    assert ev["evaluator_disagreements"] == [{"check": "product", **dis}]
    assert "PRODUCT_EVALUATOR_DISAGREEMENT" not in ev["reasons"]  # recorded, not a gating reason
    assert ev["rules_version"] == eval_policy.RULES_VERSION == "2"


def test_b_pixel_identity_failure_is_product_fail(comp, monkeypatch):
    real_compose = composite.compose
    def tampered(scene, cutout, canvas=composite.CANVAS):
        ad, info = real_compose(scene, cutout, canvas)
        x, y = info["placement"]["x"], info["placement"]["y"]
        cx, cy = cutout.size[0] // 2, cutout.size[1] // 2
        px = ad.getpixel((x + cx, y + cy))
        ad.putpixel((x + cx, y + cy), tuple((c + 1) % 256 for c in px))
        return ad, info
    monkeypatch.setattr(composite, "compose", tampered)
    monkeypatch.setattr(composite, "verify_pixel_identity", lambda *a, **k: 1)  # generator-side check bypassed
    res, _ = comp.run([SCENE], [comp.variant()])  # AI says everything is perfect
    product = _evaluation(res)["checks"]["product"]
    assert product["verdict"] == "FAIL" and product["reasons"][0]["code"] == "PRODUCT_PIXEL_IDENTITY_FAIL"
    assert product["pixel_identity"]["mismatches"] == 1 and product["deterministic_evidence"] == []
    assert res.final["final_verdict"] == "FAIL"


def test_b_unverifiable_identity_fails_and_keeps_ai_reasons(comp, profile, good_response):
    meta = {"inputs": {"product_image": "does/not/exist.png"}, "cutout": {"sha256": "x"},
            "composite": {"placement": {"x": 0, "y": 0}}}
    identity = composite_pixel_identity(meta, comp.tmp / "missing.png", comp.cdir)
    assert identity["passed"] is False and "could not be verified" in identity["detail"]
    r = copy.deepcopy(good_response)
    emblem_altered(r)
    ai = product_rules(r["product"], profile)
    result = composite_product_rules(ai, identity)
    assert [x["code"] for x in result.reasons] == ["PRODUCT_PIXEL_IDENTITY_FAIL", "PRODUCT_MARK_ALTERED"]


def test_added_logo_stays_gating_even_with_pixel_identity(comp, profile, good_response):
    r = copy.deepcopy(good_response)
    added_logo(r)
    identity = {"passed": True, "checked_opaque_pixels": 10, "mismatches": 0, "cutout_sha256": "s", "detail": ""}
    result = composite_product_rules(product_rules(r["product"], profile), identity)
    assert result.verdict == "FAIL" and [x["code"] for x in result.reasons] == ["PRODUCT_BRANDING_ADDED"]
    assert result.details["evaluator_disagreement"] is None


def test_c_redraw_mode_keeps_existing_product_rules(tmp_path, profile, good_response):
    r = copy.deepcopy(good_response)
    tongue_case_variant(r)
    ai = product_rules(r["product"], profile)
    assert ai.verdict == "FAIL" and [x["code"] for x in ai.reasons] == ["PRODUCT_BRANDING_DISTORTED"]


def test_c_redraw_pipeline_product_failure_still_fails(pipe_like_redraw):
    res = pipe_like_redraw
    ev = _evaluation(res)
    assert ev["checks"]["product"]["verdict"] == "FAIL"
    assert "PRODUCT_BRANDING_DISTORTED" in ev["reasons"]
    assert "pixel_identity" not in ev["checks"]["product"] and ev["evaluator_disagreements"] == []


@pytest.fixture
def pipe_like_redraw(tmp_path, profile, good_response):
    ref = tmp_path / "product.jpg"
    ref.write_bytes(jpeg_bytes((600, 800), "skyblue"))
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    prof = copy.deepcopy(profile)
    prof["reference_image_sha256"] = hashlib.sha256(ref.read_bytes()).hexdigest()
    (pdir / "p.json").write_text(json.dumps(prof), encoding="utf-8")
    spec = spec_from_dict({"id": "redraw-case", "product_image": str(ref), "geography": "Tokyo, Japan",
                           "season": "Winter", "required_text": "Step Into Winter"})
    r = copy.deepcopy(good_response)
    tongue_case_variant(r)
    client = ScriptedClient([jpeg_bytes((1024, 1024), "white")], [json.dumps(r)])
    return run_pipeline(spec, client, output_root=tmp_path / "outputs", profiles_dir=pdir, max_attempts=1)


def test_d_ai_observation_is_stored_verbatim(comp):
    res, _ = comp.run([SCENE], [comp.variant(tongue_case_variant)])
    ev = _evaluation(res)
    stored = json.loads(ev["raw_response"])
    assert stored["product"]["branding"][0]["observed_text"] == "CoMeT"  # raw response kept
    ai = ev["checks"]["product"]["ai_observation"]
    assert ai["verdict"] == "FAIL" and ai["reasons"][0]["observed_text"] == "CoMeT"
    assert ev["checks"]["product"]["branding"]["tongue_label"] == "legible_different"


def test_e_gate_is_deterministic_and_disagreement_never_gates(profile, good_response):
    r = copy.deepcopy(good_response)
    tongue_case_variant(r)
    identity = {"passed": True, "checked_opaque_pixels": 10, "mismatches": 0, "cutout_sha256": "s", "detail": ""}
    outs = []
    for _ in range(3):
        product = composite_product_rules(product_rules(r["product"], profile), identity)
        outs.append(gate({"technical": CheckResult(), "product": product}))
    assert outs == [("PASS", [])] * 3


def test_offline_recompute_reuses_stored_response_without_model_call(comp):
    res, client = comp.run([SCENE], [comp.variant(tongue_case_variant)])
    attempt = res.run_dir / "attempt-01"
    before = (attempt / "evaluation.json").read_bytes()
    rec = recompute_evaluation(attempt, profiles_dir=comp.pdir, cutouts_dir=comp.cdir)
    assert rec["recomputed"]["model_call"] is False and rec["raw_response"] == json.loads(before)["raw_response"]
    assert rec["verdict"] == "PASS" and rec["evaluator_disagreements"][0]["code"] == "PRODUCT_EVALUATOR_DISAGREEMENT"
    assert (attempt / "evaluation.json").read_bytes() == before  # stored evaluation untouched
    assert len(client.eval_calls) == 1
