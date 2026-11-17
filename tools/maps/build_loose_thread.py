#!/usr/bin/env python3
"""Compile the edited Loose Thread MAP and bundle its runtime materials."""
import argparse
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from build_endline import BASE, LOCAL_TOOL, ROOT, prepare_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', default=LOCAL_TOOL)
    args = parser.parse_args()
    source = ROOT / 'maps/source/pp_loose_thread.map'
    stage = ROOT / 'build/loose-thread/assets'
    manifest = prepare_assets(source, stage)
    subprocess.run([
        sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
        '--source', str(source), '--tool', str(args.tool), '--basedir', str(stage),
        '--profile', 'release', '--rad-subdiv', '128', '--rad-ambient', '34',
        '--output-dir', str(BASE / 'maps'),
    ], check=True)
    bsp = 'maps/pp_loose_thread.bsp'
    archive = BASE / 'operation-loose-thread.pk3'
    staged = archive.with_suffix('.pk3.tmp')
    with ZipFile(staged, 'w', ZIP_DEFLATED) as pack:
        pack.write(BASE / bsp, bsp)
        for asset in manifest['files']:
            name = asset['path']
            if name.startswith('textures/'):
                pack.write(BASE / name, name)
    staged.replace(archive)
    print(archive)


if __name__ == '__main__':
    main()
