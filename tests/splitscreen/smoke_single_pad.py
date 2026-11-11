#!/usr/bin/env python3
"""Real SDL one-controller escape regression using the Game Bird bindings."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--client', type=Path, default=ROOT/'release/quake2')
    args = parser.parse_args()
    output = args.output.resolve()
    runtime = output/'runtime'
    base = runtime/'baseq2'
    base.mkdir(parents=True)
    for source, target in ((args.client, runtime/'quake2'),
                           (ROOT/'release/ref_gl1.so', runtime/'ref_gl1.so'),
                           (ROOT/'release/baseq2/game.so', base/'game.so'),
                           (ROOT/'release/baseq2/plastic-platoon.pk3', base/'plastic-platoon.pk3'),
                           (ROOT/'packaging/gamebird/gamebird.cfg', base/'gamebird-test.cfg')):
        shutil.copy2(source, target)
    (base/'maps.lst').write_text('pp_ant_test "Ant test"\n')
    (base/'autoexec.cfg').write_text('bind F12 "screenshot png 0"\n')
    symbols = subprocess.check_output(['nm', str(runtime/'quake2')], text=True)
    offsets = {name: re.search(r'^([0-9a-fA-F]+) [bdB] '+name+'$', symbols, re.M)[1]
               for name in ('ss_state', 'cl', 'cls', 'm_menudepth')}
    shim = output/'virtual_gamepads.so'
    flags = subprocess.check_output(['sdl2-config', '--cflags', '--libs'], text=True).split()
    subprocess.run(['cc', '-std=c11', '-shared', '-fPIC', '-O2', '-DYQ2ARCH="test"',
                    '-DYQ2OSTYPE="test"', str(ROOT/'tests/splitscreen/virtual_gamepads.c'),
                    '-ldl', *flags, '-o', str(shim)], check=True)
    script, labels, now = [], [], 1800

    def action(op, *values, delay=180):
        nonlocal now
        script.append(f'{now} {op} '+ ' '.join(map(str, values)))
        now += delay

    def button(number, pad=0):
        action('button', pad, number, 1, delay=90)
        action('button', pad, number, 0)

    def snapshot(label):
        labels.append(label)
        action('state', label)
        action('keydown', 'F12', delay=90)
        action('keyup', 'F12')

    # Navigate exclusively with the physical pad into a two-player lobby.
    button(12); button(0)  # Main -> Multiplayer.
    button(14); button(14); button(12); button(12); button(0)
    button(11); button(0)  # Match settings -> lobby.
    snapshot('one-pad-lobby')
    button(0); snapshot('guest-ready')
    button(1); snapshot('guest-unready')
    button(1); snapshot('cancel-back')
    button(0); snapshot('reopened-select')
    button(4); snapshot('select-back')
    button(0); button(6); snapshot('start-blocked')
    button(1); button(1); button(1); snapshot('main-menu')
    # Reenter, then cancel from a newly attached, unassigned pad as well.
    # Normal menus retain their selected actions when revisited.
    button(0); button(0); button(0)
    snapshot('reopened-unassigned')
    # SDL debounces hotplug for 30 input updates; allow the 30-FPS Pi preset
    # to finish registration before pressing the new controller's button.
    action('attach', 1, delay=2000)
    snapshot('unassigned-connected')
    button(1, pad=1); snapshot('unassigned-back')
    action('quit', delay=0)
    inputs = output/'input.txt'
    inputs.write_text('\n'.join(script)+'\n')
    env = {**os.environ, 'SDL_VIDEODRIVER':'offscreen', 'SDL_AUDIODRIVER':'dummy',
           'LIBGL_ALWAYS_SOFTWARE':'1', 'LP_NUM_THREADS':'2',
           'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS':'1', 'LD_PRELOAD':str(shim),
           'PP_SMOKE_SCRIPT':str(inputs), 'PP_SMOKE_PADS':'1',
           'PP_SMOKE_STATE_OFFSET':offsets['ss_state'], 'PP_SMOKE_CLIENT_OFFSET':offsets['cl'],
           'PP_SMOKE_STATIC_OFFSET':offsets['cls'], 'PP_SMOKE_MENU_OFFSET':offsets['m_menudepth']}
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
               '+set','vid_renderer','gl1','+set','vid_fullscreen','0',
               '+set','r_mode','-1','+set','r_customwidth','240','+set','r_customheight','240',
               '+set','con_notifytime','0',
               '+set','s_initsound','0','+set','logfile','2',
               '+exec','gamebird-test.cfg','+menu_main']
    with (output/'console.log').open('w') as log:
        result = subprocess.run(command, cwd=runtime, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=now/1000+60)
    log = (output/'console.log').read_text(errors='replace')
    states = {s['label']:s for s in (json.loads(line) for line in re.findall(r'PP_SMOKE_STATE (.+)', log))}
    errors = []

    def check(condition, message):
        if not condition: errors.append(message)

    for label in labels:
        check(label in states, 'missing '+label)
    if all(label in states for label in labels):
        check([s['device'] for s in states['one-pad-lobby']['slots']] == [1,2], 'one pad not assigned as guest')
        check(states['one-pad-lobby']['connected_pads'] == 1, 'initial lobby does not have exactly one controller')
        check(states['guest-ready']['lobby'] and states['guest-ready']['slots'][1]['ready'], 'guest ready failed')
        check(states['guest-unready']['lobby'] and not states['guest-unready']['slots'][1]['ready'], 'first cancel must only unready')
        for label in ('cancel-back','select-back','unassigned-back'):
            check(not states[label]['lobby'] and states[label]['menu_depth'] == 3, label+' did not return to match settings')
        check(states['reopened-select']['lobby'], 'could not reopen after cancel')
        check(states['start-blocked']['lobby'] and not states['start-blocked']['session'], 'guest Start launched without host/all ready')
        check(states['main-menu']['menu_depth'] == 1 and not states['main-menu']['lobby'], 'pad could not return to main menu')
        check(states['reopened-unassigned']['lobby'], 'could not reenter for unassigned pad case')
        check(states['unassigned-connected']['connected_pads'] == 2, 'new unassigned controller not registered')
    images = sorted((base/'scrnshot').glob('*.png'))
    for label, image in zip(labels, images): shutil.copy2(image, output/(label+'.png'))
    check(len(images) == len(labels), 'missing screenshots')
    check(result.returncode == 0, 'engine exit '+str(result.returncode))
    report = dict(returncode=result.returncode, states=states, errors=errors)
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'output':str(output),'errors':errors}, indent=2))
    if errors: raise SystemExit(1)


if __name__ == '__main__':
    main()
