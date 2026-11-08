from pathlib import Path

import pytest

from anything2speech.errors import ExtractionError, UnsupportedFileError
from anything2speech.sources import Source, SourceKind, discover, extract


def test_discover_mixed_directory_natural_order(tmp_path: Path):
    for name in ["page10.png", "page2.jpg", "notes.txt", "ignore.pdf", ".hidden.txt"]:
        (tmp_path / name).write_bytes(b"")
    found = discover([tmp_path])
    assert [s.path.name for s in found] == ["notes.txt", "page2.jpg", "page10.png"]
    assert [s.kind for s in found] == [SourceKind.TEXT, SourceKind.IMAGE, SourceKind.IMAGE]


def test_discover_explicit_files_keep_order(tmp_path: Path):
    b, a = tmp_path / "b.txt", tmp_path / "a.txt"
    b.write_text("b")
    a.write_text("a")
    assert [s.path for s in discover([b, a])] == [b, a]


def test_discover_recursive(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.md").write_text("x")
    assert discover([tmp_path]) == []
    assert len(discover([tmp_path], recursive=True)) == 1


def test_discover_rejects_unsupported_file(tmp_path: Path):
    f = tmp_path / "book.pdf"
    f.write_bytes(b"")
    with pytest.raises(UnsupportedFileError):
        discover([f])


def test_discover_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        discover([tmp_path / "nope"])


def test_extract_text_strips_bom(tmp_path: Path):
    f = tmp_path / "t.txt"
    f.write_bytes("﻿Привіт,  світе!".encode())
    assert extract(Source(f, SourceKind.TEXT), ocr_lang="ukr") == "Привіт, світе!"


def test_extract_text_bad_encoding(tmp_path: Path):
    f = tmp_path / "t.txt"
    f.write_bytes("Привіт".encode("cp1251"))
    with pytest.raises(ExtractionError):
        extract(Source(f, SourceKind.TEXT), ocr_lang="ukr")
    assert extract(Source(f, SourceKind.TEXT), ocr_lang="ukr", encoding="cp1251") == "Привіт"
