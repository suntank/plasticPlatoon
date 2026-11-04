#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -O2 -g -UNDEBUG -fno-strict-aliasing -fwrapv -ffunction-sections -fdata-sections \
    ${TEST_CFLAGS:-} tests/screen_image/client_test.c src/client/cl_parse.c \
    src/client/cl_screen.c src/common/shared/shared.c src/common/movemsg.c \
    -Wl,--gc-sections -lm -o "$test_build/client_test"
"$test_build/client_test"
# Use the complete production game objects so savegame callback lookup and
# reloading exercise the real registration tables, rather than test copies.
make -s -j4 DEBUG=1 QUIET=1 game
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    tests/screen_image/game_test.c $(find build/debug/baseq2 -name '*.o' -print) \
    -lm -o "$test_build/game_test"
"$test_build/game_test" "$test_build/overlay.sav"
