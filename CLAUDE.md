# CLAUDE.md — Project Rules for the Coding Agent

These rules bind any coding agent working in this repository. The user approves important engineering decisions. When in doubt, stop and ask.

## Project purpose

This is a G2 AI Engineering Hackathon submission for **Problem Statement 2: Enrichment of image generation using structured context**. We build a display-ad image-generation pipeline on a Gemini image model and show that generation quality is ensured through:

- an evaluator,
- a bounded quality gate, and
- automated tests that validate the evaluator.

**Sources of truth (read-only, never modify):**
- `G2_Problem_Statement_2.md`
- `G2_SUBMISSION_GUIDE.pdf` (original reference)
- `G2_AI_Engineering_Hackathon_Submission_Guide.md` (transcription of the PDF)

`REQUIREMENTS.md` holds the approved requirements analysis. Do not modify it without explicit instruction.

## Official constraints (from the sources)

- Pipeline inputs are exactly four: **reference product image, target geography, season, required text** (the text must appear in the generated image).
- Generator must be **Gemini 3.1 Flash-Lite Image or Gemini 3.1 Flash Image**.
- Generated images: **long edge ≤ 1024 px**.
- Imperfect text rendering is acceptable but must be handled in the design.
- The evaluator judges about 20 pipeline outputs. Minimum metrics:
  - **context adherence**
  - **reference-product fidelity**
  - **text-rendering fidelity**
- Automated tests must show the evaluator identifies **passing and failing** outputs.
- Preferred languages: Python, TypeScript or Ruby. **This project uses Python.**
- Coding-agent use is allowed but must be disclosed, including how the agent was directed.
- HackerEarth upload fields (Presentation, Source Code) are limited to **50 MB each**.

## Approved architecture direction

```
Reference image + Geography + Season + Required text
        → Generator (Gemini image model)
        → Generated advertisement (long edge ≤ 1024 px)
        → Evaluator (context / product / text checks)
        → Quality gate
             PASS → accept
             FAIL → bounded regeneration (max N attempts, then stop and record)
```

- Generation and evaluation are **separate responsibilities** (separate modules, no shared hidden state).
- The retry loop is always **bounded** by an explicit, configurable maximum. Never write an unbounded loop.
- Every run records all attempts and verdicts, not just the final one.

## Approved model direction

| Role | Model ID |
|---|---|
| Generator | `gemini-3.1-flash-image` |
| Evaluator | `gemini-3.1-flash-lite` |

- These IDs are the current direction, not immutable facts. If an API compatibility check shows an ID is wrong or unavailable, a change is allowed **only** with the reason logged in `AGENT_LOG.md` and the user informed.
- Model IDs go in configuration, not scattered through the code.
- The official constraint applies to the generator only. Any generator change must remain a Gemini 3.1 Flash or Flash-Lite **Image** model.

## Engineering principles

1. **Minimal and explainable.** Add complexity only for a concrete, stated requirement.
2. **Deterministic first.** Use plain Python rules for anything checkable deterministically, e.g.:
   - image dimensions,
   - comparing required vs transcribed text with string similarity,
   - thresholds and verdict aggregation.

   Use the multimodal model only where visual understanding is needed.
3. **Auditable verdicts.** Each evaluation produces a structured record: per-metric scores, the threshold applied, the reason, and an overall PASS/FAIL. It must be traceable from inputs to verdict.
4. **Structured model outputs.** Parse evaluator responses into a defined schema. Treat malformed responses as explicit errors, never as silent passes.
5. **Secrets.** API keys come only from environment variables. Never hard-code, log or commit keys. Keep `.env` in `.gitignore`.
6. **Configuration over constants.** Thresholds, max retries, model IDs and output size go in one config location.
7. **Fresh work only.** All code is written in this hacking window. Never copy or adapt code from previous prototypes.

## Testing principles

- Tests must show the evaluator producing **both PASS and FAIL** verdicts, for each of the three minimum metrics.
- A labeled **golden dataset** (inputs, images, expected verdicts) lives in the repo and stays small (well under the 50 MB source upload limit).
- Deterministic logic (size check, text matching, thresholds, gate/retry bounds) gets fast unit tests that need no API key.
- Tests that call live Gemini must be clearly separated or marked, so the default test run is reproducible without network access or a key.
- Include a test showing the retry loop stops at its bound.
- Record test results, including failures, faithfully. Never weaken a test just to make it pass.

## Documentation and agent-disclosure rules

- After each significant interaction, update `AGENT_LOG.md` with:
  - date,
  - instruction purpose,
  - decisions made,
  - corrections from the user,
  - experiments run and results,
  - what was deliberately deferred.
- Log any deviation from this file or from the approved model direction, with its reason.
- Final submission must include:
  - **Solution Details** (design, rationale, success criteria, achievement against criteria, limitations)
  - **Coding-agent disclosure** (derived from `AGENT_LOG.md`)
  - **Code repository**
  - **Golden dataset**
  - **Tests**
  - **Clear run instructions**
  - **Presentation/deck** (allowed format, ≤ 50 MB)
- Report outcomes honestly: failed tests, skipped steps and known limitations are stated plainly.

## Do NOT

- Do not modify the source files or `REQUIREMENTS.md` unless explicitly instructed.
- Do not write code, call Gemini, generate images, install packages or add tooling beyond what the current approved task asks for.
- Do not build agents, RAG, vector databases, MCP integrations or orchestration frameworks without a concrete requirement and user approval.
- Do not create unbounded retry or regeneration loops.
- Do not merge generation and evaluation logic.
- Do not use the multimodal model for checks that deterministic Python can do.
- Do not commit secrets, `.env` files or API keys.
- Do not copy or adapt code from previous prototypes.
- Do not change model IDs, thresholds or architecture silently. Document the change and inform the user.
- Do not silently resolve ambiguities or discrepancies between sources. Flag them.
- Do not commit or push unless the user asks.
