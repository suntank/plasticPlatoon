#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -O2 -g -UNDEBUG -fno-strict-aliasing -fwrapv -ffunction-sections -fdata-sections \
    ${TEST_CFLAGS:-} tests/splitscreen/state_test.c \
    src/common/shared/shared.c -Wl,--gc-sections -lm -o "$test_build/state_test"
"$test_build/state_test"
