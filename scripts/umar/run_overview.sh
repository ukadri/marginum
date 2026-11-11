#!/usr/bin/env bash
# Launches greatdatachunking_overview.py with the repo's venv already
# activated. Pass a CSV path as the first argument, or leave it off to use
# the labelled Big pieces reference recording.
#
# Usage:
#   ./run_overview.sh
#   ./run_overview.sh "/path/to/some_other_signal.csv"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DEFAULT_CSV="/Users/farooqkadri/UEF/Industrial Project/data/Big pieces reference data/Big pieces [15-high] [15-middle] [15-low] [15-zero] [water].csv"
CSV_PATH="${1:-$DEFAULT_CSV}"

source "$REPO_ROOT/.venv/bin/activate"
python3 "$SCRIPT_DIR/greatdatachunking_overview.py" "$CSV_PATH"
