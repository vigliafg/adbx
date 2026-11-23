#!/usr/bin/env bash
#
# Costruisce il pacchetto 1.0: wheel e sdist in dist/.
# Richiede `python -m build` (pip install build) oppure usa pip wheel.
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ADBX_PYTHON:-python3}"
cd "$HERE"

rm -rf dist build
"$PY" -m pytest -q
"$PY" -m ruff check src tests tools 2>/dev/null || true

if "$PY" -c 'import build' >/dev/null 2>&1; then
  "$PY" -m build
else
  echo "adbx: modulo 'build' assente, uso 'pip wheel'." >&2
  mkdir -p dist
  "$PY" -m pip wheel --no-deps -w dist .
fi

ls -l dist
