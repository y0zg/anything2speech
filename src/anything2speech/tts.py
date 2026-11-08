"""Text-to-speech engines."""

from __future__ import annotations

import io
import logging
from typing import Protocol

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from anything2speech.errors import SynthesisError

log = logging.getLogger(__name__)


class TTSEngine(Protocol):
    """Anything that turns a piece of text into MP3 bytes."""

    name: str

    @property
    def cache_key(self) -> str:
        """Identifies settings that affect output; changing them invalidates cached audio."""
        ...

    def synthesize(self, text: str) -> bytes: ...


class GTTSEngine:
    """Google Translate TTS via gTTS. Free, but rate limited; retries with backoff."""

    name = "gtts"

    def __init__(
        self,
        lang: str = "uk",
        *,
        tld: str = "com",
        slow: bool = False,
        max_attempts: int = 5,
    ) -> None:
        from gtts.lang import tts_langs

        if lang not in tts_langs():
            raise SynthesisError(f"Language '{lang}' is not supported by gTTS")
        self.lang = lang
        self.tld = tld
        self.slow = slow
        self.max_attempts = max_attempts

    @property
    def cache_key(self) -> str:
        return f"{self.name}:{self.lang}:{self.tld}:{self.slow}"

    def synthesize(self, text: str) -> bytes:
        from gtts import gTTSError

        retrying = retry(
            retry=retry_if_exception_type(gTTSError),
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(multiplier=2, min=5, max=120),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        )
        try:
            return retrying(self._synthesize_once)(text)
        except gTTSError as e:
            raise SynthesisError(f"gTTS failed after {self.max_attempts} attempts: {e}") from e

    def _synthesize_once(self, text: str) -> bytes:
        from gtts import gTTS

        buf = io.BytesIO()
        gTTS(text, lang=self.lang, tld=self.tld, slow=self.slow).write_to_fp(buf)
        return buf.getvalue()
