# Coding-Agent Collaboration Log

Record of how the coding agent was directed on this project. It feeds the required "Disclosure of Coding Agent Use" (G2_Problem_Statement_2.md §Restrictions, §Submission Format).

- **Coding agent:** Claude Code (Anthropic), model Claude Opus 5.5, running in the VS Code extension
- **Project:** G2 AI Engineering Hackathon, Problem Statement 2 (Enrichment of image generation using structured context)

---

## Interaction 1: Requirements analysis

- **Date:** 2026-09-26
- **Context:** First interaction in a fresh project created during the official hacking window. At this point the directory held only the three official source files.

### Purpose of the prompt
Requirements analysis only. The agent was told to:
- read all three source files (`G2_Problem_Statement_2.md`, `G2_AI_Engineering_Hackathon_Submission_Guide.md`, `G2_SUBMISSION_GUIDE.pdf`)
- treat them as the source of truth, with the PDF as the original reference
- flag rather than silently resolve discrepancies
- produce `REQUIREMENTS.md` and this log

It was explicitly told **not** to:
- write application code
- call Gemini or any API
- generate images
- install packages
- initialize tooling
- create other files
- reuse or assume anything from earlier prototypes

It was also told to stop and wait for approval afterwards.

### Agent actions
- Read the three source files, including all 5 PDF pages and their screenshots.
- Created `REQUIREMENTS.md` and `AGENT_LOG.md`. No other files were created. Source files were not modified. No API calls, no installs.

### Summary of requirements identified
- **Pipeline:** display-ad image generation using Gemini 3.1 Flash-Lite Image or Gemini 3.1 Flash Image. Inputs are a reference product image plus geography, season and freeform text (the text must appear in the image). The context must refine the output. The design must account for imperfect text rendering.
- **Constraint:** output long edge ≤ 1024 px.
- **Evaluator:** judges quality over about 20 pipeline outputs. Minimum metrics are context adherence, reference-product fidelity and text-rendering fidelity.
- **Automated tests:** must prove the evaluator separates passing from failing outputs.
- **Repository:** code, golden dataset and tests.
- **Solution Details document:** design, rationale, success criteria, achievement against them, limitations.
- **Coding-agent disclosure:** how the agent was directed.
- **HackerEarth form:** Title, Description, Presentation (≤ 50 MB, listed formats), Repository URL, Source Code (≤ 50 MB), Instructions to Run, then **Submit** (not Save as Draft).

### Discrepancies flagged (not resolved)
1. The repository host is "GitHub/GitLab" in the problem statement but "GitHub, Bitbucket" in the guide.
2. A Presentation is required by the guide but not by the problem statement. Solution Details and the disclosure have no dedicated form field.
3. The hacking window / deadline (Sep 26 2026, 9:00 AM–5:00 PM Asia/Kolkata) appears only in PDF screenshots, not as text, and not in the Markdown transcription. The user needs to confirm it.
4. The Markdown guide vs the PDF: no substantive text differences.
5. Size risk: the golden dataset in the repo has to fit the 50 MB source-code upload limit.

### Architectural decisions deliberately NOT made yet
- Choice between the three candidate architectures:
  - A: single-shot + offline evaluator
  - B: generate → evaluate → retry quality gate
  - C: planner brief + generation + text safeguard
- Generation model (Flash-Lite vs Flash) and exact API model IDs
- Evaluator model and method (vision judge, deterministic checks or hybrid)
- Metric scales, pass/fail thresholds and how metrics combine
- Strategy for imperfect text rendering, including whether a deterministic overlay is acceptable
- Golden-dataset composition and how failing examples are obtained
- Whether tests use live API calls or recorded/mocked responses
- Language and stack, repo layout, output and report formats
- Input value formats, and ad aspect ratio and size

### Human decisions / corrections
- User reviewed the analysis and approved an architecture direction. See Interaction 2.

---

## Interaction 2: Architecture direction approved

- **Date:** 2026-09-26
- **Summary:** Architecture direction approved; CLAUDE.md created to preserve approved project constraints.

### Instruction given to the agent
Create only `CLAUDE.md`, capturing:
- project purpose,
- official constraints,
- approved architecture and model direction,
- engineering, testing and documentation principles,
- explicit "do not do" rules.

The agent was told not to:
- modify `REQUIREMENTS.md` or the source files,
- write source code,
- call Gemini,
- install packages.

It was told to update this log and then stop.

### Decisions made by the user
- **Architecture:** generator → evaluator (context / product / text checks) → quality gate. PASS is accepted; FAIL triggers **bounded** regeneration. This is essentially candidate Option B from `REQUIREMENTS.md` §11.
- **Models:**
  - generator `gemini-3.1-flash-image`,
  - evaluator `gemini-3.1-flash-lite`.

  They may change only if an API compatibility check requires it, with the reason documented.
- **Principles:**
  - exactly four pipeline inputs;
  - long edge ≤ 1024 px;
  - the three minimum metrics;
  - auditable PASS/FAIL;
  - tests showing both PASS and FAIL cases;
  - bounded retry loop;
  - generation and evaluation kept separate;
  - deterministic Python where possible, multimodal model only for visual understanding;
  - no agents, RAG, vector DBs, MCP or orchestration frameworks without a concrete need;
  - secrets only in environment variables;
  - no reuse of previous prototypes;
  - every significant interaction logged here.
- **Final submission contents:**
  - solution details,
  - coding-agent disclosure,
  - repository,
  - golden dataset,
  - tests,
  - run instructions,
  - presentation.

### Agent interpretations (for user review)
These are written into `CLAUDE.md` but were not explicitly stated by the user:
- **Language:** Python, since it is the first preference in the problem statement and implied by principle 8.
- **Tests:** deterministic unit tests run without an API key. Live-Gemini tests are kept separate or marked.
- **Retry bound test:** a test must show the retry loop stops at its bound.
- **Config:** model IDs, thresholds and max retries live in one config location.
- **Malformed evaluator output:** treated as an explicit error, never a silent pass.

### Agent actions
- Created `CLAUDE.md` and updated `AGENT_LOG.md`. No other files were changed. No code, no API calls, no installs.

### Still open / deliberately deferred
- **Model IDs:** not yet verified against the live API.
- **Evaluator design:** exact per-metric method, scales and pass/fail thresholds.
- **Retry settings:** max retries N, and whether the prompt is revised using failure feedback.
- **Text rendering:** strategy for imperfect text.
- **Golden dataset:** composition and how failing examples are obtained.
- **Ad format:** aspect ratio and format.
- **Deadline:** confirmation still pending (only shown in PDF screenshots).

---

## Interaction 3: Development environment setup

- **Date:** 2026-09-26

### Instruction given to the agent
Create only these three files:
- `.gitignore`
- `requirements.txt`
- `.env.example`

Set minimum versions in `requirements.txt` from the versions actually installed in the existing virtual environment, without inventing any.

The agent was told not to:
- create source code, tests or config modules,
- call Gemini or generate images,
- add frameworks,
- modify `REQUIREMENTS.md`, `CLAUDE.md` or the source files.

### Agent actions
- Checked the user's existing `.venv` (created by the user; the agent installed nothing). It runs Python 3.13.15. `pip list` reported these installed versions:
  - `google-genai` 2.25.0
  - `pillow` 12.3.0
  - `python-dotenv` 1.2.3
  - `pytest` 9.1.1
- Created the three files:

| File | Contents |
|---|---|
| `.gitignore` | Excludes `.venv/`, `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/` |
| `requirements.txt` | The four dependencies, each pinned as `>=` the installed version |
| `.env.example` | `GEMINI_API_KEY=your-key-here`, with a comment that the real key goes in the git-ignored `.env` and must never be committed |

### Why each dependency exists
- **google-genai:** official Google Gen AI SDK for calling the Gemini generator (`gemini-3.1-flash-image`) and evaluator (`gemini-3.1-flash-lite`).
- **pillow:** deterministic image handling, i.e. loading reference images, checking and enforcing long edge ≤ 1024 px, and saving outputs.
- **python-dotenv:** loads `GEMINI_API_KEY` from the local `.env`, so the key stays in the environment and is never in code (CLAUDE.md, Secrets principle).
- **pytest:** the automated test runner required to show the evaluator's PASS/FAIL behavior (PS2 §Task 4).

### Confirmations
- No API calls were made.
- Nothing was installed.
- No source code, tests or configuration modules were created.

---

## Interaction 4: API access check script

- **Date:** 2026-09-26

### Instruction given to the agent
Create only `scripts/check_api.py`. It must be a small, read-only script that:
- loads `GEMINI_API_KEY` from the project-root `.env`,
- never prints any part of the key,
- fails clearly if the key is missing,
- checks that `gemini-3.1-flash-image` and `gemini-3.1-flash-lite` are accessible using model metadata only,
- reports `RESULT: SUCCESS` or `RESULT: FAILURE`,
- never silently substitutes a model ID.

The agent was told not to call the API while writing the file, and not to install anything.

### Why the check exists
Before writing any pipeline code, we need to confirm that the approved model IDs (CLAUDE.md, Approved model direction) actually exist and are accessible with our key. This was listed as an open item after Interaction 2. If an ID is wrong, we want to learn it now, explicitly, and decide the change ourselves.

### Design
- **Intentionally read-only.** It uses only `client.models.get(model=...)`, which retrieves model metadata. **No image-generation call and no content-generation call is made.**
- **Checked against the installed SDK, offline.** The agent inspected the local `google-genai` 2.25.0 package without network access, confirming:
  - the `Models.get(*, model, config=None)` signature,
  - the `genai.Client(api_key=...)` constructor,
  - the attributes `code`, `status` and `message` on `errors.APIError`.
- **No fallback.** Both models are checked so both results are reported. If either is inaccessible, the script prints FAILURE and exits 1 without trying alternative IDs.
- **Secret handling:**
  - the key is read only from the environment or `.env` and passed straight to the client;
  - the key is never printed;
  - any error text is passed through `redact()` before printing, which replaces the key if it appears.

### Agent actions
- Created `scripts/check_api.py` and updated `AGENT_LOG.md`.
- No API calls were made. The script has **not yet been run**. The user will run it.
- Nothing was installed, and no other files were modified.

### Verification result (run by the user)
The user ran `python scripts/check_api.py` and reported:
```
[OK] gemini-3.1-flash-image: name=models/gemini-3.1-flash-image, supported_actions=generateContent, countTokens, batchGenerateContent
[OK] gemini-3.1-flash-lite: name=models/gemini-3.1-flash-lite, supported_actions=generateContent, countTokens,createCachedContent, batchGenerateContent
RESULT: SUCCESS
```
Both approved model IDs are accessible with the project key, so no model change is needed.

The user also initialized a git repository in the project directory. It had no commits at the time of Interaction 5.

---

## Interaction 5: Single-shot generator, design then implementation

- **Date:** 2026-09-26

### 5a. Design request (no code)
**Direction given to the agent (summarized):**
- Design, but don't implement, the single-shot generator:
  - spec loading and validation (`id, product_image, geography, season, required_text`);
  - a prompt built from the three text fields;
  - the reference image and prompt sent to `gemini-3.1-flash-image`;
  - a 1K output request, then image extraction;
  - a local long-edge ≤ 1024 check;
  - saving the image and metadata;
  - clear failures for a missing image, missing key, no image returned, API error, or a decode/save error.
- Use the current google-genai **Interactions API**.
- Follow the prompt principles: the reference image is the source of truth; preserve the product; reflect geography and season naturally; render the text exactly; no unrelated claims; generic wording; no hidden product descriptions.
- Deliver sections A–H (structure, responsibilities, request flow, prompt, metadata, errors, offline tests, example), then stop.

**What the agent found in the installed SDK (google-genai 2.25.0, read offline):**
- `client.interactions.create(model=..., input=[...content blocks...], response_modalities=[...], response_format=..., store=...)` returns an `Interaction` with the helper fields `status`, `output_image` (base64 `data`, `mime_type`) and `output_text`.
- `generation_config.image_config` is **deprecated**. The current way is `response_format={"type": "image", "image_size": "1K", "aspect_ratio": ..., "delivery": "inline"}`.
- SDK errors are translated into `google.genai.errors.APIError`.
- Both approved model IDs appear in the SDK's list of known model names.
- **Flagged:** "1K" does not guarantee a long edge ≤ 1024. Earlier Gemini image models' size tables give non-square outputs at 1K a longer edge (e.g. 16:9 ≈ 1376×768). The local resize is therefore needed for compliance, not only as a safety net.

