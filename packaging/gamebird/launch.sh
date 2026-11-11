#!/bin/sh
set -eu

game_dir=${GAMEBIRD_GAME_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
save_dir=${GAMEBIRD_SAVE_DIR:-$game_dir/../../saves/plastic-platoon}
mkdir -p "$save_dir/baseq2"

# Yamagi's -cfgdir is relative to the user's home. Resolve this at launch so
# Game Bird's separate persistent save location also works outside /home.
config_dir=$(python3 -c 'import os,sys; print(os.path.relpath(os.path.realpath(sys.argv[1]), os.path.expanduser("~")))' "$save_dir")

if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -d "$XDG_RUNTIME_DIR" ]; then
    runtime_dir="$save_dir/runtime"
    mkdir -p "$runtime_dir"
    chmod 700 "$runtime_dir"
    export XDG_RUNTIME_DIR="$runtime_dir"
fi
export SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-KMSDRM}

# DRM card numbers can change across boots. Select the same physical output
# as Game Bird, using its TV-mode marker and the panel's SPI device identity.
if [ -z "${SDL_KMSDRM_DEVICE_INDEX:-}" ]; then
    if [ -e /run/gamebird-tv-mode ]; then
        for connector in /sys/class/drm/card*-HDMI-A-*/status; do
            [ -r "$connector" ] || continue
            [ "$(cat "$connector")" = connected ] || continue
            card=${connector%/status}
            card=${card##*/}
            card=${card%%-HDMI-A-*}
            SDL_KMSDRM_DEVICE_INDEX=${card#card}
            break
        done
    else
        for card in /sys/class/drm/card[0-9]*; do
            index=${card##*/card}
            case "$index" in ''|*[!0-9]*) continue ;; esac
            device=$(readlink -f "$card/device") || continue
            case "$device/" in
                */spi0.0/*) SDL_KMSDRM_DEVICE_INDEX=$index; break ;;
            esac
        done
    fi
    if [ -n "${SDL_KMSDRM_DEVICE_INDEX:-}" ]; then
        export SDL_KMSDRM_DEVICE_INDEX
    fi
fi

cd "$game_dir"
if [ "$#" -eq 0 ]; then
    set -- +map "${PLASTIC_PLATOON_MAP:-pp_sandstorm}"
fi

# Keep renderer selection/resolution early: SDL creates its context before
# executing config files. Extra arguments replace the default map command.
exec "$game_dir/quake2" -datadir "$game_dir" -cfgdir "$config_dir" \
    +set vid_renderer "${PLASTIC_PLATOON_RENDERER:-gl1}" \
    +set vid_fullscreen 1 +set r_mode -1 \
    +set r_customwidth 240 +set r_customheight 240 \
    +exec gamebird.cfg "$@"
