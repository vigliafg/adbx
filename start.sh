#!/usr/bin/env bash
#
# Avvia adbx senza dover attivare a mano un ambiente virtuale.
#
#   ./start.sh                # apre l'interfaccia
#   ./start.sh --smoke        # avvio headless di verifica
#   ./start.sh --version
#
# Interprete scelto, in ordine:
#   1. $ADBX_PYTHON, se impostata
#   2. .venv/bin/python del progetto
#   3. python3 / python di sistema
# Se l'interprete scelto non ha PyQt6, la prima volta crea `.venv` e vi
# installa il pacchetto con le sue dipendenze; le volte successive riusa
# quell'ambiente. Nessuna attivazione manuale e' necessaria.

set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"

say() { printf 'adbx: %s\n' "$*" >&2; }
die() { say "$*"; exit 1; }

find_python() {
  local candidate
  for candidate in "${ADBX_PYTHON:-}" "$VENV/bin/python" python3 python; do
    [ -n "$candidate" ] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1 || continue
    printf '%s' "$candidate"
    return 0
  done
  return 1
}

has_qt() { "$1" -c 'import PyQt6.QtWidgets' >/dev/null 2>&1; }

PY="$(find_python)" || die "serve Python 3.11 o successivo"

if ! has_qt "$PY"; then
  if [ -x "$VENV/bin/python" ]; then
    # Il venv esiste ma non e' completo: prova a installarvi il pacchetto.
    say "PyQt6 assente in $VENV, installo le dipendenze"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -e "$HERE" || die "installazione in .venv fallita"
  else
    say "preparo .venv alla prima esecuzione (serve PyQt6)"
    "$PY" -m venv "$VENV" || die "creazione di .venv fallita (serve python3-venv)"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -e "$HERE" || die "installazione delle dipendenze fallita"
  fi
  PY="$VENV/bin/python"
  has_qt "$PY" || die "PyQt6 non disponibile nemmeno dopo l'installazione"
fi

# Funziona anche senza `pip install -e .`: la sorgente e' sempre in src/.
export PYTHONPATH="$HERE/src${PYTHONPATH:+:$PYTHONPATH}"

exec "$PY" -m adbx "$@"
