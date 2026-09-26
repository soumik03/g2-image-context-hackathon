# Solution Details

**Problem Statement 2:** a display-ad generation pipeline enriched by structured context (reference product image + geography + season + required text) using Gemini 3.1 Flash Image. The core question in the problem statement is how to *guarantee* generation quality.

## 1. Engineering design

```
spec (4 official inputs)
  ├─ preflight: valid spec · reference decodes · human-verified profile (· human-verified cutout)
  └─ bounded loop (MAX_ATTEMPTS = 3):
       generate ──► evaluate (Gemini 3.1 Flash-Lite, observations only)
                ──► deterministic rules + gate (Python)
                ──► PASS: accept │ FAIL: targeted correction from evaluator evidence ──► next attempt
                                 │ ERROR: stop (never retried silently, never PASS)
```

**Two generation strategies:**
- **Baseline, `redraw`:** Gemini receives the reference image and a structured prompt, and draws the whole ad.
- **Primary, `composite`:** Gemini receives **only text** (geography, season, required text, layout and camera constraints) and generates the advertising scene and headline. The **exact product pixels** from a human-approved cutout of the reference image are then composited locally with Pillow, at native scale (never resampled), with a deterministic contact shadow. The final ad is saved as lossless PNG. A pixel-identity check proves every fully opaque product pixel equals the cutout. A mismatch is `ERROR_INTERNAL`.
  - **Interior backing:** all preserved opaque product pixels come directly from the reference cutout; a deterministic interior backing fills the reference photo's non-product cavity where packing tissue was removed.
  - The backing is a dark-neutral gradient drawn *behind* the cutout, only in transparent regions fully enclosed by the product. It never replaces an opaque product pixel, and its parameters are recorded in the metadata.

**Why the strategy changed (engineering evolution):**
1. **Baseline evidence:** in all three live redraw generations, Gemini changed the product's distinctive side emblem into a five-pointed star with a lightning-bolt tail. The "COMET" branding came out garbled ("JOMET", "CONET"), and an unrelated "ABT" mark appeared.
2. **Correction attempt:** a targeted correction (Interaction 19) did not fix the emblem and introduced new regressions.
3. **Conclusion:** the **evaluator caught every one of these failures**, but prompting the model to redraw the product could not reliably keep it intact.
4. **Response:** preserve the product pixels, let Gemini generate the context, and let the evaluator verify the final result. This is an openly declared engineering choice. **The product in composite ads is not generated; it comes from the reference photo.**

**Evaluator (the part that catches model mistakes):**
- **One combined Flash-Lite call** per image returns structured observations in three independent sections:
  - **text:** literal transcription of all visible text, with a role for each item;
  - **product:** a status for each attribute in the human-verified profile (preserved / altered / missing / not_visible), branding legibility, `same_product`, and genuinely added marks;
  - **context:** geography and season, each with concrete cues, a rating and conflicting cues.
- **The model never issues PASS/FAIL.** Versioned deterministic rules (`adgen/evaluator/policy.py`, currently rules v2: the v1 rules plus the composite product-preservation rule) produce per-check verdicts with **reason codes and evidence**. Overall PASS requires technical, text, product and context to all pass.
- **The model is kept blind to two things:** it is never told `required_text`, so it transcribes without confirmation bias, and it never sees the profile's `critical` flags.
- **Malformed or incomplete output** (bad JSON, missing section, missing profile id, unknown label) → **ERROR, never PASS**.
- **Composite-mode product rule (rules v2):** the evaluator itself re-checks, from the files on disk, that every fully opaque pixel of the approved, lineage-checked cutout appears unchanged in the ad.
  - **When that holds:** it records `PRODUCT_PIXEL_IDENTITY_PASS`. That deterministic evidence is authoritative for the preserved product pixels. Any AI product reason about those pixels is recorded as `PRODUCT_EVALUATOR_DISAGREEMENT` (non-gating) instead of a FAIL. The AI observation stays stored in full.
  - **Reasons pixel identity cannot rule out:** something added around the product (`PRODUCT_BRANDING_ADDED`) stays gating.
  - **If identity is not verified:** the product FAILS (`PRODUCT_PIXEL_IDENTITY_FAIL`), and all AI reasons stay gating.
  - **Redraw mode** is unchanged.

