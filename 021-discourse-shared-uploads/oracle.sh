#!/usr/bin/env bash
set -euo pipefail

install -d -m 0755 /var/lib/discourse/shared/standalone/uploads/default
cp -a /var/lib/discourse/releases/20260810/public/uploads/default/. \
  /var/lib/discourse/shared/standalone/uploads/default/
sed -i \
  's|^UPLOAD_ROOT=.*|UPLOAD_ROOT=/var/lib/discourse/shared/standalone/uploads/default|' \
  /etc/discourse/discourse.env
systemctl restart discourse-web.service
