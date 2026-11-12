#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
for backend in sdl openal; do
    extra=
    sources=
    if [ "$backend" = openal ]; then
        if ! printf '#include <AL/al.h>\n' | ${CC:-cc} -E - >/dev/null 2>&1; then
            echo 'OpenAL headers unavailable; SDL audio regressions only'
            continue
        fi
        extra=-DUSE_OPENAL
        sources=src/client/sound/qal.c
    fi
    ${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
        -O2 -g -UNDEBUG -DDEFAULT_OPENAL_DRIVER='"test"' -fno-strict-aliasing -fwrapv -ffunction-sections -fdata-sections \
        ${TEST_CFLAGS:-} $extra tests/sound/audio_test.c $sources src/common/shared/shared.c \
        -Wl,--gc-sections -lm -ldl -o "$test_build/audio-$backend"
    "$test_build/audio-$backend"
done
