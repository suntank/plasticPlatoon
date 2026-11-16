#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
for renderer in GL1 GL3 SOFT; do
    ${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
        -DTEST_$renderer -O2 -g -UNDEBUG -ffunction-sections -fdata-sections \
        ${TEST_CFLAGS:-} $(sdl2-config --cflags) \
        tests/renderers/view_weapon_clip_regression.c \
        -Wl,--gc-sections -lm -o "$test_build/$renderer"
    "$test_build/$renderer"
done
