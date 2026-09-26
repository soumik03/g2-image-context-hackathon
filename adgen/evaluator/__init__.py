"""Evaluator for generated ads. The generator never imports this package.

The evaluator model only reports structured observations; deterministic Python
rules (rules.py, configured in policy.py) decide PASS / FAIL. Anything that
prevents a trustworthy evaluation becomes ERROR, never PASS.
"""


class EvaluationError(Exception):
    """An evaluation could not be completed. `code` is an EVAL_* reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
