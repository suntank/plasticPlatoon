#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_alias_color_regression.c \
    src/client/refresh/files/models.c src/common/shared/shared.c \
    -Wl,--gc-sections -lm -o "$test_build/gl1_alias_color_test"
"$test_build/gl1_alias_color_test" baseq2/models/monsters/soldier/tris.md2 \
    baseq2/models/items/ammo/shells/medium/tris.md2
