#!/usr/bin/env sh
set -eu

# Default values
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-}"
LOG_LEVEL="${LOG_LEVEL:-info}"
TIMEOUT="${TIMEOUT:-60}"
GRACEFUL_TIMEOUT="${GRACEFUL_TIMEOUT:-30}"
KEEPALIVE="${KEEPALIVE:-5}"
# Recycle workers to mitigate leaks and keep memory low on small instances
MAX_REQUESTS="${MAX_REQUESTS:-1000}"
MAX_REQUESTS_JITTER="${MAX_REQUESTS_JITTER:-100}"
# Log to stdout by default so Docker can collect the logs
ACCESS_LOG="${ACCESS_LOG:--}"
# Use tmp in-memory dir for worker tmpfiles (small but faster); override if needed
WORKER_TMP_DIR="${WORKER_TMP_DIR:-/dev/shm}"

# Determine number of workers if not explicitly set
if [ -z "${WORKERS}" ]; then
  if command -v nproc >/dev/null 2>&1; then
    CPU_COUNT=$(nproc)
  else
    CPU_COUNT=2
  fi
  if [ "$CPU_COUNT" -le 2 ]; then
    WORKERS=1
  else
    WORKERS=$CPU_COUNT
  fi
fi

# Support running behind a reverse proxy
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-*}"
export FORWARDED_ALLOW_IPS

# Use uv to run the app; gunicorn with uvicorn workers is common for production
exec uv run \
  gunicorn app.main:app \
  --bind "${HOST}:${PORT}" \
  --workers "${WORKERS}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout "${TIMEOUT}" \
  --graceful-timeout "${GRACEFUL_TIMEOUT}" \
  --keep-alive "${KEEPALIVE}" \
  --max-requests "${MAX_REQUESTS}" \
  --max-requests-jitter "${MAX_REQUESTS_JITTER}" \
  --access-logfile "${ACCESS_LOG}" \
  --worker-tmp-dir "${WORKER_TMP_DIR}" \
  --log-level "${LOG_LEVEL}"


