#!/usr/bin/env python3
"""Capture End of the Line and exercise its mission in an isolated real engine.

Only the project's original asset overlay and loose artwork are staged. No PAK
files or user settings are read. Mission checks use ordinary movement and gunfire,
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

from verify_sandkeep import BSP, enabled, entity_bounds, parse_entities, vec

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
                        r_farsee=args.farsee, r_vsync=0, vid_maxfps=60, cl_maxfps=60,
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

    def game_seconds(self):
        # Player list connection time advances with server frames, including
        # when software-rendered split-screen runs slower than wall time.
        start = len(self.console())
        self.run('cmd playerlist', .25)
        clock = self.until(lambda: re.search(r'(?m)^(\d+):(\d{2})\s+\d+\s+-?\d+\s+Player$',
                                             self.console()[start:]),
                           5, 'No server clock in the player list')
        return int(clock[1]) * 60 + int(clock[2])

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


def boarding_fight(runtime, bsp, min_x, stop, wave, *, name, hatch_prefix,
                   clear_message, door_names=(), deployment_only=False):
    """Watch live enemies board, then verify that the last kill frees the train."""
    stop_x = vec(stop['origin'])[0]

    def parked_at_stop():
        x = min_x()
        return x if abs(x - stop_x) < 10 and abs(min_x() - x) < 1 else None

    parked_x = runtime.until(parked_at_stop, 60, f'Train did not stop at the {name}')
    runtime.check(f'Train stops at the {name}', True, train_min_x=parked_x)

    # The train's preserved footprint is 1152 units long. The last 464
    # units are the open-topped car. Enemies in this volume below the rim
    # have crossed the wall; their sealed spawn rooms are above the rim.
    def boarder():
        return next((p for kind, p in runtime.entities()
                     if kind.startswith('monster_soldier')
                     and parked_x + 712 < p[0] < parked_x + 1120
                     and -108 < p[1] < 110 and 328 <= p[2] < 407), None)

    enemy = runtime.until(boarder, 35, f'No live soldier dropped below the car rim at the {name}')
    runtime.check(f'Live {name} ambusher drops into armored car', True, enemy_origin=enemy)
    runtime.run('cl_gun 1')
    runtime.run('+right', .5)
    runtime.run('-right', .1)
    runtime.capture(f'{name}_boarders')
    if deployment_only:
        return parked_x

    def opened_doors():
        expected = [bsp.open_door_offset(entity, model, offset)
                    for entity, model, offset in bsp.bmodels
                    if entity['keys'].get('targetname') in door_names
                    or entity['keys'].get('targetname', '').startswith(hatch_prefix)]
        actual = [p for kind, p in runtime.entities() if kind == 'func_door']
        for offset in expected:
            closest = min(actual, key=lambda p: math.dist(p, offset), default=None)
            if closest is None or math.dist(closest, offset) > 2:
                return False
            actual.remove(closest)
        return bool(expected)

    runtime.until(opened_doors, 30, f'The {name} shutters or doors did not open')
    runtime.check(f'All {name} shutters and doors open with train parked',
                  abs(min_x() - parked_x) < 1)

    # This check isolates progression from combat balance. Pose into each
    # soldier to cause real damage and follow the engine's live death counter.
    counter_line = re.compile(r'\b(\d+) more to go\.\.\.')
    start = len(runtime.console())
    spawn_positions = [vec(e['keys']['origin']) for e in wave]
    x_lo = min(p[0] for p in spawn_positions) - 80
    x_hi = parked_x + 1176
    y_lo = min(p[1] for p in spawn_positions) - 80
    y_hi = max(140, max(p[1] for p in spawn_positions) + 80)
    kills_left = len(wave)
    last_enemy_holds = False
    deadline = time.monotonic() + 90

    while kills_left and time.monotonic() < deadline:
        positions = [p for kind, p in runtime.entities()
                     if kind.startswith('monster_soldier')
                     and x_lo < p[0] < x_hi and y_lo < p[1] < y_hi
                     and 305 < p[2] < 665]
        for x, y, z in positions:
            runtime.pose([x, y, z - 10, 0, 0], wait=.2)
            messages = runtime.console()[start:]
            if 'Sequence completed!' in messages:
                kills_left = 0
                break
            remaining = counter_line.findall(messages)
            if remaining:
                new_count = int(remaining[-1])
                if new_count == 1 and kills_left > 1:
                    last_enemy_holds = abs(min_x() - parked_x) < 1
                kills_left = new_count

    runtime.check(f'Train waits for the last {name} enemy', last_enemy_holds)
    runtime.check(f'The last kill clears the {name} ambush', kills_left == 0)
    # Put the tester back in a clear firing lane after the telefrag. A real
    # kill never leaves the player sharing the target's collision hull.
    runtime.pose([parked_x + 940, -76, 329, 0, 180])
    runtime.until(lambda: clear_message in runtime.console()[start:], 12,
                  f'The {name} clear message did not fire after the last kill')
    return parked_x


def garage_finale(runtime, bsp, min_x, stop, wave):
    parked_x = boarding_fight(
        runtime, bsp, min_x, stop, wave, name='garage', hatch_prefix='endline_ambush_hatch_',
        clear_message='AMBUSH CLEARED', door_names=('endline_garage_door',),
        deployment_only=runtime.args.deployment_only,
    )
    if runtime.args.deployment_only:
        return

    runtime.until(lambda: 'MISSION COMPLETE' in runtime.console(), 24,
                  'The cleared ambush did not lead to intermission')
    runtime.capture('garage_exit_intermission')
    # Intermission suppresses client-side entity queries, but the train keeps
    # moving during the cinematic. Capture the late camera after the final leg.
    outside = next(e['keys'] for e in bsp.entities
                   if e['keys'].get('targetname') == 'endline_outside')
    train = next(e['keys'] for e in bsp.entities if e['keys']['classname'] == 'func_train')
    outside_seconds = abs(vec(outside['origin'])[0] - parked_x) / float(train['speed'])
    time.sleep(outside_seconds + 3)
    runtime.capture('mission_complete')
    runtime.check('Final path completes mission', True)


def mission(runtime):
    """Exercise the parked train, one-way boarding, shoot switch, and ambush stops."""
    a = runtime.args
    source = parse_entities((runtime.out / 'pp_endline.map').read_text())
    live = [e for e in source if enabled(e, a.skill)]

    def named(name):
        return next(e for e in live if e['keys'].get('targetname') == name)

    bsp = BSP(runtime.base / 'maps/pp_endline.bsp')
    train = next(e['keys'] for e in bsp.entities if e['keys']['classname'] == 'func_train')
    train_min_x = bsp.models[int(train['model'][1:])][0]

    def min_x():
        return runtime.train()[0] + train_min_x

    siding_x = vec(named('endline_siding')['keys']['origin'])[0]
    bridge_stop = named('endline_bridge_stop')['keys']
    garage_stop = named('endline_gate_stop')['keys']
    bridge_wave = [e for e in live if e['keys'].get('deathtarget') == 'endline_bridge_down']
    wave = [e for e in live if e['keys'].get('deathtarget') == 'endline_ambush_down']
    runtime.check('Difficulty-selected bridge ambush', len(bridge_wave) == (6, 8, 10)[a.skill],
                  enemies=len(bridge_wave))
    runtime.check('Difficulty-selected garage ambush', len(wave) == (9, 12, 15)[a.skill],
                  enemies=len(wave))
    runtime.check('Train starts at the station', abs(min_x() - siding_x) < 4)
    runtime.capture('window_insertion')

    shotgun = next(e for e in live if e['keys']['classname'] == 'weapon_supershotgun')
    runtime.pose([*vec(shotgun['keys']['origin']), 0, 90], wait=.5)
    runtime.until(lambda: 'DOUBLE BARREL SHOTGUN' in runtime.console(), 4,
                  'Double-barrel pickup did not trigger its introduction')
    runtime.check('Ground route shotgun pickup and introduction fire', True)

    medic = next(e for e in live if e['keys']['classname'] == 'trigger_once'
                 and e['keys'].get('target') == 'endline_secret_medic')
    refuge = entity_bounds(medic)
    if a.players > 1:
        runtime.pose([refuge[0]+48, refuge[1]+48, refuge[2]+24, 0, 90], slot=1)
    else:
        runtime.run('save endline_station', .5)
        saved = runtime.base / 'save/endline_station/pp_endline.sav'
        runtime.check('Native save written at station', saved.is_file() and saved.stat().st_size > 0)
        runtime.run('load endline_station', 2)
        runtime.check('Station train survives save/load', abs(min_x() - siding_x) < 4)

    def cover_count():
        return sum(kind == 'func_explosive' for kind, _ in runtime.entities())

    covers = cover_count()
    runtime.check('A box covers the shoot switch', covers > 0)
    # Begin just inside the raised station lip and use real forward input to
    # step over the rail and fall into the armored car.
    runtime.pose([1610, -169, 488, 15, 90], wait=.6)
    runtime.capture('station_boarding_gantry')
    runtime.run('+forward', .32)
    runtime.run('-forward', .9)
    view = runtime.capture('boarded_car')['0']
    runtime.check('Player drops from gantry into the car',
                  -111 < view['y'] < 110 and 348 < view['z'] < 420, view=view)

    control = entity_bounds(named('endline_depart_switch'))
    aim = [(control[i] + control[i+3]) / 2 for i in range(3)]
    shooter = (aim[0], -34, 329)
    dx, dy = aim[0] - shooter[0], aim[1] - shooter[1]
    pitch = -math.degrees(math.atan2(aim[2] - shooter[2] - 22, math.hypot(dx, dy)))
    yaw = math.degrees(math.atan2(dy, dx))

    def shoot_switch():
        runtime.pose([*shooter, pitch, yaw], wait=.5)
        runtime.run('+attack', .85)
        runtime.run('-attack', .12)

    if a.players > 1:
        shoot_switch()
        runtime.check('Cover blocks gunfire until the living squad boards',
                      cover_count() == covers and abs(min_x() - siding_x) < 4)
        runtime.pose([1740, -75, 329, 0, 180], slot=1)
    runtime.until(lambda: cover_count() == covers-1, 8, 'Boarding did not burst the cover box')
    runtime.check('Boarding exposes the switch without starting the train',
                  abs(min_x() - siding_x) < 4)
    runtime.pose([*shooter, pitch, yaw], wait=.5)
    runtime.capture('departure_switch_exposed')

    runtime.pose([1648, -84, 329, 0, 270], wait=.5)
    runtime.run('+forward', .22)
    runtime.run('+moveup', .65)
    runtime.run('-moveup', .08)
    runtime.run('-forward', .55)
    captive = runtime.capture('car_rim_blocks_jump')['0']
    runtime.check('Jumping into the armored rim keeps the player aboard',
                  -111 < captive['y'] < 110 and 348 < captive['z'] < 354, view=captive)

    shoot_switch()
    runtime.until(lambda: min_x() < siding_x - 20, 12, 'Shooting the exposed switch did not start the train')
    runtime.check('Only a shot at the uncovered switch starts the train', True)
    before = runtime.capture('train_departing')
    time.sleep(.8)
    after = runtime.capture('train_ride')
    for slot in range(a.players):
        key = str(slot)
        runtime.check('Train carries player ' + str(slot+1),
                      key in before and key in after and after[key]['x'] < before[key]['x'] - 24,
                      before=before.get(key), after=after.get(key))
    if a.players > 1:
        # Keep the idle second view safe while the active player observes
        # the AI and clears the ambushes for the progression test.
        runtime.pose([refuge[0]+48, refuge[1]+48, refuge[2]+24, 0, 90], slot=1)
    runtime.run('notarget')  # OFF: both ambushes must really acquire the rider.
    bridge_x = boarding_fight(
        runtime, bsp, min_x, bridge_stop, bridge_wave, name='bridge',
        hatch_prefix='endline_bridge_hatch_', clear_message='BRIDGE CLEAR',
    )
    runtime.until(lambda: min_x() < bridge_x - 20, 12,
                  'Train did not depart the bridge after the ambush cleared')
    runtime.check('Train resumes after the bridge ambush', True)
    runtime.until(lambda: min_x() < -2700, 55, 'Train did not leave the west bridge')
    runtime.capture('train_ride_west_bridge')
    garage_finale(runtime, bsp, min_x, garage_stop, wave)


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
    p.add_argument('--deployment-only', action='store_true', help='Stop after observing a live ambusher board the train')
    p.add_argument('--renderer', choices=('gl1', 'gl3', 'soft'), default='gl3')
    p.add_argument('--farsee', type=int, choices=(0, 1), default=1,
                   help='Start with this archived draw distance setting')
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
