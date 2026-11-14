#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -fno-strict-aliasing -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_world_batch_regression.c \
    src/client/refresh/files/surf.c src/common/shared/shared.c \
    -Wl,--gc-sections -lm -o "$test_build/gl1_world_batch_test"
"$test_build/gl1_world_batch_test"
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -fno-strict-aliasing -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_lightmap_copies_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/gl1_lightmap_copies_test"
"$test_build/gl1_lightmap_copies_test"
