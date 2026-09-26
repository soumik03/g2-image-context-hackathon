# Requirements Analysis — G2 AI Engineering Hackathon, Problem Statement 2

**Status:** Draft for review. No architecture chosen yet.
**Date:** 2026-09-26

**Source abbreviations used below**

| Abbrev. | File | Notes |
|---|---|---|
| **PS2** | `G2_Problem_Statement_2.md` | Problem statement. Sections: Overview, Tech Stack, Task (1–4), Restrictions, Submission Format |
| **SG-PDF** | `G2_SUBMISSION_GUIDE.pdf` | Official submission guide, 5 pages (the original reference) |
| **SG-MD** | `G2_AI_Engineering_Hackathon_Submission_Guide.md` | Markdown transcription of SG-PDF |

---

## 1. Problem understanding

We need to build an **image-generation pipeline for display ads** on a Gemini image model. Each run takes:

- a **reference product image** (what the product actually looks like), and
- **structured context**: a target geography, a season, and a short text that must appear in the ad.

It produces an ad image that shows *that* product, fits *that* place and season, and contains *that* text.

The main question in PS2 (Overview) is: **"How would you guarantee that generation quality is achieved in the generation process?"** Image models don't behave deterministically. They can change the product, ignore the context, or misspell the text. So the real engineering problem is not "call an image API". It is:

1. a **generation strategy** that makes good outputs likely,
2. an **evaluator** that measures quality on defined metrics over about 20 outputs, and
3. **automated tests** proving the evaluator can tell good outputs from bad ones.

In engineering terms, this is a generator plus a quality-measurement system. The measurement system must itself be validated, using a golden dataset and tests.

---

## 2. Mandatory functional requirements

| ID | Requirement | Source |
|---|---|---|
| FR-1 | Propose an image-generation pipeline for **display advertisement** generation. | PS2 §Task 1 |
| FR-2 | The pipeline must use **Gemini 3.1 Flash-Lite Image** or **Gemini 3.1 Flash Image**. | PS2 §Task 1 |
| FR-3 | Pipeline input = reference product image + three structured text fields: target geography, season, and freeform text that must be included in the generated image. | PS2 §Task 1 |
| FR-4 | The structured context must **refine** the generated image, i.e. visibly affect the output. | PS2 §Task 1 |
| FR-5 | The solution must take into account that text rendering may not be perfect. Imperfect text is acceptable, but the design must address it. | PS2 §Task 1 (Note) |
| FR-6 | Decide on an **effective generation strategy**, then **implement** the pipeline. | PS2 §Task 2 |
| FR-7 | Implement an **evaluator** that judges output quality across about 20 images produced by the pipeline. | PS2 §Task 3 |
| FR-8 | Define **quality metrics**. At minimum: (1) context adherence, (2) reference-product fidelity, (3) text-rendering fidelity. | PS2 §Task 4 |
| FR-9 | Provide **automated tests** showing the evaluator can tell **passing** outputs from **failing** ones against those metrics. | PS2 §Task 4 |
| FR-10 | Provide a **golden dataset** in the repository. | PS2 §Submission Format (Repository) |

---

## 3. Mandatory constraints

Only constraints stated explicitly in the sources are listed.

| ID | Constraint | Source |
|---|---|---|
| C-1 | Generated images must be at most 1K resolution: **long edge ≤ 1024 px**. | PS2 §Task 2 |
| C-2 | Model is limited to Gemini 3.1 Flash-Lite Image or Gemini 3.1 Flash Image (for generation). | PS2 §Task 1 |
| C-3 | A Gemini API key is required (free key available from aistudio.google.com). | PS2 §Overview (Note) |
| C-4 | Tech stack: Python, TypeScript or Ruby **preferred**. This is a preference, not a hard rule. | PS2 §Tech Stack |
| C-5 | Coding agents are allowed, but we must explain how we collaborated with (prompted) the agent. | PS2 §Restrictions |
| C-6 | Each upload field (Presentation, Source Code) is limited to **50 MB**. | SG-PDF p.4, p.5; SG-MD Steps 4–5 |
| C-7 | Presentation formats accepted: `.key, .odp, .odt, .pdf, .pps, .ppt, .pptx`. | SG-PDF p.4; SG-MD Step 4 |
| C-8 | The submission counts only after clicking **Submit**. "Save as Draft" does not submit. | SG-PDF p.5; SG-MD Step 5 |

