#!/usr/bin/env python3
"""Compile and execute real renderer cache code and the production MD2 loader."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sanitize', action='store_true')
parser.add_argument('--models', type=Path, default=Path('baseq2/models'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
models = args.models.resolve()
with tempfile.TemporaryDirectory(prefix='pp-renderer-tests-') as temp:
    binary = Path(temp) / 'renderer-cache-test'
    flags = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else ['-O2']
    command = [os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
               '-ffunction-sections', '-fdata-sections', '-DYQ2OSTYPE="test"',
               '-DYQ2ARCH="test"', *flags, str(root / 'tests/renderer_cache_test.c'),
               str(root / 'src/client/refresh/files/models.c'), '-Wl,--gc-sections',
               '-lm', '-o', str(binary)]
    subprocess.run(command, check=True, cwd=root)
    subprocess.run([str(binary), *map(str, sorted(models.rglob('*.md2')))], check=True, cwd=root)
    # The renderer diagnostics use SDL's high-resolution CPU clock. This fixture
    # stubs GL query calls and engine cvars, and needs no display or GL context.
    sdl = subprocess.run(['pkg-config', '--cflags', '--libs', 'sdl2'],
                         capture_output=True, text=True)
    sdl_define = []
    if sdl.returncode:
        sdl = subprocess.run(['pkg-config', '--cflags', '--libs', 'sdl3'],
                             capture_output=True, text=True, check=True)
        sdl_define = ['-DUSE_SDL3']
    diagnostic = Path(temp) / 'renderer-perf-lifecycle-test'
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                    *flags, *sdl_define, str(root / 'tests/renderer_perf_lifecycle_test.c'),
                    *shlex.split(sdl.stdout), '-o', str(diagnostic)], check=True, cwd=root)
    subprocess.run([str(diagnostic)], check=True, cwd=root)
