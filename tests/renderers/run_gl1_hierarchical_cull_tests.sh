#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
test_build=$(mktemp -d)
trap 'rm -rf "$test_build"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
    ${CFLAGS:--O2} -fno-strict-aliasing -UNDEBUG -ffunction-sections -fdata-sections \
    $(sdl2-config --cflags) tests/renderers/gl1_hierarchical_cull_regression.c \
    src/common/shared/shared.c -Wl,--gc-sections -lm -o "$test_build/cull-test"
python3 - "$test_build" <<'PY'
from pathlib import Path
import sys,zipfile
out=Path(sys.argv[1])
for name,archive in [('pp_sandbox2','plastic-platoon'),('pp_sandstorm','operation-sandstorm-preview'),('pp_endline','operation-endline'),('pp_temple','operation-temple')]:
    with zipfile.ZipFile(Path('release/baseq2')/(archive+'.pk3')) as z:
        (out/(name+'.bsp')).write_bytes(z.read('maps/'+name+'.bsp'))
PY
"$test_build/cull-test" "$test_build/pp_sandbox2.bsp" "$test_build/pp_sandstorm.bsp" \
    "$test_build/pp_endline.bsp" "$test_build/pp_temple.bsp"
