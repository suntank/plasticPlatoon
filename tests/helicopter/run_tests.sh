#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
# Exercise production flight, weapons, physics and savegame tables.
make -s -j4 DEBUG=1 QUIET=1 game
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    tests/helicopter/game_test.c $(find build/debug/baseq2 -name '*.o' -print) \
    -lm -o "$test_build/game_test"
"$test_build/game_test" "$test_build/helicopter.sav"
# The render transform must keep each spinning axle fixed to the moving body.
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -UNDEBUG -ffunction-sections -fdata-sections \
    ${TEST_CFLAGS:-} tests/helicopter/rotor_render_test.c src/common/shared/shared.c \
    -Wl,--gc-sections -lm -o "$test_build/rotor_render_test"
"$test_build/rotor_render_test"