## 2. Success criteria

| Criterion | How it is measured |
|---|---|
| **S1** Output constraint | Long edge ≤ 1024 px on every output (technical check, enforced in code) |
| **S2** Evaluator separates PASS from FAIL | The golden dataset replays to exact hand-written verdicts and reason codes, with PASS and FAIL both represented |
| **S3** Real model mistakes are captured | The evaluator flags real observed failures in real Gemini outputs |
| **S4** Robust gate | Malformed or incomplete evaluator output → ERROR; tested |
| **S5** Bounded, auditable regeneration | At most 3+3 calls per spec; full attempt lineage; tested |
| **S6** Product fidelity in the primary strategy | Pixel-exact product (invariant tested offline and checked at runtime) |
| **S7** Context and text in the final ads | Evaluator verdicts on live composite outputs: the bounded run and the 20-output experiment (section 3) |

## 3. Level of achievement

The evidence comes in five kinds, kept separate. All live calls are logged in `AGENT_LOG.md`.

### 3.1 Deterministic offline tests

- `python -m pytest -q` gives **355 passed**. The suite needs no network and no API key.
- It covers:
  - schemas: malformed output → ERROR;
  - every reason code;
  - the golden dataset;
  - loop bounds and lineage;
  - exact product pixels and the interior backing;
  - the composite product-preservation rule (v2);
  - filesystem-finalization failures → `ERROR_INTERNAL`;
  - file hygiene.

**Evaluator audit against the official requirements:**

| Requirement | Status | Evidence |
|---|---|---|
| Context adherence | ✅ | Geography and season are rated separately, with cues. Real catches: `CONTEXT_GEO_WEAK`, `CONTEXT_GEO_ABSENT` and `CONTEXT_SEASON_CONFLICT` |
| Reference-product fidelity | ✅ | Human-verified profile. Real catches in redraw outputs: `PRODUCT_MARK_ALTERED` (emblem), `PRODUCT_BRANDING_DISTORTED` (JOMET/CONET) and `PRODUCT_BRANDING_ADDED` ("ABT"). This metric also produces false positives; see 3.5 |
| Text-rendering fidelity | ✅ | Literal transcription plus an exact, case-sensitive Python comparison. Edited fixtures prove that `TEXT_MISMATCH` and `TEXT_EXTRA_AD_COPY` are detected |
| Automated PASS and FAIL | ✅ | `golden/manifest.json`: 14 cases, 3 PASS and 11 FAIL. They are 2 real Gemini outputs (redraw FAIL, composite PASS), 2 deterministic edits and 10 hypothetical cases. Tested in `tests/test_golden.py` |
| Evaluator evidence | ✅ | Every reason carries evidence. The raw response, rules version and policy snapshot are saved in `evaluation.json` |
| Deterministic final gate | ✅ | `adgen/evaluator/rules.py`: every FAIL carries at least one reason code |
| Malformed → ERROR | ✅ | `tests/test_eval_schemas.py`, `tests/test_evaluate.py` |

### 3.2 Real baseline failure (redraw strategy)

- **Results:** 3 redraw generations, **0 passed.** Text passed in all 3; product fidelity failed in all 3.
- **Bounded redraw loop (max 2):** `FAIL_EXHAUSTED` in 2 + 2 calls. New regressions appeared after the correction.
- **Consequence:** this evidence motivated the composite strategy.

### 3.3 Real evaluator validation (composite)

- **What was evaluated:** the user-approved offline re-composite of the first live composite scene, with 1 evaluator call.
- **Results:** technical, text and product PASS (`same_product: yes`, all 8 attributes preserved). Context FAIL (`CONTEXT_GEO_ABSENT`): no Tokyo cues.
- **What this shows:** the evaluator confirms the exact product and isolates the context defect.

