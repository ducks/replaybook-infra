#!/usr/bin/env bash
set -euo pipefail
exec python "$(dirname "$0")/lifecycle.py" preflight "$1" "$2"
