#!/usr/bin/env bash
set -euo pipefail
sed -i 's/READER_GROUP=.*/READER_GROUP=receipts/' /etc/receipts/reader.env
systemctl restart receipt-reader.service
