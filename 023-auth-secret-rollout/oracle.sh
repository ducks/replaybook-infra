#!/usr/bin/env bash
set -euo pipefail

set -a
source /etc/replaybook/session-common.env
source /etc/replaybook/session-rotation.env
set +a
/var/lib/session-app/current/rotate_sessions.py

sed -i \
  -e 's/^RELEASE_VERSION=.*/RELEASE_VERSION=20260812/' \
  -e 's/^SESSION_SECRET=.*/SESSION_SECRET=current-signing-secret-20260812/' \
  /etc/replaybook/session-old.env
sed -i \
  's/^OLD_SESSION_SECRET=.*/OLD_SESSION_SECRET=current-signing-secret-20260812/' \
  /etc/replaybook/session-rotation.env

systemctl restart session-old.service session-new.service
