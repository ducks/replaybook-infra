#!/usr/bin/env bash
set -euo pipefail

sed -i \
  's/open_documents().lock().unwrap().push(file);/drop(file);/' \
  /var/lib/fd-service/src/main.rs
cd /var/lib/fd-service
cargo build --release --offline
systemctl restart document-service.service
