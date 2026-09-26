#!/usr/bin/env bash
# Reproduce this study end-to-end..
set -euo pipefail

cd "$(dirname "$0")"

# Find a Python 3 interpreter (macOS / many Linux ship only "python3").
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then echo "Error: Python 3 not found on PATH." >&2; exit 1; fi

echo "==> Creating virtual environment"
"$PY" -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo "==> Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Fetching data"
python3 fetch_data.py || echo "WARNING: data fetch step failed; main.py will report missing real data if required."

echo "==> Running experiment"
python3 main.py

# Optional analysis/figures, if the package includes them.
if [ -f analysis.py ]; then echo "==> Running analysis"; python3 analysis.py; fi
if [ -f plots.py ]; then echo "==> Generating plots"; python3 plots.py; fi

echo "==> Done. Results are in results/ (see results/results.json)."
