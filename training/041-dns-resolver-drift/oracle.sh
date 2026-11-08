#!/usr/bin/env bash
set -euo pipefail
sed -i 's/127\.0\.0\.2/127.0.0.1/' /etc/discovery/resolv.conf
systemctl restart resolver-policy.service discovery-web.service nginx.service
