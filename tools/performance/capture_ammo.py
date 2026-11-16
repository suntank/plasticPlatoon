#!/usr/bin/env python3
"""Inspect seven authored ammo pickups in real isolated maps and touch them.

The close gallery establishes shape, label orientation and actual pickup
behavior. Distance substitution is measured separately by capture_pickup_lod.
These offscreen host captures are not target-device performance measurements.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
import zipfile

from capture_pickup_lod import compile_fixtures, stage_runtime
from qa_controls import FileControls, compile_controls

ROOT = Path(__file__).resolve().parents[2]
AMMO = {
    'ammo_shells': ('Shells', 'shells', 10),
    'ammo_bullets': ('Bullets', 'bullets', 50),
    'ammo_grenades': ('Grenades', 'grenades', 2),
    'ammo_gl_rounds': ('GL Ammo', 'gl_ammo', 5),
    'ammo_rockets': ('Rockets', 'rockets', 5),
    'ammo_cells': ('Napalm', 'cells', 50),
    'ammo_slugs': ('Sniper Rounds', 'slugs', 10),
}
MODELS = {name: 'models/items/ammo/' + item[1] + '/medium/tris.md2'
          for name, item in AMMO.items()}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(data):
    header = struct.unpack_from('<17i', data)
    scale = struct.unpack_from('<3f', data, header[14])
    offset = struct.unpack_from('<3f', data, header[14] + 12)
    vertices = [tuple(data[header[14] + 40 + i * 4 + axis] * scale[axis] + offset[axis]
                      for axis in range(3)) for i in range(header[6])]
    return [[min(v[axis] for v in vertices) for axis in range(3)],
            [max(v[axis] for v in vertices) for axis in range(3)]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'release')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--renderer', choices=('gl1', 'gl3', 'soft'), default='gl1')
    p.add_argument('--q2tool', type=Path, default=ROOT.parent / 'q2tools-220/build/q2tool')
    p.add_argument('--compile-assets', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--map-dir', type=Path, help='Reuse seven previously compiled gallery BSPs')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--targets', nargs='+', choices=list(AMMO), default=list(AMMO))
    args = p.parse_args()
    out, source = args.output.resolve(), args.source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    maps = ({name: args.map_dir.resolve() / f'pp_pickup_lod_{i}.bsp'
             for i, name in enumerate(AMMO)} if args.map_dir else
            compile_fixtures(out, args.q2tool.resolve(), args.compile_assets.resolve(), AMMO))
    if args.prepare_only:
        print(json.dumps({name: str(path) for name, path in maps.items()}, indent=2))
        return
    runtime = stage_runtime(source, out, maps)
    base = runtime / 'baseq2'
    if (ROOT / 'baseq2/tuning').exists():
        shutil.copytree(ROOT / 'baseq2/tuning', base / 'tuning')
    library, offsets = compile_controls(source, out)
    control_path, logpath = out / 'controls.txt', out / 'console.log'
    control_path.write_text('')
    shots = out / 'screenshots'
    shots.mkdir()
    config = dict(vid_renderer=args.renderer, vid_fullscreen=0, r_mode=-1,
                  r_customwidth=1280, r_customheight=720, r_vsync=0,
                  vid_maxfps=60, cl_maxfps=60, s_initsound=0, cheats=1,
                  cl_gun=0, crosshair=0, r_hudscale=0, cl_blend=0,
                  con_notifytime=0, r_pickup_lod=1, r_perf=1,
                  cl_bob=0, cl_kickangles=0, cl_gamebird_autolevel=0,
                  in_grab=0, logfile=2)
    cfg = ''.join(f'set {key} "{value}"\n' for key, value in config.items())
    cfg += 'set maxclients 2\nset coop 1\nset singleplayer 0\nset deathmatch 0\n'
    cfg += 'map ' + maps[args.targets[0]].stem + '\n'
    (base / 'ammo-review.cfg').write_text(cfg)
    command = [str(runtime / 'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'vid_renderer', args.renderer, '+set', 'r_mode', '-1',
               '+set', 'r_customwidth', '1280', '+set', 'r_customheight', '720',
               '+set', 's_initsound', '0', '+exec', 'ammo-review.cfg']
    env = dict(os.environ, SDL_VIDEODRIVER='offscreen', SDL_AUDIODRIVER='dummy',
               LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='2',
               LD_PRELOAD=str(library), PP_COLOR_CONTROLS=str(control_path),
               XDG_CACHE_HOME=str(runtime / 'cache'), **offsets)
    report = dict(complete=False, passed=False, renderer=args.renderer,
                  host_timings_not_pi=True, items={}, views=[],
                  inputs_sha256={name:sha(runtime / name) for name in
                                 ('quake2', 'ref_' + args.renderer + '.so',
                                  'baseq2/game.so', 'baseq2/plastic-platoon.pk3')})
    with zipfile.ZipFile(base / 'plastic-platoon.pk3') as archive:
        model_bounds = {name:bounds(archive.read(path)) for name, path in MODELS.items()}
    process = None
    try:
        with logpath.open('w') as log:
            process = subprocess.Popen(command, cwd=runtime, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            controls = FileControls(control_path, logpath, process)

            def wait(check, label, timeout=30):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    result = check()
                    if result:
                        return result
                    if process.poll() is not None:
                        raise RuntimeError('Engine exited before ' + label)
                    time.sleep(.04)
                raise RuntimeError('Timed out: ' + label)

            def entities():
                return controls.record('enemy_state', 'PP_COLOR_ENEMIES ')['entities']

            def pose(origin, pitch, yaw):
                controls.console('cl_bench_pose 0 ' + ' '.join(str(v) for v in (*origin, pitch, yaw)))
                time.sleep(.2)
                controls.action('clear_teleport 0')
                time.sleep(.4)
                camera = controls.record('camera_state', 'PP_QA_CAMERA ')
                if abs(camera['view'][0] - pitch) > .1:
                    raise RuntimeError('Camera did not reach requested pitch: ' + str(camera))
                return camera

            def shot(name):
                before = set((base / 'scrnshot').glob('*.png'))
                controls.console('screenshot png')
                path = wait(lambda: next(iter(set((base / 'scrnshot').glob('*.png')) - before), None), name)
                wait(lambda: path.read_bytes().endswith(b'IEND\xaeB`\x82'), name + ' PNG')
                destination = shots / (name + '.png')
                shutil.copy2(path, destination)
                report['views'].append(dict(name=name, screenshot=destination.name, sha256=sha(destination)))
                print(destination, flush=True)

            for index, classname in enumerate(args.targets):
                item_name, _, quantity = AMMO[classname]
                if index:
                    controls.console('gamemap ' + maps[classname].stem)
                    time.sleep(.8)
                wait(lambda: controls.state()['clients'][0]['spawned'], 'spawn ' + classname, 60)
                model = MODELS[classname]
                item = wait(lambda: next((entity for entity in entities() if entity['model'] == model), None), classname)
                controls.action('clientcmd 0 noclip')
                lo, hi = model_bounds[classname]
                center = [item['origin'][axis] + (lo[axis] + hi[axis]) * .5 for axis in range(3)]
                distance = max(48., max(b-a for a,b in zip(lo,hi)) * 2.6)
                views = [('front', (0., -distance, 0.), 0., 90.),
                         ('opposite', (0., distance, 0.), 0., 270.),
                         ('side', (-distance, 0., 0.), 0., 0.),
                         ('lid', (0., -distance*.55, distance*.8), math.degrees(math.atan2(.8,.55)), 90.)]
                for name, delta, pitch, yaw in views:
                    eye = [center[axis] + delta[axis] for axis in range(3)]
                    # The ordinary teleport command adds ten origin units;
                    # standing view height then adds another twenty-two.
                    origin = [eye[0], eye[1], eye[2] - 32.]
                    camera = pose(origin, pitch, yaw)
                    shot(classname + '-' + name)
                    report['views'][-1]['camera'] = camera
                before = controls.record('ammo_state', 'PP_AMMO_INVENTORY ')['counts']
                controls.action('clientcmd 0 noclip')
                pose([item['origin'][0], item['origin'][1], 24.], 0., 0.)
                after = wait(lambda: (counts if counts[item_name] > before[item_name] else None)
                             if (counts := controls.record('ammo_state', 'PP_AMMO_INVENTORY ')['counts']) else None,
                             'touch ' + classname)
                gone = wait(lambda: not any(entity['model'] == model for entity in entities()), 'removed ' + classname)
                delta = after[item_name] - before[item_name]
                if delta != quantity:
                    raise RuntimeError(f'{classname} gained {delta}, expected {quantity}')
                report['items'][classname] = dict(model=model, bounds=[lo,hi], origin=item['origin'],
                                                inventory_before=before, inventory_after=after,
                                                gained=delta, expected=quantity, pickup_removed=gone)
                print(classname + ': gained ' + str(delta), flush=True)
            report.update(complete=True, passed=True)
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        if process and process.poll() is None:
            controls.console('quit')
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=4)
        report['returncode'] = process.returncode if process else None
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(out / 'report.json')


if __name__ == '__main__':
    main()
