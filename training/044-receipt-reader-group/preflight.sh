#!/usr/bin/env bash
set -euo pipefail
python "$(dirname "$0")/check.py" "$1" preflight "$2"
