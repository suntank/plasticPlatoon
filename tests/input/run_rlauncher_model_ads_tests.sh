#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG ${TEST_CFLAGS:-} \
    tests/input/rlauncher_model_ads_test.c -lm -o "$test_build/rlauncher_model_ads_test"
"$test_build/rlauncher_model_ads_test"
