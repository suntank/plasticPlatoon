#!/usr/bin/env python3
"""Stage and validate q2tools-220 builds; release means BSP + full VIS + RAD."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from map_inventory import bsp_inventory, map_inventory

ROOT = Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--map', help='map basename in --maps-dir')
    source.add_argument('--source', type=Path, help='exact MAP source path')
    p.add_argument('--maps-dir', type=Path, default=ROOT / 'maps/source')
    p.add_argument('--basedir', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--tool', default=os.environ.get('Q2TOOL', 'q2tool'))
    p.add_argument('--profile', choices=('release', 'preview'), default='release')
    p.add_argument('--threads', type=int, default=max(1, min(4, os.cpu_count() or 1)))
    p.add_argument('--build-dir', type=Path, default=ROOT / 'build/maps')
    p.add_argument('--output-dir', type=Path, help='publish validated BSP here; defaults to basedir/maps')
    p.add_argument('--vis', action='store_true', help='also run full VIS in preview mode')
    p.add_argument('--rad', action='store_true', help='also run VIS and RAD in preview mode')
    p.add_argument('--allow-missing-textures', action='store_true', help='diagnostic builds only, never published')
    a = p.parse_args()
    if a.threads < 1:
        p.error('--threads must be positive')
    if a.map and (Path(a.map).name != a.map or a.map in ('.', '..')):
        p.error('--map must be a basename; use --source for a path')
    src = (a.source or a.maps_dir / (a.map.removesuffix('.map') + '.map')).expanduser().resolve()
    if not src.is_file():
        p.error(f'MAP source does not exist: {src}')
    tool = shutil.which(os.path.expanduser(a.tool))
    if not tool:
        p.error('q2tool not found; set --tool /path/to/q2tool or Q2TOOL')
    tool = str(Path(tool).resolve())
    basedir = a.basedir.expanduser().resolve()
    if not basedir.is_dir():
        p.error(f'asset base directory does not exist: {basedir}')
    stage = (a.build_dir.expanduser() / src.stem).resolve()
    destination = (a.output_dir or basedir / 'maps').resolve()
    if destination == stage or src.parent == stage:
        p.error('build directory must be separate from source and published output directories')
    stage.mkdir(parents=True, exist_ok=True)
    staged_src = stage / src.name
    manifest = {'source': str(src), 'source_sha256': sha(src), 'profile': a.profile,
                'tool': tool, 'tool_sha256': sha(tool), 'basedir': str(basedir),
                'threads': a.threads, 'diagnostic': a.allow_missing_textures,
                'stages': [], 'published': False}
    manifest_path = stage / 'manifest.json'
    try:
        manifest['source_inventory'] = map_inventory(src)
        shutil.copyfile(src, staged_src)
        for suffix in ('.bsp', '.prt', '.lin'):
            staged_src.with_suffix(suffix).unlink(missing_ok=True)
        stages = ['bsp']
        if a.profile == 'release' or a.vis or a.rad:
            stages.append('vis')
        if a.profile == 'release' or a.rad:
            stages.append('rad')
        for name in stages:
            target = staged_src if name == 'bsp' else staged_src.with_suffix('.bsp')
            cmd = [tool, '-' + name, '-threads', str(a.threads), '-basedir', str(basedir), str(target)]
            logfile = stage / (name + '.log')
            print(f'{name.upper()}: {logfile}', flush=True)
            started = time.monotonic()
            with logfile.open('w') as log:
                proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
            logtext = logfile.read_text(errors='replace')
            manifest['stages'].append({'name': name, 'command': cmd, 'returncode': proc.returncode,
                                       'seconds': time.monotonic() - started, 'log': logfile.name})
            if proc.returncode:
                raise RuntimeError(f'{name} exited {proc.returncode}; see {logfile}')
            if re.search(r'\*+\s*leaked\s*\*+|MAP LEAKED|no entities in empty space', logtext, re.I) or staged_src.with_suffix('.lin').exists():
                raise RuntimeError(f'map leak detected; see {logfile}')
            missing = re.findall(r'^.*(?:couldn.t locate texture|couldn.t load.*(?:texture|\.wal|colormap)|couldn.t open.*(?:texture|\.wal|colormap)).*$', logtext, re.I | re.M)
            if missing and not a.allow_missing_textures:
                raise RuntimeError(f'missing compile assets ({len(missing)} warnings); see {logfile}; supply complete --basedir')
        output = staged_src.with_suffix('.bsp')
        manifest['bsp_inventory'] = bsp_inventory(output, a.profile == 'release')
        if not a.allow_missing_textures:
            destination.mkdir(parents=True, exist_ok=True)
            final = destination / output.name
            fd, temporary = tempfile.mkstemp(prefix=final.stem + '-', suffix='.bsp.tmp', dir=destination)
            os.close(fd)
            try:
                shutil.copyfile(output, temporary)
                shutil.copymode(output, temporary)
                os.replace(temporary, final)
            finally:
                Path(temporary).unlink(missing_ok=True)
            manifest['published'] = True
            manifest['output'] = str(final)
            print(f'Validated BSP: {final}')
        else:
            print(f'Diagnostic BSP only (not published): {output}')
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        manifest['error'] = str(e)
        print(f'Compile failed: {e}', file=sys.stderr)
        return 1
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

if __name__ == '__main__':
    sys.exit(main())
