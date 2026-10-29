#!/usr/bin/env bash
set -euo pipefail
exec python "$(dirname "$0")/lifecycle.py" "$2" "$1" "$3"
