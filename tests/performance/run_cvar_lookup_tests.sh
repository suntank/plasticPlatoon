#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -Wall -Wextra -Werror -Wno-sign-compare -UNDEBUG \
    -ffunction-sections -fdata-sections $(sdl2-config --cflags) \
    tests/performance/cvar_lookup_test.c -Wl,--gc-sections -lm -o "$test_build/cvar-lookup"
"$test_build/cvar-lookup"
