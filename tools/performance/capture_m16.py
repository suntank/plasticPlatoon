#!/usr/bin/env python3
"""Capture authored rifle/pistol views and four-player aiming in an isolated runtime.

This uses the existing opt-in visual QA controller only to equip real players.
It does not modify engine, renderer, model or gameplay code. Timing results from
an offscreen software GL host are not Raspberry Pi performance measurements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True)
    p.add_argument('--weapon', choices=['Rifle','Pistol'], default='Rifle')
    p.add_argument('--mixed-weapons', action='store_true', help='Alternate pistol/rifle across four slots')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--renderer', choices=['gl1', 'gl3'], default='gl1')
    p.add_argument('--source', type=Path, default=ROOT / 'release')
    p.add_argument('--fullbright', action='store_true', help='Unlit material/geometry QA')
    p.add_argument('--ads', action='store_true', help='Exercise actual-model aim and recovery')
    p.add_argument('--target', action='store_true', help='Add an idle soldier downrange in single-view captures')
    p.add_argument('--map-file', type=Path, help='Compiled pp_m16_review.bsp fixture')
    p.add_argument('--four', action='store_true')
    p.add_argument('--frames', type=int, default=240)
    p.add_argument('--sdl-include', type=Path)
    p.add_argument('--hold', action='store_true')
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        p.error('output must be a fresh directory')
    base = out / 'runtime/baseq2'
    base.mkdir(parents=True)
    runtime = base.parent
    shots = out / 'screenshots'
    shots.mkdir()
    for name in ('quake2', 'ref_' + a.renderer + '.so'):
        shutil.copy2(a.source / name, runtime / name)
    shutil.copy2(a.source / 'baseq2/game.so', base / 'game.so')
    shutil.copy2(a.package, base / 'plastic-platoon.pk3')
    for path in (ROOT / 'baseq2').glob('operation-*.pk3'):
        (base / path.name).symlink_to(path.resolve())
    shutil.copytree(ROOT / 'baseq2/tuning', base / 'tuning')
    map_name = 'pp_ant_test'
    if a.map_file:
        map_name = a.map_file.stem
        (base / 'maps').mkdir()
        shutil.copy2(a.map_file, base / 'maps' / a.map_file.name)
    symbols = subprocess.check_output(['nm', str(runtime / 'quake2')], text=True)
    names = ['cl', 'cls', 'svs', 'ge', 'maxclients', 'Cmd_TokenizeString',
             'Info_SetValueForKey', 'SS_GetSlot', 'Cvar_Set', 'Cbuf_AddText', 'CL_GetModelADSBlend']
    offsets = {name: re.search(r'^([0-9a-fA-F]+) [a-zA-Z] ' + name + r'$', symbols, re.M)[1]
               for name in names}
    symbols = subprocess.check_output(['nm', str(base / 'game.so')], text=True)
    game_offsets = {name: re.search(r'^([0-9a-fA-F]+) [a-zA-Z] ' + name + r'$', symbols, re.M)[1]
                    for name in ['FindItem', 'ChangeWeapon']}
    shim = out / 'controls.so'
    flags = ['-I' + str(a.sdl_include)] if a.sdl_include else subprocess.check_output(
        ['pkg-config', '--cflags', 'sdl2'], text=True).split()
    subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-D_DEFAULT_SOURCE',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"', *flags,
                    str(ROOT / 'tests/input/color_variants_runtime.c'),
                    str(ROOT / 'tests/input/color_variants_game.c'), '-ldl', '-o', str(shim)], check=True)
    controls = out / 'controls.txt'
    controls.write_text('')
    token = secrets.token_hex(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    players = 4 if a.four else 1
    settings = dict(name='M16 review', skin='soldier/green', vid_renderer=a.renderer,
                    vid_fullscreen=0, r_mode=-1, r_customwidth=1280,
                    r_customheight=720, r_vsync=0, vid_maxfps=120,
                    cl_maxfps=120, cl_async=1, s_initsound=0, cheats=1,
                    skill=0, cl_bob=0, cl_mflash_tune_mode=0,
                    cl_mflash_tune_cam_back=28, cl_mflash_tune_cam_right=70,
                    cl_mflash_tune_cam_up=8, cl_mflash_tune_target_up=10,
                    cl_mflash_tune_lookat=1, cl_mflash_tune_show_viewmodel=0,
                    crosshair=0, cl_blend=0, cl_kickangles=0, r_hudscale=0,
                    con_notifytime=0, r_fullbright=int(a.fullbright), r_novis=0, r_cull=1,
                    r_msaa_samples=0, r_anisotropic=0, in_grab=0, logfile=2,
                    cl_aimassist=0, rcon_password=token)
    startup = ('cl_bench_local 4 ' + map_name if a.four else
               'set maxclients 2\nset coop 1\nset singleplayer 0\nset deathmatch 0\nmap ' + map_name)
    cfg = '\n'.join(f'set {k} "{v}"' for k, v in settings.items()) + '\n' + startup + '\n'
    (base / 'm16-review.cfg').write_text(cfg)
    (out / 'settings.cfg').write_text(cfg.replace(token, 'LOCAL_RCON_TOKEN'))
    command = [str(runtime / 'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'ip', '127.0.0.1', '+set', 'port', str(port)]
    for key in ['vid_renderer', 'vid_fullscreen', 'r_mode', 'r_customwidth', 'r_customheight', 's_initsound']:
        command += ['+set', key, str(settings[key])]
    command += ['+exec', 'm16-review.cfg']
    env = {**os.environ, 'SDL_VIDEODRIVER': 'offscreen', 'SDL_AUDIODRIVER': 'dummy',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2', 'LD_PRELOAD': str(shim),
           'XDG_CACHE_HOME': str(runtime / 'cache'), 'PP_COLOR_CONTROLS': str(controls),
           **{'PP_COLOR_' + k: v for k, v in offsets.items()},
           **{'PP_COLOR_GAME_' + k: v for k, v in game_offsets.items()}}
    manifest = dict(label=a.label, renderer=a.renderer, players=players,
                    executable_sha256=digest(runtime / 'quake2'),
                    game_sha256=digest(base / 'game.so'),
                    renderer_sha256=digest(runtime / ('ref_' + a.renderer + '.so')),
                    package_sha256=digest(base / 'plastic-platoon.pk3'),
                    map=map_name, backend='SDL offscreen, llvmpipe',
                    pi_benchmark=False, fullbright=a.fullbright, target=a.target, weapon=a.weapon, mixed_weapons=a.mixed_weapons, views=[], states={})
    process = None
    logpath = out / 'console.log'

    def wait(check, label, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = check()
            if result:
                return result
            if process.poll() is not None:
                raise RuntimeError('engine exited before ' + label)
            time.sleep(.04)
        raise RuntimeError('timeout: ' + label)

    def rcon(cmd):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(.25)
            s.sendto(b'\xff' * 4 + b'rcon ' + token.encode() + b' ' + cmd.encode() + b'\n', ('127.0.0.1', port))
            replies = []
            while True:
                try:
                    replies.append(s.recv(65535).decode(errors='replace'))
                    s.settimeout(.025)
                except socket.timeout:
                    return '\n'.join(replies)

    def action(cmd):
        with controls.open('a') as f:
            f.write(cmd + '\n')

    def state(label):
        action('state ' + label)
        def read():
            for line in logpath.read_text(errors='replace').splitlines():
                if 'PP_COLOR_STATE ' in line:
                    try:
                        item = json.loads(line.split('PP_COLOR_STATE ', 1)[1])
                    except json.JSONDecodeError:
                        continue
                    if item['label'] == label:
                        return item
        result = wait(read, 'state ' + label)
        manifest['states'][label] = result
        return result

    def shot(name, **metadata):
        time.sleep(.4)
        before = set((base / 'scrnshot').glob('*.png'))
        rcon('screenshot png')
        path = wait(lambda: next(iter(set((base / 'scrnshot').glob('*.png')) - before), None), name)
        wait(lambda: path.read_bytes().endswith(b'IEND\xaeB`\x82'), 'PNG complete')
        dest = shots / (name + '.png')
        shutil.copy2(path, dest)
        manifest['views'].append(dict(name=name, screenshot=dest.name, sha256=digest(dest), **metadata))
        print(dest, flush=True)

    try:
        with logpath.open('w') as log:
            process = subprocess.Popen(command, cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
                                       env=env, start_new_session=True)
            wait(lambda: map_name in rcon('status'), 'local server', 60)
            for i in range(80):
                ready = state('ready-' + str(i))
                if ready['connection'] == 4 and all(c['spawned'] for c in ready['clients'][:players]):
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('players did not spawn')
            for slot in range(players):
                for cmd in ['notarget', 'give health 10000', 'give weapons', 'give ammo', 'use ' + (('Rifle' if slot % 2 else 'Pistol') if a.mixed_weapons else a.weapon)]:
                    action(f'clientcmd {slot} {cmd}')
                action(f'skin {slot} green')
            time.sleep(1)
            rcon('cl_bench_pose 0 -500 -1400 24 0 90')
            if a.four:
                rcon('cl_bench_pose 1 -590 -1312 24 0 66')
                rcon('cl_bench_pose 2 -500 -1262 24 0 90')
                rcon('cl_bench_pose 3 -410 -1312 24 0 114')
                time.sleep(1)
                shot('four-player', view='four-player')
                rcon('set cl_perf_frames ' + str(a.frames))
                rcon('set cl_perf_quit 0')
                rcon('cl_perf_start m16-four')
                capture_csv = base / 'perf/m16-four-frames.csv'
                # RCON-triggered console text may remain redirected or buffered.
                # A complete CSV is the authoritative end of this bounded run.
                wait(lambda: capture_csv.exists() and
                     len(capture_csv.read_text().splitlines()) >= a.frames + 1,
                     'performance capture', 45)
                shutil.copytree(base / 'perf', out / 'perf')
                state('four-equipped')
                if a.ads:
                    action('ads 0 1'); action('ads 2 1')
                    time.sleep(.5)
                    shot('four-mixed-ads', view='slots 1/3 aimed, 2/4 hip')
                    aimed = state('four-mixed-ads')
                    assert [c['model_ads_blend'] for c in aimed['clients']] == [1, 0, 1, 0]
                    for slot in range(4): action(f'attack {slot} 1')
                    shot('four-mixed-ads-fire', view='four firing, slots 1/3 aimed')
                    for slot in range(4): action(f'attack {slot} 0')
                    action('ads 0 0'); action('ads 1 1'); action('ads 2 0'); action('ads 3 1')
                    time.sleep(.5)
                    shot('four-mixed-ads-reversed', view='slots 2/4 aimed, 1/3 hip')
                    aimed = state('four-mixed-ads-reversed')
                    assert [c['model_ads_blend'] for c in aimed['clients']] == [0, 1, 0, 1]
                    for slot in range(4): action(f'attack {slot} 1')
                    shot('four-mixed-ads-reversed-fire', view='four firing, slots 2/4 aimed')
                    for slot in range(4): action(f'attack {slot} 0')
            else:
                if a.target:
                    action('clientcmd 0 spawnentity ' + ('monster_soldier_light' if a.weapon == 'Pistol' else 'monster_soldier') + ' -500 -1080 24 0 270 0')
                time.sleep(.7)
                shot('fps', view='first-person')
                if a.ads:
                    action('ads 0 1')
                    time.sleep(.5)
                    shot('ads', view='actual-model sights')
                    assert state('ads')['clients'][0]['model_ads_blend'] == 1
                    rcon('+attack')
                    time.sleep(.1)
                    shot('ads-fire', view='aimed firing')
                    rcon('-attack')
                    action('ads 0 0')
                    time.sleep(.5)
                    shot('fps-return', view='return from sights')
                    assert state('ads-return')['clients'][0]['model_ads_blend'] == 0
                    action('clientcmd 0 use Shotgun')
                    time.sleep(.8)
                    action('ads 0 1')
                    shot('shotgun-ads', view='existing shotgun image-overlay regression')
                    other = state('shotgun-ads')['clients'][0]
                    assert 'v_shotg' in other['gunmodel'] and other['model_ads_blend'] == 0
                    action('ads 0 0')
                    action('clientcmd 0 use ' + a.weapon)
                    time.sleep(.8)
                rcon('set cl_mflash_tune_mode 1')
                shot('held', view='third-person player')
                rcon('set cl_mflash_tune_mode 0')
                rcon('set cl_gun 0')
                action('clientcmd 0 spawnentity ' + ('weapon_blaster' if a.weapon == 'Pistol' else 'weapon_machinegun') + ' -500 -1342 40 0 0 0')
                action('clientcmd 0 noclip')
                rcon('cl_bench_pose 0 -500 -1412 34 24 90')
                time.sleep(.8)
                shot('pickup', view='item pickup')
                state('rifle-equipped')
            if a.hold:
                (out / 'control.json').write_text(json.dumps({'port': port, 'token': token, 'pid': process.pid}))
                print('Holding runtime for manual QA: ' + str(out / 'control.json'), flush=True)
                while process.poll() is None:
                    time.sleep(.2)
            else:
                rcon('quit')
                process.wait(timeout=10)
            manifest['returncode'] = process.returncode
            if process.returncode:
                raise RuntimeError('engine exit ' + str(process.returncode))
            manifest['complete'] = True
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
