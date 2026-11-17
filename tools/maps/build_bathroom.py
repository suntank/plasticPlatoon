#!/usr/bin/env python3
"""Compile the edited Tile Tide MAP and package it for the portable game."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from build_endline import BASE, LOCAL_TOOL, ROOT, prepare_assets

MAP_NAME = 'pp_tile_tide'
SOURCE = ROOT / 'maps/source' / (MAP_NAME + '.map')
BSP = Path('maps') / (MAP_NAME + '.bsp')
CONFIG = Path('tile_tide_dm.cfg')
ARCHIVE = 'operation-tile-tide.pk3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=os.environ.get(
        'Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool'))
    parser.add_argument('--release-dir', type=Path, default=ROOT / 'release/baseq2')
    args = parser.parse_args()

    build = ROOT / 'build/tile-tide'
    manifest = prepare_assets(SOURCE, build / 'compile-assets')
    with TemporaryDirectory(dir=build) as directory:
        stage = Path(directory)
        subprocess.run([
            sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
            '--source', str(SOURCE), '--tool', args.tool,
            '--basedir', str(build / 'compile-assets'), '--profile', 'release',
            '--rad-subdiv', '128', '--rad-ambient', '30', '--output-dir', str(stage),
        ], check=True)
        files = {BSP.as_posix(): stage / BSP.name, CONFIG.as_posix(): BASE / CONFIG}
        files.update({asset['path']: BASE / asset['path'] for asset in manifest['files']
                      if asset['path'].startswith('textures/')})
        files.update({file.relative_to(BASE).as_posix(): file
                      for file in (BASE / 'env').glob('unit1_*.tga')})
        with ZipFile(stage / ARCHIVE, 'w', ZIP_DEFLATED) as pack:
            for name, path in sorted(files.items()):
                pack.write(path, name)
        (stage / BSP.name).replace(BASE / BSP)
        (stage / ARCHIVE).replace(BASE / ARCHIVE)

    if args.release_dir.is_dir() and args.release_dir.resolve() != BASE:
        shutil.copy2(BASE / ARCHIVE, args.release_dir / ARCHIVE)
    print(BASE / ARCHIVE)


if __name__ == '__main__':
    main()
