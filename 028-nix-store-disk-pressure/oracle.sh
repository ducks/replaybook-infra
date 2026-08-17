#!/usr/bin/env bash
set -euo pipefail

sed -i \
  's/^CACHE_WARMUP=.*/CACHE_WARMUP=disabled/' \
  /etc/replaybook/cache-warmup.env

nix-collect-garbage
systemctl restart billing-ledger.service nginx.service
