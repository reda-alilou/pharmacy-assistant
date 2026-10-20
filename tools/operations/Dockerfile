FROM ghcr.io/astral-sh/uv:0.11.19 AS uv
FROM python:3.12-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
COPY services/core/ ./services/core/
COPY services/language/ ./services/language/
COPY packages/ ./packages/
COPY tools/operations/ ./tools/operations/
COPY tools/evaluation/pyproject.toml ./tools/evaluation/pyproject.toml
RUN uv sync --frozen --no-dev --no-editable --package pharmacy-ops

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PHARMACY_PROJECT_ROOT=/app PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=build /app/.venv /app/.venv
COPY services/core/alembic.ini ./services/core/
COPY services/core/migrations/ ./services/core/migrations/
COPY services/language/alembic.ini ./services/language/
COPY services/language/migrations/ ./services/language/migrations/
COPY data/imports/ammps_medications_enriched.jsonl data/imports/pharmacies_rabat.jsonl ./data/imports/
USER 10001:10001
ENTRYPOINT ["pharmacy-db", "--from-environment"]
