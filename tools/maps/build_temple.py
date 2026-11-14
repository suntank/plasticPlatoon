#!/usr/bin/env python3
"""Compile and verify Temple using full VIS and baked lighting.

Only private compiler textures are converted from RGB to opaque RGBA, using
the existing q2tools color-loader workaround. Runtime artwork is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from build_endline import prepare_assets

ROOT = Path(__file__).resolve().parents[2]
LOCAL_TOOL = Path.home() / 'q2tools-220/build/q2tool'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'maps/source/pp_temple.map')
    parser.add_argument('--tool', default=os.environ.get(
        'Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool'))
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--rad-subdiv', type=int, default=128)
    parser.add_argument('--rad-ambient', type=int, default=24)
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'build/maps')
    parser.add_argument('--assets', type=Path, default=ROOT / 'build/temple-compile-assets')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'baseq2/maps')
    parser.add_argument('--verification', type=Path,
                        default=ROOT / 'build/maps/pp_temple/verification.json')
    parser.add_argument('--prepare-only', action='store_true',
                        help='stage and validate compiler materials without compiling')
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('--threads must be positive')
    if not 8 <= args.rad_subdiv <= 1024:
        parser.error('--rad-subdiv must be in 8..1024')
    if not 0 <= args.rad_ambient <= 255:
        parser.error('--rad-ambient must be in 0..255')
    try:
        source = args.source.expanduser().resolve()
        assets = args.assets.expanduser().resolve()
        manifest = prepare_assets(source, assets)
        command = [sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
                   '--source', str(source), '--basedir', str(assets),
                   '--tool', args.tool, '--profile', 'release',
                   '--threads', str(args.threads), '--rad-subdiv', str(args.rad_subdiv),
                   '--rad-ambient', str(args.rad_ambient),
                   '--build-dir', str(args.build_dir), '--output-dir', str(args.output_dir)]
        manifest['compile_command'] = command
        (assets / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        converted = sum(item['rgb_to_opaque_rgba'] for item in manifest['files'])
        print(f'Prepared {manifest["material_count"]} materials; '
              f'{converted} private RGB PNGs converted to opaque RGBA.', flush=True)
        if args.prepare_only:
            return 0
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
        bsp = args.output_dir.expanduser().resolve() / (source.stem + '.bsp')
        verify = [sys.executable, str(ROOT / 'tools/maps/verify_temple.py'),
                  '--map', str(source), '--bsp', str(bsp),
                  '--bsp-log', str(args.build_dir.expanduser().resolve() / source.stem / 'bsp.log'),
                  '--output', str(args.verification)]
        return subprocess.run(verify, check=False).returncode
    except (OSError, ValueError) as error:
        print('Temple build failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
