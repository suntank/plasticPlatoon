#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    -O2 -g -UNDEBUG -fno-strict-aliasing -fwrapv -ffunction-sections -fdata-sections \
    ${TEST_CFLAGS:-} tests/performance/effects_regression.c \
    src/client/cl_particles.c src/client/cl_effects.c src/client/cl_entities.c src/client/cl_lights.c \
    src/server/sv_send.c src/common/shared/shared.c src/common/movemsg.c src/common/szone.c \
    -Wl,--gc-sections -lm -o "$test_build/effects_regression"
"$test_build/effects_regression"
