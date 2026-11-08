from pathlib import Path

import pytest

from anything2speech.cli import main, plan_jobs, resolve_ocr_lang
from anything2speech.errors import Anything2SpeechError
from anything2speech.sources import discover


def test_resolve_ocr_lang():
    assert resolve_ocr_lang("uk", None) == "ukr"
    assert resolve_ocr_lang("uk", "ukr+eng") == "ukr+eng"
    with pytest.raises(Anything2SpeechError):
        resolve_ocr_lang("xx", None)


def test_plan_jobs_default_output_named_after_input(tmp_path: Path):
    f = tmp_path / "rabbit.txt"
    f.write_text("x")
    [(srcs, out)] = plan_jobs(discover([f]), [f], None, per_file=False)
    assert out == Path("output/rabbit.mp3") and len(srcs) == 1


def test_plan_jobs_per_file_detects_collisions(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "a.md").write_text("y")
    with pytest.raises(Anything2SpeechError):
        plan_jobs(discover([tmp_path]), [tmp_path], None, per_file=True)


def test_text_only_writes_txt(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    f = tmp_path / "in.txt"
    f.write_text("Hello   world")
    out = tmp_path / "res.mp3"
    assert main([str(f), "-o", str(out), "--text-only", "-q"]) == 0
    assert (tmp_path / "res.txt").read_text() == "Hello world\n"
    assert not out.exists()


def test_missing_input_returns_error(tmp_path: Path):
    assert main([str(tmp_path / "missing.txt"), "-q"]) == 1
