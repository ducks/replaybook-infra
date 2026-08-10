#!/usr/bin/env bash
set -euo pipefail

sed -i \
  -e 's/^WEB_WORKERS=.*/WEB_WORKERS=1/' \
  -e 's/^WEB_THREADS=.*/WEB_THREADS=4/' \
  -e 's/^REQUEST_TIMEOUT=.*/REQUEST_TIMEOUT=10/' \
  /etc/replaybook/export-web.env
systemctl restart export-web.service
