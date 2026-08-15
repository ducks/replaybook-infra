#!/usr/bin/env bash
set -euo pipefail

migration="/var/lib/discourse/releases/20260814/db/migrate/202608140001_add_export_delivery.sql"

psql \
  --host 127.0.0.1 \
  --username discourse \
  --dbname discourse \
  --set ON_ERROR_STOP=1 \
  --file "$migration"

sed -i \
  -e 's#/var/lib/discourse/releases/20260813#/var/lib/discourse/current#' \
  -e 's/RELEASE_VERSION=20260813/RELEASE_VERSION=20260814/' \
  /etc/discourse/green.env

systemctl restart \
  discourse-web-green.service \
  discourse-export-worker.service
