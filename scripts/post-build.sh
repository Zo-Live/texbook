#!/usr/bin/env bash
# Move LaTeX build outputs to their proper directories after compilation.
# Usage: post-build.sh [repo_root_or_src_dir]

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$SCRIPT_DIR/..}"
REPO_ROOT="$(cd -- "$REPO_ROOT" && pwd)"

if [[ "$(basename -- "$REPO_ROOT")" == "src" && -d "$REPO_ROOT/.." ]]; then
    REPO_ROOT="$(cd -- "$REPO_ROOT/.." && pwd)"
fi

SRC="$REPO_ROOT/src"
OUT="$REPO_ROOT/out"
BUILD="$REPO_ROOT/build"

mkdir -p "$OUT" "$BUILD"

shopt -s nullglob

# PDF -> out/
for file in "$SRC"/*.pdf "$SRC/out"/*.pdf "$SRC/build"/*.pdf "$BUILD"/*.pdf; do
    mv -f -- "$file" "$OUT/"
done

# Auxiliary files -> build/
AUX_EXTS=(aux log out toc nav snm synctex synctex.gz fls fdb_latexmk bbl blg thm lol lot lof xdv)
for ext in "${AUX_EXTS[@]}"; do
    for file in "$SRC"/*."$ext" "$SRC/out"/*."$ext" "$SRC/build"/*."$ext" "$OUT"/*."$ext"; do
        mv -f -- "$file" "$BUILD/"
    done
done

rmdir "$SRC/out" "$SRC/build" 2>/dev/null || true
