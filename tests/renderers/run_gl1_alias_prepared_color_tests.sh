#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -UNDEBUG -ffp-contract=off -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_alias_prepared_color_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/prepared-colors"
"$test_build/prepared-colors"
