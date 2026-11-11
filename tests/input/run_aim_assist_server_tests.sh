#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -g -UNDEBUG \
    -ffunction-sections -fdata-sections ${TEST_CFLAGS:-} \
    tests/input/aim_assist_server_test.c src/common/shared/shared.c \
    -Wl,--gc-sections -lm -o "$test_build/aim_assist_server_test"
"$test_build/aim_assist_server_test"
