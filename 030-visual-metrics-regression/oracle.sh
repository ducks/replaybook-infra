#!/usr/bin/env bash
set -euo pipefail

sed -i 's/^CACHE_MAX_ENTRIES=0$/CACHE_MAX_ENTRIES=32/' \
  /etc/metrics-api/service.env
systemctl restart metrics-api.service
