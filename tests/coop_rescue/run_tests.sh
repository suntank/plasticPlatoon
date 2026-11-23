#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
make -s -j2 DEBUG=1 game
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DDEDICATED_ONLY -DYQ2ARCH='"test"' \
    -DYQ2OSTYPE='"test"' -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    tests/coop_rescue/game_test.c src/common/pmove.c \
    $(find build/debug/baseq2 -name '*.o' -print) -lm -o "$test_build/game_test"
"$test_build/game_test"