Constraints from the user's project rules (not from the sources, recorded for completeness): everything is built fresh in the hacking window, no reuse of earlier prototypes, and the solution stays minimal and explainable.

---

## 4. Required inputs (to the image-generation pipeline)

Per PS2 §Task 1, **exactly four inputs**:

1. **Reference product image**: an image file of the product.
2. **Target geography**: structured text field (e.g. a country, region or city).
3. **Season**: structured text field.
4. **Freeform text**: a string that must appear in the generated image.

Also needed to operate (implied, not listed as pipeline inputs): a Gemini API key (PS2 §Overview).

The sources do **not** say what format, allowed values or length limits these fields have. See §10.

---

## 5. Required outputs

**Pipeline outputs**
- A generated display-ad image per input set, **long edge ≤ 1024 px** (PS2 §Task 2).
- Enough outputs to evaluate **about 20 images** (PS2 §Task 3).

**Evaluator outputs**
- A quality judgment per image against the defined metrics, and a result across the full set of about 20 (PS2 §Task 3–4).
- A **pass/fail** outcome relative to the metrics. Task 4 requires telling "passing and failing outputs" apart (PS2 §Task 4).

**Documentation outputs** (PS2 §Submission Format)
- Success-criteria definition and **level of achievement against those criteria**. In practice this means the evaluator's results have to be reported.

The sources do not define the output file format, report format or storage layout (§10).

---

## 6. Evaluator requirements

From PS2 §Task 3 and §Task 4, the evaluator must:

1. **Judge quality** of pipeline outputs, run over about 20 generated images.
2. Score each output against **metrics we define**. The minimum set is:
   - **Context adherence**: does the image reflect the target geography and season?
   - **Reference-product fidelity**: is the product in the ad recognizably the same product as the reference image?
   - **Text-rendering fidelity**: does the required freeform text appear, and is it rendered accurately?
3. Produce **pass/fail** decisions against those metrics. This is required for Task 4's testing.

We may add further metrics (e.g. the ≤ 1024 px resolution constraint, general ad quality), but none are required beyond the three above. The sources leave the evaluation method open (model-as-judge, deterministic checks, or both). See §10.

---

## 7. Automated-testing requirements

From PS2 §Task 4:

- Tests must be **automated**.
- They must **show that the evaluator correctly identifies passing and failing outputs** against our metrics. This means the tests validate the **evaluator**, not only the pipeline code.
- They must cover at least context adherence, product fidelity and text-rendering fidelity.

Implication: we need **labeled examples** with a known expected verdict for each metric, including **known-bad** examples (wrong text, wrong or altered product, wrong season or geography). The tests then assert that the evaluator's verdict matches the label. This labeled set is effectively the **golden dataset** required in the repository (PS2 §Submission Format).

The sources do **not** say whether tests may call live APIs, how many cases are needed, or what accuracy threshold counts as success (§10).

---

## 8. Submission requirements

### From PS2 §Submission Format
| Artifact | Detail |
|---|---|
| **Solution Details** document (Markdown or PDF) | Engineering design, rationale, **definition of success criteria**, **level of achievement against criteria**, **limitations** |
| **Disclosure of Coding Agent Use** | How we directed the agent: architectural requirements given, or summarized interaction traces |
| **Repository** (GitHub/GitLab) | Code, **golden dataset** and **tests** |

### From SG-PDF pp.4–5 (and SG-MD Steps 4–5): HackerEarth form, all mandatory (*)
| Field | Detail / limit |
|---|---|
| **Title** | Clear, descriptive |
| **Description** | Project/solution description; formatting and links allowed |
| **Presentation** | Pitch deck/slides; `.key/.odp/.odt/.pdf/.pps/.ppt/.pptx`; **≤ 50 MB** |
| **Repository URL** | Link to code repository |
| **Source Code** | Upload (e.g. `.zip`); **≤ 50 MB** |
| **Instructions to Run** | Clear steps so reviewers can run **and test** the project |
| **Submit** | Must click Submit, not Save as Draft |

