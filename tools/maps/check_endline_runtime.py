#!/usr/bin/env python3
"""Capture End of the Line and exercise its mission in an isolated real engine.

Only the project's original asset overlay and loose artwork are staged. No PAK
files or user settings are read. Mission checks use ordinary button contact,
real monster deaths (cheat-assisted telefrags), and measured engine positions;
they are progression checks, not a combat-balance playthrough.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import zipfile

from verify_sandkeep import enabled, entity_bounds, parse_entities, vec

ROOT = Path(__file__).resolve().parents[2]
ENTITY = re.compile(r'^([A-Za-z_][A-Za-z_0-9]*):\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$', re.M)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Runtime:
    """Disposable game client with localhost control and reproducible evidence."""

    def __init__(self, args):
        self.args = args
        self.out = args.output_root.resolve() / args.label
        self.out.mkdir(parents=True, exist_ok=False)
        (self.out / 'screenshots').mkdir()
        shutil.copy2(args.source, self.out / 'pp_endline.map')
        self.root = Path(tempfile.mkdtemp(prefix='pp-endline-qa-'))
        self.base = self.root / 'baseq2'
        (self.base / 'maps').mkdir(parents=True)
        (self.root / 'cache').mkdir()
        for name in ('quake2', 'ref_' + args.renderer + '.so'):
            shutil.copy2(args.runtime / name, self.root / name)
        shutil.copy2(args.runtime / 'baseq2/game.so', self.base / 'game.so')
        shutil.copy2(args.bsp, self.base / 'maps/pp_endline.bsp')
        # Only this explicitly named original project package is allowed.
        shutil.copy2(ROOT / 'baseq2/plastic-platoon.pk3', self.base / 'plastic-platoon.pk3')
        for name in ('textures', 'env', 'tuning'):
            if (ROOT / 'baseq2' / name).is_dir():
                shutil.copytree(ROOT / 'baseq2' / name, self.base / name)
        with zipfile.ZipFile(self.base / 'zz-endline-qa-art.pk3', 'w', zipfile.ZIP_STORED) as archive:
            for name in ('models', 'sound', 'pics', 'sprites', 'players'):
                for path in sorted((ROOT / 'baseq2' / name).rglob('*')):
                    if path.is_file() and path.suffix.lower() in ('.md2', '.md3', '.png', '.pcx', '.tga', '.wal', '.wav', '.ogg', '.sp2', '.skin'):
                        archive.write(path, path.relative_to(ROOT / 'baseq2').as_posix())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.port = reservation.getsockname()[1]
        self.token = secrets.token_hex(16)
        self.control = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control.settimeout(.25)
        width, height = map(int, args.size.split('x'))
        settings = dict(name='Player', vid_renderer=args.renderer, vid_fullscreen=0,
                        r_mode=-1, r_customwidth=width, r_customheight=height,
                        r_farsee=1, r_vsync=0, vid_maxfps=60, cl_maxfps=60,
                        s_initsound=0, cheats=1, coop=1, maxclients=2,
                        deathmatch=0, singleplayer=0, skill=args.skill,
                        logfile=2, rcon_password=self.token, con_notifytime=0,
                        cl_gun=0, crosshair=0, r_hudscale=0, r_retexturing=1,
                        allow_download=0)
        cfg = '\n'.join(f'set {key} "{value}"' for key, value in settings.items())
        cfg += ('\ncl_bench_local ' + str(args.players) + ' pp_endline\n' if args.players > 1
                else '\nmap pp_endline\n')
        (self.base / 'endline-qa.cfg').write_text(cfg)
        (self.out / 'settings.cfg').write_text(cfg.replace(self.token, 'LOCAL_RCON_TOKEN'))
        self.report = dict(passed=False, skill=args.skill, players=args.players,
                           map_sha256=digest(self.base / 'maps/pp_endline.bsp'),
                           source_sha256=digest(self.out / 'pp_endline.map'),
                           binary_sha256=digest(self.root / 'quake2'),
                           game_sha256=digest(self.base / 'game.so'),
                           runtime=str(self.root), asset_policy='Original project PK3 and loose art only; no PAKs',
                           checks=[], actions=[], views=[])
        self.process = None
        self.log = None
        self.started = time.monotonic()

    def console(self):
        path = self.base / 'qconsole.log'
        return path.read_text(errors='replace') if path.exists() else ''

    def run(self, command, wait=.15):
        # Console output may span several UDP replies; discard leftover replies
        # before issuing the next command so readiness cannot read stale status.
        self.control.settimeout(0)
        try:
            while True:
                self.control.recvfrom(65535)
        except BlockingIOError:
            pass
        self.control.settimeout(.25)
        self.control.sendto(b'\xff\xff\xff\xffrcon ' + self.token.encode() + b' ' + command.encode() + b'\n',
                            ('127.0.0.1', self.port))
        try:
            reply = self.control.recvfrom(65535)[0].decode(errors='replace')
        except socket.timeout:
            reply = 'No acknowledgement'
        self.report['actions'].append(dict(command=command, seconds=round(time.monotonic()-self.started, 2), reply=reply))
        time.sleep(wait)
        return reply

    def until(self, predicate, seconds, message):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError(f'Engine exited {self.process.returncode}: {message}')
            result = predicate()
            if result:
                return result
            time.sleep(.15)
        raise RuntimeError(message)

    def start(self):
        # Saved constructor data keeps setup readable while allowing imports.
        self.log = (self.out / 'console.log').open('w')
        # Reconstruct launch command from the exact private config and options.
        a = self.args
        command = [str(self.root / 'quake2'), '-portable', '-datadir', str(self.root),
                   '+set', 'ip', '127.0.0.1', '+set', 'port', str(self.port),
                   '+set', 'vid_renderer', a.renderer, '+set', 'vid_fullscreen', '0',
                   '+set', 'r_mode', '-1', '+set', 'r_customwidth', a.size.split('x')[0],
                   '+set', 'r_customheight', a.size.split('x')[1],
                   '+set', 's_initsound', '0', '+exec', 'endline-qa.cfg']
        env = {**os.environ, 'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2',
               'XDG_CACHE_HOME': str(self.root / 'cache')}
        if a.display_backend == 'xvfb':
            w, h = a.size.split('x')
            command = ['xvfb-run', '-a', '-s', f'-screen 0 {w}x{h}x24'] + command
        elif a.display_backend in ('offscreen', 'dummy'):
            env['SDL_VIDEODRIVER'] = a.display_backend
        if a.display_backend == 'offscreen' and a.egl_device is not None:
            env['SDL_HINT_EGL_DEVICE'] = str(a.egl_device)
        if a.renderer == 'soft':
            env['SDL_RENDER_DRIVER'] = 'software'
        self.process = subprocess.Popen(command, cwd=self.root, env=env, stdout=self.log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
        self.until(lambda: sum('Player' in line and 'CNCT' not in line and 'ZMBI' not in line
                               for line in self.run('status', 0).splitlines()) >= a.players,
                   50, 'Local players did not connect')
        self.run('god')
        self.run('notarget')

    def check(self, name, condition, **evidence):
        self.report['checks'].append(dict(name=name, passed=bool(condition), **evidence))
        print(name + ': ' + ('PASS' if condition else 'FAIL'), evidence, flush=True)
        if not condition:
            raise RuntimeError(name)

    def pose(self, pose, slot=0, wait=.25):
        self.run('cl_bench_pose ' + str(slot) + ' ' + ' '.join(str(n) for n in pose), wait)

    def entities(self):
        start = len(self.console())
        self.run('listentities all', .25)
        # RCON forwards this client command on a later rendered frame. Wait for
        # the train line instead of assuming the whole dump fits one UDP reply.
        chunk = self.until(lambda: self.console()[start:] if '\nfunc_train:' in self.console()[start:]
                           and '\ninfo_player_intermission:' in self.console()[start:] else None,
                           5, 'Entity snapshot did not finish')
        entries = ENTITY.findall(chunk)
        return [(kind, tuple(map(float, xyz))) for kind, *xyz in entries]

    def train(self):
        matches = [xyz for kind, xyz in self.entities() if kind == 'func_train']
        if len(matches) != 1:
            raise RuntimeError('Expected one live func_train, got ' + str(matches))
        return matches[0]

    def capture(self, name):
        self.run('cl_perf_start qa_' + name, .22)
        before = set((self.base / 'scrnshot').glob('*.png'))
        self.run('screenshot png', .1)
        shot = self.until(lambda: next(iter(set((self.base / 'scrnshot').glob('*.png')) - before), None),
                          8, 'Missing screenshot ' + name)
        self.until(lambda: shot.read_bytes().endswith(b'IEND\xaeB`\x82'), 8, 'Incomplete screenshot ' + name)
        shutil.copy2(shot, self.out / 'screenshots' / (name + '.png'))
        self.run('cl_perf_stop', .2)
        path = self.base / 'perf' / ('qa_' + name + '-views.csv')
        rows = list(csv.DictReader(path.open()))
        poses = {}
        for row in rows:
            poses[row.get('slot', '0')] = {key: float(row[key]) for key in ('x', 'y', 'z', 'pitch', 'yaw')}
        self.report['views'].append(dict(name=name, poses=poses,
                                        screenshot=str(self.out / 'screenshots' / (name + '.png'))))
        print('Captured ' + name, flush=True)
        return poses

    def close(self):
        if self.process and self.process.poll() is None:
            self.run('quit', .1)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait()
        if self.log:
            self.log.close()
        self.control.close()
        (self.out / 'qconsole.log').write_text(self.console().replace(self.token, 'LOCAL_RCON_TOKEN'))
        for path in (self.out / 'console.log',):
            if path.exists():
                path.write_text(path.read_text(errors='replace').replace(self.token, 'LOCAL_RCON_TOKEN'))
        if (self.base / 'perf').exists():
            shutil.copytree(self.base / 'perf', self.out / 'poses')
        self.report['seconds'] = round(time.monotonic() - self.started, 2)
        # RCON replies can contain the ephemeral token in an echoed command.
        (self.out / 'run.json').write_text(json.dumps(self.report, indent=2).replace(self.token, 'LOCAL_RCON_TOKEN') + '\n')
        try:
            from PIL import Image, ImageDraw
            views = self.report['views']
            if views:
                sheet = Image.new('RGB', (1280, 266 * ((len(views)+2)//3)), (20, 24, 28))
                draw = ImageDraw.Draw(sheet)
                for i, view in enumerate(views):
                    im = Image.open(view['screenshot']).convert('RGB')
                    im.thumbnail((426, 240))
                    x, y = i % 3 * 426, i // 3 * 266
                    sheet.paste(im, (x, y + 26))
                    draw.text((x + 8, y + 7), view['name'], fill='white')
                sheet.save(self.out / 'contact-sheet.jpg', quality=92)
        except ImportError:
            pass
        if not self.args.keep_runtime:
            shutil.rmtree(self.root)


def capture_views(runtime, views):
    runtime.run('noclip')
    for view in views:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', view['name']):
            raise ValueError('Invalid capture name')
        for command in view.get('commands', []):
            runtime.run(command)
        if 'pose' in view:
            runtime.pose(view['pose'])
        for action in view.get('after_pose', []):
            if action.get('command'):
                runtime.run(action['command'], action.get('wait', .1))
            else:
                time.sleep(action.get('wait', .1))
        poses = runtime.capture(view['name'])
        for axis, (lo, hi) in view.get('expect_eye_bounds', {}).items():
            runtime.check(view['name'] + ' camera ' + axis, lo <= poses['0'][axis] <= hi, poses=poses)
        for marker in view.get('expect_log', []):
            runtime.check(view['name'] + ' message', marker in runtime.console(), marker=marker)


def mission(runtime):
    """Filled from MAP entities, so geometry edits cannot silently stale probes."""
    a = runtime.args
    source = parse_entities((runtime.out / 'pp_endline.map').read_text())
    live = [e for e in source if enabled(e, a.skill)]
    def one(predicate):
        found = [e for e in live if predicate(e['keys'])]
        if len(found) != 1:
            raise ValueError('Expected one mission entity, found ' + str(len(found)))
        return found[0]
    train = one(lambda k: k['classname'] == 'func_train')
    train_bounds = entity_bounds(train)
    def min_x():
        return runtime.train()[0] + train_bounds[0]
    def stopped_at(x):
        if abs(min_x()-x) >= 4:
            return False
        time.sleep(.4)
        return abs(min_x()-x) < 4
    switch = one(lambda k: k['classname'] == 'func_button' and k.get('target') == 'endline_divert')
    departure = one(lambda k: k['classname'] == 'func_button' and k.get('target') == 'depart_arm')
    extraction = one(lambda k: k['classname'] == 'trigger_platoon_extract')
    wave = [e for e in live if e['keys']['classname'].startswith('monster_') and e['keys'].get('deathtarget') == 'endline_wave_down']
    runtime.check('Difficulty-selected counterattack', len(wave) == (6, 9, 12)[a.skill], enemies=len(wave))
    if a.players > 1:
        # Only the primary client receives console cheats. Shelter the other
        # living client behind the medic station's walls during the long intro;
        # leaving an idle partner exposed would test death handling instead.
        medic = one(lambda k: k['classname'] == 'trigger_once' and k.get('target') == 'endline_secret_medic')
        refuge = entity_bounds(medic)
        runtime.pose([refuge[0]+48, refuge[1]+48, refuge[2]+24, 0, 90], slot=1)
    # The spawn trigger arms the intro via ordinary player contact.
    initial_x = min_x()
    runtime.run('+forward', .25)
    runtime.run('-forward', .1)
    runtime.until(lambda: min_x() < initial_x - 80, 12, 'Intro train did not move')
    runtime.capture('intro_train_moving')
    shotgun = next(e for e in live if e['keys']['classname'] == 'weapon_supershotgun')
    runtime.pose([*vec(shotgun['keys']['origin']), 0, 90], wait=.5)
    runtime.until(lambda: 'DOUBLE BARREL SHOTGUN' in runtime.console(), 4,
                  'Double-barrel pickup did not trigger its introduction')
    runtime.run('use Double Barrel Shotgun', .5)
    runtime.check('Double-barrel pickup and introduction fire', True)
    def touch_button(entity):
        bounds = entity_bounds(entity)
        # Approach opposite the button's push direction. The signal console
        # pushes west; the departure console pushes north. Start outside its
        # protective cover so an ordinary move also exercises the physical gate.
        yaw = float(entity['keys'].get('angle', 0))
        dx, dy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        distance = (abs(dx)*(bounds[3]-bounds[0]) + abs(dy)*(bounds[4]-bounds[1]))/2 + 56
        x = (bounds[0]+bounds[3])/2 - dx*distance
        y = (bounds[1]+bounds[4])/2 - dy*distance
        runtime.pose([x, y, bounds[2]-24, 0, yaw])
        runtime.run('+forward', .65)
        runtime.run('-forward', .1)
    if not a.early_switch:
        # At the negative-wait corner train_next teleports to the offstage east
        # pocket before pausing. Both offstage pockets must be inaccessible.
        runtime.until(lambda: stopped_at(2496), 75, 'Intro train did not reach its offstage wait')
        parked = min_x()
        time.sleep(.8)
        runtime.check('Train waits for switch', abs(min_x()-parked) < 2, train_min_x=parked)
    touch_button(switch)
    runtime.until(lambda: 'SIGNAL GREEN' in runtime.console(), 4, 'Signal control did not activate')
    runtime.until(lambda: min_x() < 2450, 8, 'Signal button did not dispatch train')
    runtime.capture('signal_diverted')
    runtime.until(lambda: stopped_at(800), 75 if a.early_switch else 35, 'Train did not reach loading siding')
    time.sleep(.5)
    runtime.check('Train remains at siding during defense', abs(min_x()-800) < 4, train_min_x=min_x())
    shutters = [e for e in live if e['keys'].get('targetname') == 'endline_reserve_doors'
                and e['keys']['classname'] == 'func_door']
    if shutters:
        # The four reserve doors rise; the service shortcut moves down and the
        # departure cover remains closed, so upward origins identify them.
        raised = [xyz for kind, xyz in runtime.entities() if kind == 'func_door' and xyz[2] > 150]
        runtime.check('All four reinforcement shutters open', len(raised) == len(shutters) == 4,
                      door_origins=raised)
    if a.players == 1:
        runtime.run('save endline_smoke', .5)
        save = runtime.base / 'save/endline_smoke/pp_endline.sav'
        runtime.check('Native save written at siding', save.is_file() and save.stat().st_size > 0)
        runtime.run('load endline_smoke', 3)
        runtime.check('Stopped train survives save/load', abs(min_x()-800) < 4, train_min_x=min_x())
    touch_button(departure)
    runtime.check('Departure control stays covered during defense', 'DEPARTURE REQUESTED' not in runtime.console())
    bounds = entity_bounds(extraction)
    deck_z = bounds[2] + 24
    board = [(bounds[0]+bounds[3])/2, (bounds[1]+bounds[4])/2, deck_z, 0, 180]
    # Kill exactly the difficulty-filtered counterattack through real damage.
    for entity in wave:
        runtime.pose([*vec(entity['keys']['origin']), 0, 90], wait=.35)
    runtime.capture('counterattack_cleared')
    runtime.check('Train waits for manual departure', abs(min_x()-800) < 4, train_min_x=min_x())
    touch_button(departure)
    runtime.pose(board)
    if a.players > 1:
        time.sleep(1)
        poses = runtime.capture('awaiting_living_partner')
        runtime.check('Waiting teammate remains alive', poses.get('1', {}).get('z', -1000) > refuge[2]+38,
                      pose=poses.get('1'))
        runtime.check('Living teammate outside prevents departure', abs(min_x()-800) < 4, train_min_x=min_x())
        # Keep the two players separated on the wide rear deck.
        runtime.pose([board[0]+80, board[1], board[2], 0, 180], slot=1)
    runtime.until(lambda: min_x() < 750, 8, 'All-aboard check did not start departure')
    before = runtime.capture('train_departing')
    time.sleep(1)
    after = runtime.capture('train_ride')
    for slot in range(a.players):
        key = str(slot)
        runtime.check('Train carries player ' + str(slot+1),
                      key in before and key in after and after[key]['x'] < before[key]['x'] - 30,
                      before=before.get(key), after=after.get(key))
    runtime.until(lambda: 'MISSION COMPLETE' in runtime.console() or 'END OF THE LINE COMPLETE' in runtime.console(),
                   60, 'Final train path did not complete the mission')
    runtime.capture('mission_complete')
    runtime.check('Final path completes mission', True)
    deaths = re.findall(r'(?m)^Player(?: P2)? (?:died\.|was squished|blew up|was in the wrong place|tried to invade).*', runtime.console())
    runtime.check('No squad death bypassed boarding gate', not deaths, deaths=deaths)


def deployment(runtime):
    """Observe real AI leaving every reserve room with the activator visible."""
    source = [e for e in parse_entities((runtime.out / 'pp_endline.map').read_text()) if enabled(e, runtime.args.skill)]
    wave = [e for e in source if e['keys'].get('deathtarget') == 'endline_wave_down']
    # Full room envelopes, expanded one soldier radius at the exits: a body
    # must actually clear its doorway before it counts as deployed.
    rooms = {'upper': (-1488, -656, 240, -880, -336, 432),
             'lower': (-816, 848, 0, -112, 1152, 208),
             'yard': (2096, -1728, 0, 2608, -1104, 208)}
    def remaining():
        actors = [xyz for kind, xyz in runtime.entities() if kind.startswith('monster_')]
        return {name: [p for p in actors if all(bounds[i] <= p[i] <= bounds[i+3] for i in range(3))]
                for name, bounds in rooms.items()}
    before = remaining()
    expected = {name: sum(e['keys'].get('_endline_reserve') == name for e in wave) for name in rooms}
    runtime.check('Reserve rooms contain exactly the selected wave',
                  all(len(before[name]) == expected[name] for name in rooms),
                  before=before, expected=expected)
    if runtime.args.players > 1:
        runtime.pose([-2464, -1656, 24, 0, 90], slot=1)
    switch = next(e for e in source if e['keys'].get('target') == 'endline_divert' and e['keys']['classname'] == 'func_button')
    bounds = entity_bounds(switch)
    runtime.run('notarget')  # OFF: triggered monsters must really acquire us.
    runtime.pose([bounds[3]+56, (bounds[1]+bounds[4])/2, bounds[2]-24, 0, 180])
    runtime.run('+forward', .65)
    runtime.run('-forward', .1)
    runtime.until(lambda: 'SIGNAL GREEN' in runtime.console(), 5, 'Signal control did not activate')
    def deployed():
        current = remaining()
        runtime.report['deployment_last_remaining'] = current
        return current if not any(current.values()) else False
    result = runtime.until(deployed, 40, 'Counterattack troops did not leave all three reserve rooms')
    runtime.check('Live counterattack exits all three rooms', True, remaining=result, counts=expected)
    for name, pose in [('upper_deployed', [-1216, -224, 280, 0, 270]),
                       ('lower_deployed', [-448, 640, 40, 0, 90]),
                       ('storage_deployed', [1920, -1392, 56, 0, 0])]:
        runtime.pose(pose)
        runtime.capture(name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True)
    p.add_argument('--bsp', type=Path, default=ROOT / 'baseq2/maps/pp_endline.bsp')
    p.add_argument('--source', type=Path, default=ROOT / 'maps/source/pp_endline.map')
    p.add_argument('--runtime', type=Path, default=ROOT / 'debug')
    p.add_argument('--output-root', type=Path, default=ROOT / 'build/endline-qa')
    p.add_argument('--skill', type=int, choices=(0, 1, 2), default=1)
    p.add_argument('--players', type=int, choices=(1, 2), default=2)
    p.add_argument('--views', type=Path, help='Capture a JSON list of views instead of the mission integration test')
    p.add_argument('--early-switch', action='store_true', help='Operate signal while intro train is moving, exercising dispatch event order')
    p.add_argument('--deployment-only', action='store_true', help='Observe live AI leaving all three reserve rooms instead of completing the mission')
    p.add_argument('--renderer', choices=('gl1', 'gl3', 'soft'), default='gl3')
    p.add_argument('--display-backend', choices=('offscreen', 'xvfb', 'dummy', 'current'), default='xvfb')
    p.add_argument('--egl-device', type=int, default=1)
    p.add_argument('--size', default='1280x720')
    p.add_argument('--keep-runtime', action='store_true')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', a.label):
        p.error('label must be a simple basename')
    if not re.fullmatch(r'[0-9]+x[0-9]+', a.size):
        p.error('size must be WIDTHxHEIGHT')
    if a.display_backend == 'dummy' and a.renderer != 'soft':
        p.error('dummy display requires soft renderer')
    runtime = Runtime(a)
    try:
        runtime.start()
        if a.views:
            capture_views(runtime, json.loads(a.views.read_text()))
        elif a.deployment_only:
            deployment(runtime)
        else:
            mission(runtime)
        runtime.report['passed'] = True
    except Exception as exc:
        runtime.report['error'] = str(exc)
        print(str(exc), flush=True)
    finally:
        runtime.close()
    print(runtime.out, flush=True)
    return 0 if runtime.report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
