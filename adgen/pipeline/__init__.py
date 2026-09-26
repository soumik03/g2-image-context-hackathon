"""Bounded, evaluator-gated regeneration pipeline.

The only package that uses both the generator and the evaluator. The generator
never imports it. Run statuses:

  PASS               an attempt passed the deterministic gate and was accepted
  FAIL_EXHAUSTED     MAX_ATTEMPTS reached, still failing; nothing accepted
  FAIL_NO_PROGRESS   failing reasons unchanged after a correction; stopped early
  ERROR_PREFLIGHT    invalid reference or no approved profile; zero API calls
  ERROR_GENERATOR    generation failed (API error, no image, output error); no retry
  ERROR_EVALUATOR    evaluator returned ERROR (API, malformed, incomplete); no retry
  ERROR_INTERNAL     a pipeline-generated artifact violated an invariant the generator
                     guarantees (e.g. technical FAIL), or evaluation could not run

Technical-failure semantics: when the evaluator is used standalone, a technical
problem is a technical FAIL. Inside this pipeline the generator guarantees the
technical invariants (decodable image, long edge <= 1024, complete metadata), so a
technical FAIL on a pipeline artifact indicates a bug and becomes ERROR_INTERNAL.
"""

PASS = "PASS"
FAIL_EXHAUSTED = "FAIL_EXHAUSTED"
FAIL_NO_PROGRESS = "FAIL_NO_PROGRESS"
ERROR_PREFLIGHT = "ERROR_PREFLIGHT"
ERROR_GENERATOR = "ERROR_GENERATOR"
ERROR_EVALUATOR = "ERROR_EVALUATOR"
ERROR_INTERNAL = "ERROR_INTERNAL"