### Discrepancies / gaps between sources (flagged, not resolved)
1. **Repository host:** PS2 says "GitHub/GitLab". SG-PDF p.5 says "e.g. GitHub, Bitbucket". GitHub satisfies both.
2. **Presentation:** required by SG-PDF p.4 but not mentioned in PS2. **Solution Details** and **Coding-agent disclosure** are required by PS2 but have no dedicated field in SG-PDF. Where they go is unspecified (likely the repo and/or the Description field).
3. **Hacking window / deadline:** SG-PDF p.1 shows "Sep 26 – Sep 26, 2026, 9:00 AM – 5:00 PM · Asia/Kolkata", and p.2–3 show "Submission begin … Sep 26, 2026, 9:00 AM". Both appear **only in screenshots**. SG-MD does not transcribe them because it omits screenshots. Neither source states a deadline as text. **Please confirm the deadline.**
4. **SG-MD vs SG-PDF text:** no substantive differences found. SG-MD splits some sentences into bullet lists and omits the screenshots (as its header says). The "Register" step appears in the flow of both but has no step describing it.
5. **Size risk (not a conflict):** the golden dataset (images) must be in the repo, and the Source Code upload is capped at 50 MB. Dataset images must be kept small.

---

## 9. Coding-agent disclosure

Required by PS2 §Restrictions and §Submission Format. We must:

- **Disclose** that a coding agent (Claude Code) was used.
- **Explain how we directed it**: the architectural requirements we supplied, and/or **summarized traces** of the interactions.
- Show how the collaboration led to the solution: key prompts, decisions we made, and corrections we gave the agent.

Plan: keep `AGENT_LOG.md` updated after each significant interaction (prompt purpose, what the agent produced, what we approved, rejected or corrected). Summarize it in the final disclosure section.

---

## 10. Ambiguities / engineering decisions (left open by the sources)

**Model & API**
1. Which model: Flash-Lite Image vs Flash Image (cost/speed vs quality). The exact API model IDs must be checked against current Gemini docs, not assumed.
2. Which model(s) to use for **evaluation**. PS2 limits only the generation model.
3. How to enforce ≤ 1024 px: request settings, post-generation downscaling, or both. Plus a check that verifies it.

**Inputs**
4. Allowed values for geography and season (free text vs a fixed list), and a length limit for the freeform text.
5. Ad format and aspect ratio. "Display advertisement" doesn't specify sizes.
6. Where the reference product images come from, and their licensing.

**Generation strategy**
7. Prompt construction: a template vs a model-written creative brief.
8. Single-shot vs best-of-N vs generate → evaluate → retry.
9. How to handle imperfect text rendering (FR-5): accept and measure, retry, constrain text length, or overlay text deterministically. Overlay may conflict with "included in the generated image"; that interpretation must be decided explicitly.

**Evaluator**
10. Method per metric: vision-model judge, deterministic checks (e.g. string similarity on transcribed text), image similarity, or a hybrid.
11. Scoring scale and **pass/fail thresholds** per metric, and how metrics combine into an overall verdict.
12. How to reduce and report judge unreliability (fixed rubric, structured output, repeated runs).

**Golden dataset & tests**
13. Makeup of the ~20-image evaluation set (number of products × contexts).
14. How to get labeled **failing** examples: natural failures, deliberately bad prompts, or edited/corrupted images.
15. Whether automated tests call the live API or use recorded/mocked judge responses (reproducibility, cost, need for a key in CI). Possibly both tiers.
16. Accuracy threshold for "the evaluator works", e.g. agreement with human labels.

**Deliverables**
17. Language and stack (Python is the default preference).
18. Where Solution Details and the disclosure live (repo files vs the Description field).
19. Presentation content and format.

---

## 11. Candidate architecture options

All three options share: an input spec (image + 3 fields) → prompt builder → Gemini image model → size check (≤ 1024 px) → saved output, and a separate evaluator run over about 20 outputs, with tests against a labeled golden set. They differ in **how quality is ensured during generation**.

