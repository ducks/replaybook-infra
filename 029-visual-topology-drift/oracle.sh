#!/usr/bin/env bash
set -euo pipefail

sed -i 's|127.0.0.1:3101/health|127.0.0.1:3100/health|' \
  /etc/reservation-api/nginx.conf
sed -i 's|redis://127.0.0.1:6379/7|redis://127.0.0.1:6379/4|' \
  /etc/reservation-api/worker.env

systemctl restart reservation-worker.service incident-nginx.service
