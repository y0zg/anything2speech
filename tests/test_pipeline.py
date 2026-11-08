from pathlib import Path

import pytest

from anything2speech.errors import Anything2SpeechError, SynthesisError
from anything2speech.pipeline import Pipeline, PipelineOptions
from anything2speech.sources import discover


class FakeEngine:
    name = "fake"
    cache_key = "fake:v1"

    def __init__(self, fail_on: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on

    def synthesize(self, text: str) -> bytes:
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            self.fail_on = None
            raise SynthesisError("rate limited")
        self.calls.append(text)
        return f"<{text}>".encode()


OPTS = PipelineOptions(chunk_chars=10, delay=0, progress=False)


def _write_inputs(tmp_path: Path) -> list[Path]:
    src = tmp_path / "in"
    src.mkdir()
    (src / "1.txt").write_text("alpha beta\ngamma")
    (src / "2.md").write_text("delta")
    return [src]


def test_run_combines_all_chunks_in_order(tmp_path: Path):
    engine = FakeEngine()
    out = tmp_path / "out" / "book.mp3"
    Pipeline(engine, OPTS).run(discover(_write_inputs(tmp_path)), out, save_text=True)

    assert engine.calls == ["alpha beta", "gamma", "delta"]
    assert out.read_bytes() == b"<alpha beta><gamma><delta>"
    assert out.with_suffix(".txt").read_text().startswith("alpha beta")
    assert not any(p.name.endswith(".parts") for p in out.parent.iterdir())


def test_resume_after_failure_reuses_cached_chunks(tmp_path: Path):
    sources = discover(_write_inputs(tmp_path))
    out = tmp_path / "book.mp3"

    engine = FakeEngine(fail_on=2)
    with pytest.raises(SynthesisError):
        Pipeline(engine, OPTS).run(sources, out)
    assert engine.calls == ["alpha beta", "gamma"]
    assert not out.exists()

    engine.calls.clear()
    Pipeline(engine, OPTS).run(sources, out)
    assert engine.calls == ["delta"]  # first two came from cache
    assert out.read_bytes() == b"<alpha beta><gamma><delta>"


def test_empty_text_is_an_error(tmp_path: Path):
    with pytest.raises(Anything2SpeechError):
        Pipeline(FakeEngine(), OPTS).synthesize("  ", tmp_path / "x.mp3")
