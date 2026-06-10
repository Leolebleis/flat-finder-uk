FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY flat_finder/ flat_finder/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
ENV PATH="/app/.venv/bin:$PATH"

FROM runtime AS ui
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn flat_finder.api.app:app --host 0.0.0.0 --port 8000"]

FROM runtime AS scraper
VOLUME /app/data
ENV FLAT_FINDER_DB=/app/data/flat_finder.db
CMD ["sh", "-c", "alembic upgrade head && while true; do python -m flat_finder.scraper.runner; sleep 900; done"]
