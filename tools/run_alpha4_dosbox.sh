#!/usr/bin/env bash
# Avvia Alpha Four v3 originale in DOSBox-X, montando il drive C: dello zip.
#
#   tools/run_alpha4_dosbox.sh                 # estrae se serve e avvia
#   tools/run_alpha4_dosbox.sh --reset         # riestrae da zero
#   ADBX_ALPHA4_ZIP=/percorso.zip tools/run_alpha4_dosbox.sh
#
# L'archivio originale è escluso da git: lo script lo cerca nella radice del
# repository (nome predefinito "DRIVEC TERZA VERSIONE.zip") o nel percorso
# indicato dalla variabile ADBX_ALPHA4_ZIP. I file DOS sono estratti nella
# cache utente, mai nel repository.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP="${ADBX_ALPHA4_ZIP:-$ROOT/DRIVEC TERZA VERSIONE.zip}"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/adbx/alpha4-dos"
DRIVE="$CACHE/drivec"
CONF="$CACHE/dosbox-alpha4.conf"
CAPTURES="$CACHE/captures"
RESET=0

for arg in "$@"; do
    case "$arg" in
        --reset) RESET=1 ;;
    esac
done

if ! command -v dosbox-x >/dev/null 2>&1; then
    echo "dosbox-x non trovato. Su Ubuntu: sudo apt-get install dosbox-x" >&2
    exit 2
fi

if [ "$RESET" = 1 ] || [ ! -x "$DRIVE/ALPHA4V3/A4.EXE" ]; then
    [ -f "$ZIP" ] || {
        echo "Archivio Alpha Four non trovato: $ZIP" >&2
        echo "Indica il percorso con ADBX_ALPHA4_ZIP." >&2
        exit 2
    }
    rm -rf "$CACHE"
    mkdir -p "$CACHE"
    unzip -q "$ZIP" "drivec/*" -d "$CACHE"
fi

mkdir -p "$CAPTURES"
cat > "$CONF" <<EOF
[sdl]
fullscreen=false
autolock=false
showmenu=false

[dosbox]
machine=svga_s3
memsize=16
captures=$CAPTURES

[cpu]
core=auto
cycles=auto

[autoexec]
mount c $DRIVE
c:
cd \\ALPHA4V3
A4.EXE
EOF

ARGS=()
for arg in "$@"; do
    [ "$arg" = "--reset" ] || ARGS+=("$arg")
done
exec dosbox-x -conf "$CONF" -fastlaunch "${ARGS[@]}"