**User decisions on the design:**
- Approved, with two changes:
  1. **No `MAX_TEXT_CHARS = 80` limit.** `required_text` only has to be non-empty, because the problem statement requires freeform text. Long text may produce a warning but must never make generation fail.
  2. **Keep the global 1:1 aspect ratio as configuration.** It is not a fifth spec input.
- Accepted as proposed:
  - `response_modalities=["image","text"]`,
  - `store=False`,
  - `outputs/` git-ignored,
  - `adgen/` package run with `python -m adgen.cli`.

### 5b. Implementation
**Direction given to the agent (summarized):**
- Implement only single-shot generation, following the approved design.
- Files: `adgen/{__init__,config,errors,spec,prompt,image_io,generator,cli}.py`, `specs/example.json`, `tests/test_{spec,prompt,image_io,generator}.py`, plus the `.gitignore` update.
- Explicitly out of scope: no evaluator, no retry, no batch, no RAG/agents/MCP/frameworks, no reuse of prior prototypes.
- Requirements:
  - validate the reference image before the API call;
  - send it as explicit base64 + MIME, keeping the original bytes;
  - never put the API key in metadata, logs, exceptions or outputs;
  - save atomically;
  - all tests run offline with a fake client.
- Run pytest. Exercise the CLI without calling Gemini unless necessary.

**What was built:**

| File | Purpose |
|---|---|
| `adgen/config.py` | Model ID, `IMAGE_SIZE="1K"`, `ASPECT_RATIO="1:1"`, `MAX_LONG_EDGE=1024`, `LONG_TEXT_WARNING_CHARS=80` (warning only), output directory |
| `adgen/errors.py` | `GenerationError` base with `SpecError`, `ConfigError`, `GenerationAPIError`, `NoImageReturnedError`, `OutputProcessingError`; `redact()` helper |
| `adgen/spec.py` | Frozen `GenerationSpec`. Rejects missing or unknown fields, empty or non-string values, unsafe `id` (used as a directory name), and a missing image file. Text is kept exactly as given. `spec_warnings()` flags long text without failing |
| `adgen/prompt.py` | The approved template, filled from the three text fields only |
| `adgen/image_io.py` | Validates the reference image (PNG/JPEG/WEBP, format detected from content, not extension) and builds the `{"type":"image","mime_type","data":base64}` block. Decodes the output, resizes proportionally when needed (1376×768 → 1024×571, rounding down), leaves in-limit images byte-identical, and saves atomically (temp dir, then rename) |
| `adgen/generator.py` | The only module that uses the network. Builds the request, calls `client.interactions.create`, translates errors with redaction, checks `status == "completed"` and that `output_image` is present, then writes metadata |
| `adgen/cli.py` | `python -m adgen.cli <spec> [--dry-run]`. Validates offline first, then checks the key, then generates |

**Metadata fields:**
- exact inputs,
- reference image SHA-256 and MIME type,
- exact prompt,
- model,
- request config,
- interaction id, status and model text,
- raw and saved resolution,
- whether the image was downscaled,
- warnings,
- UTC timestamp, duration, SDK version.

**Other additions:**
- The agent added `--dry-run` to the CLI, a small addition beyond the design. It validates the spec, prints the prompt and makes no API call, so config handling can be checked without spending a generation.
- `.gitignore` now excludes `outputs/`.

**Results:**
- `python -m pytest`: **63 passed**, offline, no key needed (fake client; test images created in temporary folders).
- CLI checks, no Gemini call made:

| Case | Result |
|---|---|
| `specs/example.json` | `SpecError` (reference image `inputs/products/sneaker.png` not supplied yet), exit 1 |
| No arguments | argparse usage error, exit 2 |
| `--dry-run` on a temporary image | spec OK, prompt printed, exit 0 |
| `GEMINI_API_KEY` empty | `ConfigError`, exit 1 |

- **No Gemini call was made in this interaction.** The first real generation is left for the user to trigger once a reference image is in place.

**Known limitations / deferred:**
- The first live call still has to confirm that the API accepts `response_modalities=["image","text"]` together with the image `response_format`. If it doesn't, the change will be logged.
- Tests must be run as `python -m pytest` from the project root, so that `adgen` can be imported. There is no pytest config file.
- Not started: evaluator, quality gate and retry, batch of about 20, golden dataset.

---

## Interaction 6: Live smoke test, blocked (no reference image)

- **Date:** 2026-09-26
- **Direction given to the agent (summarized):**
  - Run exactly one real Gemini smoke test: `python -m adgen.cli specs/example.json` with Tokyo, Japan / Winter / "Step Into Winter".
  - First check that `inputs/products/` contains a real reference product image.
  - If it doesn't, stop and tell the user which file to add. Do not invent or generate a replacement.
  - No retries, and no evaluator, retry or batch work.
- **Result:** `inputs/products/` does not exist, so there is no reference image. The agent stopped before the API call.
  - No Gemini call was made.
  - No image was created.
  - No code was changed.
- **Waiting on:** the user adds a real product photo at `inputs/products/sneaker.png`, or tells the agent another filename to put in `specs/example.json`.

---

## Interaction 7: Live smoke test

- **Date:** 2026-09-26

### Direction given to the agent (summarized)
- The reference image is `inputs/products/sneaker.jpg` (supplied by the user). Change only `product_image` in `specs/example.json`.
- Make exactly one real generation call: `python -m adgen.cli specs/example.json` with Tokyo, Japan / Winter / "Step Into Winter".
- If the API request itself fails: make the smallest correction, log it, and rerun once.
- Report observations only, with no pass/fail judgment. No prompt tuning, and no evaluator, retry or batch work.

### Reference image, as the agent saw it
- A pair of light-blue patent-leather low-top sneakers with dark-blue laces and a ribbed blue sole.
- A yellow **elongated four-pointed star** on the side, and a yellow tab on the tongue.
- **"COMET"** branding on the tongue label and the insole.
- The pair is shown on a shoe box on a tiled floor.

### Attempt 1: API rejected the request (no image generated)
- **Error:** `GenerationAPIError: Gemini request failed: BadRequestError: Error code: 400 - {'error': {'message': 'Image delivery mode is not supported.', 'code': 'invalid_request'}}`, exit 1.
- **Cause:** `response_format` contained `"delivery": "inline"`. The field exists in the SDK 2.25.0 type (`ImageResponseFormatParam.delivery`), but the live API rejects it for this model.
- **Correction (smallest possible):**
  - removed the `delivery` key from `response_format` in `adgen/generator.py`, with a comment explaining why;
  - removed its copy from the metadata `request` block.

  Nothing else changed: same model, `image_size="1K"`, `aspect_ratio="1:1"`, same modalities, same prompt.
- **Side observation, not fixed:** this 400 arrived as the SDK's internal `BadRequestError`, not as `google.genai.errors.APIError`. It was therefore caught by the generic handler: the message was clear and redacted, but the `code`/`status` attributes were not filled in. This is noted for later and was deliberately not changed now.

### Attempt 2: success (after the one allowed rerun)
- **Command:** `python -m adgen.cli specs/example.json`, exit 0.
- **Output:** `outputs/sneaker-tokyo-winter/20260926T060958_761600Z/ad.jpg` (JPEG, **1024×1024**, 808 KB) plus `metadata.json`.

**Metadata:**

| Field | Value |
|---|---|
| model | `gemini-3.1-flash-image` |
| request | `image_size` 1K, `aspect_ratio` 1:1, modalities `[image, text]`, `store` false |
| status | `completed` |
| response mime_type | `image/jpeg` |
| raw / saved resolution | 1024×1024 / 1024×1024 (downscaled false) |
| duration | 11.9 s |
| reference SHA-256 | `9bed45b6…030f` |
| warnings | none |
| model_text | "I have captured the vibrant colors of your sneakers in a winter-themed setting for the Tokyo market." |
| interaction_id | `""` (empty; probably because `store=False`, since the request is not kept server-side) |

### Observations (not a pass/fail evaluation)
- **Text:** "Step Into Winter" appears once, top right, in a large white serif font on two lines ("Step Into" / "Winter"). The spelling and capitalization appear exact. No slogan, price or claim was added.
- **Product, what was kept:**
  - light-blue glossy patent upper, dark-blue laces, blue ribbed sole;
  - perforated toe box and overall low-top shape;
  - the pair is still placed on a shoe box, echoing the reference.
- **Product, what changed:**
  - The yellow side graphic became a **five-pointed star with a lightning-bolt tail**, instead of the reference's elongated four-pointed star. It now resembles a well-known third-party sneaker brand's star-and-bolt logo, i.e. branding that is not in the reference.
  - The tongue label text is small and not clearly legible as "COMET" (it looks partly garbled).
  - The yellow tongue tab is not clearly visible.
  - The insole branding is not visible from this angle.
- **Context:**
  - **Winter:** strongly shown (falling snow, snow piles, frosted glass, an ice-textured box).
  - **Tokyo:** only weakly shown: a generic night street with blurred signage and no identifiable Tokyo landmarks.
  - **Cherry blossoms:** the scene includes snow-covered blossoms, a Japan cue that is normally associated with spring rather than winter.
- **Unexpected text or branding:** the changed star-and-bolt side logo (above); faint letter-like shapes in the box pattern; blurred background signs with no readable text.

These observations are inputs for designing the evaluator, especially for product-fidelity checks on logos and branding. **No prompt or generation change was made because of them.**

### Tests afterwards
`python -m pytest -q`: **63 passed**. The offline tests did not assert the `delivery` field, so no test change was needed.

---

## Interaction 8: Baseline failure recorded, evaluator design (no code)

- **Date:** 2026-09-26

### Human assessment of the first live output (user's words, summarized)
The user compared `outputs/sneaker-tokyo-winter/20260926T060958_761600Z/ad.jpg` with the reference image and classified the observations. This is a **human correction of emphasis**: the agent had reported observations neutrally, and the user ruled that the emblem and branding changes are failures, not stylistic variation.

| Observation | User's classification |
|---|---|
| Shape, light-blue color, blue laces and sole preserved | reasonably well preserved |
| Yellow side emblem changed from an elongated four-point star to a different star/lightning mark | **product-fidelity failure** |
| "COMET" tongue branding distorted or garbled | **product-fidelity failure** |
| Tokyo shown only by a generic urban night scene | **context-adherence issue** (weak geography) |
| Snow-covered cherry blossoms | **context-adherence issue** (conflicting seasonal cue) |
| Strong winter cues | good |
| "Step Into Winter" once, matches the wording, no meaningful extra ad text | **text-rendering success** |

The user required that the evaluator tell these categories apart instead of collapsing them into one visual-similarity score. Generator prompt and code stay **unchanged**.

### Direction given to the agent
- Continue with the evaluator **design** only, using these observations as rubric anchors and examples.
- No Gemini call, no code changes, no evaluator implementation, no retry, no batch.
- **Flagged by the agent:** the "evaluator DESIGN prompt I previously provided" never reached this session. The design was therefore based on `REQUIREMENTS.md`, `CLAUDE.md`, the approved principles and this baseline, and the user was asked to paste the original prompt if it had specific sections.

### SDK finding (offline)
The Interactions API supports structured JSON output with `response_format={"type": "text", "mime_type": "application/json", "schema": {...}}`. `GenerationConfig` in 2.25.0 has `seed` but no temperature field.

### Design summary (proposed, awaiting approval)
- **Split responsibilities:** the evaluator model only *observes* (transcribes text, compares listed product attributes, lists context cues, all with categorical labels plus evidence). Deterministic Python *decides* PASS/FAIL using named rules and reason codes.
- **Four checks:**
  1. technical (deterministic only),
  2. text rendering,
  3. product fidelity (attribute by attribute, driven by a reference-attribute profile extracted from the reference image),
  4. context adherence (geography and season rated separately, with conflict detection).
- No single similarity score. See the chat response for the full design and the decisions still open.

---

## Interaction 9: Evaluator design revised per user changes (no code)

- **Date:** 2026-09-26

### User changes to the design (summarized)
1. **Call count:** 1 profile call per unique product (only if no profile exists) plus **1 combined** evaluator call per image, with three independent sections (text, product, context). Split into separate calls only if evidence later shows the combined call is unreliable.
2. **Reference profile:** a model draft is *not* trusted. Workflow: draft → human review → approved `reference_profile.json` with `"human_verified": true`, which the evaluator then uses. It must capture the sneaker's yellow side emblem geometry, COMET branding, colors, material and silhouette. The generator never uses it.
3. **Product reason codes, no double counting:**
   - reference mark changed → `PRODUCT_MARK_ALTERED`
   - reference mark absent → `PRODUCT_MARK_MISSING`
   - genuinely new mark → `PRODUCT_BRANDING_ADDED`
   - distorted branding text → `PRODUCT_BRANDING_DISTORTED`
