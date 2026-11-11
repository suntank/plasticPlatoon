#!/usr/bin/env python3
"""Compile End of the Line using color-correct, private compiler textures.

The q2tools-220 RGB PNG loader in lbmlib.c initializes green_sample and
blue_sample inside a short-circuited transparency comparison. Ordinary RGB
PNGs consequently produce undefined green/blue reflectivity during RAD. Its
RGBA PNG path initializes all channels correctly. This wrapper converts only
private compile copies from RGB to RGBA (opaque alpha), preserving every RGB
pixel. Source artwork, the compiler, and runtime textures remain untouched.

Default builds run BSP, full VIS and RAD with 128-unit patches, then publish
through the existing compile_map.py validation. --prepare-only prepares and
checks the material closure without launching a compiler. --quick uses fast VIS
and coarser 256-unit RAD patches for the user's shorter test-quality build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image

from platoon_palette import load_palette
from verify_sandkeep import parse_entities

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'performance'))
from map_inventory import bsp_inventory

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
SOURCE = ROOT / 'maps/source/pp_endline.map'
STAGING = ROOT / 'build/endline-compile-assets'
LOCAL_TOOL = Path.home() / 'q2tools-220/build/q2tool'
RAD_AMBIENT = 16
WORKAROUND = ('q2tools-220 lbmlib.c RGB PNG loader uses short-circuit && while '
              'initializing green/blue samples. Private opaque RGBA copies '
              'select its correct decoder path; original RGB pixels preserved.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_closure(source):
    pending = list({name for e in parse_entities(source.read_text()) for name in e['textures']})
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        if not re.fullmatch(r'(endline|sandbox|sandkeep|bedroom)/[A-Za-z0-9_+\-]+', name):
            raise ValueError('Unexpected material name: ' + name)
        seen.add(name)
        path = BASE / 'textures' / (name+'.wal')
        data = path.read_bytes()
        if len(data) < 100:
            raise ValueError('Truncated WAL header: ' + str(path))
        # name[32], dimensions[8], mip offsets[16], then animname[32].
        following = struct.unpack_from('<32s', data, 56)[0].split(b'\0')[0].decode('ascii')
        if following:
            pending.append(following)
    return sorted(seen)


def prepare_assets(source=SOURCE, staging=STAGING):
    """Create private inputs and verify that conversion preserves exact color."""
    names = material_closure(source)
    staging.mkdir(parents=True, exist_ok=True)
    palette = BASE / 'pics/colormap.pcx'
    load_palette(palette)  # Reject anything except the original PP palette.
    files = []
    for relative in ['pics/colormap.pcx'] + [
            'textures/'+name+suffix for name in names for suffix in ('.wal', '.png', '.tga')
            if (BASE/'textures'/(name+suffix)).is_file()]:
        src, dest = BASE/relative, staging/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        converted = False
        if src.suffix == '.png':
            with Image.open(src) as im:
                if im.mode == 'RGB':
                    original = im.tobytes()
                    im.convert('RGBA').save(dest)
                    with Image.open(dest) as copy:
                        if copy.mode != 'RGBA' or copy.convert('RGB').tobytes() != original:
                            raise ValueError('RGB preservation check failed: '+relative)
                        if copy.getextrema()[3] != (255, 255):
                            raise ValueError('Nonopaque converted material: '+relative)
                    converted = True
        if not converted:
            shutil.copyfile(src, dest)
        files.append({'path':relative, 'source_sha256':sha(src), 'compile_sha256':sha(dest),
                      'rgb_to_opaque_rgba':converted})
    # Remove stale copies for selected names when an authored format disappears;
    # otherwise an old private PNG could mask the current TGA or WAL on a rebuild.
    for name in names:
        for suffix in ('.png', '.tga'):
            relative = 'textures/'+name+suffix
            if not (BASE/relative).is_file():
                (staging/relative).unlink(missing_ok=True)
    manifest = {'source':str(source), 'source_sha256':sha(source),
                'workaround':WORKAROUND, 'material_count':len(names),
                'materials':names, 'files':files}
    (staging/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def quick_build(args, command):
    """Build BSP first, fast VIS/RAD second, publishing only the complete result."""
    stage = (args.build_dir.expanduser() / SOURCE.stem).resolve()
    manifest_path = stage / 'manifest.json'
    # compile_map.py owns leak/missing-material checks and initial BSP staging.
    # Its preview output stays private until VIS and lighting are validated.
    with tempfile.TemporaryDirectory(prefix='endline-prelight-', dir=ROOT/'build') as temporary:
        first = list(command)
        first[first.index('--output-dir')+1] = temporary
        first[first.index('--profile')+1] = 'preview'
        result = subprocess.run(first, check=False)
        if result.returncode:
            return result.returncode
    manifest = json.loads(manifest_path.read_text())
    manifest.update(profile='preview', fast_vis=True, rad_subdiv=args.rad_subdiv,
                    published=False, quality='Fast VIS and coarse RAD; test-quality build')
    manifest.pop('output', None)
    output = stage / (SOURCE.stem+'.bsp')
    try:
        rad_flags = ['-subdiv', str(args.rad_subdiv), '-ambient', str(RAD_AMBIENT)]
        for name, flags in (('vis', ['-fast']), ('rad', rad_flags)):
            cmd = [manifest['tool'], '-'+name, '-threads', str(args.threads),
                   '-basedir', str(STAGING), *flags, str(output)]
            logfile = stage / (name+'.log')
            print(f'{name.upper()} (quick): {logfile}', flush=True)
            started = time.monotonic()
            with logfile.open('w') as log:
                result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
            manifest['stages'].append({'name':name, 'command':cmd, 'returncode':result.returncode,
                                      'seconds':time.monotonic()-started, 'log':logfile.name})
            if result.returncode:
                raise RuntimeError(f'{name} exited {result.returncode}; see {logfile}')
            logtext = logfile.read_text(errors='replace')
            if re.search(r'\*+\s*leaked\s*\*+|MAP LEAKED|no entities in empty space', logtext, re.I):
                raise RuntimeError(f'Map leak detected; see {logfile}')
            if re.search(r"couldn.t (?:locate texture|load.*(?:texture|\.wal|colormap)|open.*(?:texture|\.wal|colormap))", logtext, re.I):
                raise RuntimeError(f'Missing compiler assets; see {logfile}')
        if manifest['source_sha256'] != sha(SOURCE):
            raise RuntimeError('Source changed during compilation; rebuild the current MAP')
        # The flag asks for complete valid visibility rows and baked lighting,
        # not full VIS quality; the manifest explicitly records this as preview.
        manifest['bsp_inventory'] = bsp_inventory(output, require_release=True)
        manifest['bsp_sha256'] = sha(output)
        destination = args.output_dir.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        final = destination / output.name
        fd, temporary = tempfile.mkstemp(prefix=final.stem+'-', suffix='.bsp.tmp', dir=destination)
        os.close(fd)
        try:
            shutil.copyfile(output, temporary)
            shutil.copymode(output, temporary)
            os.replace(temporary, final)
        finally:
            Path(temporary).unlink(missing_ok=True)
        manifest.update(published=True, output=str(final))
        print(f'Validated quick BSP: {final}', flush=True)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        manifest['error'] = str(exc)
        print('Quick compile failed: '+str(exc), file=sys.stderr)
        return 1
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tool', default=os.environ.get('Q2TOOL', str(LOCAL_TOOL) if LOCAL_TOOL.is_file() else 'q2tool'))
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--rad-subdiv', type=int, help='RAD patch size; default 128, or 256 with --quick')
    p.add_argument('--quick', action='store_true', help='Fast VIS and coarse lighting; publish a validated test-quality BSP')
    p.add_argument('--profile', choices=('release','preview'), default='release')
    p.add_argument('--vis', action='store_true', help='Full VIS in a preview build')
    p.add_argument('--rad', action='store_true', help='VIS and RAD in a preview build')
    p.add_argument('--build-dir', type=Path, default=ROOT/'build/maps')
    p.add_argument('--output-dir', type=Path, default=BASE/'maps')
    p.add_argument('--prepare-only', action='store_true', help='Stage exact material copies without compiling')
    a = p.parse_args()
    if a.rad_subdiv is None:
        a.rad_subdiv = 256 if a.quick else 128
    if a.threads < 1:
        p.error('--threads must be positive')
    if not 8 <= a.rad_subdiv <= 1024:
        p.error('--rad-subdiv must be in 8..1024')
    if a.quick and (a.vis or a.rad):
        p.error('--quick already includes fast VIS and RAD; omit --vis/--rad')
    try:
        manifest = prepare_assets()
        command = [sys.executable, str(ROOT/'tools/performance/compile_map.py'),
                   '--source', str(SOURCE), '--basedir', str(STAGING),
                   '--output-dir', str(a.output_dir), '--build-dir', str(a.build_dir),
                   '--tool', a.tool, '--threads', str(a.threads),
                   '--large-bounds', '--rad-ambient', str(RAD_AMBIENT),
                   '--profile', 'preview' if a.quick else a.profile, '--rad-subdiv', str(a.rad_subdiv)]
        if a.vis:
            command.append('--vis')
        if a.rad:
            command.append('--rad')
        manifest['compile_command'] = command
        manifest.update(quick=a.quick, fast_vis=a.quick, rad_subdiv=a.rad_subdiv)
        (STAGING/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        converted = sum(v['rgb_to_opaque_rgba'] for v in manifest['files'])
        print(f'Prepared {manifest["material_count"]} materials; {converted} private RGB PNGs converted to opaque RGBA.', flush=True)
        print(f'Compiler asset manifest: {STAGING / "manifest.json"}', flush=True)
        if a.prepare_only:
            print('Preparation only; compiler not launched.')
            return 0
        if a.quick:
            return quick_build(a, command)
        return subprocess.run(command, check=False).returncode
    except (OSError, ValueError) as exc:
        print('Endline build failed: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
