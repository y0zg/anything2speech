# Self-contained image with Tesseract (Ukrainian + English) preinstalled.
#   docker build -t anything2speech .
#   docker run --rm -v "$PWD:/work" anything2speech examples/rabbit.txt -o output/rabbit.mp3
# Base images are pinned by digest; Dependabot keeps them current.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd /uv /bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv build --offline --wheel --out-dir /dist
RUN uv export --offline --locked --no-dev --no-emit-project --all-extras -o /dist/requirements.txt

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ARG TESSERACT_LANGS="ukr eng"
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
       $(for l in $TESSERACT_LANGS; do echo tesseract-ocr-$l; done) \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /dist/ /tmp/dist/
# Install exactly the locked, hash-verified dependency set, then the app without deps.
RUN pip install --no-cache-dir --require-hashes -r /tmp/dist/requirements.txt \
    && pip install --no-cache-dir --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist
RUN useradd --create-home app
USER app
WORKDIR /work
ENTRYPOINT ["anything2speech"]
CMD ["--help"]
