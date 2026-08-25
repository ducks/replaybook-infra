#!/usr/bin/env bash
set -euo pipefail

sed -i 's#/var/lib/checkout/releases/41#/var/lib/checkout/current#' \
  /etc/checkout/blue.env \
  /etc/checkout/green.env \
  /etc/checkout/worker.env

systemctl restart \
  checkout-web-blue.service \
  checkout-web-green.service \
  checkout-worker.service
