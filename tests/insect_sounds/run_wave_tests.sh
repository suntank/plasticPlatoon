#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -O2 -g -UNDEBUG ${TEST_CFLAGS:-} \
    -DYQ2OSTYPE='"Test"' -DYQ2ARCH='"Test"' \
    tests/insect_sounds/wave_test.c src/client/sound/wave.c \
    -o "$test_build/wave_test"
"$test_build/wave_test" baseq2/sound/ant/*.wav baseq2/sound/spider/*.wav
