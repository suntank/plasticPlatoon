#!/bin/sh
# Portable entry point: arguments are passed without shell expansion or eval.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/tools/performance/compile_map.py" "$@"
