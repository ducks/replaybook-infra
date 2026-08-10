#!/usr/bin/env bash
set -euo pipefail

sed -i \
  's/const runTask = (done) => { execFileSync(sleep, \["1"\]); done(); };/const runTask = (done) => { execFile(sleep, ["1"], done); };/' \
  /var/lib/checkout-node/server.js
systemctl restart checkout-node.service
