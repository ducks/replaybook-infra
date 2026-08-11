#!/usr/bin/env bash
set -euo pipefail

migration="/var/lib/discourse/current/db/migrate/202608110001_add_delivery_state.sql"
[[ -f "$migration" ]]

psql \
  --host 127.0.0.1 \
  --username replaybook \
  --dbname discourse_secondary \
  --set ON_ERROR_STOP=1 \
  --file "$migration"

systemctl restart discourse-worker.service
