#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -O2 -UNDEBUG -ffunction-sections -fdata-sections \
    tests/renderers/software_sprite_regression.c src/client/refresh/soft/sw_sprite.c \
    src/common/shared/shared.c -Wl,--gc-sections -lm -o "$test_build/software_sprite_test"
"$test_build/software_sprite_test"
