#!/usr/bin/env python3
"""Run real SDL gamepad -> command -> server -> aiming feedback in isolation."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or Path(tempfile.mkdtemp(prefix='pp-aim-smoke-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / 'runtime'
    base = runtime / 'baseq2'
    base.mkdir(parents=True)
    for source, target in (
            (ROOT/'release/quake2', runtime/'quake2'),
            (ROOT/'release/ref_gl1.so', runtime/'ref_gl1.so'),
            (ROOT/'release/baseq2/game.so', base/'game.so'),
            (ROOT/'release/baseq2/plastic-platoon.pk3', base/'plastic-platoon.pk3'),
            (ROOT/'release/baseq2/operation-ant-test.pk3', base/'operation-ant-test.pk3')):
        shutil.copy2(source, target)
    shutil.copytree(ROOT/'release/baseq2/tuning', base/'tuning')
    symbols = subprocess.check_output(['nm', str(runtime/'quake2')], text=True)
    offsets = {}
    for label, symbol in (('CLIENT', 'cl'), ('STATIC', 'cls')):
        offsets[label] = re.search(r'^([0-9a-fA-F]+) [bdB] ' + symbol + '$', symbols, re.M)[1]
    shim = output/'aim_assist_virtual.so'
    flags = subprocess.check_output(['sdl2-config', '--cflags', '--libs'], text=True).split()
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-shared', '-fPIC', '-O2',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"',
                    str(ROOT/'tests/input/aim_assist_virtual.c'), '-ldl', *flags, '-o', str(shim)], check=True)
    controls = output/'controls.txt'
    controls.write_text('')
    token = secrets.token_hex(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    (base/'aim-smoke.cfg').write_text(
        'set maxclients 2\nset coop 1\nset singleplayer 0\nset deathmatch 0\n'
        'set cheats 1\nset skill 0\nset cl_aimassist 1\nset sv_aimassist 1\n'
        'set cl_gamebird_autolevel 0\nset cl_aimassist_speed 30\nset cl_aimassist_strength 8\n'
        f'set rcon_password {token}\n'
        'bind BTN_WEST +ads\nbind BTN_BACK centerview\nbind F8 centerview\n')
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'vid_renderer', 'gl1', '+set', 'vid_fullscreen', '0',
               '+set', 'r_mode', '-1', '+set', 'r_customwidth', '320', '+set', 'r_customheight', '240',
               '+set', 's_initsound', '0', '+set', 'r_vsync', '0', '+set', 'vid_maxfps', '120',
               '+set', 'logfile', '2', '+set', 'ip', '127.0.0.1', '+set', 'port', str(port),
               '+exec', 'aim-smoke.cfg', '+map', 'pp_ant_test']
    env = {**os.environ, 'SDL_VIDEODRIVER': 'offscreen', 'SDL_AUDIODRIVER': 'dummy',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2',
           'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS': '1', 'LD_PRELOAD': str(shim),
           'PP_AIM_CONTROLS': str(controls), **{'PP_AIM_'+key+'_OFFSET': value for key, value in offsets.items()}}
    log_path = output/'console.log'
    snapshots = {}
    errors = []

    def rcon(command):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
            control.settimeout(.3)
            control.sendto(b'\xff'*4+b'rcon '+token.encode()+b' '+command.encode()+b'\n', ('127.0.0.1', port))
            chunks = []
            while True:
                try:
                    chunks.append(control.recvfrom(65535)[0][4:].decode(errors='replace'))
                    control.settimeout(.02)
                except socket.timeout:
                    return ''.join(chunks)

    def action(text):
        with controls.open('a') as stream:
            stream.write(text+'\n')
            stream.flush()

    def snapshot(label):
        action('state '+label)
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            for line in re.findall(r'PP_AIM_STATE (.+)', log_path.read_text(errors='replace')):
                item = json.loads(line)
                snapshots[item['label']] = item
            if label in snapshots:
                return snapshots[label]
            if process.poll() is not None:
                raise RuntimeError('client exited before snapshot '+label)
            time.sleep(.03)
        raise RuntimeError('missing snapshot '+label)

    def check(condition, label):
        if not condition: errors.append(label)
        print(label+': '+('PASS' if condition else 'FAIL'), flush=True)

    def restore_pose():
        rcon('cl_bench_pose 0 0 -1488 24 0 90')
        time.sleep(.45)

    def pulse(button):
        action(f'button {button} 1')
        time.sleep(.1)
        action(f'button {button} 0')
        time.sleep(.2)

    with log_path.open('w') as log:
        process = subprocess.Popen(command, cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic()+40
            while time.monotonic() < deadline:
                state = snapshot('ready_'+str(int(time.monotonic()*100)))
                if state['connection'] == 4 and 'pp_ant_test' in rcon('status'): break
                time.sleep(.2)
            else: raise RuntimeError('map/player did not become ready')
            rcon('god'); rcon('notarget')
            restore_pose()
            # Keep the central body point inside the narrow hip-fire cone.
            rcon('spawnentity monster_ant 12 -1232 24 0 270 0 1')
            time.sleep(.5)
            baseline = snapshot('keyboard_baseline')
            check(not baseline['buttons'] & 8 and baseline['stats'][0] == 0, 'keyboard_initially_unassisted')
            pulse(4)  # SDL Back: bound to harmless centerview, establishes controller ownership.
            time.sleep(.35)
            hip = snapshot('hip_assisted')
            check(hip['buttons'] & 8 and hip['stats'][0] & 3 == 3, 'gamepad_flag_reaches_server_and_selects_target')
            check(abs(hip['stats'][3])+abs(hip['stats'][4]) > 100, 'hip_reticle_offset_tracks_target')
            check(max(abs(hip['angles'][i]-baseline['angles'][i]) for i in (0, 1)) < .2, 'hip_camera_stays_stable')
            action('button 2 1')  # SDL West: ADS.
            time.sleep(.12)
            ads_start = snapshot('ads_start')
            time.sleep(.65)
            ads_end = snapshot('ads_end')
            first_error = math.hypot(ads_start['stats'][1], ads_start['stats'][2])
            last_error = math.hypot(ads_end['stats'][1], ads_end['stats'][2])
            check(ads_end['buttons'] & 12 == 12, 'real_controller_ads_held')
            check(last_error < first_error*.55, 'ads_camera_converges_on_target')
            check(max(abs(ads_end['angles'][i]-hip['angles'][i]) for i in (0, 1)) > 1, 'ads_changes_actual_camera_angles')
            check(ads_end['stats'][3] == ads_end['stats'][4] == 0, 'ads_has_no_duplicate_hip_correction')
            action('button 2 0')
            action('key F8')
            time.sleep(.45)
            keyboard = snapshot('keyboard_disabled')
            check(not keyboard['buttons'] & 8 and keyboard['stats'][0] == 0, 'keyboard_switch_disables_assistance')
            rcon('screenshot png')
            time.sleep(.3)
            rcon('quit')
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                rcon('quit')
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
    report = dict(returncode=process.returncode, snapshots=snapshots, errors=errors,
                  scope='Real virtual SDL2 events, actual command/server feedback and camera; isolated original asset package.')
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Report: '+str(output/'report.json'))
    if errors or process.returncode: raise SystemExit(1)


if __name__ == '__main__':
    main()
