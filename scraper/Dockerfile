FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY shared/ shared/
COPY scraper/ scraper/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

VOLUME /app/data
ENV PATH="/app/.venv/bin:$PATH"
ENV FLAT_FINDER_DB=/app/data/scraper.db

CMD ["sh", "-c", "while true; do python -m scraper.scraper; sleep 900; done"]
