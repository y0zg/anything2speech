"""anything2speech: turn text files and images into speech audio."""

from anything2speech.errors import Anything2SpeechError
from anything2speech.pipeline import Pipeline, PipelineOptions

__all__ = ["Anything2SpeechError", "Pipeline", "PipelineOptions"]
__version__ = "0.2.0"
