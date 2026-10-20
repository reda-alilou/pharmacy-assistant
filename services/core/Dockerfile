FROM ghcr.io/astral-sh/uv:0.11.19 AS uv
FROM python:3.12-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
COPY services/core/ ./services/core/
COPY services/language/pyproject.toml ./services/language/pyproject.toml
COPY tools/operations/pyproject.toml ./tools/operations/pyproject.toml
COPY tools/evaluation/pyproject.toml ./tools/evaluation/pyproject.toml
COPY packages/ ./packages/
RUN uv sync --frozen --no-dev --no-editable --package pharmacy-core

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PHARMACY_PROJECT_ROOT=/app PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=build /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "pharmacy_core.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api", "--no-access-log"]
