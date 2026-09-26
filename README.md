# Structured-Context Ad Generation with an Evaluator-Gated Pipeline

G2 AI Engineering Hackathon, **Problem Statement 2: Enrichment of image generation using structured context.**

The pipeline takes **one reference product image + geography + season + required text** and produces a display ad (long edge ≤ 1024 px) with Gemini. A multimodal evaluator plus **deterministic** rules judge every output on **context adherence, reference-product fidelity and text-rendering fidelity**. A bounded loop regenerates failed outputs.

- **Design, results, limitations:** [SOLUTION_DETAILS.md](SOLUTION_DETAILS.md)
- **AI/coding-agent disclosure:** [AI_DECLARATION_SUMMARY.md](AI_DECLARATION_SUMMARY.md) (full trace in [AGENT_LOG.md](AGENT_LOG.md))

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # then put your Gemini API key in .env (never commit it)
python scripts/check_api.py       # read-only: verifies both model IDs are accessible
```

## Run the tests (offline, no API key needed)

```bash
python -m pytest -q
```

The tests use fake Gemini clients. They cover: the generator, the evaluator schemas and rules (malformed output → ERROR), every reason code, the **golden dataset** (`golden/manifest.json`, which replays real and labeled cases to hand-written expected verdicts), the bounded loop, cutout lineage, **exact product-pixel preservation**, and file hygiene.

## Run the pipeline (live, uses the Gemini API)

```bash
# Primary strategy: exact product pixels composited into a Gemini-generated scene
python -m adgen.pipeline.cli specs/example.json --strategy composite --max-attempts 3

# Baseline strategy: Gemini redraws the whole ad (kept for comparison)
python -m adgen.pipeline.cli specs/example.json --strategy redraw --max-attempts 3

# Single pieces
python -m adgen.cli specs/example.json                     # one baseline generation
python -m adgen.evaluator.cli evaluate outputs/<id>/<run>  # evaluate one generated run
```

**~20-output evaluation experiment** (composite strategy, `max_attempts = 1`, one product, 20 geography/season/text contexts):
```bash
python scripts/run_experiment.py build    # 20 specs + manifest (offline)
python scripts/run_experiment.py check    # offline validation: 20 specs, paths, key leak, disk, approved cutout/profile
python scripts/run_experiment.py run      # LIVE: 20 generation + 20 evaluation calls at most, no retries
python scripts/run_experiment.py recompute  # OFFLINE: re-apply the current rules to the stored raw evaluator responses
python scripts/run_experiment.py report   # experiments/composite20/report.{json,md} from the recorded artifacts
```

**Budget:** each attempt is 1 generation call + 1 evaluation call. The worst case is 3 + 3 calls per spec, with no hidden retries. Outputs go to `outputs/<spec-id>/<run-id>/attempt-NN/{scene.jpg, ad.png|ad.jpg, metadata.json, evaluation.json, attempt.json}` plus `final.json`.

**Spec format** (`specs/example.json`): exactly the four official inputs, plus an id.
```json
{"id": "sneaker-tokyo-winter", "product_image": "inputs/products/sneaker.jpg",
 "geography": "Tokyo, Japan", "season": "Winter", "required_text": "Step Into Winter"}
```

## One-time, per product (human-in-the-loop)

```bash
# Reference profile for the evaluator: model draft → human review → approved
python -m adgen.evaluator.cli draft-profile inputs/products/sneaker.jpg --name sneaker
#   review/correct → save as profiles/sneaker.json with "human_verified": true

# Exact-pixel cutout for the composite strategy: mask → draft → human approval
python scripts/make_draft_mask.py inputs/products/sneaker.jpg inputs/masks/sneaker_mask.png
python -m adgen.cutout_cli build inputs/products/sneaker.jpg inputs/masks/sneaker_mask.png --name sneaker --mask-source "..."
python -m adgen.cutout_cli approve sneaker --verified-by "<reviewer>"     # only after visual review
python -m adgen.cutout_cli check inputs/products/sneaker.jpg
```

## Repository map

| Path | Contents |
|---|---|
| `adgen/` | spec, prompt, generator (baseline), `composite.py` (primary), `cutout.py`, `image_io.py`, config |
| `adgen/evaluator/` | evaluator: prompt, JSON schema, strict validation, versioned deterministic policy/rules (current composite policy v2), profile handling |
| `adgen/pipeline/` | bounded orchestrator, deterministic correction builder, CLI |
| `profiles/` | human-verified reference profile (evaluator only; never sent to the generator) |
| `cutouts/`, `inputs/masks/` | product mask and cutout (draft + approved) |
| `golden/` | golden dataset: manifest, 2 real Gemini outputs (redraw FAIL, composite PASS), edited fixtures, hypothetical cases |
| `experiments/composite20/` | 20-output experiment: specs, manifest (per-case results), aggregate report |
| `tests/` | offline test suite |
| `REQUIREMENTS.md`, `CLAUDE.md`, `AGENT_LOG.md` | requirements analysis, agent rules, full development trace |
