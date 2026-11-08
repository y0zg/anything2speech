"""Orchestrates extraction -> chunking -> synthesis -> assembly."""

from __future__ import annotations

import hashlib
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from anything2speech.errors import Anything2SpeechError
from anything2speech.sources import Source, extract
from anything2speech.text import chunk
from anything2speech.tts import TTSEngine

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineOptions:
    ocr_lang: str = "ukr"
    encoding: str = "utf-8"
    chunk_chars: int = 2000
    delay: float = 1.0
    keep_parts: bool = False
    progress: bool = True


class Pipeline:
    """Converts sources into an MP3 file.

    Synthesized chunks are cached next to the output in a ``.<name>.parts`` directory,
    so an interrupted run (e.g. hitting a rate limit on a long book) resumes where it
    stopped instead of starting over.
    """

    def __init__(self, engine: TTSEngine | None, options: PipelineOptions | None = None) -> None:
        self.engine = engine
        self.options = options or PipelineOptions()

    def extract_text(self, sources: list[Source]) -> str:
        texts: list[str] = []
        for source in tqdm(
            sources, desc="Extracting", unit="file", disable=not self.options.progress
        ):
            log.debug("Extracting %s (%s)", source.path, source.kind.value)
            text = extract(source, ocr_lang=self.options.ocr_lang, encoding=self.options.encoding)
            if text:
                texts.append(text)
            else:
                log.warning("No text found in %s", source.path)
        return "\n\n".join(texts)

    def synthesize(self, text: str, output: Path) -> Path:
        if self.engine is None:
            raise Anything2SpeechError("No TTS engine configured")
        engine = self.engine
        chunks = chunk(text, self.options.chunk_chars)
        if not chunks:
            raise Anything2SpeechError("Nothing to synthesize: extracted text is empty")

        output.parent.mkdir(parents=True, exist_ok=True)
        parts_dir = output.with_name(f".{output.name}.parts")
        parts_dir.mkdir(exist_ok=True)

        log.info("Synthesizing %d chunk(s), %d characters", len(chunks), len(text))
        parts: list[Path] = []
        for i, piece in enumerate(
            tqdm(chunks, desc="Synthesizing", unit="chunk", disable=not self.options.progress)
        ):
            part = parts_dir / f"{i:05d}-{self._digest(engine, piece)}.mp3"
            parts.append(part)
            if part.exists() and part.stat().st_size > 0:
                log.debug("Reusing cached %s", part.name)
                continue
            audio = engine.synthesize(piece)
            tmp = part.with_suffix(".tmp")
            tmp.write_bytes(audio)
            tmp.replace(part)
            if self.options.delay and i < len(chunks) - 1:
                time.sleep(self.options.delay)

        self._assemble(parts, output)
        if not self.options.keep_parts:
            shutil.rmtree(parts_dir, ignore_errors=True)
        return output

    def run(self, sources: list[Source], output: Path, *, save_text: bool = False) -> Path:
        text = self.extract_text(sources)
        if save_text:
            log.info("Extracted text saved to %s", self.save_text(text, output))
        return self.synthesize(text, output)

    @staticmethod
    def save_text(text: str, output: Path) -> Path:
        """Write text next to ``output`` with a .txt suffix."""
        text_path = output.with_suffix(".txt")
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text + "\n", encoding="utf-8")
        return text_path

    @staticmethod
    def _digest(engine: TTSEngine, piece: str) -> str:
        h = hashlib.sha256(f"{engine.cache_key}\0{piece}".encode())
        return h.hexdigest()[:12]

    @staticmethod
    def _assemble(parts: list[Path], output: Path) -> None:
        # MP3 is a frame-based stream; parts with the same encoding (as produced by
        # a single engine) can be concatenated byte-for-byte without re-encoding.
        tmp = output.with_name(f".{output.name}.tmp")
        with tmp.open("wb") as out:
            for part in parts:
                with part.open("rb") as src:
                    shutil.copyfileobj(src, out)
        tmp.replace(output)
