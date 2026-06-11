#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m trial_registry.cli --input-file examples/literature_ids.txt --input-format txt --formats csv --output-dir output

echo
echo "Done. Results are in the output folder."
read -r -p "Press Enter to close this window."
