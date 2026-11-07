#!/usr/bin/env bash
set -euo pipefail
sed -i 's/^STORAGE_OWNER=.*/STORAGE_OWNER=receipt-writer/' /etc/receipts/storage.env
systemctl restart receipt-storage-policy.service receipt-web.service nginx.service