### 3.4 Real bounded retry success (composite, max 2)

- **Run:** `outputs/sneaker-tokyo-winter/20260926T093146_984333Z`, with 2 + 2 calls.
- **Attempt 1:** FAIL `CONTEXT_GEO_WEAK`.
- **Correction:** built deterministically from that evidence; it contained a CONTEXT line only.
- **Attempt 2:** **PASS** on all four checks, with no regressions. Product and text stayed PASS.
- **Golden:** attempt 2 is now the golden case `real_composite_pass`.

### 3.5 Real ~20-output experiment (composite, `max_attempts = 1`, no retries)

The table below shows the **original live results** (rules v1), as recorded during the experiment.

**Design:**
- one approved product;
- 5 cities × 4 seasons;
- a different short required text per case;
- exactly **20 generation + 20 evaluator calls**.

**Files:** manifest and report in `experiments/composite20/` (`report.md`, `report.json`, generated from the recorded artifacts).

| Measure | Result |
|---|---|
| Generation / evaluation errors | 0 / 0 |
| **Overall** | **9 PASS (45%)**, 11 FAIL (55%), 0 ERROR |
| Technical | 20 / 20 PASS |
| **Text rendering** | **20 / 20 PASS**: in every output, the evaluator transcribed the required text exactly once and exactly as written |
| Context | 15 PASS, 5 FAIL (all `CONTEXT_GEO_WEAK`) |
| Product | 13 PASS, 7 FAIL (all `PRODUCT_BRANDING_DISTORTED` on the insole print; false positives, see below) |
| Avg generation / evaluation time | 12.6 s / 6.0 s |

**Product-failure audit (important):**
- **The product was identical every time:** all 20 outputs have **0 pixel-identity mismatches**, so the product region is byte-identical to the approved cutout in every one.
- **The evaluator read it inconsistently:** it transcribed the same insole print as `COMET`, `comet`, `COMeT`, `coMeT`, `coMet` or `cOmeT`. It even labelled `comet` as correct in two cases and as different in two others.
- **What the 7 product FAILs are:** false positives. The evaluator is not robust to the stylized lowercase-looking "e" in the insole logo, combined with the profile's expected text "COMET".
- **No real product-fidelity failure occurred.** Rules, profile and thresholds were deliberately **not** changed to remove these failures.

**Context:**
- The 5 geography failures came from scenes with only generic cues. For example, the Seoul autumn scene has a fan, chopsticks, tea and ginkgo leaves, with nothing Seoul-specific.
- Excluding the evaluator's product false positives, context is the only real failure source. The bounded loop has demonstrated that it can correct this kind of failure (3.4).

### 3.6 Recomputed experiment results (rules v2, offline)

*Recomputed offline from the same 20 live experiment artifacts after deterministic composite product-preservation rule.*

This is **not a new live experiment.** No Gemini call was made, no image was generated or changed, and every stored `evaluation.json` is byte-identical. The current rules were re-applied to each case's stored raw evaluator response, and the pixel identity was independently re-verified from the stored `ad.png`. The results are in `attempt-01/evaluation.recomputed.json` and in the manifest.

| Measure | Original live (v1) | Recomputed (v2) |
|---|---|---|
| Overall | 9 PASS / 11 FAIL / 0 ERROR | **15 PASS (75%) / 5 FAIL (25%) / 0 ERROR** |
| Technical | 20 / 0 | 20 / 0 |
| Product | 13 / 7 | **20 / 0**: pixel identity re-verified in 20/20 (310,136 pixels each, 0 mismatches) |
| Context | 15 / 5 | 15 / 5 (unchanged) |
| Text | 20 / 0 | 20 / 0 (unchanged) |
| Failure reasons | 7 × `PRODUCT_BRANDING_DISTORTED`, 5 × `CONTEXT_GEO_WEAK` | 5 × `CONTEXT_GEO_WEAK` |
| Evaluator disagreements | not tracked | **7** × `PRODUCT_EVALUATOR_DISAGREEMENT` (cases 05, 09, 10, 13, 16, 17, 18) |