4. **Context strictness:** kept as proposed. It is explicitly marked as an **engineering decision** (not an official requirement) and stored in versioned rules, to be calibrated later against the golden set. A landmark is not required; several location-specific cues can establish geography.
5. **No `seed`** (or any other unverified request field), because the live API already rejected the SDK-listed `delivery` field.
6. **Response shape:** structured output `{schema_version, text, product, context}`, containing observations only, with no model-issued PASS/FAIL.
7–9. **Section contents:**
   - product: per-attribute and per-branding statuses, `same_product`, added marks, evidence;
   - text: literal transcription with roles, with Python doing all comparisons;
   - context: separate geography and season, each with cues, rating and conflicts.
10. **Gate:** overall PASS only if technical, text, product and context all pass. Malformed or missing evaluator output = ERROR, never PASS. Every failure carries reason codes.
11. **Offline test list** (14 cases), using the real smoke-test observations as a known-failure fixture.
12. No API call, retry, batch, generator change or dataset yet.

### Agent checks (offline)
- `TextResponseFormat` accepts both `schema` and `schema_` and sends `schema`. It has `extra='allow'`, so unknown fields are passed through, which explains why `delivery` was only rejected by the live API.
- `seed` is left out because it cannot be verified without a live call.

### Agent design choices introduced in this revision (for review)
- **Required text hidden from the model:** the evaluator model is *not told* `required_text`, to avoid confirmation bias in literal transcription.
- **Profile criticality hidden from the model:** `critical` flags are used only by the Python rules.
- **Added-mark de-duplication:** each added mark carries `possible_reference_counterpart_id`. If it names a profile mark, Python reclassifies it as `PRODUCT_MARK_ALTERED` instead of `PRODUCT_BRANDING_ADDED`.
- **Profile lookup:** by reference-image SHA-256, so no new spec field is needed.
- **Technical failure:** skips the model call.
- **Smoke-test fixture:** hand-built from the human observations and labeled as such. It is **not** a recorded model response, because no evaluator call has been made.

---

## Interaction 10: Evaluator implemented, profile draft created

- **Date:** 2026-09-26

### Direction given to the agent (summarized)
- **Final design change:** `same_product = "partially"` → FAIL `PRODUCT_DESIGN_DEVIATION`, and `"no"` → FAIL `PRODUCT_REPLACED`. Documented as an **engineering decision**, a safety net that sits behind the attribute-level evidence.
- **Scope:** implement the evaluator exactly as designed:
  - `adgen/evaluator/{__init__,policy,schemas,prompts,profile,judge,rules,evaluate,cli}.py`,
  - a `profiles/` directory,
  - tests,
  - a small config change.
- **Requirements:**
  - Interactions API, `gemini-3.1-flash-lite`, one combined call per image;
  - the profile draft is a separate one-time call, and unverified profiles are never used;
  - the model never receives `required_text` or `critical` flags;
  - Python decides; malformed output = ERROR;
  - no `seed` or `delivery`;
  - raw response, rules version and policy snapshot saved; key kept out of all files.
- **Order:** implement, run offline tests, show the result, then make **one** live profile-draft call. Show the draft, do not verify it, do not evaluate the ad, and stop.
- Unchanged: the generator, retry, batch and dataset.

### What was built

| File | Purpose |
|---|---|
| `adgen/config.py` | Added `EVALUATOR_MODEL = "gemini-3.1-flash-lite"` and `PROFILES_DIR`. No generator behavior change |
| `adgen/evaluator/__init__.py` | `EvaluationError(code, message)` |
| `policy.py` | `RULES_VERSION = "1"`. All engineering-decision settings (text strictness, same_product codes, critical-attribute codes, branding fail statuses, insufficient-evidence rule, context pass ratings, conflict prominence). `snapshot()` |
| `schemas.py` | The response schema sent to the API (profile ids as enums; only `object`/`array`/`string`/`integer`/`enum`/`required`) and strict local validators. Errors map to `EVAL_MISSING_SECTION`, `EVAL_INCOMPLETE_COVERAGE` (ids missing, unknown or duplicated), `EVAL_MALFORMED_RESPONSE`, `EVAL_INVALID_PROFILE` |
| `prompts.py` | The approved evaluator prompt word for word, and the profile-draft prompt (plus one added sentence: "Use short snake_case ids."). `model_visible_profile()` strips the `critical` flags and review fields |
| `judge.py` | The only network code. Request = `model`, `input`, `response_format={"type":"text","mime_type":"application/json","schema":...}`, `store=False`. Errors → `EVAL_API_ERROR` (redacted). `request_summary()` replaces image base64 with its length |
| `profile.py` | Loads the approved profile by reference SHA-256 and skips `*.draft.json`. Rejects `human_verified != true`. Writes the draft with default critical flags by kind (flagged for review) and never overwrites |
| `rules.py` | Technical, text, product and context rules plus the gate. A check's verdict is derived from its reasons, so every FAIL has at least one code |
| `evaluate.py` | Runs one run directory and writes `evaluation.json`. Refuses to overwrite unless `overwrite=True`. A technical FAIL skips the model call |
| `cli.py` | `draft-profile <image> [--name]` and `evaluate <run_dir> [--overwrite]` |

### Fix made during implementation
The first version of the text rule ignored a punctuation-only remainder, so "Step Into Winter!" would have **passed**. That contradicts the approved "punctuation counts" rule. It was changed so that:
- a punctuation-only remainder → `TEXT_MISMATCH`;
- a remainder containing words → `TEXT_EXTRA_AD_COPY`.

A test covers this.

### Tests (offline, fake clients, no key)
New files: `tests/conftest.py`, `tests/fixtures/{sneaker_profile_test.json, smoke_test_observations.json}`, `tests/test_eval_{rules,schemas,profile}.py`, `tests/test_evaluate.py`, `tests/test_separation.py`.

Coverage includes:
- all 15 designed cases;
- `same_product` partially → FAIL;
- an oversized or unreadable image → zero model calls;
- the request contains no `required_text`, no `critical` and no `seed`/`delivery`;
- drafts and unverified profiles → ERROR with zero calls;
- the raw response is kept even when malformed;
- the key is redacted;
- no overwrite;
- a changed reference on disk → ERROR;
- the generator does not import the evaluator (checked in a separate subprocess).

`python -m pytest -q`: **144 passed** (63 existing + 81 new). The first run had 1 failure, caused by the agent's own separation test matching a *comment* in `config.py`; the test was fixed to look for imports.

### Live call: profile draft (the only live call in this interaction)
- **Command:** `python -m adgen.evaluator.cli draft-profile inputs/products/sneaker.jpg --name sneaker`, exit 0.
- **Result:** `profiles/sneaker.draft.json`, `human_verified: false`, model `gemini-3.1-flash-lite`, 2026-09-26T06:54:24Z. This confirms the live API accepts `response_format` with a JSON schema for this model and image input.
- **Draft content:**
  - 6 attributes: `silhouette`, `colorway`, `star_emblem`, `tongue_detail`, `eyelets`, `insole_art`;
  - 2 branding items: `tongue_label` "comet", `insole_text` "comet".
- **Agent's review observations (for the human, not applied):**
  - the emblem description lacks the long lower point;
  - one combined `colorway` attribute;
  - the lace color is inconsistent between two attributes;
  - toe perforations, the yellow tongue tab and the ribbed sole are missing;
  - branding text is lowercase;
  - the insole items were marked critical by the default rule.
- **Not done, as instructed:** the draft was not verified, no approved profile was written, and **the ad was not evaluated**. Waiting for the user's review.

---

## Interaction 11: Human review, trusted sneaker profile approved

- **Date:** 2026-09-26
- **Human review:** Soumik Datta reviewed `profiles/sneaker.draft.json` against `inputs/products/sneaker.jpg` and supplied the corrected, human-verified profile content. The evaluator implementation (144 offline tests) was approved.
- **Direction given to the agent (summarized):** create only `profiles/sneaker.json` from the supplied content:
  - keep the reference path, SHA-256 and `profile_version = 1`;
  - set `human_verified: true`, `verified_by: "Soumik Datta"` and `verified_at` to the current UTC date;
  - add concise review notes;
  - leave the draft unchanged;
  - no rule, generator or API changes, and do not evaluate the ad yet.

### Corrections made by the human reviewer (draft → approved)

| Area | Draft | Approved |
|---|---|---|
| Side emblem | "Four-pointed elongated yellow star logo" | `side_emblem`: asymmetric, with a vertically elongated lower point toward the sole and a shorter horizontal point. Explicitly "should not be replaced by a conventional five-point star" |
| Colorway | one combined `colorway` attribute | split into `upper` (critical), `sole` (critical) and `laces` (non-critical, royal-blue flat) |
| Missing details | none | added `toe_perforations`, `tongue_tab` and `sole_sidewall_texture` (all non-critical) |
| Removed entries | `insole_art` (marked critical by the default rule) and `eyelets` (which contradicted the lace color) | removed |
| Branding | "comet" / "comet", both critical | "COMET" / "COMET"; `insole_text` set non-critical |
| Category | "sneakers" | "pair of low-top sneakers" |
| Silhouette | — | reworded (padded tongue/collar, thick flat cupsole) |

The approved profile has 8 attributes (4 critical: silhouette, upper, sole, side_emblem) and 2 branding items (critical: tongue_label).

### Agent actions
- Wrote `profiles/sneaker.json`:
  - `human_verified: true`, `verified_by: "Soumik Datta"`, `verified_at: "2026-09-26"`;
  - 4 review notes;
  - `"derived_from_draft": "profiles/sneaker.draft.json"` for traceability. This is an extra field; the loader ignores unknown keys.
- `profiles/sneaker.draft.json` was left unchanged (still `human_verified: false`).
- Offline check, no API call: `load_approved_profile(<sha of sneaker.jpg>)` loads `sneaker.json` and it passes validation.
- `python -m pytest -q`: **144 passed**.
- No Gemini call. No evaluator, rule or generator change. **The ad has not been evaluated yet.**

---

## Interaction 12: First live evaluator run (smoke-test ad)

- **Date:** 2026-09-26
- **Direction given to the agent (summarized):**
  - Run exactly one live Flash-Lite evaluation: `python -m adgen.evaluator.cli evaluate outputs/sneaker-tokyo-winter/20260926T060958_761600Z`, using the approved `profiles/sneaker.json` and the existing ad and metadata.
  - No new generation, no automatic retry, and no code, profile, rule, prompt or generator change based on the result.
  - Report the actual evaluator behavior without editorializing, compared with the human-observed baseline facts. Then run pytest.

### Run
- **Exit code:** 1 (the CLI returns non-zero for any verdict other than PASS).
- **Model:** `gemini-3.1-flash-lite`. One call, **6.6 s**. No API or SDK issue.
- **Request fields:** `model`, `input`, `response_format` (JSON schema) and `store` only.
- **Output:** `evaluation.json` written in the run directory, with the raw response saved verbatim (`raw_response`), `rules_version` "1", the policy snapshot, the profile reference (`sneaker.json`, human_verified, Soumik Datta) and the request summary.

### Deterministic verdicts

| Check | Verdict |
|---|---|
| Technical | PASS (1024×1024) |
| Text | PASS |
| Product | FAIL |
| Context | FAIL |
| **Overall** | **FAIL** |

**Reason codes, in order:**
1. `PRODUCT_COLOR_MATERIAL_ALTERED` (sole)
2. `PRODUCT_MARK_ALTERED` (side_emblem)
3. `PRODUCT_BRANDING_DISTORTED` (tongue_label)
4. `PRODUCT_DESIGN_DEVIATION`
5. `CONTEXT_GEO_WEAK`
6. `CONTEXT_SEASON_CONTRADICTORY`
7. `CONTEXT_SEASON_CONFLICT`

### Model observations compared with the human baseline (facts only)

