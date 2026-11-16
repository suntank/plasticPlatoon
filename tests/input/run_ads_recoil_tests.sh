#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG ${TEST_CFLAGS:-} \
    tests/input/ads_recoil_test.c -lm -o "$test_build/ads_recoil_test"
"$test_build/ads_recoil_test"
