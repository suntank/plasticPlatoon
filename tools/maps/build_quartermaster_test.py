#!/usr/bin/env python3
"""Compile and package the Quartermaster test range."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_endline import BASE, LOCAL_TOOL, ROOT, prepare_assets

MAP = 'pp_quartermaster_test'
ARCHIVE = 'operation-quartermaster-test.pk3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=os.environ.get(
        'Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool'))
    args = parser.parse_args()
    source = ROOT / f'maps/source/{MAP}.map'
    build = ROOT / 'build/quartermaster-test'
    compile_assets = build / 'assets'
    assets = prepare_assets(source, compile_assets)
    bsp_name = f'{MAP}.bsp'

    with TemporaryDirectory(dir=build) as directory:
        stage = Path(directory)
        subprocess.run([
            sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
            '--source', str(source), '--tool', args.tool, '--basedir', str(compile_assets),
            '--profile', 'release', '--rad-ambient', '22', '--output-dir', str(stage),
        ], check=True)

        entries = {
            f'maps/{bsp_name}': stage / bsp_name,
            f'maps/{MAP}.map': source,
            'quartermaster_test.cfg': BASE / 'quartermaster_test.cfg',
            'quartermaster_test_coop.cfg': BASE / 'quartermaster_test_coop.cfg',
        }
        entries.update((file['path'], BASE / file['path']) for file in assets['files']
                       if file['path'].startswith('textures/'))
        with ZipFile(stage / ARCHIVE, 'w') as pack:
            for name, path in sorted(entries.items()):
                entry = ZipInfo(name)
                entry.external_attr = 0o100644 << 16
                pack.writestr(entry, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        (stage / bsp_name).replace(BASE / 'maps' / bsp_name)
        (stage / ARCHIVE).replace(BASE / ARCHIVE)

    print(BASE / ARCHIVE)


if __name__ == '__main__':
    main()
