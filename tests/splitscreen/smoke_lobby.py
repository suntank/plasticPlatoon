#!/usr/bin/env python3
"""Exercise the actual SDL2 client with virtual pads and retain rendered evidence.

Needs a current unstripped `make client` build, SDL2 >=2.24 and an offscreen
renderer. Everything writable lives under the requested output directory.
The preload fixture reads ss_state using the executable's own ELF symbol table;
it never changes engine state directly. All interaction uses SDL input events.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--size', default='1280x720')
    parser.add_argument('--players', type=int, choices=(2, 3, 4), default=2)
    parser.add_argument('--renderer', choices=('gl1', 'soft'), default='gl1')
    parser.add_argument('--menuscale', default='-1')
    parser.add_argument('--brief-captures', action='store_true',
                        help='capture only lobby, ready and started; still check every state')
    parser.add_argument('--launch', choices=('gamepad', 'f10'), default='gamepad')
    parser.add_argument('--from-match', action='store_true',
                        help='open multiplayer after the normal solo map launch')
    parser.add_argument('--check-back', action='store_true',
                        help='use host cancel to revisit match settings and reenter')
    args = parser.parse_args()
    width, height = map(int, args.size.split('x'))
    output = (args.output or Path(tempfile.mkdtemp(prefix='pp-lobby-smoke-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / 'runtime'
    if runtime.exists():
        raise SystemExit('Output runtime already exists; choose a new output folder.')
    base = runtime / 'baseq2'
    base.mkdir(parents=True, exist_ok=True)
    for source, dest in [(ROOT/'release/quake2', runtime/'quake2'),
                         (ROOT/f'release/ref_{args.renderer}.so', runtime/f'ref_{args.renderer}.so'),
                         (ROOT/'release/baseq2/game.so', base/'game.so'),
                         (ROOT/'baseq2/plastic-platoon.pk3', base/'plastic-platoon.pk3')]:
        shutil.copy2(source, dest)
    # Prefer a tiny known map over every user's loose maps/mission archives.
    (base/'maps.lst').write_text('pp_sandbox_coop1 "Sandbox coop"\n')
    (base/'autoexec.cfg').write_text('bind F12 "screenshot png 0"\nbind BTN_NORTH "screenshot png 0"\nbind F9 "menu_multiplayer"\n')
    symbols = subprocess.check_output(['nm', str(runtime/'quake2')], text=True)
    match = re.search(r'^([0-9a-fA-F]+) [bd] ss_state$', symbols, re.M)
    client = re.search(r'^([0-9a-fA-F]+) [bdB] cl$', symbols, re.M)
    static = re.search(r'^([0-9a-fA-F]+) [bdB] cls$', symbols, re.M)
    if not match or not client or not static:
        raise SystemExit('Client must retain its local symbol table (make client).')
    shim = output/'virtual_gamepads.so'
    sdl_flags = subprocess.check_output(['sdl2-config', '--cflags', '--libs'], text=True).split()
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-shared', '-fPIC', '-O2',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"',
                    str(ROOT/'tests/splitscreen/virtual_gamepads.c'), '-ldl', *sdl_flags,
                    '-o', str(shim)], check=True)
    script, screenshot_labels, now = [], [], 12000 if args.from_match else 1200

    def action(op, *values, delay=250):
        nonlocal now
        script.append(f'{now} {op} ' + ' '.join(map(str, values)))
        now += delay

    def key(name):
        action('keydown', name, delay=100)
        action('keyup', name)

    def button(pad, button):
        action('button', pad, button, 1, delay=100)
        action('button', pad, button, 0)

    def shot(label, gameplay=False):
        action('state', label)
        if args.brief_captures and label not in ('lobby', 'ready', 'started'):
            return
        screenshot_labels.append(label)
        if gameplay:
            button(0, 3)
        else:
            key('F12')

    if args.from_match:
        action('state', 'solo')
        key('F9')
    key('Right'); key('Right'); key('Down')
    for _ in range(args.players-2):
        key('Right')
    key('Down'); key('Return')
    # Up wraps from map selector to the last action, regardless of hidden rows.
    key('Up'); key('Return')
    shot('lobby')
    if args.from_match:
        key('Down'); key('Right')
        action('state', 'swapped')
        key('Left'); key('Up')
        action('state', 'restored')
    if args.check_back:
        button(0, 1)
        shot('back')
        button(0, 0)
        shot('reopened')
    # Each pad confirms its own slot; Start cannot launch until everyone is ready.
    button(1, 0)
    button(0, 6)
    shot('not_all_ready')
    button(0, 0)
    for pad in range(2, args.players):
        button(pad, 0)
    button(1, 6)
    shot('guest_start')
    button(1, 1)
    shot('unready')
    button(1, 0)
    action('detach', 1, delay=700)
    shot('disconnected')
    action('attach', 1, delay=700)
    shot('reconnected')
    button(1, 0)
    shot('ready')
    if args.launch == 'f10':
        key('F10')
    else:
        button(0, 6)
    now += 7000
    shot('started', gameplay=True)
    action('axis', 0, 1, -32768)
    action('axis', 1, 0, 32767, delay=700)
    shot('moving', gameplay=True)
    action('axis', 0, 1, 0)
    action('axis', 1, 0, 0)
    # Simultaneous buttons must never suppress the other controller's press.
    for pad in range(2):
        action('axis', pad, 5, 32767, delay=50)
        action('axis', pad, 4, 32767, delay=50)
        action('button', pad, 0, 1, delay=50)
    now += 500
    action('state', 'controls')
    for pad in range(2):
        action('axis', pad, 5, -32768, delay=50)
        action('axis', pad, 4, -32768, delay=50)
        action('button', pad, 0, 0, delay=50)
    action('quit', delay=0)
    input_script = output/'input.txt'
    input_script.write_text('\n'.join(script)+'\n')
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'vid_renderer', args.renderer, '+set', 'vid_fullscreen', '0',
               '+set', 'r_mode', '-1', '+set', 'r_customwidth', str(width),
               '+set', 'r_customheight', str(height), '+set', 'r_menuscale', args.menuscale,
               '+set', 's_initsound', '0', '+set', 'r_vsync', '0',
               '+set', 'allow_download', '0',
               '+set', 'vid_maxfps', '120', '+set', 'logfile', '2',
               *(['+map', 'pp_sandbox_coop1'] if args.from_match else ['+menu_multiplayer'])]
    env = {**os.environ, 'SDL_VIDEODRIVER': 'offscreen', 'SDL_AUDIODRIVER': 'dummy',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2',
           'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS': '1',
           'LD_PRELOAD': str(shim), 'PP_SMOKE_SCRIPT': str(input_script),
           'PP_SMOKE_PADS': str(args.players), 'PP_SMOKE_STATE_OFFSET': match[1],
           'PP_SMOKE_CLIENT_OFFSET': client[1], 'PP_SMOKE_STATIC_OFFSET': static[1]}
    with (output/'console.log').open('w') as log:
        result = subprocess.run(command, cwd=runtime, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=now/1000+90)
    log = (output/'console.log').read_text(errors='replace')
    snapshots = {s['label']: s for s in
                 (json.loads(line) for line in re.findall(r'PP_SMOKE_STATE (.+)', log))}
    report = {'returncode': result.returncode, 'size': args.size, 'players': args.players, 'launch': args.launch,
              'states': snapshots, 'screenshots': []}
    for name, image in zip(screenshot_labels, sorted((base/'scrnshot').glob('*.png'))):
        dest = output/(name+'.png')
        shutil.copy2(image, dest)
        report['screenshots'].append(str(dest))
    errors = []
    def check(condition, message):
        if not condition: errors.append(message)
    def state(name):
        check(name in snapshots, f'missing state: {name}')
        return snapshots.get(name, {'slots': [], 'lobby': 0, 'session': 0})
    if args.from_match:
        check(state('solo')['primary_connection'] == 4, 'solo map never became active')
        check(not state('solo')['session'], 'solo fixture already had a split session')
        check([s['device'] for s in state('swapped')['slots'][:2]] == [3, 2],
              'manual occupied-device selection did not swap controllers')
        check([s['device'] for s in state('restored')['slots'][:2]] == [2, 3],
              'manual device selection did not restore controllers')
    initial = state('lobby')
    check(initial['lobby'] == 1, 'did not reach lobby through menus')
    check([s['device'] for s in initial['slots']] == list(range(2, args.players+2)),
          'gamepads not assigned one per player')
    if args.check_back:
        check(not state('back')['lobby'] and not state('back')['session'],
              'host cancel did not return to match settings')
        check(state('reopened')['lobby'] == 1, 'host confirm did not reopen lobby')
    for label in ('not_all_ready', 'guest_start', 'unready', 'disconnected', 'reconnected', 'ready'):
        check(state(label)['lobby'] == 1 and state(label)['session'] == 0,
              f'{label}: launched prematurely or left lobby')
    check([s['ready'] for s in state('not_all_ready')['slots'][:2]] == [0, 1],
          'player 2 confirmation was not isolated')
    check(all(s['ready'] for s in state('guest_start')['slots']),
          'guest Start changed readiness')
    for label in ('unready', 'disconnected', 'reconnected'):
        slots = state(label)['slots']
        check(len(slots) > 1 and not slots[1]['ready'], f'{label}: player 2 was still ready')
    check(all(s['ready'] for s in state('ready')['slots']), 'ready state not reached by all pads')
    check(state('started')['session'] == 1, 'host Start did not launch match')
    slots = state('moving')['slots']
    check(len(slots) > 1 and slots[1]['snapshot'], 'player 2 never received gameplay snapshot')
    check(len(slots) > 1 and slots[0]['forward'] > 0 and slots[1]['side'] > 0,
          'independent sticks did not produce movement for both players')
    check(all(s['buttons'] & 1 and s['buttons'] & 4 and s['up'] > 0
              for s in state('controls')['slots'][:2]),
          'simultaneous attack/ADS/jump did not reach both players')
    check(result.returncode == 0, f'client exited {result.returncode}')
    check(len(report['screenshots']) == len(screenshot_labels), 'missing rendered screenshots')
    report['errors'] = errors
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'errors': errors}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
