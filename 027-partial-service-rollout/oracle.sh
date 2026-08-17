#!/usr/bin/env bash
set -euo pipefail

psql --host 127.0.0.1 --username orders --dbname orders \
  --set ON_ERROR_STOP=1 \
  --file /var/lib/order-api/releases/20260817/db/migrate/202608170001_add_deployment_generation.sql

sed -i \
  's|^RELEASE_DIR=.*|RELEASE_DIR=/var/lib/order-api/current|' \
  /etc/order-api/green.env

systemctl restart order-api-blue.service order-api-green.service
