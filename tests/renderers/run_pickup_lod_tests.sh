#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -Wall -Wextra -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    -DYQ2OSTYPE='"test"' -DYQ2ARCH='"test"' \
    tests/renderers/pickup_lod_test.c -lm -o "$test_build/pickup_lod_test"
"$test_build/pickup_lod_test"