### Option A: Single-shot generation + offline evaluator

- **Components:** input loader; template prompt builder; generator (one Gemini image call per input); resolution check; evaluator (per-metric checks → scores → pass/fail); report writer; tests against the golden set.
- **Data flow:** inputs → prompt → 1 image → save → *(separately)* evaluator over all ~20 → report.
- **Advantages:** simplest option; cheapest in API calls; easiest to explain; pipeline and evaluator are fully separate.
- **Disadvantages:** does not "guarantee" quality during generation. It only measures quality afterwards. Failed images simply stay failed.
- **Effort:** Low.
- **Quality approach:** careful prompt design for improvement; evaluation for *measurement* only.

### Option B: Generate → evaluate → retry (evaluator as quality gate)

- **Components:** everything in A, plus a loop controller that calls the evaluator on each candidate. On failure it regenerates, optionally adding the failure reason to the prompt, up to N attempts. It returns the best-scoring candidate and records attempts.
- **Data flow:** inputs → prompt → image → evaluator → pass? return : (feedback → regenerate, ≤ N) → best candidate + attempt log → final report over ~20.
- **Advantages:** directly answers "guarantee quality *in the generation process*" (PS2 §Overview). The same evaluator serves Tasks 3 and 4. Retry statistics give measurable evidence (first-try pass rate vs after-retry pass rate).
- **Disadvantages:** up to N× API cost and latency. Evaluator errors now affect outputs, not only reports. Slightly more logic.
- **Effort:** Low–Medium (A + a bounded loop).
- **Quality approach:** failing outputs are caught and regenerated. Output quality is bounded by evaluator accuracy, which the tests validate.

### Option C: Two-stage brief + generation, with a text-rendering safeguard

- **Components:** a **brief planner** (a text/vision model turns image + fields into a structured creative brief: scene, seasonal and regional cues, layout, text placement) → generator → evaluator. It adds a **text safeguard**: short-text constraints, and optionally a deterministic text overlay when text fidelity fails.
- **Data flow:** inputs → planner → structured brief → prompt → image → evaluator → (if text fails: retry or overlay) → report.
- **Advantages:** more explicit and inspectable context handling (the brief can be logged and audited). Tackles the known text-rendering weakness (FR-5) directly.
- **Disadvantages:** more moving parts and API calls. The overlay may be read as not satisfying "text included in the *generated* image" (open decision §10.9). Harder to explain in limited time.
- **Effort:** Medium.
- **Quality approach:** raises first-attempt quality through richer context. Enforces text fidelity through constraints or fallback.

*These options can be combined (e.g. B with parts of C). No choice has been made yet.*

---

## 12. Proposed implementation phases

| Phase | Goal | Exit criterion |
|---|---|---|
| **0. Decisions & setup** | Approve architecture and key decisions (§10); init git repo; choose stack; set up API key via env var; confirm current Gemini model IDs | Decisions logged in AGENT_LOG.md; repo skeleton; one trivial API call works |
| **1. Inputs & golden-dataset design** | Pick reference products and ~20 input combinations; define the metric rubric and pass/fail thresholds | Input spec file + written metric definitions |
| **2. Pipeline** | Implement the chosen generation strategy with ≤ 1024 px enforcement | ~20 generated images saved with metadata |
| **3. Evaluator** | Implement per-metric scoring + pass/fail + aggregate report | Report produced over the ~20 images |
| **4. Labeled set & automated tests** | Label pass/fail examples (including deliberate failures); write tests asserting evaluator verdicts | Tests run with one command; results recorded |
| **5. Results & analysis** | Run end to end; measure achievement against success criteria; note limitations | Numbers ready for Solution Details |
| **6. Documentation** | README (instructions to run and test), Solution Details, coding-agent disclosure (from AGENT_LOG.md) | Docs complete and consistent with code |
| **7. Packaging & submission** | Push repo; zip source (≤ 50 MB); build presentation (≤ 50 MB, allowed format); fill the HackerEarth form; click **Submit** | Submission confirmed before the deadline (to be confirmed, see §8 item 3) |
