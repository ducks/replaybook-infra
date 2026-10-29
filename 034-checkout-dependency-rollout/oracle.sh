#!/usr/bin/env bash
set -euo pipefail
sed -i 's/127.0.0.1:3009/127.0.0.1:3000/' /etc/checkout/routes.conf
sed -i 's/127.0.0.1:3001/127.0.0.1:3002/' /etc/checkout/checkout-api.env
systemctl restart checkout-api.service nginx.service
