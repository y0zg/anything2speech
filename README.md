# anything2speech

Turn **text files** and **images** (via OCR) into a single MP3, e.g. scanned book pages or a
`.txt` novel into an audiobook. It uses [Tesseract](https://github.com/tesseract-ocr/tesseract)
for OCR and [gTTS](https://github.com/pndurette/gTTS) (Google Translate TTS) for speech.

- Mix inputs freely: files, directories, images and text in one run
- Supported: `.txt` `.md` `.text`, `.jpg` `.jpeg` `.png` `.bmp` `.tif(f)` `.webp` `.gif`,
  and `.docx` (optional extra)
- Directory contents are sorted naturally (`page2` comes before `page10`)
- **Resumable**: each chunk is cached, so if a long book hits a rate limit you can re-run
  the same command and it continues where it stopped
- Cleans up OCR output (joins hyphenated words and broken lines)

## Quick start

```bash
make install                      # app + locked deps
make ocr                          # Tesseract + ukr/eng data (only needed for images)
make run IN=examples/rabbit.txt   # → output/rabbit.mp3
make run IN="intro.txt scans/" OUT=output/book.mp3 ARGS="--save-text"
make text IN=scans/               # only extract/OCR text, no audio
make                              # list all targets
```

## Install

Requires Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/). The `make` targets wrap the commands below.

```bash
uv sync                    # creates .venv with the locked dependencies
uv sync --extra docx       # optionally add .docx support
uv run anything2speech --help
```

Or install the CLI globally: `uv tool install .` (`uv tool install '.[docx]'` for .docx support).

### Tesseract (only needed for images)

| OS      | Command                                                                                    |
|---------|--------------------------------------------------------------------------------------------|
| macOS   | `brew install tesseract tesseract-lang`                                                    |
| Debian  | `sudo apt install tesseract-ocr tesseract-ocr-ukr`                                         |
| Windows | [installer](https://github.com/UB-Mannheim/tesseract/wiki), then pick the extra languages  |

If language data lives somewhere non-standard, set `TESSDATA_PREFIX` to the `tessdata` directory.

### Docker

The Docker image includes Tesseract with Ukrainian and English language data:

```bash
docker build -t anything2speech .
docker run --rm -v "$PWD:/work" anything2speech examples/rabbit.txt -o output/rabbit.mp3
# other OCR languages:
docker build --build-arg TESSERACT_LANGS="ukr eng deu" -t anything2speech .
```

## Usage

```bash
# A text file -> output/rabbit.mp3
uv run anything2speech examples/rabbit.txt

# A folder of scanned pages plus an intro text file, combined into one file
uv run anything2speech intro.txt scans/ -o output/book.mp3

# One MP3 per input file
uv run anything2speech texts/ --per-file -o output/

# English, British accent; OCR in both Ukrainian and English
uv run anything2speech page.png -l en --tld co.uk --ocr-lang ukr+eng

# Check the OCR result before spending time on synthesis
uv run anything2speech scans/ --text-only
```

Main options (see `--help` for all of them):

| Option                       | Meaning                                                           |
|------------------------------|-------------------------------------------------------------------|
| `-o, --output`               | Output `.mp3` (or a directory with `--per-file`)                  |
| `-l, --lang`                 | Speech language (gTTS code, default `uk`)                         |
| `--ocr-lang`                 | Tesseract language(s), default derived from `--lang`              |
| `-r, --recursive`            | Recurse into sub-directories                                      |
| `--save-text` / `--text-only`| Save the extracted text / only extract text                       |
| `--encoding`                 | Text file encoding (default `utf-8`, e.g. `cp1251`)               |
| `--chunk-chars`, `--delay`, `--retries` | Tune request size and rate-limit behavior              |

If you interrupt a run or it fails, run the same command again. Finished chunks are kept in
`.<name>.mp3.parts/` next to the output and deleted once the MP3 is assembled.

## Development

`make dev` installs everything and sets up the git hooks. `make check` runs everything CI runs
(lint, format check, type-check, tests and the gitleaks secret scan). The raw commands:

```bash
uv sync --all-extras
uv run pre-commit install   # once: gitleaks blocks commits containing secrets
uv run pytest          # tests (no network needed)
uv run ruff check      # lint
uv run ruff format     # format
uv run mypy            # type-check
uv build               # build sdist + wheel into dist/
```

Project layout:

```
src/anything2speech/
  cli.py        argument parsing, job planning
  pipeline.py   extract -> chunk -> synthesize (cached) -> assemble
  sources.py    input discovery + text/OCR/docx extraction
  text.py       normalization and chunking
  tts.py        TTS engine protocol + gTTS implementation
tests/          unit tests (fake TTS engine, no network)
```

To add a TTS engine, implement the `TTSEngine` protocol in `tts.py` (`name`, `cache_key`,
`synthesize(text) -> bytes`).

### Supply-chain hardening

- A [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook, pinned to a commit SHA,
  scans staged changes for secrets. Bump it with `uv run pre-commit autoupdate --freeze`.
- GitHub Actions are pinned to full commit SHAs, and Docker base images are pinned by digest.
  Dependabot keeps both up to date.
- The CI token is read-only (`permissions: contents: read`), checkout doesn't keep
  credentials, and harden-runner audits network egress.
- `[tool.uv] exclude-newer = "7 days"` sets a minimum release age: newly published package
  versions are ignored until they are a week old. Dependabot uses the same 7-day cooldown.
- `uv.lock` records hashes. CI installs with `--locked`, and the Docker image installs with
  `pip --require-hashes`.
