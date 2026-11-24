#!/usr/bin/env bash
#
# Lancia il worktree legacy (griglia 80x25) da qualunque directory.
#
#   ./start-legacy.sh                 # interfaccia
#   ./start-legacy.sh --smoke         # verifica headless
#   ./start-legacy.sh --data ~/dati   # cartella dati della legacy
#
# Non serve attivare il venv: `start.sh` usa `.venv/bin/python` se c'e',
# altrimenti l'interprete di sistema con PyQt6. Lo script entra nella
# directory del worktree, cosi' `config.json` e i dati restano qui anche
# quando lo si lancia da `../adbx`.

set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

exec "$HERE/start.sh" "$@"
