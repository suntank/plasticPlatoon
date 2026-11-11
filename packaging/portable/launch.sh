#!/bin/sh
set -eu

game_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$game_dir"
if [ "$#" -eq 0 ]; then
    set -- +map pp_sandstorm
fi
if [ ! -f "$game_dir/baseq2/config.cfg" ]; then
    set -- +set skin soldier/green "$@"
fi
exec "$game_dir/quake2" -portable -datadir "$game_dir" "$@"
