#!/usr/bin/env python3
"""Launch a bounded, isolated Quake II capture with explicit graphics settings."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
from summarize import summarize

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', required=True, type=Path)
    p.add_argument('--data', required=True, type=Path, help='isolated runtime directory containing baseq2')
    p.add_argument('--label', required=True)
    p.add_argument('--renderer', choices=('gl1', 'gles1', 'gl3', 'gles3'), default='gl1')
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--map')
    source.add_argument('--demo', help='recorded demo gives identical snapshots to each revision')
    p.add_argument('--players', type=int, choices=(1, 2, 3, 4), default=1)
    p.add_argument('--size', default='640x480')
    p.add_argument('--frames', type=int, default=1800)
    p.add_argument('--warmup', type=int, default=120)
    p.add_argument('--timeout', type=float, default=300)
    p.add_argument('--pose', action='append', nargs=6, metavar=('SLOT', 'X', 'Y', 'Z', 'PITCH', 'YAW'))
    p.add_argument('--set', action='append', nargs=2, default=[], metavar=('CVAR', 'VALUE'))
    p.add_argument('--screenshot', action='store_true')
    p.add_argument('--xvfb', action='store_true', help='software host validation only; never call these Pi GPU timings')
    p.add_argument('--unprivileged', help='root test environments only: run as this existing account')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,55}', a.label):
        p.error('label must contain only letters, digits, _ and -')
    if not re.fullmatch(r'[A-Za-z0-9_/-]+' if a.map else r'[A-Za-z0-9_./-]+', a.map or a.demo) or '..' in (a.map or a.demo):
        p.error('invalid map/demo path')
    if a.demo and a.players != 1:
        p.error('standard demos contain one local client; use --map for real split screen')
    if a.demo and a.pose:
        p.error('--pose requires --map; recorded demos already contain camera positions')
    if not math.isfinite(a.timeout) or a.timeout <= 0:
        p.error('timeout must be finite and positive')
    if not re.fullmatch(r'\d+x\d+', a.size):
        p.error('size must be WIDTHxHEIGHT')
    width, height = map(int, a.size.split('x'))
    if min(width, height) < 1 or a.warmup < 0 or a.frames <= a.warmup:
        p.error('positive dimensions and frames > warmup >= 0 are required')
    binary, data = a.binary.resolve(), a.data.resolve()
    if not binary.is_file() or not (data / 'baseq2').is_dir():
        p.error('binary and data/baseq2 must exist')
    perf = data / 'baseq2/perf'
    perf.mkdir(parents=True, exist_ok=True)
    cfg = perf / (a.label + '.cfg')
    output_files = [perf / (a.label + suffix) for suffix in ('-frames.csv', '-views.csv', '-settings.txt')]
    reserved_files = output_files + [perf / (a.label + suffix) for suffix in ('-console.log', '-run.json')]
    if cfg.exists() or any(f.exists() for f in reserved_files):
        p.error('capture already exists; use a new label so measurements are not overwritten')
    settings = [('vid_renderer', a.renderer), ('vid_fullscreen', '0'), ('r_mode', '-1'),
                ('r_customwidth', str(width)), ('r_customheight', str(height)),
                ('r_vsync', '0'), ('vid_maxfps', '1000'), ('cl_maxfps', '60'), ('cl_async', '1'),
                ('s_initsound', '0'), ('r_perf', '1'), ('r_perf_gpu', '1'),
                ('gl1_picmip', '0'), ('r_shadows', '0'), ('r_fullbright', '0'), ('r_novis', '0'),
                ('r_cull', '1'), ('r_drawentities', '1'), ('r_drawworld', '1'), ('r_lerpmodels', '1'),
                ('cl_entities', '1'), ('cl_lights', '1'), ('cl_particles', '1'),
                ('gl_texturemode', 'GL_LINEAR_MIPMAP_NEAREST'), ('r_msaa_samples', '0'),
                ('r_anisotropic', '0'), ('gl_finish', '0'), ('gl1_dynamic', '1'), ('r_retexturing', '1'),
                ('cl_perf_frames', str(a.frames)), ('cl_perf_quit', '1'),
                ('cl_perf_screenshot', '1' if a.screenshot else '0')]
    for key, value in a.set:
        if not re.fullmatch(r'[A-Za-z0-9_]+', key) or not re.fullmatch(r'[A-Za-z0-9_.+-]+', value):
            p.error('--set accepts plain cvar names and scalar values')
        if key in ('vid_renderer', 'game', 'basedir', 'cddir', 'r_mode', 'r_customwidth', 'r_customheight',
                   'cl_perf_frames', 'cl_perf_quit', 'cl_perf_screenshot', 'r_perf', 'timedemo'):
            p.error(f'{key} is controlled by explicit benchmark options')
    settings += a.set
    if a.pose:
        settings.append(('cheats', '1'))
    commands = [f'set {key} "{value}"' for key, value in settings]
    commands.append(f'cl_perf_start {a.label}')
    if a.demo:
        commands += ['set timedemo 1', f'demomap {a.demo}']
    else:
        commands += [f'cl_bench_local {a.players} {a.map}']
        for pose in a.pose or []:
            try:
                values = [float(v) for v in pose]
            except ValueError:
                p.error('pose entries must be numeric')
            if not all(math.isfinite(v) for v in values) or any(abs(v) > 32767 for v in values[1:]):
                p.error('pose coordinates and angles must be finite and within +/-32767')
            if values[0] not in range(a.players):
                p.error('pose slot must be an active player')
            commands.append('cl_bench_pose ' + str(int(values[0])) + ' ' + ' '.join(format(v, '.9g') for v in values[1:]))
    try:
        with cfg.open('x') as f:
            f.write('\n'.join(commands) + '\n')
    except FileExistsError:
        p.error('capture already exists; use a new label so measurements are not overwritten')
    cmd = [str(binary), '-portable', '-datadir', str(data)]
    # Startup flags apply before SDL initialization; cfg commands also document them.
    startup = {'vid_renderer', 'vid_fullscreen', 'r_mode', 'r_customwidth', 'r_customheight', 'r_vsync', 's_initsound', 'r_msaa_samples'}
    for key, value in settings:
        if key in startup:
            cmd += ['+set', key, value]
    cmd += ['+exec', f'perf/{a.label}.cfg']
    if a.xvfb:
        cmd = ['xvfb-run', '-a', '-s', f'-screen 0 {width}x{height}x24'] + cmd
    if a.unprivileged:
        if os.geteuid() != 0:
            p.error('--unprivileged is only for a root validation environment')
        import pwd
        account = pwd.getpwnam(a.unprivileged)
        os.chown(perf, account.pw_uid, account.pw_gid)
        os.chown(cfg, account.pw_uid, account.pw_gid)
        cmd = ['runuser', '-u', a.unprivileged, '--'] + cmd
    meta = {'command': cmd, 'settings': dict(settings), 'platform': platform.platform(),
            'machine': platform.machine(), 'cpu_count': os.cpu_count(),
            'binary_sha256': digest(binary), 'renderer_sha256': digest(binary.parent / f'ref_{a.renderer}.so'),
            'game_sha256': digest(data / 'baseq2/game.so'),
            'map_sha256': digest(data / f'baseq2/maps/{a.map}.bsp') if a.map else None,
            'pak0_sha256': digest(data / 'baseq2/pak0.pak'),
            'project_overlay_sha256': digest(data / 'baseq2/plastic-platoon.pk3'),
            'software_display_requested': a.xvfb, 'warmup_frames': a.warmup,
            'environment': {k: os.getenv(k) for k in ('LIBGL_ALWAYS_SOFTWARE', 'LP_NUM_THREADS', 'SDL_VIDEODRIVER', 'VC4_DEBUG')}}
    started = time.monotonic()
    try:
        with (perf / (a.label + '-console.log')).open('w') as log:
            process = subprocess.Popen(cmd, cwd=data, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                returncode = process.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        meta['returncode'] = returncode
        if returncode:
            raise RuntimeError(f'engine exited {returncode}; inspect console log')
        meta['summary'] = summarize(output_files[0], a.warmup)
        print(json.dumps(meta['summary'], indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
        meta['error'] = str(e)
        print(str(e), file=sys.stderr)
        return 1
    finally:
        meta['seconds'] = time.monotonic() - started
        (perf / (a.label + '-run.json')).write_text(json.dumps(meta, indent=2) + '\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
