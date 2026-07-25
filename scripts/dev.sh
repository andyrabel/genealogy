#!/usr/bin/env bash
# One-shot local dev setup: create/activate a venv and install the project.
# Usage: source scripts/dev.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"

echo "Virtualenv ready and activated. Try:"
echo "  genealogy import path/to/file.ged --db data/tree.db"
echo "  genealogy export data/tree.db path/to/out.ged"
echo "  pytest"
