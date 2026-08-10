#!/usr/bin/env bash
set -euo pipefail

exec gunicorn \
  --bind 127.0.0.1:3000 \
  --reuse-port \
  --worker-class gthread \
  --workers "${WEB_WORKERS}" \
  --threads "${WEB_THREADS}" \
  --timeout "${REQUEST_TIMEOUT}" \
  app:application