| Baseline fact | Evaluator output |
|---|---|
| Altered yellow side emblem | **Detected.** `side_emblem: altered`, "The emblem is a five-pointed star rather than the reference four-pointed asymmetric emblem." |
| Distorted COMET branding | **Detected.** `tongue_label: legible_different`, observed "JOMET", "Text on the tongue patch is JOMET, not COMET." |
| Winter cues strong | Cues listed ("Snow on the ground", "Frost-covered window glass", "Snow particles in the air"), but the season was rated **`contradictory`**, not `strong`. This produced `CONTEXT_SEASON_CONTRADICTORY` in addition to the conflict code |
| Tokyo cues weak | **Detected.** `geography: weak`. Cue: "Architecture and signage visible through the window suggest an urban setting, possibly East Asian style buildings." |
| Prominent cherry blossoms conflict | **Detected.** Conflicting cue "Cherry blossoms on the branches outside the window", prominence `prominent`, "Cherry blossoms are a classic indicator of Spring, not Winter." |
| "Step Into Winter" once | **Detected.** Transcribed "Step Into Winter" as `headline_or_ad_text`, 1 occurrence, similarity 1.0 |
| No extra ad copy | **Detected.** No other ad-text items (the only other text is "JOMET" as `product_branding`) |

### Evaluator findings that differ from the human baseline (reported, not corrected)
- **Sole:** `sole: altered`, "Medium-blue rubber cupsole, color matches, but missing the distinctive ribbed/textured vertical sidewall detail." `sole` is critical, so this gave `PRODUCT_COLOR_MATERIAL_ALTERED`. The human baseline had said the blue sole was "preserved reasonably well".
- **Sidewall texture:** `sole_sidewall_texture: missing`, "The sidewall is smooth instead of ribbed/textured." Non-critical, so recorded only.
- **Tongue tab:** `tongue_tab: altered`, "…lacks the specific yellow tab detail." Non-critical, so recorded only.
- **Profile overlap:** the same sidewall observation shows up under two profile attributes. The `sole` description includes "textured/ribbed vertical sidewall", and there is also a separate `sole_sidewall_texture` attribute. This is a fact noted for later calibration; nothing was changed.
- **Other product outputs:** `same_product: partially` → `PRODUCT_DESIGN_DEVIATION`, evidence cites the emblem shape and "JOMET vs COMET". `genuinely_added_marks_or_logos` was empty, so no reclassification was needed and nothing was double-counted.
- **Compared with the hand-built smoke fixture's expected codes:** the live run produced the same 5 codes plus `PRODUCT_COLOR_MATERIAL_ALTERED` and `CONTEXT_SEASON_CONTRADICTORY`.

### Afterwards
- `python -m pytest -q`: **144 passed**.
- No further Gemini calls. No code, profile, rule, prompt or generator changes.

---

## Interaction 13: Profile correction to avoid double-counting sole texture

- **Date:** 2026-09-26
- **Human decision (Soumik Datta):**
  - **Accepted:** the live evaluator validation (Interaction 12) is accepted.
  - **Problem:** the missing ribbed sidewall was counted twice: once under the critical `sole` attribute (→ `PRODUCT_COLOR_MATERIAL_ALTERED`), and once under the non-critical `sole_sidewall_texture`.
  - **Fix:** a profile-only correction:
    - `sole` description changed from "Medium-to-dark blue rubber cupsole with a textured/ribbed vertical sidewall." to **"Medium-to-dark blue rubber cupsole."**
    - `sole_sidewall_texture` stays unchanged and non-critical.
- **Agent actions:**
  - Edited `profiles/sneaker.json`: the `sole` description, plus one dated `review_notes` entry recording the correction and its reason.
  - Kept `human_verified: true`, `verified_by` and `verified_at` as they were.
  - Did not change the reference path or SHA, branding, critical flags, the evaluator prompt or rules, or the generator.
  - Offline check: `load_approved_profile` still loads and validates the profile.
- **Tests:** no offline test uses `profiles/sneaker.json` (they use `tests/fixtures/sneaker_profile_test.json`), so no test change was needed. `python -m pytest -q`: **144 passed**.
- **Note for traceability:** the existing `outputs/sneaker-tokyo-winter/20260926T060958_761600Z/evaluation.json` was produced with the **previous** `sole` description and is kept as the record of that run. Re-evaluating with the corrected profile would need a new live call (`--overwrite`), which was not done.
- No Gemini API call was made.

---

## Interaction 14: Golden dataset for evaluator validation (offline)

- **Date:** 2026-09-26

### Direction given to the agent (summarized)
- Design and implement a small, controlled golden dataset proving that the evaluator separates PASS from FAIL.
- Keep **real Gemini outputs**, **hand-edited fixtures** and **hypothetical labels** clearly separate, and never present fixtures as Gemini outputs.
- **Minimum cases:** known-good, the real baseline failure, altered emblem, garbled COMET, misspelled text, extra ad copy, weak geography, conflicting season, multiple failures.
- **For fixtures:** reuse the real baseline image, use deterministic edits, and record for each one the source, transformation, expected failure mode, expected gate result and source type.
- Write a manifest.
- **Out of scope:** no Gemini calls, no new generations, no retry or batch, no policy, prompt or generator changes. The historical evaluation stays untouched.

### Design decisions (agent)
- **What a case is:** image (if any) + observations (the evaluator-response JSON) + a **hand-written** expected outcome.
- **What the offline tests do:** replay the observations through the unchanged deterministic rules. Expected outcomes are written out in `scripts/build_golden.py` and are **never computed by the rules**, so the tests are not circular.
- **The three source types:**
  - `real_gemini_output`: the real baseline only. Image and metadata are **copied** into `golden/real/…` because `outputs/` is git-ignored; the originals are untouched. Observations are the **verbatim recorded live evaluator response**. A human label from Interaction 8 is included, and the known disagreements (sole; season rated `contradictory`) are recorded rather than hidden.
  - `edited_fixture`: deterministic Pillow edits of the real image. Transformation parameters and source/target SHA-256 are recorded. They are explicitly "NOT a Gemini output" and **inherit all the product/context defects of the real image**, so their expected outcomes include those codes. The product and context observations are copied from the recorded response, since those image regions are unchanged; only the text section is hand-edited.
  - `hypothetical`: no image. Hand-authored observations against `profiles/sneaker.json`, used to isolate single failure modes and provide PASS cases.
- **Why no real PASS case:** no real passing output exists yet, and generating one was out of scope. Known-good is therefore hypothetical, and a real PASS case is still to come.

### Files
- `scripts/build_golden.py`: deterministic, offline builder (copies, edits, observations, manifest).
- `golden/manifest.json`: 13 cases.
- `golden/real/sneaker-tokyo-winter_20260926T060958_761600Z/{ad.jpg, metadata.json, evaluation.json}`: verbatim copies. The copied `evaluation.json` has the same SHA-256 as the original (`590c3f1a…`).
- `golden/edited/{edited_misspelled_text.jpg, edited_extra_ad_copy.jpg}`
- `golden/observations/*.json`: 13 files.
- `tests/test_golden.py`

Total size: 1.5 MB.

### Cases (expected outcomes)

| Case | Source | Expected overall | Expected reason codes |
|---|---|---|---|
| `real_baseline` | real | FAIL | `PRODUCT_COLOR_MATERIAL_ALTERED`, `PRODUCT_MARK_ALTERED`, `PRODUCT_BRANDING_DISTORTED`, `PRODUCT_DESIGN_DEVIATION`, `CONTEXT_GEO_WEAK`, `CONTEXT_SEASON_CONTRADICTORY`, `CONTEXT_SEASON_CONFLICT` |
| `edited_misspelled_text` | edited | FAIL | `TEXT_MISMATCH` + the 7 real-baseline codes |
| `edited_extra_ad_copy` | edited | FAIL | `TEXT_EXTRA_AD_COPY` + the 7 real-baseline codes |
| `hyp_known_good` | hypothetical | PASS | none |
| `hyp_minor_season_conflict` | hypothetical | PASS | none (minor conflict recorded only) |
| `hyp_altered_emblem` | hypothetical | FAIL | `PRODUCT_MARK_ALTERED`, `PRODUCT_DESIGN_DEVIATION` |
| `hyp_garbled_branding` | hypothetical | FAIL | `PRODUCT_BRANDING_DISTORTED` |
| `hyp_added_logo` | hypothetical | FAIL | `PRODUCT_BRANDING_ADDED` |
| `hyp_misspelled_text` | hypothetical | FAIL | `TEXT_MISMATCH` |
| `hyp_extra_ad_copy` | hypothetical | FAIL | `TEXT_EXTRA_AD_COPY` |
| `hyp_weak_geography` | hypothetical | FAIL | `CONTEXT_GEO_WEAK` |
| `hyp_conflicting_season` | hypothetical | FAIL | `CONTEXT_SEASON_CONFLICT` |
| `hyp_multiple_failures` | hypothetical | FAIL | `TEXT_MISMATCH`, `PRODUCT_MARK_ALTERED`, `PRODUCT_BRANDING_DISTORTED`, `PRODUCT_DESIGN_DEVIATION`, `CONTEXT_GEO_WEAK`, `CONTEXT_SEASON_CONFLICT` |

### Tests (`tests/test_golden.py`, 49 tests)
- **Manifest integrity:** every case has an explicit expected outcome (overall, per-check, ordered reasons), and PASS ⇔ no reasons. Image presence matches the source type, and images have a long edge ≤ 1024.
- **Core claim:** for each case, the rules reproduce the expected overall verdict, the per-check verdicts and the exact ordered reason list.
- **Coverage:** both PASS and FAIL are present; multi-failure cases keep ≥ 3 reasons across ≥ 2 failing checks; all required failure modes are covered.
- **Honesty:**
  - only `real_baseline` is `real_gemini_output`, and every other case has hand-authored observations;
  - the real case's observations equal the historical `raw_response` exactly;
  - replaying them reproduces the historical verdict and reasons;
  - check-level agreement with the human label holds, and the human-expected codes are a subset of the replayed codes;
  - the image SHA matches the provenance record and, when present, the original run;
  - edited fixtures reference the real image's SHA, record their transformation and are labeled "NOT a Gemini output".
- **Result:** `python -m pytest -q`: **193 passed** (144 + 49), all on the first run.

