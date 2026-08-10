#!/usr/bin/env bash
set -euo pipefail

sed -i 's|RELEASE_DIR=/var/lib/checkout/releases/20260809|RELEASE_DIR=/var/lib/checkout/current|' /etc/replaybook/express.env
systemctl restart checkout-sidekiq-express.service
