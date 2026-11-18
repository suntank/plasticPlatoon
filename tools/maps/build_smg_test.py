#!/usr/bin/env python3
"""Compile the SMG test range and package its map, launch config, and textures."""

import argparse
import os
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_endline import BASE, LOCAL_TOOL, ROOT, prepare_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=os.environ.get(
        'Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool'))
    args = parser.parse_args()

    source = ROOT / 'maps/source/pp_smg_test.map'
    stage = ROOT / 'build/smg-test/assets'
    assets = prepare_assets(source, stage)
    subprocess.run([
        sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
        '--source', str(source), '--tool', args.tool, '--basedir', str(stage),
        '--profile', 'release', '--rad-ambient', '34',
        '--output-dir', str(BASE / 'maps'),
    ], check=True)

    entries = {'maps/pp_smg_test.bsp': BASE / 'maps/pp_smg_test.bsp',
               'maps/pp_smg_test.map': source, 'smg_test.cfg': BASE / 'smg_test.cfg'}
    entries.update((file['path'], BASE / file['path']) for file in assets['files']
                   if file['path'].startswith('textures/'))
    archive = BASE / 'operation-smg-test.pk3'
    temporary = archive.with_suffix('.pk3.tmp')
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED) as pack:
            for name, path in sorted(entries.items()):
                entry = ZipInfo(name)
                entry.external_attr = 0o100644 << 16
                pack.writestr(entry, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    print(archive)


if __name__ == '__main__':
    main()
