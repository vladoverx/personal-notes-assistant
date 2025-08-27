# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Install uv (https://docs.astral.sh/uv/)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency manifests first for better caching
COPY pyproject.toml /app/pyproject.toml

# Install project dependencies into a local virtual environment (.venv)
# Use BuildKit cache mounts to speed up resolves; falls back gracefully if disabled
# Use --no-dev for runtime-only dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Create a non-root user (before copying files we will chown)
RUN useradd -m appuser

# Copy application code
COPY . /app

# Ensure non-root user can read project files and virtualenv
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Container healthcheck (FastAPI health endpoint)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Use tini as PID 1 for proper signal handling/child reaping
ENTRYPOINT ["/usr/bin/tini", "--"]
# Start script handles worker count and server config
CMD ["sh", "docker/start.sh"]


