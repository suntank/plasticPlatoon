#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -fno-strict-aliasing -fwrapv -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_lightmap_build_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/gl1_lightmap_build_test"
"$test_build/gl1_lightmap_build_test"
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -DYQ2_GL1_GLES ${CFLAGS:--O2} -fno-strict-aliasing -fwrapv -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_lightmap_build_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/gles1_lightmap_build_test"
"$test_build/gles1_lightmap_build_test"
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -fno-strict-aliasing -fwrapv -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_lightmap_upload_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/gl1_lightmap_upload_test"
"$test_build/gl1_lightmap_upload_test"
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -DYQ2_GL1_GLES ${CFLAGS:--O2} -fno-strict-aliasing -fwrapv -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_lightmap_upload_regression.c \
    -Wl,--gc-sections -lm -o "$test_build/gles1_lightmap_upload_test"
"$test_build/gles1_lightmap_upload_test"
