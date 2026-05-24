#!/usr/bin/env bash
# Move local LaTeX build outputs for the current latexmk job into mirror dirs.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$SCRIPT_DIR/..}"
ROOT_NAME="${2:-}"
AUX_DIR="${3:-}"
OUT_DIR="${4:-}"
TEX_FILE="${5:-}"
REPO_ROOT="$(cd -- "$REPO_ROOT" && pwd)"

if [[ "$(basename -- "$REPO_ROOT")" == "src" && -d "$REPO_ROOT/.." ]]; then
    REPO_ROOT="$(cd -- "$REPO_ROOT/.." && pwd)"
fi

SRC="$REPO_ROOT/src"
OUT="${OUT_DIR:-$REPO_ROOT/out}"
BUILD="${AUX_DIR:-$REPO_ROOT/build}"

if [[ "$OUT" != /* ]]; then
    OUT="$REPO_ROOT/$OUT"
fi
if [[ "$BUILD" != /* ]]; then
    BUILD="$REPO_ROOT/$BUILD"
fi

if [[ -z "$ROOT_NAME" ]]; then
    exit 0
fi

mkdir -p "$OUT" "$BUILD"

shopt -s nullglob

SOURCE_DIR="$SRC"
if [[ -n "$TEX_FILE" ]]; then
    TEX_FILE="${TEX_FILE#\"}"
    TEX_FILE="${TEX_FILE%\"}"
    if [[ "$TEX_FILE" == */* ]]; then
        SOURCE_DIR="$(cd -- "$(dirname -- "$TEX_FILE")" && pwd)"
    else
        PWD_ABS="$(pwd)"
        if [[ "$PWD_ABS" == "$SRC" || "$PWD_ABS" == "$SRC/"* ]]; then
            SOURCE_DIR="$PWD_ABS"
        fi
    fi
fi

move_if_exists() {
    local destination_dir="$1"
    shift
    local file
    for file in "$@"; do
        if [[ -f "$file" ]]; then
            mkdir -p "$destination_dir"
            mv -f -- "$file" "$destination_dir/"
        fi
    done
}

move_if_empty_dir() {
    local directory="$1"
    rmdir "$directory" 2>/dev/null || true
}

move_if_exists "$OUT" \
    "$SOURCE_DIR/$ROOT_NAME.pdf" \
    "$SOURCE_DIR/out/$ROOT_NAME.pdf" \
    "$SOURCE_DIR/build/$ROOT_NAME.pdf" \
    "$BUILD/$ROOT_NAME.pdf"

AUX_EXTS=(aux log out toc nav snm synctex synctex.gz fls fdb_latexmk bbl blg thm lol lot lof xdv)
for ext in "${AUX_EXTS[@]}"; do
    move_if_exists "$BUILD" \
        "$SOURCE_DIR/$ROOT_NAME.$ext" \
        "$SOURCE_DIR/out/$ROOT_NAME.$ext" \
        "$SOURCE_DIR/build/$ROOT_NAME.$ext" \
        "$OUT/$ROOT_NAME.$ext"
done

move_if_empty_dir "$SOURCE_DIR/out"
move_if_empty_dir "$SOURCE_DIR/build"
