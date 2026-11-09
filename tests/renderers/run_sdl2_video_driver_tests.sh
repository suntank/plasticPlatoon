#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
for compatibility in current old_headers; do
    defines=
    if [ "$compatibility" = old_headers ]; then defines=-DTEST_OLD_SDL_HEADERS; fi
    ${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
        ${CFLAGS:--O2} $defines -UNDEBUG -ffunction-sections -fdata-sections \
        $(sdl2-config --cflags) tests/renderers/sdl2_video_driver_regression.c \
        -Wl,--gc-sections -o "$test_build/sdl2_video_test"
    "$test_build/sdl2_video_test"
done