### Notes
- The copied `metadata.json` contains an absolute local path (the user's Windows home-directory path to `inputs/products/sneaker.jpg`; the path itself was redacted in Interaction 16) in `inputs.product_image`. It was kept verbatim for provenance. The user should decide whether that is acceptable in a public repo.
- The edited-text fixture's blurred headline box is visible as a darker panel. That is acceptable for a text-fidelity fixture but is an obvious edit.
- No Gemini call. No generator, evaluator rule, prompt or profile change. `outputs/…/evaluation.json` is unchanged.

---

## Interaction 15: Golden-dataset path sanitization

- **Date:** 2026-09-26

### Direction given to the agent (summarized)
- Committed golden artifacts must not contain the user's absolute local Windows path. Sanitize such paths to project-relative ones (e.g. `inputs/products/sneaker.jpg`).
- Make `scripts/build_golden.py` do this on every rebuild, and update the committed golden metadata.
- Preserve SHA-256, source type, run identity and all other provenance.
- Do not touch the git-ignored `outputs/` run. No rule, generator or Gemini changes.
- Add an offline test that finds user-specific absolute paths.

### Agent changes
- **`scripts/build_golden.py`:**
  - The JSON copies (`metadata.json`, `evaluation.json`) are now rewritten on every build. They are read from the original run when it is present, otherwise from the existing golden copy, since sanitizing is idempotent.
  - `_sanitize()` walks the JSON. Absolute paths inside the project become project-relative. Any absolute path outside the project, or any embedded user path pattern, **stops the build** instead of being committed.
  - `ad.jpg` is still copied as binary only, so its SHA-256 is preserved (`b4604fde…`).
  - The manifest's `real_baseline.image_provenance` now includes `json_copy_sanitization`:
    - a note;
    - `fields_made_relative` (`["metadata.json.inputs.product_image"]`);
    - `original_sha256` of the unmodified originals (`metadata.json b0381f75…`, `evaluation.json 590c3f1a…`), carried over from the previous manifest when `outputs/` is not present, e.g. in a fresh clone.
- **Committed file:** `golden/real/…/metadata.json` now has `inputs.product_image = "inputs/products/sneaker.jpg"`. It was the only occurrence found in `golden/`.
- **Tests added to `tests/test_golden.py`:**
  - a byte-level scan of **every** file under `golden/` for user-path patterns (`X:\Users\`, `/Users/`, `/home/`);
  - a JSON walk that rejects any absolute-path string;
  - a check that the real metadata path is project-relative and exists, that its reference SHA matches the trusted profile, and that the sanitization record (including original SHAs) is present.

### Verification
- **Tests fail before the fix:** the new tests were run against the unsanitized copy first and failed (3 failures), so they do catch the problem.
- **Rebuild is idempotent:** rebuilt twice with identical results.
- **Originals untouched:** SHA-256 of every file in `outputs/sneaker-tokyo-winter/20260926T060958_761600Z/` is unchanged (diff against hashes taken beforehand).
- `python -m pytest -q`: **229 passed**. The count rose from 193 because the path scan is parametrized per golden file.

### Flagged, not changed
The earlier Interaction 14 entry of this log quotes a partial local path in its "Notes". It was left unchanged because the log is a historical record and the cleanup was scoped to golden artifacts. The user may want it redacted before publishing.

No Gemini call was made.

---

## Interaction 16: AGENT_LOG.md path sanitization

- **Date:** 2026-09-26
- **Direction given to the agent (summarized):**
  - Replace user-specific absolute paths in `AGENT_LOG.md` with project-relative paths, preserving the historical meaning and all disclosure information.
  - Scan the whole log.
  - Add an offline test only if an appropriate test location exists.
  - No code, evaluator, generator or golden-artifact changes. No Gemini calls.
- **Scan result:** one user-specific path, in the Interaction 14 "Notes" bullet. The Interaction 15 bullet listing the generic search patterns (`X:\Users\`, `/Users/`, `/home/`) contains no user name and was left as is.
- **Edit:**
  - The Interaction 14 bullet now says the copied `metadata.json` contained "the user's Windows home-directory path to `inputs/products/sneaker.jpg`", with an inline note that the path was redacted in Interaction 16.
  - The meaning is unchanged: an absolute path was present and the user was asked to decide.
  - No interaction or disclosure content was removed.
- **Test:** added `tests/test_docs_hygiene.py` in the existing `tests/` location.
  - It scans every root `*.md` file (`AGENT_LOG.md`, `CLAUDE.md`, `REQUIREMENTS.md`, the source Markdown files) for a drive or home prefix followed by a user name.
  - It was confirmed to catch the old wording and not to flag the generic pattern list.
- **Result:** `python -m pytest -q`: **234 passed** (229 + 5 docs checks).
- No Gemini call. No application code, evaluator, generator or golden-artifact changes.

---

## Interaction 17: Bounded regeneration loop, design only

- **Date:** 2026-09-26
- **Direction given to the agent (summarized):**
  - Design, but do not implement, the loop: generation → evaluation → deterministic gate → accept on PASS, otherwise a targeted correction and a bounded regeneration.
  - Cover:
    - orchestrator responsibilities;
    - the attempt artifact structure and lineage;
    - correction instructions built from reason codes and evidence, without hard-coded hidden product descriptions;
    - original prompt + correction section;
    - a bounded max-attempt count (an engineering decision, not tuned to pass rate);
    - stopping and error behavior;
    - failure-loop prevention;
    - the offline test matrix;
    - worst-case API usage;
    - integration with the future 20-output experiment;
    - metrics to collect;
    - requirement vs decision separation;
    - the file structure;
    - a worked sneaker example.
  - No code, no Gemini calls, and no changes to the generator prompt, evaluator policy or golden dataset.
- **Agent note:** the user's summary said 229 tests; the current suite is 234 (Interaction 16 added 5 docs checks).
- **Design summary (proposed, awaiting approval):**
  - A new `adgen/pipeline/` package is the only place where the generator and evaluator meet. It holds a pure `correction.py` and a for-loop `orchestrator.py` bounded by `MAX_ATTEMPTS` (proposed 3).
  - **Layout:** `outputs/<spec-id>/<run-id>/attempt-NN/{ad.jpg, metadata.json, evaluation.json, attempt.json}` plus `final.json`.
  - **Retry prompt:** original prompt unchanged + an appended correction section built deterministically from the latest failing reason codes and their evidence.
  - **Stopping:** any ERROR terminates. An unchanged set of failing codes stops as `FAIL_NO_PROGRESS`.
  - **Generator change needed:** two optional `generate()` parameters (target directory, correction section). The default behavior and the base prompt stay unchanged.

---

## Interaction 18: Bounded regeneration pipeline implemented (offline)

- **Date:** 2026-09-26

### User approvals and final changes (summarized)
- **Approved:**
  - `MAX_ATTEMPTS = 3` (configurable), with 1 generator + 1 evaluator call per attempt;
  - immutable inputs;
  - original prompt + appended correction; a deterministic correction builder;
  - evaluator evidence allowed as *observed previous-output evidence*;
  - errors terminate without retry; no-progress detection;
  - lineage + `final.json`; no best-of selection; FAIL outputs never accepted.
- **Final changes:**
  1. **Deduplicate** overlapping codes: a specific product line beats `PRODUCT_DESIGN_DEVIATION`, and season rating + conflict are consolidated into one line.
  2. **Evidence framing:** evidence is always framed as "Observed in the previous generated image". No profile content or critical flags go to the generator.
  3. **Fresh runs:** every run starts with a fresh attempt-01. Interaction 12's evaluation is never reused and never modified.
  4. **Generator compatibility:** only two optional parameters; `generate(spec, client)` behaves identically; the base template is untouched.
  5. **Technical-error semantics:** documented (standalone technical FAIL vs `ERROR_INTERNAL` in the pipeline).
  6. **Correction purity.**
  7. **Input-immutability tests.**
  8. **No hidden retries.**
  9. **Implement:** the listed files.
  10. **Test:** the 16 scenarios plus the sneaker combination.
  11. **No live call.**
  12. **Log it.**

### What was built

| File | Change |
|---|---|
| `adgen/generator.py` | Keyword-only `target_dir=None` and `correction=None`. With the defaults, the prompt, output layout (`outputs/<id>/<timestamp>/`) and metadata schema are unchanged. With `correction`, the prompt is `build_prompt(spec) + "\n\n" + correction`. `prompt.py` is untouched |
| `adgen/config.py` | `MAX_ATTEMPTS = 3` and `MAX_EVIDENCE_CHARS = 200`, labeled as engineering decisions |
| `adgen/pipeline/__init__.py` | Status constants, plus the technical-error semantics documented in the docstring |
| `adgen/pipeline/correction.py` | Pure `build_correction(evaluation, spec, attempt, max_attempts, history)`. Uses only failing reasons from the evaluation's checks, the spec's geography/season/required_text, and evaluator evidence (whitespace-collapsed, double quotes → single, capped at 200 characters, at most 3 quotes per line). It never receives the profile |
| `adgen/pipeline/orchestrator.py` | `run_pipeline(spec, client, output_root, profiles_dir, max_attempts, secret)`. Fresh `run_id` folder (`exist_ok=False`); preflight (reference + approved profile) before any call; a `for` loop over `max_attempts`; per-attempt `attempt.json`; `final.json` written in one step; call counting; no-progress stop and identical-request guard; regressions recorded |
| `adgen/pipeline/cli.py` | `python -m adgen.pipeline.cli <spec> [--max-attempts N]`. An invalid spec or missing key → `ERROR_PREFLIGHT` before any client is created |

**Deduplication rules in `correction.py`:**
- `PRODUCT_DESIGN_DEVIATION` is suppressed if any specific product code or `PRODUCT_REPLACED` is present; otherwise it is kept with its evidence.
- `CONTEXT_SEASON_{WEAK,ABSENT,CONTRADICTORY}` + `CONTEXT_SEASON_CONFLICT` → one seasonal line (the rating codes are listed as suppressed). A rating code on its own → one "did not read clearly as {season}" line.
- One line per code, with each line's evidence items deduplicated.
- Codes that persist across attempts are prefixed "STILL UNRESOLVED since attempt N".

### Tests
New:
- `tests/test_correction.py` (13): the sneaker combination, evidence framing, no profile leakage, purity, both dedup rules, text lines using spec values, recorded-only items excluded, persistence, evidence cap.
- `tests/test_pipeline.py` (21): all 16 designed scenarios.
- `tests/test_generator.py`: +2 backward-compatibility tests.
- `tests/test_separation.py`: now also checks that the generator does not load or reference `adgen.pipeline`.

The fake client is scripted and uses a `BaseException` sentinel, so any call beyond the scripted budget fails the test rather than being swallowed.

`python -m pytest -q`: **269 passed** (234 existing + 35 new), all on the first run.

### Example correction (fake evaluation, offline)
- **Input:** the hand-authored smoke fixture with the season rated `contradictory`, checks produced by the real rules.
- **Codes:** `PRODUCT_MARK_ALTERED`, `PRODUCT_BRANDING_DISTORTED`, `PRODUCT_DESIGN_DEVIATION`, `CONTEXT_GEO_WEAK`, `CONTEXT_SEASON_CONTRADICTORY`, `CONTEXT_SEASON_CONFLICT`.
- **Result:** 4 lines (2 product, 2 context). Suppressed: `PRODUCT_DESIGN_DEVIATION`, `CONTEXT_SEASON_CONTRADICTORY`. 1,489 characters including the header.

### API bound
Worst case per spec: `MAX_ATTEMPTS` generator + `MAX_ATTEMPTS` evaluator calls = **6 at the default of 3**. There are no hidden retries; this is tested for max_attempts 1, 2 and 3.

### Not done, as instructed
- No Gemini call.
- The pipeline CLI was not run against the real sneaker.
- No change to the evaluator policy or prompt, the profile, the golden dataset, or `prompt.py`.

---

## Interaction 19: First live end-to-end pipeline run (max 2 attempts)

- **Date:** 2026-09-26
- **Direction given to the agent (summarized):**
  - Run one fresh live pipeline: `python -m adgen.pipeline.cli specs/example.json --max-attempts 2`.
  - Budget: at most 2 generator + 2 evaluator calls, with no hidden retries.
  - Use the current profile, rules and prompt. Do not reuse the Interaction 12 evaluation. No code, profile, rule or golden changes.
  - Report the actual results without reinterpretation, and make no further calls.
- **Inputs:** `inputs/products/sneaker.jpg` / Tokyo, Japan / Winter / "Step Into Winter".

### Result
- **Run:** `outputs/sneaker-tokyo-winter/20260926T081326_629006Z/`
- **Status:** `FAIL_EXHAUSTED`, final verdict FAIL, accepted attempt none, stop reason `max_attempts_reached`. CLI exit 1.
- **Live Gemini calls (from `final.json` and the CLI):** **generator 2, evaluator 2, total 4.** No API or SDK errors. Run duration 40.8 s.
- **Reason history:**
  1. `[PRODUCT_MARK_ALTERED, PRODUCT_DESIGN_DEVIATION]`
  2. `[PRODUCT_BRANDING_ADDED, PRODUCT_MARK_ALTERED, PRODUCT_BRANDING_DISTORTED, PRODUCT_DESIGN_DEVIATION]`

| Attempt | Generation | Image | Evaluation | Text | Product | Context | Correction applied |
|---|---|---|---|---|---|---|---|
| 1 | OK, 17.0 s | 1024×1024 JPEG, not resized | FAIL, 5.3 s | PASS ("Step Into Winter" ×1) | FAIL | PASS | no |
| 2 | OK, 12.0 s | 1024×1024 JPEG, not resized | FAIL, 6.4 s | PASS ("Step Into Winter" ×1) | FAIL | PASS | yes (from attempt-01) |

**Attempt 1 details:**
- *Product:* `side_emblem` altered, "The emblem is a conventional five-pointed star rather than the reference's asymmetric yellow four-pointed emblem with a downward elongation." `same_product` partially. The tongue label was `legible_correct`; everything else preserved; insole not visible.
- *Context:* geography strong (cues: stone lanterns (tōrō), architecture, "Japanese suburban streets"), season strong.

**Attempt 2 details:**
- *Product:*
  - `side_emblem` altered ("conventional five-pointed star…");
  - `tongue_label` legible_different, read as **"CONET"**;
  - a genuinely added mark: "Text 'ABT' embossed or printed on the lateral heel area of the midsole";
  - `same_product` partially;
  - `sole_sidewall_texture` altered (non-critical, recorded only);
  - `insole_text` legible_correct.
- *Context:* geography strong (cues: Japanese script on signs, e.g. 'サロンパス'; a street scene resembling Shibuya crossing), season strong.
- *Regressions recorded:* `PRODUCT_BRANDING_ADDED`, `PRODUCT_BRANDING_DISTORTED:tongue_label`.
- *No-progress check:* the failing set changed between attempts, so no-progress did not trigger. The run ended at the max-attempt bound.

### Correction appended for attempt 2 (exact text)
```
CORRECTIONS FROM PREVIOUS ATTEMPT (attempt 2 of 2)
The previous generated image was rejected by automated quality checks. Keep everything that was already correct and fix only the issues below. The attached reference image remains the source of truth for the product.
- [PRODUCT] A distinctive mark on the product was changed. Observed in the previous generated image: "The emblem is a conventional five-pointed star rather than the reference's asymmetric yellow four-pointed emblem with a downward elongation.". Reproduce every mark, emblem and logo exactly as in the reference image: same shape, geometry, proportions, color and position. Do not substitute a different or more conventional symbol.
```
- Codes: `[PRODUCT_MARK_ALTERED]`; suppressed: `[PRODUCT_DESIGN_DEVIATION]`; nothing persisting yet.

### Invariants checked on the artifacts
- `spec_sha256` `e1e5995f…`, `reference_image_sha256` `9bed45b6…` and `base_prompt_sha256` `95543213…` are identical in both `attempt.json` files and in `final.json`.
- Both metadata files have geography, season and required text unchanged, and the same reference SHA.
- Attempt 1's prompt SHA equals the base prompt SHA. Attempt 2's prompt equals the base prompt + `"\n\n"` + the correction text.
- Every attempt folder contains `ad.jpg`, `metadata.json`, `evaluation.json` and `attempt.json`, plus `final.json` at run level.

### Observations (factual, not changes)
- **Double period in the correction:** the evaluator evidence ended with a period, so the rendered line reads `…elongation.".` This is cosmetic, in the correction template. Not changed.
- **Evidence mentions the profile:** attempt 2's emblem evidence says "…emblem described in the reference profile". The evaluator model is referring to the profile it was given. That string was **not** sent to the generator in this run; correction text is only generated for a next attempt, and there was none.
- **Real-world signage in attempt 2:** the background shows Japanese signage and billboards, including real-world brand-like names (e.g. 'サロンパス'). The current rubric classifies scene text as `background_incidental` and does not evaluate third-party branding in the background.
- **Emblem in both images:** both show a yellow five-pointed star with a lightning-bolt-style tail on the side panel, consistent with the evaluator's `PRODUCT_MARK_ALTERED` findings.
- **The inspection script,** not the pipeline, hit a Windows console encoding error printing "ō". It was rerun with UTF-8 output; nothing was called again.

### Afterwards
- `python -m pytest -q`: **269 passed**.
- The Interaction 12 `evaluation.json` is unchanged (SHA-256 `590c3f1a…`).
- No further Gemini calls. No code, profile, rule, prompt or golden changes.

---

## Interaction 20: Generation-strategy redesign, analysis only

- **Date:** 2026-09-26
- **User's diagnosis:** the pipeline behaved correctly, but prompt-based regeneration did not fix product drift.
  - Across three live generations the side emblem was redrawn as a five-pointed star with a lightning-bolt tail every time.
  - Branding became JOMET / CONET, and an unrelated "ABT" mark appeared.
  - This is a **generation-strategy problem**, not an evaluator problem.
- **Direction given to the agent (summarized):**
  - Compare three strategies:
    - A: an enhanced product-lock / edit-framed prompt;
    - B: a hybrid, where Gemini generates the scene and the exact reference product pixels are composited in locally;
    - C: a two-stage Gemini flow.
  - Cover 15 dimensions each. Keep the four official inputs, and do not add extra reference photos as inputs.
  - Separate official requirements from engineering decisions.
  - Recommend one strategy, show the revised architecture and list what stays unchanged and what would change.
  - No code, no Gemini calls, and no change to the generator, evaluator, gate, golden dataset or `MAX_ATTEMPTS`.
- **Agent recommendation (proposed, awaiting approval):**
  - **B, the hybrid product-preserving pipeline.** Gemini generates the scene and the headline; a human-verified cutout derived from the single reference image is composited locally without redrawing.
  - The evaluator, gate, profile, golden dataset and loop are kept.
  - Key risks: compositing realism (lighting, perspective, shadow); a one-time cutout step; branding legibility after scaling.

---

## Interaction 21: Strategy B approved; cutout workflow implemented (offline)

- **Date:** 2026-09-26

### Strategy decision (user)
- **Primary quality-controlled strategy: B, the hybrid product-preserving pipeline.**
  - Flow: reference image → human-approved exact-pixel cutout, plus a Gemini-generated advertising scene → deterministic local composition → existing evaluator → existing gate → bounded retry.
  - The existing redraw generator and single-shot CLI stay unchanged as the **documented baseline**.
  - Strategy A (further live prompt experiments) and C (two-stage Gemini) will not be implemented.

### Why redraw was insufficient (live evidence)
- **Emblem:** in all three live redraw generations (Interaction 7 / 12, and Interaction 19 attempts 1–2), the side emblem was regenerated as a five-pointed star with a lightning-bolt-style tail instead of the reference's asymmetric four-pointed emblem.
- **Branding:** it varied between COMET, JOMET and CONET, and an unrelated "ABT" mark appeared.
- **The correction didn't work:** the targeted correction in Interaction 19 did not fix the emblem and was followed by new product regressions, while text and context passed.
- **Conclusion:** the evaluator detected the drift reliably, but asking the model to redraw the product does not reliably preserve it.

### Why hybrid was selected
- It removes the cause: the product's pixels are **preserved and composited, not regenerated**.
- Product fidelity becomes a deterministic invariant that can be tested offline.
- API cost is unchanged: 1 generator + 1 evaluator call per attempt, 6 worst case.
- The evaluator, gate, profile, golden dataset and loop are reused.

### Official requirements vs engineering decisions

**Official (PS2):**
- a display-ad pipeline using Gemini 3.1 Flash (Lite) Image;
- inputs: one reference image + geography + season + required text;
- the context refines the output;
- imperfect text is acceptable but considered;
- long edge ≤ 1K;
- an evaluator over about 20 outputs covering the three metrics;
- tests showing PASS and FAIL.

**Engineering decisions (user-approved):**
- the product is composited, not generated, and this will be stated openly in the Solution Details;
- a manual human-made mask, with no automatic segmentation dependency;
- the cutout is a derived, human-verified artifact linked to the reference by SHA-256, analogous to the profile, **not an extra input**;
- the scene call receives **no** reference image, cutout or profile;
- Gemini renders `required_text`;
- an overhead or near-overhead layout that matches the reference;
- the pixel-identity invariant, where a violation is `ERROR_INTERNAL`;
- product failures remain FAIL in composite mode and are recorded as diagnostics;
- a supplementary **non-gating** integration-quality observation;
- composite retries send only TEXT and CONTEXT corrections;
- `MAX_ATTEMPTS = 3` is unchanged;
- no new official inputs.

### Implemented in this interaction (cutout workflow only)
The user instructed: implement the cutout workflow first, and only if it can be done without inventing the mask.

| File | Purpose |
|---|---|
| `adgen/cutout.py` | `load_mask` (validation), `make_cutout`, `build_draft`, `approve`, `load_approved_cutout`, `verify_lineage` |
| `adgen/cutout_cli.py` | `build` / `approve` / `check` with a `--cutouts-dir` option |
| `adgen/errors.py` | Added `CutoutError` (a subclass of `GenerationError`). No behavior change |
| `adgen/config.py` | Added `CUTOUTS_DIR = cutouts/` and `MASKS_DIR = inputs/masks/` |
| `tests/test_cutout.py` | 20 tests |

- **`load_mask` rejects:** a wrong size, colored pixels, transparency, a keep area under 1% or over 95%. It accepts grayscale L, 1-bit or gray-valued RGB.
- **`make_cutout`:** RGB copied **byte-for-byte** from the reference, alpha taken from the mask, cropped to the mask's bounding box.
- **`build_draft`:** writes `cutouts/<name>.draft.png/.json` with `human_verified: false`, the reference, mask and cutout SHA-256, the crop box, sizes, opaque and partial-alpha pixel counts, `view` and review notes. It never overwrites.
- **`approve`:** a human action with `--verified-by`. It checks the draft SHA, writes `cutouts/<name>.png/.json` with `human_verified: true`, `verified_by` and `verified_at`, keeps the draft as history, and never overwrites.
- **`load_approved_cutout` (preflight):** matches by reference SHA; ignores drafts; requires `human_verified: true`, a valid view, and a PNG that exists with a matching SHA and RGBA mode; then re-verifies **pixel lineage**, meaning every pixel with alpha > 0 equals the reference pixel at `crop_box`.

`python -m pytest -q`: **289 passed** (269 + 20).

### Not done yet, as instructed
- No mask was created or invented; `inputs/masks/` does not exist.
- No scene prompt, compositor, composite generator, pipeline strategy switch or supplementary integration field yet. These come next, after the user supplies the mask.
- No Gemini call.

---

## Interaction 22: Deadline mode: AI declaration, evaluator audit, draft cutout, composite pipeline (offline)

- **Date:** 2026-09-26, around 14:15 IST. Target: submission-ready by 16:30 IST.

### Direction given to the agent (summarized)
- **Priorities, in order:**
  1. P0: `AI_DECLARATION_SUMMARY.md` (a new G2 announcement), an evaluator-criteria audit, offline tests green, and a cutout **draft** made by offline local segmentation instead of waiting for a hand-drawn mask (never approved automatically, never invented);
  2. P1: complete Strategy B offline;
  3. P2: exactly one live composite generation, after the human reviews the cutout;
  4. P3: documentation and packaging.
- No MCP, RAG, agents, heavy dependencies or evaluator redesign. No inflating PASS rates. No live call before human review.

### Done
- **`AI_DECLARATION_SUMMARY.md`:**
  - development tools: Claude Code in VS Code as the coding agent; ChatGPT as a planning/review assistant, as reported by the developer;
  - application models: `gemini-3.1-flash-image` for generation and scenes; `gemini-3.1-flash-lite` for evaluation and the profile draft;
  - **MCP: none used.** Connectors were available in the agent environment but none was invoked; the log only mentions MCP as excluded;
  - how the agent was directed, human decisions, the testing approach and the secrets policy.
- **Hygiene tests:** added to `tests/test_docs_hygiene.py`: a check for API-key-like strings in all root `*.md` files, and a completeness check for the declaration.
- **Evaluator audit:** all official criteria were already met, so no evaluator code changed. The audit is documented in `SOLUTION_DETAILS.md` §3.
  - context, product and text checks each have real catches, or edited-fixture catches for text;
  - PASS and FAIL cases are both in the golden set;
  - evidence and the raw response are stored;
  - the gate is deterministic;
  - malformed output → ERROR.
- **Draft mask:** `scripts/make_draft_mask.py` does deterministic HSV colour segmentation using Pillow only (numpy, OpenCV and scipy are not installed). It fills holes, removes specks and keeps only large connected regions.
  - **Tuning (4 tries):**
    - raising the light-blue saturation threshold removed the box strip but broke the collar ring;
    - separating by hue fixed it: the lining sits at H 141–145 and the box top at H ≥ 149.
  - **Result:** `inputs/masks/sneaker_mask.png`, 720×1280, mode L, keeps 35.8%.
  - **Visual check:** both shoes, laces, the yellow emblem and tab, both COMET marks, collar, insole and soles kept; box, floor and shadows removed. Small losses: the left heel's cream rim, and a jagged rear-heel edge on the right shoe.
- **Draft cutout:** `python -m adgen.cutout_cli build … --name sneaker --mask-source "automatic draft by scripts/make_draft_mask.py …"` → `cutouts/sneaker.draft.png` (624×772 RGBA, crop 57,242 → 681,1014, 321,317 opaque + 17,774 soft-edge pixels) and `.draft.json` with `human_verified: false`.
  - **Honesty fix:** the first draft's review note wrongly said "human-made mask". `mask_source` was added (a CLI flag, recorded in the metadata), the note made neutral, and the agent-created draft rebuilt.
  - **Not approved.**
- **Composite strategy implemented:**
  - `adgen/composite.py`:
    - text-only scene request (no image, cutout or profile sent);
    - scene prompt built from geography, season, required text and camera/layout only;
    - the cutout pasted at **native scale** (never resampled) in a fixed layout: centred, bottom-aligned, below a 22% headline band;
    - deterministic contact shadow;
    - final **PNG**;
    - pixel-identity check on the canvas and on the saved file;
    - a supplementary **non-gating** deterministic integration observation.
  - `adgen/pipeline/correction.py`: a `sections` filter; excluded codes are reported.
  - `adgen/pipeline/orchestrator.py`:
    - `strategy="redraw"` (the default, unchanged) or `"composite"`;
    - cutout preflight;
    - TEXT/CONTEXT-only corrections;
    - product-only failures → `FAIL_NO_PROGRESS` / `no_actionable_correction` (still FAIL, never PASS);
    - `CompositeInvariantError` → `ERROR_INTERNAL`.
  - `adgen/pipeline/cli.py`: `--strategy`.
  - The redraw generator and the single-shot CLI are unchanged.
- **Design point (logged for review):** the pixel-identity requirement rules out any cutout resampling. The 624×772 cutout fits the 1024 canvas at 1:1, so no global resize is needed. JPEG would change product pixels, so the final image is saved as PNG.
- **Offline preview:** the draft cutout was composited onto a plain synthetic background, with 321,317 opaque pixels verified identical.
- **Docs:** `README.md` (setup, tests, run commands, repo map) and `SOLUTION_DETAILS.md` (design, evolution, success criteria, audit, results, limitations, requirement-vs-decision split).
- **Tests:** `python -m pytest -q`: **313 passed** (289 + 24).

### Waiting for the human
- Review of `cutouts/sneaker.draft.png`, then `approve`.
- Authorization for the single live composite call.
- **Live Gemini calls in this interaction: 0.**

## Interaction 23 — 2026-09-26 — Cutout refinement after human review (offline)

**Instruction:** the user reviewed `cutouts/sneaker.draft.png` and withheld approval. Two changes were requested:
- remove the packing tissue inside the left shoe (it is not part of the product);
- set `view` to `near_overhead`.

Constraints: offline only; evaluator, generator, pipeline and profile untouched; no approval.

**Corrections from the user:**
- The draft wrongly kept the tissue. The hole fill had swallowed it together with the insole.
- The view is `near_overhead`, not `overhead`.

**Decisions:**
- **Tissue removal in `scripts/make_draft_mask.py`:** a new `tissue_mask` step runs after the opening. It works only inside `TISSUE_BOX = (112, 728, 292, 820)`, a reviewer-directed reference-pixel box that stops above the insole's COMET print.
  - Tissue rule: low saturation (S ≤ 64, 35 ≤ V ≤ 215); then close, fill creases, open.
  - Protection: every pixel with S ≥ 80 (laces, lining) is put back.
  - `fill_holes` was factored out, with no behavior change.
- **Rebuild:** the previous draft is protected against overwrite, so it was removed by explicit user instruction and rebuilt with `--view near_overhead` and an updated `mask_source`.

**Verification:**
- **Cutout RGB:** 0 mismatches against the reference on all non-transparent pixels.
- **Scope of the change:** alpha is unchanged everywhere outside the tissue box (plus a 3 px blur margin), so the emblem, COMET branding, soles and outer laces are untouched. Alpha increased nowhere; 11,181 pixels were reduced inside the box.
- **New draft:** 624×772, crop unchanged; 310,136 opaque pixels (was 321,317) and 21,069 partial pixels; `human_verified: false`.
- **Residue:** a thin dark crease line next to the lace (V < 35) remains inside the shoe opening.

**Tests:** `python -m pytest -q`: **317 passed**.

**Live Gemini calls: 0.** Approval is still pending with the human.

## Interaction 24 — 2026-09-26 — Cutout approval (human instruction)

- The user reviewed the refined draft and explicitly instructed the agent to run `python -m adgen.cutout_cli approve sneaker --verified-by "Soumik Datta"`.
- **Result:** `cutouts/sneaker.png` + `cutouts/sneaker.json` were written with `human_verified: true`, `verified_by: Soumik Datta`, `view: near_overhead` and cutout SHA-256 `f69b09cf…` (identical to the reviewed draft).
- **Lineage check:** `cutout_cli check` passes: 624×772, 310,136 opaque pixels.
- **Live Gemini calls: 0.** The single live composite call is still awaiting authorization.

## Interaction 25 — 2026-09-26 — First live composite smoke test (single run, crashed after generation)

**Instruction:** run exactly one `python -m adgen.pipeline.cli specs/example.json --strategy composite --max-attempts 1`, with no code changes before the run, no retries and no rerun.

**Result: crash (unhandled `PermissionError`), exit code 1.**
- **Scene generation (live call 1, `gemini-3.1-flash-image`):** succeeded, a 1024×1024 scene.
- **Composite:** built at native scale, 1024×1024 PNG, placement x=200, y=232. Pixel identity: 310,136 opaque pixels checked, 0 mismatches (in the saved PNG).
- **Failure:** the final atomic rename `os.replace(attempt-01.tmp → attempt-01)` in `adgen/composite.py:263` raised `PermissionError: [WinError 5] Access is denied`. The likely cause is Windows/OneDrive (or antivirus) holding a handle on the freshly written folder. This is not confirmed.
- **Evaluator:** never called (0 calls). No `evaluation.json`, `attempt.json` or `final.json` was written.
- **Code defect found:** the orchestrator catches `GenerationError`, `EvaluationError` and `CompositeInvariantError`, but not `OSError`. The filesystem failure therefore escaped as a traceback instead of a recorded `ERROR_INTERNAL`.
- **Evidence left untouched:** `outputs/sneaker-tokyo-winter/20260926T091135_842125Z/attempt-01.tmp/` (scene.jpg, ad.png, metadata.json).
- **Visual inspection (agent):**
  - **Text:** the headline "Step Into Winter" is rendered correctly on a navy band.
  - **Scene:** a dark wooden floor with a steaming tea cup, a plaid scarf, wool socks, felt slippers and ginkgo leaves. Winter and Japan cues are present but modest; there is no snow and no explicit Tokyo landmark.
  - **Product:** the pixels are exact.
  - **Integration:** weak. The bright product sits on a dark scene (brightness gap 78.1), and a partly cut edge on the right shoe (the reference photo's frame edge) is visible. The product covers 75% of the canvas height.
- **Integration observation (non-gating):** brightness gap 78.1; red-minus-blue colour gap 78.2; product height share 0.754; edge soft-pixel share 0.0636.

**API calls:** 1 generator + 0 evaluator. **Tests:** 317 passed (after the run; no code changed).

**Not done, per instruction:** no rerun, no retry, no code fix. The rename defect and the missing `OSError` handling await user direction.

## Interaction 26 — 2026-09-26 — Interior cavity backing in the compositor (offline)

**Correction from the user:** the live composite (Interaction 25) was rejected visually. The transparent cavity left by the tissue removal let the generated wooden floor show through the left shoe, so the shoe looked hollow and pasted.

**Constraints:**
- no Gemini call; no scene regeneration;
- evaluator, profile, base scene prompt and mask unchanged;
- fix in the deterministic compositor only.

**Decisions:**
- **`adgen/composite.py`:**
  - `cavity_mask`: transparent regions (alpha < 128) not connected to the cutout border. Components under 64 px are ignored, and the mask is grown 2 px under the soft rim.
  - `backing_layer`: a dark-neutral vertical gradient from (34,32,30) to (68,64,60).
  - Layer order in `compose`: scene → contact shadow → interior backing → exact cutout.
- **Metadata:** `composite.interior_backing` records `used`, the documented claim, the cavity pixel count and bbox, and all `BACKING` parameters.
- **Cutout asset:** unchanged. The cutout and profile SHA lineage is unchanged.
- **Real cutout check:** the approved cutout has exactly one enclosed cavity (9,500 px before growth), inside `TISSUE_BOX`.

**Documentation claim, as directed by the user:** "All preserved opaque product pixels come directly from the reference cutout; a deterministic interior backing fills the reference photo's non-product cavity where packing tissue was removed."

**Tests:** 7 new tests in `tests/test_composite.py`:
- the cavity is opaque backing, not scene;
- opaque pixels are identical, and differences occur only inside the cavity mask and never over opaque product pixels;
- outside regions and small specks are not backed;
- determinism, metadata recording and long edge ≤ 1024;
- no cavity → a byte-identical composite with no backing;
- the cutout file, pixels and SHA are unchanged;
- the real sneaker cavity lies inside the tissue box.

`python -m pytest -q`: **324 passed**.

**Offline preview (no API call):** `outputs/previews/composite-backing-offline/{ad.png, metadata.json}`, re-composited from the existing Interaction 25 `scene.jpg`.
- 1024×1024 PNG;
- 310,136 opaque pixels verified identical in the saved PNG;
- not evaluated.

The Interaction 25 evidence folder was left untouched.

**Live Gemini calls: 0.**

## Interaction 27 — 2026-09-26 — Filesystem finalization fix + one live evaluator call on the approved preview

**Instruction:**
- Fix only the two filesystem issues from Interaction 25.
- Then evaluate the user-approved offline preview with exactly one Flash-Lite call: no generation, no retry loop.

**Fixes (filesystem only):**
- **`adgen/image_io.finalize_dir`:** first tries the directory rename. On `OSError` it falls back to create target → copy each file → verify SHA-256 → best-effort removal of the temp directory. It returns `"rename"` or `"copy"`. If the fallback fails too, it raises `FinalizationError` and keeps the temp directory with all artifacts. No step is retried.
- **Used by:** `adgen/composite.generate_composite` (`CompositeResult.finalization`) and `image_io.save_run` (redraw path, same pattern).
- **`adgen/errors.FinalizationError`:** deliberately not a `GenerationError`.
- **`adgen/pipeline/orchestrator.py`:**
  - `FinalizationError`/`OSError` after the generator call → `ERROR_INTERNAL` with `stop_reason: filesystem_error`, plus `attempt.json` and `final.json`. `_call_gemini` wraps all transport errors, so an `OSError` here is local.
  - `OSError` during evaluation → `ERROR_INTERNAL`, with the evaluator call counted as an upper bound.
  - `attempt.json` records `finalization`.
- **`adgen/pipeline/cli.py`:** a last-resort `OSError` handler prints `ERROR_INTERNAL` (key redacted) instead of a traceback.
- **Tests:** 7 new tests in `tests/test_composite.py`:
  - rename path;
  - copy fallback with byte-identical files;
  - total failure raises and preserves the artifacts;
  - the composite pipeline passes via copy when the rename is locked, with pixel identity checked on the copied PNG;
  - finalization failure → auditable `ERROR_INTERNAL`, with 1 generator and 0 evaluator calls and no regeneration;
  - evaluation `OSError` → `ERROR_INTERNAL`;
  - the CLI prints no traceback and does not leak the key.
- **Result:** `python -m pytest -q`: **331 passed**.

**Preparing the preview for evaluation:**
- The standard composite metadata was written into `outputs/previews/composite-backing-offline/metadata.json`. It is derived read-only from the historical run's metadata, with the preview's composite, backing, pixel identity and integration values, plus a `provenance` block (offline re-composite, source scene SHA, no new generation call).
- **Reproducibility:** recomposing gives pixels identical to the approved `ad.png`, which was not rewritten.
- **Historical run:** its files hash identically before and after (untouched).

**Live evaluator call:** `python -m adgen.evaluator.cli evaluate outputs/previews/composite-backing-offline`. **Overall: FAIL** (`CONTEXT_GEO_ABSENT`). Duration 6.777 s.

| Check | Verdict | Detail |
|---|---|---|
| Technical | PASS | 1024×1024 |
| Text | PASS | "Step Into Winter", 1 occurrence, similarity 1.0, no extra ad copy |
| Product | PASS | `same_product: yes`; all 8 profile attributes preserved; tongue and insole "COMET" legible and correct; no added marks |
| Context | FAIL | geography `absent` (no cues); season `strong` (steaming drink, knitwear/socks, plaid scarf, dark leaves) |

- **Integration (non-gating):** brightness gap 78.2; colour-cast gap 77.7; product height share 0.754; edge soft share 0.0636.
- **Interpretation:** the evaluator confirms the exact reference product is preserved. The failure is in the generated scene, which lacks visible Tokyo/Japan cues. That is a CONTEXT correction the bounded composite loop is designed to send; it was not run, as instructed.

**API calls this interaction:** 0 generator + 1 evaluator. `pytest` after the call: **331 passed**.

Not started: the bounded loop and the 20-image experiment.

## Interaction 28 — 2026-09-26 — First bounded composite run (max 2 attempts)

**Instruction:** run `python -m adgen.pipeline.cli specs/example.json --strategy composite --max-attempts 2` as a new run, with no code changes and no extra calls.

**Run:** `outputs/sneaker-tokyo-winter/20260926T093146_984333Z/`. **Status: PASS**, accepted on `attempt-02`, `stop_reason: passed`, 43.1 s.

**Attempt 1** (fresh scene): **FAIL** `CONTEXT_GEO_WEAK`. A new scene, so the code is not the preview's `CONTEXT_GEO_ABSENT`.
- **Checks:** technical, text and product PASS (`same_product: yes`, all 8 attributes preserved, both COMET labels correct).
- **Geography:** `weak`, with the single cue "tactile paving".
- **Season:** `strong`; minor conflicting cue: ginkgo leaves, which are late autumn.
- **Pixel identity:** 310,136 pixels, 0 mismatches; backing used. Evaluator 6.353 s.

**Correction** (generated deterministically from attempt-1 `evaluation.json`):
- `codes: [CONTEXT_GEO_WEAK]`; nothing excluded or suppressed.
- One `[CONTEXT]` line quoting the evaluator's cue; no product text.
- **Wording defect found:** the shared correction header says "The attached reference image remains the source of truth for the product". In composite mode no image is attached. The sentence is harmless but inaccurate. Not fixed (no code changes were authorized).

**Attempt 2:** **PASS**, with all four checks PASS.
- **Geography:** `strong` (Shinjuku Sanchome station sign, braille paving, ginkgo leaves).
- **Season:** `strong`.
- **Text:** "Step Into Winter" exactly once. The station sign was classed as `background_incidental`, so it is not extra ad copy.
- **Product:** PASS.
- **Pixel identity:** 0 mismatches. Evaluator 5.945 s.
- **Finalization:** both attempts used `rename`; the copy fallback was not needed.

**Reason history:** `[[CONTEXT_GEO_WEAK], []]`. **Regressions:** none. Product and text stayed PASS in both attempts.

**Integration (non-gating):**

| Attempt | Brightness gap | Colour-cast gap | Product height share |
|---|---|---|---|
| 1 | 16.7 | 58.6 | 0.754 |
| 2 | 9.5 | 68.4 | 0.754 |

**Agent visual inspection of the final image:**
- **Correct:** the headline is correct; the Tokyo cues are clear.
- **Scale:** the product is oversized relative to the props (boots, bicycle wheel).
- **Season:** the scene is sunny, with no snow; winter is carried mainly by the headline, gloves and boots.
- **Evaluator error:** the sign's second line in the image appears as "新宿丁駅", with 三 missing. The evaluator transcribed it as "新宿三丁目駅", a silent correction. It does not affect gating, because incidental text is not gated.

**API calls:** 2 generator + 2 evaluator (matching `final.json`). No other calls. `pytest` after the run: **331 passed**.

Not started: the 20-image experiment.

## Interaction 29 — 2026-09-26 — Final experiment mode: header cleanup, 20-output experiment, golden composite PASS

**Instruction:**
- Make one wording cleanup.
- Run the ~20-output composite experiment (`max_attempts=1`, no retries).
- Add the real composite PASS to golden.
- Update the docs.
- No evaluator/profile/threshold/scene-strategy changes.

**Decisions and changes:**
- **Correction header** (`adgen/pipeline/correction.py`): a new `COMPOSITE_HEADER` ("The approved product reference remains the source of truth for the task.") is used when PRODUCT is not among the sent sections, which is composite mode. Redraw keeps its accurate "attached reference image" header. The rest of the correction logic is unchanged. Test assertion added.
- **`scripts/run_experiment.py`** (build / check / run / report):
  - 20 deterministic specs (`experiments/composite20/specs/`), 5 cities × 4 seasons, each with a distinct short product-agnostic required text.
  - The manifest records per case the official inputs, source, run dir, generation result and evaluation result.
  - **Guards:** a recorded case is never re-run; it aborts after 3 consecutive generator errors; the manifest is written after each case.
- **Pre-flight check (offline):**
  - 20 specs, 20 distinct pairs and texts; no absolute paths;
  - the real key was checked against every repo text file (0 hits; the key was not printed);
  - 9.4 GB free; approved cutout and profile load.
- **Golden:** `scripts/build_golden.py` adds `real_composite_pass`.
  - Copies of `ad.png`, `metadata.json`, `evaluation.json` and `attempt.json` from `outputs/sneaker-tokyo-winter/20260926T093146_984333Z/attempt-02/`, paths sanitized.
  - Provenance: SHA, cutout SHA, pixel identity. The observations are the verbatim `raw_response`.
  - A rebuild changed only `manifest.json` and added new files; every existing golden file is byte-identical, including the historical baseline.
  - `test_golden.py` now asserts the exact real set `[real_baseline, real_composite_pass]` and adds provenance and replay tests for the new case.
- **Correction to Interaction 28:** the sign's second line misses both 三 and 目 ("新宿丁駅"), verified by zoom. Recorded in the golden observations note.

**Experiment result: 20 generation + 20 evaluator calls (exact), 0 errors, no retries.**
- **Overall:** 9 PASS (45%), 11 FAIL (55%), 0 ERROR.
- **Per check:** technical 20/20 PASS; text 20/20 PASS; context 15 PASS / 5 FAIL (`CONTEXT_GEO_WEAK`); product 13 PASS / 7 FAIL (`PRODUCT_BRANDING_DISTORTED`, insole).
- **Per geography (PASS/FAIL):** Tokyo 3/1, Paris 3/1, New York 1/3, London 1/3, Seoul 1/3.
- **Per season (PASS/FAIL):** Winter 1/4, Spring 3/2, Summer 4/1, Autumn 1/4.
- **Averages:** generation 12.576 s, evaluation 6.028 s. Wall time was about 90 s per case, dominated by local compositing and metrics.
- **Product-failure audit:**
  - Pixel-identity mismatches: 0 in all 20 outputs.
  - The evaluator transcribed the identical insole print as COMET / comet / COMeT / coMeT / coMet / cOmeT, and labelled "comet" correct in 06 and 08 but different in 13 and 16.
  - **Conclusion:** all 7 product FAILs are evaluator false positives; no real product-fidelity failure occurred. Nothing was tuned in response.
- **Agent visual checks:**
  - **Case 05 (Paris winter):** the headline is correct and the Paris cues are clear. The generator rendered a garbled map label ("CONIS ARRONDISSEMENTS"), which is incidental.
  - **Case 20 (Seoul autumn):** the scene is generic East Asian, so the geography-weak verdict is justified.
- **Report:** `experiments/composite20/report.md` and `report.json`, with a product-failure audit section added to the report generator.

**Docs:**
- SOLUTION_DETAILS §3 is restructured into offline tests / baseline failure / evaluator validation / bounded retry success / 20-output experiment; §4 limitations are updated.
- README gains the experiment commands and repo-map rows.
- AI_DECLARATION_SUMMARY is unchanged: no new tool or action; no MCP used.

**Tests:** `python -m pytest -q`: **345 passed**.

## Interaction 30 — 2026-09-26 — Rules v2: deterministic composite product preservation + offline recomputation

**Instruction:**
- Design and implement one evaluator/gate refinement from the experiment evidence.
- 7 product FAILs were insole capitalization readings on pixel-identical products.
- Then recompute the experiment report offline.
- No Gemini calls; no new images; no profile, text or context rule changes; redraw unchanged.

**Rule design (`RULES_VERSION` 1 → 2; recorded in `policy.py` → `product.composite_pixel_identity`):**
- **Applies to** runs whose metadata says `strategy: composite`.
- **Evaluator-side re-verification** (`rules.composite_pixel_identity`): it does not trust the generator's claim.
  - It loads the approved cutout for the reference via `load_approved_cutout`, which re-checks the human-verified flag and SHA lineage.
  - It requires that cutout to be the one recorded in the metadata.
  - It compares every alpha = 255 pixel with the saved ad at the recorded placement.
  - Pass condition: 0 mismatches, and the checked count equals the cutout's `opaque_pixels`.
  - Any file or lineage problem → not verified.
- **Verdict** (`rules.composite_product_rules`):
  - **Identity passes:** record `PRODUCT_PIXEL_IDENTITY_PASS` as deterministic evidence. AI reasons about the preserved pixels become one `PRODUCT_EVALUATOR_DISAGREEMENT` record (non-gating; lists the AI codes, with a resolution note). `PRODUCT_BRANDING_ADDED` stays gating, because pixel identity cannot rule out marks added around the product.
  - **Identity fails or is unverifiable:** `PRODUCT_PIXEL_IDENTITY_FAIL`, plus all AI reasons, gating.
  - **Stored either way:** the unchanged v1 product result is kept as `ai_observation`, and `raw_response` stays verbatim.
- **`evaluate.decide()`** holds the deterministic part, shared by live evaluation and the new `recompute_evaluation()` (offline, no model call, writes nothing). `evaluation.json` gains `evaluator_disagreements`.
- **Orchestrator:** passes `cutouts_dir` to the evaluator.
- **Import direction:** the evaluator imports `adgen.cutout` (shared artifact), not the compositor.

**Tests:** 355 passed (was 345).
- **Two composite tests updated,** because their premise changed under v2: an AI "emblem altered" claim with exact pixels is now a disagreement, not a FAIL. They now use `PRODUCT_BRANDING_ADDED`, which is still gating and still excluded from composite corrections.
- **New tests:**
  - (a) exact identity + branding case variant → product PASS, disagreement recorded, never gating, rules v2;
  - (b) a tampered composite pixel → `PRODUCT_PIXEL_IDENTITY_FAIL`, and an unverifiable identity → FAIL with the AI reasons kept;
  - an added logo stays gating;
  - (c) the redraw rule and the redraw pipeline still FAIL on the same observation;
  - (d) the AI observation and raw response are stored verbatim;
  - (e) the gate is deterministic;
  - offline recompute makes no model call and leaves `evaluation.json` byte-identical;
  - golden `real_composite_pass` passes under v2 with no disagreement.

**Offline recomputation** (`scripts/run_experiment.py recompute`): writes `attempt-01/evaluation.recomputed.json` per case and `recomputed_evaluation` in the manifest. All 80 image, metadata and evaluation files hash identically before and after. Pixel identity was re-verified in 20/20 cases (310,136 pixels, 0 mismatches).
- **Recomputed** (labelled "Recomputed offline from the same 20 live experiment artifacts after deterministic composite product-preservation rule."):
  - 15 PASS / 5 FAIL / 0 ERROR;
  - technical 20/0, product 20/0, context 15/5, text 20/0;
  - reasons: 5 × `CONTEXT_GEO_WEAK`;
  - 7 evaluator disagreements (cases 05, 09, 10, 13, 16, 17, 18);
  - geography PASS/FAIL: Tokyo 3/1, Paris 4/0, New York 3/1, London 3/1, Seoul 2/2;
  - season PASS/FAIL: Winter 5/0, Spring 4/1, Summer 4/1, Autumn 2/3.
- **Original live results** (9 PASS / 11 FAIL) are kept alongside in `report.json` and `report.md`.

**Docs:**
- SOLUTION_DETAILS: the §1 rule description; a new §3.6 with the why and how; limitations, including that v2 was designed after seeing the data.
- README: the `recompute` command.
- AI declaration unchanged.

**API calls: 0 generator + 0 evaluator.**

## Interaction 31 — 2026-09-26 — Final submission audit (documentation metadata only)

**Changes (docs and metadata only):**
- **README repo map:** "policy (rules v1)" → "versioned deterministic policy/rules (current composite policy v2)".
- **SOLUTION_DETAILS §1:** the current rules were still called "rules v1" (a failed consistency check), now "currently rules v2: the v1 rules plus the composite product-preservation rule". Historical "v1" references are unchanged.
- **Golden manifest:** `rules_version: "1"` kept. A new `rules_version_note` (golden outcomes v1, current evaluator v2, v2 recomputation separate) was added via `scripts/build_golden.py`. A rebuild changed only `golden/manifest.json`; the expected outcomes were not touched.

**Audit results:**
- **Tests:** 355 passed.
- **Files git would track:** 114, about 5.7 MB. `.env`, `.venv/` and `outputs/` are ignored (`.gitignore` lines 5/13). The repo has no commits yet.
- **Secrets and paths:** no real key in any trackable file. Pattern hits were only placeholders (`your-key-here`), pattern documentation and test examples. No user-specific absolute paths.
- **Required files:** all present.
- **Report:** 29 consistency checks passed, covering sums, verdicts vs manifest, the 7 disagreements = the 7 original product FAILs, 20/20 live calls, 0/0 recompute calls, the recomputation label, and version wording.

**Live Gemini calls: 0.**
