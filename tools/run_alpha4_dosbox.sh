#!/usr/bin/env bash
# Avvia Alpha Four v3 originale in DOSBox-X, montando il drive C: dello zip.
#
#   tools/run_alpha4_dosbox.sh                 # TTF, corpo 58 (default)
#   tools/run_alpha4_dosbox.sh --reset         # riestrae da zero
#   tools/run_alpha4_dosbox.sh --ttf           # TTF, finestra al 50%
#   tools/run_alpha4_dosbox.sh --ttf=45        # TTF, finestra al 45%
#   tools/run_alpha4_dosbox.sh --ttf-size=58   # TTF, corpo in punti
#   tools/run_alpha4_dosbox.sh --no-ttf        # output bitmap/OpenGL
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
TTF=1
TTF_PERC=50
TTF_SIZE=58

for arg in "$@"; do
    case "$arg" in
        --reset) RESET=1 ;;
        --ttf) TTF=1; TTF_SIZE="" ;;
        --ttf=*) TTF=1; TTF_SIZE=""; TTF_PERC="${arg#--ttf=}" ;;
        --ttf-size=*) TTF=1; TTF_SIZE="${arg#--ttf-size=}" ;;
        --no-ttf) TTF=0 ;;
    esac
done

if [ "$TTF" = 1 ]; then
    if [ -n "$TTF_SIZE" ]; then
        case "$TTF_SIZE" in
            ''|*[!0-9]*) echo "--ttf-size=<punti, minimo 9>" >&2; exit 2 ;;
        esac
        if [ "$TTF_SIZE" -lt 9 ]; then
            echo "--ttf-size=<punti, minimo 9>" >&2
            exit 2
        fi
    else
        case "$TTF_PERC" in
            ''|*[!0-9]*) echo "--ttf=<percentuale 10-100>" >&2; exit 2 ;;
        esac
        if [ "$TTF_PERC" -lt 10 ] || [ "$TTF_PERC" -gt 100 ]; then
            echo "--ttf=<percentuale 10-100>" >&2
            exit 2
        fi
    fi
fi

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
    case "$arg" in
        --reset|--ttf|--ttf=*|--ttf-size=*|--no-ttf) ;;
        *) ARGS+=("$arg") ;;
    esac
done
if [ "$TTF" = 1 ]; then
    if [ -n "$TTF_SIZE" ]; then
        ARGS+=(-set output=ttf -set "ttf ptsize=$TTF_SIZE")
    else
        ARGS+=(-set output=ttf -set "ttf winperc=$TTF_PERC")
    fi
fi
exec dosbox-x -conf "$CONF" -fastlaunch "${ARGS[@]}"
