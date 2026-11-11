#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    tests/renderers/color_pic_cache_test.c -o "$test_build/color_pic_cache_test"
"$test_build/color_pic_cache_test"
