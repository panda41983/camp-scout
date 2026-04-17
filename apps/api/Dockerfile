FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files (hatchling needs source to build)
COPY pyproject.toml uv.lock ./
COPY campscout/ campscout/
COPY alembic/ alembic/
COPY alembic.ini ./

# Sync dependencies into a venv
RUN uv sync --frozen --no-dev

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy venv and source from builder
COPY --from=builder /app/.venv .venv/
COPY --from=builder /app/campscout campscout/
COPY --from=builder /app/alembic alembic/
COPY --from=builder /app/alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "campscout.main:app", "--host", "0.0.0.0", "--port", "8080"]
