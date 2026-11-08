#!/usr/bin/env bash
set -euo pipefail
sed -i '/inventory\.internal/d' /etc/discovery/hosts
systemctl restart resolver-policy.service discovery-web.service nginx.service
