import pytest

from anything2speech.text import chunk, normalize


def test_normalize_joins_hyphenated_line_breaks():
    assert normalize("сло-\nво") == "слово"


def test_normalize_join_lines_keeps_paragraphs():
    raw = "first line\nsecond line\n\n\n\nnext para"
    assert normalize(raw, join_lines=True) == "first line second line\n\nnext para"


def test_normalize_preserves_lines_by_default():
    assert normalize("  a  \r\nb\t\tc ") == "a\nb c"


def test_chunk_respects_limit_and_keeps_all_words():
    text = "\n".join(f"Sentence number {i}. Another one here!" for i in range(200))
    chunks = chunk(text, 120)
    assert all(0 < len(c) <= 120 for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_chunk_packs_small_paragraphs_together():
    assert chunk("a\nb\nc", 100) == ["a\nb\nc"]


def test_chunk_splits_oversized_sentence_and_word():
    text = "word " * 50 + "x" * 25
    chunks = chunk(text, 10)
    assert all(len(c) <= 10 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_chunk_empty():
    assert chunk("   \n\n ") == []


def test_chunk_rejects_bad_size():
    with pytest.raises(ValueError):
        chunk("abc", 0)
