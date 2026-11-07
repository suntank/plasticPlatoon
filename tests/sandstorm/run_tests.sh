#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
make -s -j4 DEBUG=1 QUIET=1 game
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    tests/sandstorm/game_test.c $(find build/debug/baseq2 -name '*.o' -print) \
    -lm -o "$test_build/game_test"
"$test_build/game_test" "$test_build/sandstorm.sav"
