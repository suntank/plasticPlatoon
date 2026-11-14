#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -Wall -Wextra -Werror -Wno-sign-compare -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_world_array_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/world-arrays"
"$test_build/world-arrays"
