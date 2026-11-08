# anything2speech: common tasks. Run `make` to list them.
#
# Usage examples:
#   make install
#   make run IN=examples/rabbit.txt
#   make run IN="intro.txt scans/" OUT=output/book.mp3 ARGS="--save-text"
#   make text IN=scans/

SHELL        := /bin/bash
.SHELLFLAGS  := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV     ?= uv
IMAGE  ?= anything2speech
IN     ?=
OUT    ?=
ARGS   ?=
TESSERACT_LANGS ?= ukr eng

OUT_FLAG := $(if $(OUT),-o $(OUT),)

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [IN=... OUT=... ARGS=...]\n\n"} \
		/^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2} \
		/^## / {printf "\n\033[1m%s\033[0m\n", substr($$0, 4)}' $(MAKEFILE_LIST)

## Setup

.PHONY: check-uv
check-uv:
	@command -v $(UV) >/dev/null || { \
		echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }

.PHONY: install
install: check-uv ## Install the app and its locked runtime deps (with .docx support)
	$(UV) sync --locked --no-dev --extra docx

.PHONY: dev
dev: check-uv ## Install everything for development + git hooks (gitleaks)
	$(UV) sync --locked --all-extras
	$(UV) run pre-commit install

.PHONY: ocr
ocr: ## Install Tesseract + Ukrainian/English language data (macOS/Debian)
	@if command -v brew >/dev/null; then \
		brew install tesseract tesseract-lang; \
	elif command -v apt-get >/dev/null; then \
		sudo apt-get update && sudo apt-get install -y tesseract-ocr \
			$(foreach l,$(TESSERACT_LANGS),tesseract-ocr-$(l)); \
	else \
		echo "Install Tesseract manually: https://tesseract-ocr.github.io/tessdoc/Installation.html"; exit 1; \
	fi
	@tesseract --list-langs

.PHONY: tool
tool: check-uv ## Install the `anything2speech` command globally (uv tool)
	$(UV) tool install --force '.[docx]'

## Usage

.PHONY: run
run: _require-in ## Convert IN to speech (OUT=file.mp3, ARGS="extra flags")
	$(UV) run --no-dev anything2speech $(IN) $(OUT_FLAG) $(ARGS)

.PHONY: text
text: _require-in ## Only extract text/OCR from IN to .txt (no audio)
	$(UV) run --no-dev anything2speech $(IN) $(OUT_FLAG) --text-only $(ARGS)

.PHONY: example
example: ## Convert the bundled sample (examples/rabbit.txt; long, many requests)
	$(UV) run --no-dev anything2speech examples/rabbit.txt $(OUT_FLAG) $(ARGS)

.PHONY: _require-in
_require-in:
	@test -n "$(IN)" || { echo 'Set IN, e.g.: make $(MAKECMDGOALS) IN=examples/rabbit.txt'; exit 1; }

## Quality

.PHONY: test
test: ## Run tests
	$(UV) run pytest

.PHONY: lint
lint: ## Lint + format check + type-check
	$(UV) run ruff check
	$(UV) run ruff format --check
	$(UV) run mypy

.PHONY: fmt
fmt: ## Auto-format and fix lint issues
	$(UV) run ruff format
	$(UV) run ruff check --fix

.PHONY: secrets
secrets: ## Scan the whole repo for secrets (gitleaks)
	$(UV) run pre-commit run gitleaks --all-files

.PHONY: check
check: lint test secrets ## Everything CI checks, locally

## Build

.PHONY: build
build: ## Build sdist + wheel into dist/
	$(UV) build

.PHONY: docker-build
docker-build: ## Build the Docker image (TESSERACT_LANGS="ukr eng ...")
	docker build --build-arg TESSERACT_LANGS="$(TESSERACT_LANGS)" -t $(IMAGE) .

.PHONY: docker-run
docker-run: _require-in ## Run via Docker on IN (paths relative to repo)
	docker run --rm -v "$(CURDIR):/work" $(IMAGE) $(IN) $(OUT_FLAG) $(ARGS)

.PHONY: lock
lock: ## Re-resolve dependencies (respects the 7-day release cooldown)
	$(UV) lock --upgrade

.PHONY: clean
clean: ## Remove caches and build artifacts (keeps output/)
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