**Recomputed results by geography and season (PASS/FAIL):**
- By geography: Tokyo 3/1, Paris 4/0, New York 3/1, London 3/1, Seoul 2/2.
- By season: Winter 5/0, Spring 4/1, Summer 4/1, Autumn 2/3.

**Why the original evaluator produced false positives:**
- The insole logo is stylized: its "e" looks lowercase.
- Flash-Lite transcribed the same pixels differently from run to run (`COMET`, `comet`, `COMeT`, `coMeT`, `coMet`, `cOmeT`) and assigned inconsistent statuses.
- Rules v1 compare the transcription with the profile's "COMET", so a reading variation became `PRODUCT_BRANDING_DISTORTED`.

**Why pixel identity is stronger evidence:**
- In composite mode the system knows exactly which pixels are the product. It can prove they equal the human-approved cutout of the reference photo.
- That is a deterministic fact.
- An OCR or capitalization reading is a model observation that can vary between runs.

**Why the AI evaluator remains useful:**
- It still judges text, context and anything added around the product.
- Its product observations are retained verbatim in every evaluation, and exposed as `ai_observation`.
- When it contradicts the pixel evidence, the disagreement is recorded explicitly, not hidden and not treated as ground truth.

**What did not change:** the profile, text rules, context rules, thresholds, redraw product rules and the three official metrics.

**Evaluator transcription limits, recorded as observed:**
- In the golden composite PASS, a garbled station sign ("新宿丁駅") was transcribed as the correct name "新宿三丁目駅".
- Garbled background text such as "CONIS ARRONDISSEMENTS" also appears.
- Background text is `background_incidental` and does not count toward the required-text gate.

## 4. Limitations

- **Evaluator reliability on stylized branding:** under rules v1, product fidelity produced 7/20 false FAILs on pixel-identical products (3.5).
  - Rules v2 resolve this for composite mode only, using deterministic pixel identity (3.6).
  - In redraw mode the AI product observation still decides, and remains vulnerable to such reading variation.
  - Model observations vary between runs, and the thresholds are not calibrated at scale.
- **Rules v2 was designed after seeing the experiment:** the v2 figures are an offline recomputation, not an independent live test of the rule.
- **Composite realism:**
  - Lighting, perspective, shadow and **scale** are approximated; the product often looks oversized next to props.
  - The supplementary integration observation is deterministic and **non-gating**.
- **Product is composited, not generated:** the pose is limited to the single near-overhead reference photo.
- **Cutout:**
  - The mask was drafted automatically and approved by a human.
  - Packing tissue was removed inside a reviewer-directed region. The resulting cavity is filled by a deterministic interior backing, so those pixels are not reference pixels. All preserved opaque product pixels come directly from the reference cutout.
- **Scale of evidence:**
  - one product;
  - 20 single-attempt outputs;
  - one bounded composite run.
  - The golden dataset is small, with 2 real outputs.
- **Errors are terminal by design,** including transient API errors. Filesystem-finalization failures become auditable `ERROR_INTERNAL`.

## 5. Official requirements vs engineering decisions

**Official:**
- Gemini 3.1 Flash (Lite) Image;
- the four inputs;
- long edge ≤ 1K;
- an evaluator over about 20 outputs covering the three metrics;
- automated PASS/FAIL tests;
- a coding-agent disclosure.

**Engineering decisions:**
- model-observes / Python-decides;
- rules v1 strictness, and the rules v2 composite product-preservation rule (pixel identity authoritative for preserved product pixels; AI disagreement recorded);
- human-verified profile and cutout;
- `MAX_ATTEMPTS = 3`;
- corrections driven by evaluator evidence (TEXT/CONTEXT only in composite mode);
- the composite strategy;
- the non-gating integration metric;
- errors are terminal.
