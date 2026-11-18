#!/usr/bin/env bash
set -euo pipefail
exec python "$(dirname "$0")/controller.py" preflight "$1" "$2"
