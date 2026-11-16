#!/usr/bin/env python3
"""Inspect five authored health pickups and exercise their native behavior.

The close gallery establishes shape, cross/label orientation, healing amounts,
normal health caps and over-health behavior. Stimpack distance substitution
is measured separately by capture_pickup_lod.
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
HEALTH = {
    'item_health_small': ('models/items/healing/stimpack/tris.md2', 2),
    'item_health': ('models/items/healing/medium/tris.md2', 10),
    'item_health_large': ('models/items/healing/large/tris.md2', 25),
    'item_health_mega': ('models/items/mega_h/tris.md2', 100),
    'item_adrenaline': ('models/items/adrenal/tris.md2', None),
}
MODELS = {name: item[0] for name, item in HEALTH.items()}


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
    p.add_argument('--package', type=Path, help='Optional isolated preview package')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--renderer', choices=('gl1', 'gl3', 'soft'), default='gl1')
    p.add_argument('--q2tool', type=Path, default=ROOT.parent / 'q2tools-220/build/q2tool')
    p.add_argument('--compile-assets', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--map-dir', type=Path, help='Reuse five previously compiled gallery BSPs')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--gallery-only', action='store_true', help='Close views and ordinary pickup gains; skip additional cap scenarios')
    p.add_argument('--targets', nargs='+', choices=list(HEALTH), default=list(HEALTH))
    args = p.parse_args()
    out, source = args.output.resolve(), args.source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    maps = ({name: args.map_dir.resolve() / f'pp_pickup_lod_{i}.bsp'
             for i, name in enumerate(HEALTH)} if args.map_dir else
            compile_fixtures(out, args.q2tool.resolve(), args.compile_assets.resolve(), HEALTH))
    if args.prepare_only:
        print(json.dumps({name: str(path) for name, path in maps.items()}, indent=2))
        return
    runtime = stage_runtime(source, out, maps)
    base = runtime / 'baseq2'
    if args.package:
        shutil.copy2(args.package.resolve(), base / 'plastic-platoon.pk3')
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
    (base / 'health-review.cfg').write_text(cfg)
    command = [str(runtime / 'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'vid_renderer', args.renderer, '+set', 'r_mode', '-1',
               '+set', 'r_customwidth', '1280', '+set', 'r_customheight', '720',
               '+set', 's_initsound', '0', '+exec', 'health-review.cfg']
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

            def health():
                return controls.record('health_state', 'PP_HEALTH_STATE ')

            def noclip(enabled):
                if (controls.state()['clients'][0]['pm_type'] == 1) != enabled:
                    controls.action('clientcmd 0 noclip')
                    wait(lambda: (controls.state()['clients'][0]['pm_type'] == 1) == enabled, 'camera movement mode')

            def visible_item(model):
                return next((entity for entity in entities() if entity['model'] == model and not(entity['svflags'] & 1)), None)

            def fresh(classname):
                # Returning to the same coop level through gamemap restores
                # its collected-item state; map starts a genuinely fresh test.
                controls.console('map ' + maps[classname].stem)
                time.sleep(.8)
                wait(lambda: controls.state()['clients'][0]['spawned'], 'spawn ' + classname, 60)
                return wait(lambda: visible_item(MODELS[classname]), 'fresh ' + classname)

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
                _, quantity = HEALTH[classname]
                if index:
                    controls.console('gamemap ' + maps[classname].stem)
                    time.sleep(.8)
                wait(lambda: controls.state()['clients'][0]['spawned'], 'spawn ' + classname, 60)
                model = MODELS[classname]
                item = wait(lambda: visible_item(model), classname)
                noclip(True)
                lo, hi = model_bounds[classname]
                center = [item['origin'][axis] + (lo[axis] + hi[axis]) * .5 for axis in range(3)]
                distance = max(48., max(b-a for a,b in zip(lo,hi)) * 2.6)
                views = [('front', (0., -distance, 0.), 0., 90.),
                         ('opposite', (0., distance, 0.), 0., 270.),
                         ('side', (-distance, 0., 0.), 0., 0.),
                         ('lid', (0., -distance*.55, distance*.8), math.degrees(math.atan2(.8,.55)), 90.)]
                for name, delta, pitch, yaw in views:
                    if item['effects'] & 1:
                        clock = controls.record('camera_state', 'PP_QA_CAMERA ')['client_time_ms']
                        angle = math.radians(((clock + 700) / 10.) % 360.)
                        delta = (delta[0]*math.cos(angle)-delta[1]*math.sin(angle),
                                 delta[0]*math.sin(angle)+delta[1]*math.cos(angle), delta[2])
                        yaw += math.degrees(angle)
                    eye = [center[axis] + delta[axis] for axis in range(3)]
                    # The ordinary teleport command adds ten origin units;
                    # standing view height then adds another twenty-two.
                    origin = [eye[0], eye[1], eye[2] - 32.]
                    camera = pose(origin, pitch, yaw)
                    shot(classname + '-' + name)
                    report['views'][-1]['camera'] = camera
                def touch(start, expect_taken=True):
                    controls.action('clientcmd 0 give health ' + str(start))
                    before = wait(lambda: (current if (current := health())['health'] == start else None), 'set initial health')
                    noclip(False)
                    pose([item['origin'][0], item['origin'][1], 24.], 0., 0.)
                    if expect_taken:
                        after = wait(lambda: (current if (current := health())['health'] > start else None), 'healed ' + classname)
                        wait(lambda: not visible_item(model), 'consumed ' + classname)
                    else:
                        time.sleep(.6)
                        after = health()
                        if after['health'] != start or not visible_item(model):
                            raise RuntimeError('Full-health pickup refusal failed: ' + classname)
                    remaining = [entity for entity in entities() if entity['model'] == model]
                    if expect_taken and classname == 'item_health_mega' and not any(entity['svflags'] & 1 and entity['solid'] == 0 for entity in remaining):
                        raise RuntimeError('Mega health did not become hidden/non-solid')
                    return dict(before=before, after=after, gained=after['health']-start,
                                pickup_consumed=not bool(visible_item(model)), item_entities_after=remaining)

                normal = touch(50)
                expected = normal['before']['max_health'] + 1 if quantity is None else 50 + quantity
                if normal['after']['health'] != expected:
                    raise RuntimeError('Incorrect healing gain: ' + classname + ' ' + str(normal))
                result = dict(model=model,bounds=[lo,hi],origin=item['origin'],normal=normal,extra={})
                if not args.gallery_only:
                    item = fresh(classname)
                    maximum = health()['max_health']
                    if classname in ('item_health','item_health_large'):
                        capped = touch(maximum-5)
                        if capped['after']['health'] != maximum:
                            raise RuntimeError('Normal health cap failed: ' + classname)
                        result['extra']['near_cap'] = capped
                        item = fresh(classname)
                        result['extra']['full_refused'] = touch(health()['max_health'],False)
                    else:
                        over = touch(maximum)
                        expected = maximum + (1 if quantity is None else quantity)
                        if over['after']['health'] != expected:
                            raise RuntimeError('Over-health behavior failed: ' + classname)
                        if quantity is None and over['after']['max_health'] != maximum+1:
                            raise RuntimeError('Booster max-health increase failed')
                        result['extra']['at_maximum'] = over
                        if classname == 'item_health_mega':
                            decayed = wait(lambda: (current if (current := health())['health'] < expected else None), 'native mega decay',10)
                            result['extra']['timed_decay'] = decayed
                report['items'][classname] = result
                print(classname + ': gained ' + str(normal['gained']),flush=True)
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
