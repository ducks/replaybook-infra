#!/usr/bin/env bash
set -euo pipefail
sed -i 's/DECODER=1/DECODER=2/' /etc/notification/notification-worker.env
systemctl restart notification-worker.service
