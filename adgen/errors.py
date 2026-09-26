"""Error types for the generation pipeline, plus secret redaction."""


class GenerationError(Exception):
    """Base class for every expected pipeline failure."""


class SpecError(GenerationError):
    """The generation spec or its reference image is invalid."""


class ConfigError(GenerationError):
    """Required configuration (e.g. the API key) is missing."""


class GenerationAPIError(GenerationError):
    """Gemini returned an API error or the request failed."""

    def __init__(self, message: str, code=None, status=None):
        super().__init__(message)
        self.code = code
        self.status = status


class NoImageReturnedError(GenerationError):
    """Gemini responded but did not return an image."""


class OutputProcessingError(GenerationError):
    """The returned image could not be decoded, resized or saved."""


class CutoutError(GenerationError):
    """A product cutout (or its mask) is missing, invalid, unapproved or not traceable to the reference."""


class FinalizationError(Exception):
    """Completed run artifacts could not be moved into their final directory (filesystem failure).

    Deliberately NOT a GenerationError: the pipeline maps it to ERROR_INTERNAL, never to a success.
    The completed artifacts are preserved in the temporary directory for audit.
    """


def redact(text: str, secret: str | None) -> str:
    """Replace every occurrence of the secret in text."""
    if not secret:
        return text
    return text.replace(secret, "[REDACTED]")
