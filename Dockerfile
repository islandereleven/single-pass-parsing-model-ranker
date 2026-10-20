FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

RUN python -m pip install poetry==2.2.1

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root --no-ansi

COPY src ./src
RUN poetry build --format wheel
RUN /app/.venv/bin/pip install --no-deps dist/*.whl


FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 ranker \
    && mkdir /workspace \
    && chown ranker:ranker /workspace

COPY --from=builder /app/.venv /app/.venv

WORKDIR /workspace
USER ranker

ENTRYPOINT ["single-pass-ranker", "run"]
