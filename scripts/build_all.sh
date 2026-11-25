#!/usr/bin/env bash
# Rebuild every table, image set, cry, the SQLite database and the Kaggle metadata, then validate.
# Sources are cloned into .cache/ (ignored by git). Needs git, Python 3.10+ with pandas and mutagen.
#
#   bash scripts/build_all.sh            # everything, ready for a Kaggle upload
#   SKIP_MEDIA=1 bash scripts/build_all.sh   # tables only (no 1 GB sprite download)
set -euo pipefail
cd "$(dirname "$0")/.."
CACHE=.cache
PY=${PYTHON:-python3}
mkdir -p "$CACHE"

clone() {  # clone <repo> <dir> [sparse paths...]
  local repo=$1 dir=$CACHE/$2; shift 2
  if [ ! -d "$dir/.git" ]; then
    if [ $# -gt 0 ]; then
      git clone -q --depth 1 --filter=blob:none --sparse "https://github.com/$repo.git" "$dir"
      git -C "$dir" sparse-checkout set "$@"
    else
      git clone -q --depth 1 "https://github.com/$repo.git" "$dir"
    fi
  else
    git -C "$dir" pull -q --depth 1 || true
  fi
}

clone PokeAPI/pokeapi pokeapi data/v2/csv
clone smogon/pokemon-showdown pokemon-showdown data
"$PY" scripts/build_tables.py "$CACHE/pokeapi/data/v2/csv"
"$PY" scripts/build_competitive.py "$CACHE/pokemon-showdown" --cache "$CACHE/smogon"
if [ -z "${SKIP_MEDIA:-}" ]; then
  clone PokeAPI/sprites sprites sprites/pokemon/other/official-artwork sprites/pokemon/other/home \
    sprites/pokemon/other/showdown
  clone PokeAPI/cries cries
  "$PY" scripts/build_media.py "$CACHE/pokeapi/data/v2/csv" --sprites "$CACHE/sprites" --cries "$CACHE/cries"
else
  "$PY" scripts/build_media.py "$CACHE/pokeapi/data/v2/csv"
fi
"$PY" scripts/build_sqlite.py
"$PY" scripts/build_metadata.py
"$PY" scripts/validate.py
