#!/usr/bin/env bash
set -euo pipefail
install -m 0644 /etc/delivery/pki/platform.pem /etc/dispatch/ca-bundle.pem
systemctl restart delivery-dispatch.service
