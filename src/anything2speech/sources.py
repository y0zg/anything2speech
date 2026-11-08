"""Discovering input files and extracting text from them."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from anything2speech.errors import ExtractionError, UnsupportedFileError
from anything2speech.text import normalize

log = logging.getLogger(__name__)


class SourceKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCX = "docx"


EXTENSIONS: dict[str, SourceKind] = {
    **dict.fromkeys((".txt", ".text", ".md"), SourceKind.TEXT),
    **dict.fromkeys(
        (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"), SourceKind.IMAGE
    ),
    ".docx": SourceKind.DOCX,
}

# gTTS language code -> Tesseract traineddata name, for the common cases.
OCR_LANGS: dict[str, str] = {
    "uk": "ukr",
    "en": "eng",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "it": "ita",
    "pl": "pol",
    "pt": "por",
    "nl": "nld",
    "cs": "ces",
    "sk": "slk",
    "ro": "ron",
    "bg": "bul",
    "ru": "rus",
    "tr": "tur",
    "ja": "jpn",
    "ko": "kor",
    "zh-CN": "chi_sim",
    "zh-TW": "chi_tra",
}


@dataclass(frozen=True)
class Source:
    path: Path
    kind: SourceKind


def kind_of(path: Path) -> SourceKind | None:
    return EXTENSIONS.get(path.suffix.lower())


def _natural_key(path: Path) -> list[int | str]:
    """Sort 'page2' before 'page10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(path))]


def discover(paths: Iterable[Path], *, recursive: bool = False) -> list[Source]:
    """Expand files and directories into an ordered list of supported sources.

    Explicit files keep the order given; directory contents are naturally sorted.
    """
    sources: list[Source] = []
    for path in paths:
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            found = [
                p
                for p in path.glob(pattern)
                if p.is_file() and not p.name.startswith(".") and kind_of(p)
            ]
            if not found:
                log.warning("No supported files in %s", path)
            sources.extend(Source(p, kind_of(p)) for p in sorted(found, key=_natural_key))  # type: ignore[arg-type]
        elif path.is_file():
            kind = kind_of(path)
            if kind is None:
                supported = ", ".join(sorted(EXTENSIONS))
                raise UnsupportedFileError(
                    f"{path}: unsupported file type (supported: {supported})"
                )
            sources.append(Source(path, kind))
        else:
            raise FileNotFoundError(f"No such file or directory: {path}")
    return sources


def _read_text(path: Path, encoding: str) -> str:
    try:
        # utf-8-sig transparently strips a BOM if present.
        enc = "utf-8-sig" if encoding.lower().replace("_", "-") == "utf-8" else encoding
        return path.read_text(encoding=enc)
    except UnicodeDecodeError as e:
        raise ExtractionError(f"{path}: cannot decode as {encoding} (try --encoding)") from e


def _read_image(path: Path, ocr_lang: str) -> str:
    import pytesseract
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as img:
            return str(pytesseract.image_to_string(img.convert("RGB"), lang=ocr_lang))
    except pytesseract.TesseractNotFoundError as e:
        raise ExtractionError(
            "Tesseract is not installed or not on PATH. See README for setup instructions."
        ) from e
    except pytesseract.TesseractError as e:
        raise ExtractionError(
            f"{path}: OCR failed ({e.message.strip()}). "
            f"Is the '{ocr_lang}' language data installed?"
        ) from e
    except (UnidentifiedImageError, OSError) as e:
        raise ExtractionError(f"{path}: cannot open image: {e}") from e


def _read_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as e:
        raise ExtractionError(
            "Reading .docx requires the optional extra: pip install 'anything2speech[docx]'"
        ) from e
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)


def extract(source: Source, *, ocr_lang: str, encoding: str = "utf-8") -> str:
    """Extract normalized text from a single source."""
    if source.kind is SourceKind.TEXT:
        raw, join_lines = _read_text(source.path, encoding), False
    elif source.kind is SourceKind.IMAGE:
        raw, join_lines = _read_image(source.path, ocr_lang), True
    else:
        raw, join_lines = _read_docx(source.path), False
    return normalize(raw, join_lines=join_lines)
