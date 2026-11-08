"""Text normalization and chunking."""

from __future__ import annotations

import re

_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SOFT_BREAK = re.compile(r"(?<!\n)\n(?!\n)")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def normalize(text: str, *, join_lines: bool = False) -> str:
    """Clean up extracted text before synthesis.

    Args:
        text: Raw text.
        join_lines: Join single line breaks into spaces. Useful for OCR output, where
            line breaks mark the edge of the page rather than the end of a paragraph.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    if join_lines:
        text = _SOFT_BREAK.sub(" ", text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _split_long(piece: str, max_chars: int) -> list[str]:
    """Split a piece that exceeds max_chars on sentences, then on words."""
    if len(piece) <= max_chars:
        return [piece]

    parts: list[str] = []
    for sentence in _SENTENCE_END.split(piece):
        if len(sentence) <= max_chars:
            parts.append(sentence)
            continue
        # Pathological sentence: fall back to word boundaries (or hard cuts).
        current = ""
        for raw_word in sentence.split():
            word = raw_word
            while len(word) > max_chars:
                if current:
                    parts.append(current)
                    current = ""
                parts.append(word[:max_chars])
                word = word[max_chars:]
            candidate = f"{current} {word}" if current else word
            if len(candidate) > max_chars:
                parts.append(current)
                current = word
            else:
                current = candidate
        if current:
            parts.append(current)
    return parts


def chunk(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks of at most max_chars, preferring natural boundaries.

    Paragraphs are kept together when possible, then sentences, then words.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    pieces: list[str] = []
    for line in text.split("\n"):
        paragraph = line.strip()
        if paragraph:
            pieces.extend(_split_long(paragraph, max_chars))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n{piece}" if current else piece
        if len(candidate) > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
