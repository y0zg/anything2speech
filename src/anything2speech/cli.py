"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from anything2speech import __version__
from anything2speech.errors import Anything2SpeechError
from anything2speech.pipeline import Pipeline, PipelineOptions
from anything2speech.sources import EXTENSIONS, OCR_LANGS, Source, SourceKind, discover
from anything2speech.tts import GTTSEngine

log = logging.getLogger("anything2speech")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anything2speech",
        description=(
            "Convert text files and images (OCR) into speech. Inputs can be any mix of "
            f"files and directories. Supported: {', '.join(sorted(EXTENSIONS))}."
        ),
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Files and/or directories")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Output .mp3 file (default: output/<first input>.mp3). "
            "With --per-file, an output directory (default: output/)."
        ),
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Write one audio file per input file instead of combining everything",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into directories")

    lang = parser.add_argument_group("language")
    lang.add_argument("-l", "--lang", default="uk", help="Speech language, gTTS code (default: uk)")
    lang.add_argument(
        "--ocr-lang",
        help="Tesseract language(s), e.g. 'ukr' or 'ukr+eng' (default: derived from --lang)",
    )
    lang.add_argument("--tld", default="com", help="Google domain for accent, e.g. com, co.uk")
    lang.add_argument("--slow", action="store_true", help="Slower speech")

    proc = parser.add_argument_group("processing")
    proc.add_argument("--encoding", default="utf-8", help="Text file encoding (default: utf-8)")
    proc.add_argument(
        "--chunk-chars", type=int, default=2000, help="Max characters per TTS chunk (default: 2000)"
    )
    proc.add_argument(
        "--delay", type=float, default=1.0, help="Seconds to wait between chunks (default: 1)"
    )
    proc.add_argument("--retries", type=int, default=5, help="Attempts per chunk (default: 5)")
    proc.add_argument(
        "--save-text", action="store_true", help="Also save the extracted text next to the audio"
    )
    proc.add_argument(
        "--text-only",
        action="store_true",
        help="Only extract text (to .txt); skip speech synthesis. Handy for checking OCR.",
    )
    proc.add_argument(
        "--keep-parts", action="store_true", help="Keep per-chunk audio after assembling"
    )

    out = parser.add_argument_group("output")
    out.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    out.add_argument("-q", "--quiet", action="store_true", help="Errors only, no progress bars")
    out.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def resolve_ocr_lang(lang: str, ocr_lang: str | None) -> str:
    if ocr_lang:
        return ocr_lang
    if lang in OCR_LANGS:
        return OCR_LANGS[lang]
    raise Anything2SpeechError(
        f"No default Tesseract language for '{lang}'; pass --ocr-lang explicitly"
    )


def plan_jobs(
    sources: list[Source], inputs: Sequence[Path], output: Path | None, per_file: bool
) -> list[tuple[list[Source], Path]]:
    """Decide which sources go into which output file."""
    if per_file:
        out_dir = output or Path("output")
        targets = [out_dir / f"{s.path.stem}.mp3" for s in sources]
        seen: set[Path] = set()
        for target in targets:
            if target in seen:
                raise Anything2SpeechError(
                    f"Two inputs map to {target}; rename them or don't use --per-file"
                )
            seen.add(target)
        return [([s], t) for s, t in zip(sources, targets, strict=True)]

    if output is None:
        first = inputs[0].resolve()
        output = Path("output") / f"{first.stem if first.is_file() else first.name}.mp3"
    elif output.suffix.lower() != ".mp3":
        output = output.with_suffix(".mp3")
    return [(sources, output)]


def configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.ERROR if quiet else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", stream=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose, args.quiet)

    try:
        sources = discover(args.inputs, recursive=args.recursive)
        if not sources:
            raise Anything2SpeechError("No supported input files found")

        needs_ocr = any(s.kind is SourceKind.IMAGE for s in sources)
        ocr_lang = resolve_ocr_lang(args.lang, args.ocr_lang) if needs_ocr else ""
        options = PipelineOptions(
            ocr_lang=ocr_lang,
            encoding=args.encoding,
            chunk_chars=args.chunk_chars,
            delay=args.delay,
            keep_parts=args.keep_parts,
            progress=not args.quiet,
        )

        engine = (
            None
            if args.text_only
            else GTTSEngine(args.lang, tld=args.tld, slow=args.slow, max_attempts=args.retries)
        )
        pipeline = Pipeline(engine, options)

        for job_sources, output in plan_jobs(sources, args.inputs, args.output, args.per_file):
            if args.text_only:
                print(pipeline.save_text(pipeline.extract_text(job_sources), output))
            else:
                print(pipeline.run(job_sources, output, save_text=args.save_text))
    except (Anything2SpeechError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted. Re-run the same command to resume from cached chunks.")
        return 130
    return 0
