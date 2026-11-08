class Anything2SpeechError(Exception):
    """Base error for expected, user-facing failures."""


class UnsupportedFileError(Anything2SpeechError):
    """Raised when an input file type is not supported."""


class ExtractionError(Anything2SpeechError):
    """Raised when text cannot be extracted from an input file."""


class SynthesisError(Anything2SpeechError):
    """Raised when the TTS engine fails after all retries."""
