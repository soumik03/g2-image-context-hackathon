# AI Declaration Summary

**Project:** G2 AI Engineering Hackathon, Problem Statement 2: Enrichment of image generation using structured context
**Developer:** Soumik Datta
**Full trace:** [AGENT_LOG.md](AGENT_LOG.md) records every significant instruction, decision, correction, experiment and result, interaction by interaction.

## 1. AI tools used during development

| Tool | Type | Used for | Why |
|---|---|---|---|
| **Claude Code** (Anthropic), VS Code extension | AI coding agent | Reading the official sources, requirements analysis, implementing all code (generator, evaluator, quality gate, bounded regeneration pipeline, cutout workflow), writing tests, running tests and the approved live API calls, and writing the documentation and the log | Fast, test-driven implementation within the hacking window, under explicit human direction |
| **ChatGPT** (OpenAI) | AI planning/review assistant, *not* used to write repository code directly | Planning and reviewing architecture, prompt design, evaluation strategy and debugging decisions, and reviewing Claude Code's proposals before approval (as reported by the developer) | A second opinion on design decisions before they were given to the coding agent |

**MCP (Model Context Protocol): none used.** MCP connectors were available in the coding-agent environment, but none was invoked for this project. The design rules in `CLAUDE.md` explicitly excluded MCP, RAG, vector databases and agent frameworks.

No other AI tools were used for development.

## 2. AI models used *by the application* (not coding agents)

| Model | Role in the product |
|---|---|
| `gemini-3.1-flash-image` | **Image generation.** In the baseline strategy it generates the whole ad. In the primary (hybrid) strategy it generates the contextual advertising scene and the required headline text |
| `gemini-3.1-flash-lite` | **Multimodal evaluator.** It returns structured observations only (text transcription, product-attribute comparison, context cues). A one-time call also drafted the reference profile, which a human then reviewed |

These models are called at runtime through the `google-genai` SDK. They did not write the project's code. Final PASS/FAIL verdicts come from **deterministic Python rules**, not from a model.

## 3. How the coding agent was directed

- **Phase by phase, design first:** each stage started with a design-only prompt (no code, no API calls). Claude Code presented the options and trade-offs. The developer approved, changed or rejected them, and only then was implementation requested.
- **Written constraints:** `CLAUDE.md` recorded the approved architecture, the constraints and "do not" rules. Examples: four official inputs only; long edge ≤ 1024 px; generation and evaluation kept separate; bounded retries; secrets only in environment variables; no reuse of earlier prototypes.
- **Strict API budgets:** every live Gemini call was explicitly authorized with a call limit. Examples: one smoke test; one evaluator call; at most 2 + 2 calls for the first pipeline run. The agent was told to stop and report, not retry, on errors.
- **Every step logged:** `AGENT_LOG.md` records each instruction (summarized), the agent's actions, test results, live results and all human corrections.

## 4. Important agent-directed stages (examples)

1. **Requirements:** analysis of the official sources, with discrepancies flagged (`REQUIREMENTS.md`).
2. **Single-shot generator:** implemented with the Interactions API. The first live call exposed an unsupported SDK request field (`delivery`), which was fixed minimally and logged.
3. **Evaluator:** the model only observes; deterministic rules decide. It uses a **human-verified reference profile** (model draft → human correction → `human_verified: true`).
4. **Real failures captured:** the evaluator caught the first real output's failures (altered yellow emblem, garbled "COMET" branding, weak geography, conflicting seasonal cue) while the text passed.
5. **Golden dataset:** real, deterministically edited and hypothetical cases, clearly labeled by source, with expected outcomes written by hand.
6. **Bounded regeneration loop:** at most 3 attempts, corrections driven by evaluator evidence, and a stop when no progress is made. The first live run caught new regressions after a correction ("COMET"→"CONET", an added "ABT" mark).
7. **Strategy change** based on that evidence: the product is **preserved and composited from a human-approved exact-pixel cutout**, and Gemini generates only the scene and the headline.

## 5. Human review and decisions

- **All architectural decisions were made or approved by the developer.** Examples: the evaluator design and reason codes; the stricter `same_product = partially` rule; the retry budget; the hybrid strategy; the manual/verified cutout workflow.
- **The developer made the key corrections:** classifying emblem and branding changes as fidelity failures; correcting the reference profile; removing a double-counted attribute; removing local paths from committed files.
- **Verification is human-only:** the `human_verified` flags on the profile and the cutout are set only after the developer's review. The agent never sets them on its own.
- **Code review:** outputs were checked by running the automated test suite after every change and by manually inspecting the generated images and evaluation records.

## 6. Testing approach

- The offline pytest suite runs **without network access or an API key**, using fake Gemini clients.
- It covers: the generator; the evaluator schema and rules (malformed output → ERROR, never PASS); every reason code; the golden dataset replaying to its hand-written expected outcomes; loop bounds and lineage; product-pixel preservation; and file hygiene (no secrets, no absolute user paths).
- Live calls were few, pre-authorized and logged with their results.

## 7. Secrets

API keys come only from a git-ignored `.env` file. They are never printed, logged or stored, and error text is redacted. This file and `AGENT_LOG.md` contain no keys and no local absolute paths; tests enforce this.
