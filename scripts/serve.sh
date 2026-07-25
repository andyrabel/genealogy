#!/usr/bin/env bash
# Starts the genealogy web server using the project's venv.
# Invoked from the Windows Desktop shortcut via wsl.exe.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
source .venv/bin/activate
exec genealogy serve --db data/tree.db
