#!/usr/bin/env python3
"""Stage and validate q2tools-220 builds; release means BSP + full VIS + RAD."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from compile_cache import (asset_hash, cache_key, file_hash, geometry_matches,
                           load_bundle, save_bundle, topology_hash)
from map_inventory import bsp_inventory, map_inventory

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def lock_stage(stage):
    # The compiler rewrites files in place. Keep two runs out of the same stage.
    with (stage / '.compile.lock').open('ab') as lock:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def clean_stage(source):
    for suffix in ('.bsp', '.prt', '.lin', '.pts'):
        source.with_suffix(suffix).unlink(missing_ok=True)


def run_stage(name, source, a, manifest):
    stage = source.parent
    stage_flag = 'bsp' if name == 'entities' else name
    target = source if stage_flag == 'bsp' else source.with_suffix('.bsp')
    cmd = [manifest['tool'], '-' + stage_flag, '-threads', str(a.threads), '-basedir', manifest['basedir']]
    if name == 'entities':
        cmd.append('-onlyents')
    if stage_flag == 'bsp' and a.large_bounds:
        cmd.append('-largebounds')
    if name == 'rad' and a.rad_subdiv is not None:
        cmd += ['-subdiv', str(a.rad_subdiv)]
    if name == 'rad' and a.rad_ambient is not None:
        cmd += ['-ambient', str(a.rad_ambient)]
    if name == 'rad' and a.rad_smooth is not None:
        cmd += ['-smooth', str(a.rad_smooth)]
    if name == 'rad' and a.rad_gpu:
        cmd.append('-rad-gpu')
    cmd.append(str(target))
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
    if (re.search(r'\*+\s*leaked\s*\*+|MAP LEAKED|no entities in (?:empty space|open)', logtext, re.I)
            or any(source.with_suffix(suffix).exists() for suffix in ('.lin', '.pts'))):
        raise RuntimeError(f'map leak detected; see {logfile}')
    missing = re.findall(r'^.*(?:couldn.t locate texture|couldn.t load.*(?:texture|\.wal|colormap)|couldn.t open.*(?:texture|\.wal|colormap)).*$', logtext, re.I | re.M)
    if missing and not a.allow_missing_textures:
        raise RuntimeError(f'missing compile assets ({len(missing)} warnings); see {logfile}; supply complete --basedir')


def restore_compiled_map(bundle, source, a, manifest):
    cached_source_sha, cached_bsp, cached_portal = bundle
    output = source.with_suffix('.bsp')
    output.write_bytes(cached_bsp)
    if cached_source_sha != manifest['source_sha256']:
        run_stage('entities', source, a, manifest)
        if not geometry_matches(cached_bsp, output.read_bytes()):
            raise RuntimeError('entity refresh changed nonentity BSP data')
    if cached_portal is not None:
        source.with_suffix('.prt').write_bytes(cached_portal)
    print('Reusing sealed BSP and full VIS.', flush=True)


def compile_stages(stages, source, src, basedir, a, manifest):
    if not a.reuse_bsp_vis or 'vis' not in stages or a.allow_missing_textures:
        for name in stages:
            run_stage(name, source, a, manifest)
        return

    topology = topology_hash(source.read_bytes())
    textures = manifest['source_inventory']['textures']
    assets = None
    if topology is not None:
        try:
            assets = asset_hash(basedir, textures)
        except (OSError, ValueError) as error:
            print(f'BSP/VIS cache unavailable ({error}); compiling normally.', flush=True)

    manifest['bsp_vis_cache'] = 'unavailable'
    if assets is None:
        for name in stages:
            run_stage(name, source, a, manifest)
        return

    key = cache_key(src, topology, assets, manifest, a.large_bounds)
    cache = source.parent / '.bsp-vis-cache.zip'
    bundle = load_bundle(cache, key)
    reused = False
    bsp_sha = None
    output = source.with_suffix('.bsp')
    if bundle is not None:
        try:
            restore_compiled_map(bundle, source, a, manifest)
            reused = True
            if bundle[0] != manifest['source_sha256']:
                bsp_sha = file_hash(output)
        except (OSError, RuntimeError) as error:
            print(f'BSP/VIS cache update failed ({error}); compiling normally.', flush=True)
            clean_stage(source)
            reused = False

    manifest['bsp_vis_cache'] = 'hit' if reused else 'miss'
    if not reused:
        run_stage('bsp', source, a, manifest)
        run_stage('vis', source, a, manifest)
        before_rad = bsp_inventory(output, require_full_vis=True)
        if before_rad['lumps']['lighting']['bytes'] == 0:
            bsp_sha = before_rad['sha256']

    if bsp_sha is not None:
        try:
            if asset_hash(basedir, textures) == assets and file_hash(Path(manifest['tool'])) == manifest['tool_sha256']:
                save_bundle(cache, key, manifest['source_sha256'], output, source.with_suffix('.prt'), bsp_sha)
        except (OSError, ValueError) as error:
            print(f'Could not save BSP/VIS cache ({error}).', flush=True)

    if 'rad' in stages:
        run_stage('rad', source, a, manifest)


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
    p.add_argument('--rad-gpu', action='store_true', help='request q2tool GPU RAD; implies --rad in preview mode')
    p.add_argument('--rad-subdiv', type=int, help='RAD patch subdivision size (8..1024); omit for compiler default')
    p.add_argument('--rad-ambient', type=int, choices=range(256), metavar='0..255', help='Ambient fill for baked lighting')
    p.add_argument('--rad-smooth', type=float, metavar='DEGREES',
                   help='Phong smoothing angle for baked lighting (0..90); omit for compiler default')
    p.add_argument('--reuse-bsp-vis', action='store_true',
                   help='reuse full VIS and BSP for unchanged maps or numeric tweaks to existing named/targeted lights')
    p.add_argument('--large-bounds', action='store_true', help='Allow BSP geometry beyond the default 4096-unit bounds')
    p.add_argument('--allow-missing-textures', action='store_true', help='diagnostic builds only, never published')
    a = p.parse_args()
    if a.threads < 1:
        p.error('--threads must be positive')
    if a.rad_subdiv is not None and not 8 <= a.rad_subdiv <= 1024:
        p.error('--rad-subdiv must be an integer between 8 and 1024')
    if a.rad_smooth is not None and not 0 <= a.rad_smooth <= 90:
        p.error('--rad-smooth must be between 0 and 90 degrees')
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
    try:
        stage.mkdir(parents=True, exist_ok=True)
        with lock_stage(stage):
            return build_map(a, src, tool, basedir, stage, destination)
    except OSError as error:
        p.exit(1, f'Could not use build directory {stage}: {error}\n')


def build_map(a, src, tool, basedir, stage, destination):
    staged_src = stage / src.name
    manifest = {'source': str(src), 'profile': a.profile,
                'tool': tool, 'tool_sha256': file_hash(Path(tool)), 'basedir': str(basedir),
                'threads': a.threads, 'diagnostic': a.allow_missing_textures,
                'stages': [], 'published': False}
    if a.rad_subdiv is not None:
        manifest['rad_subdiv'] = a.rad_subdiv
    if a.rad_smooth is not None:
        manifest['rad_smooth'] = a.rad_smooth
    if a.rad_gpu:
        manifest['rad_gpu'] = True
    manifest_path = stage / 'manifest.json'
    try:
        shutil.copyfile(src, staged_src)
        manifest['source_inventory'] = map_inventory(staged_src)
        manifest['source_sha256'] = manifest['source_inventory']['sha256']
        clean_stage(staged_src)
        stages = ['bsp']
        run_rad = a.profile == 'release' or a.rad or a.rad_gpu
        if run_rad or a.vis:
            stages.append('vis')
        if run_rad:
            stages.append('rad')
        compile_stages(stages, staged_src, src, basedir, a, manifest)
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
