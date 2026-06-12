#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 dev_tools/sync_dev_to_main.py "$@"
