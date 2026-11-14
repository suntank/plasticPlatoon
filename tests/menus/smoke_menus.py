#!/usr/bin/env python3
"""Render every registered menu using the actual SDL2 client in an isolated run.

Requires an unstripped client build, GL1/GLES1 renderer, SDL2 development headers
and a C compiler. It navigates through real menu key handlers and retains PNGs,
selected-row state, the complete action script, console log and report.json.
Nothing is written to the developer's game settings or saves.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MENU_SYMBOLS = {
    'main': 's_main', 'game': 's_game_menu', 'loadgame': 's_loadgame_menu',
    'savegame': 's_savegame_menu', 'joinserver': 's_joinserver_menu',
    'addressbook': 's_addressbook_menu', 'startserver': 's_startserver_menu',
    'dmoptions': 's_dmoptions_menu', 'playerconfig': 's_player_config_menu',
    'downloadoptions': 's_downloadoptions_menu', 'credits': 's_credits',
    'mods': 's_mods_menu', 'multiplayer': 's_multiplayer_menu',
    'multiplayer_keys': 's_multiplayer_keys_menu', 'video': 's_opengl_menu',
    'options': 's_options_menu', 'keys': 's_keys_menu', 'joy': 's_joy_menu',
    'gyro': 's_gyro_menu', 'buttons': 's_controller_buttons_menu',
    'altbuttons': 's_controller_alt_buttons_menu', 'sticks': 's_sticks_config_menu',
    'quit': 's_quit_menu',
}
SCROLL_MENUS = {'options', 'video', 'keys', 'joy', 'gyro', 'buttons', 'altbuttons',
                'sticks', 'dmoptions', 'addressbook', 'savegame', 'loadgame',
                'playerconfig', 'startserver', 'downloadoptions', 'game',
                'multiplayer', 'multiplayer_keys', 'joinserver'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--size', default='240x240')
    parser.add_argument('--renderer', choices=('gl1', 'gles1'), default='gl1')
    parser.add_argument('--client', type=Path, default=ROOT/'release/quake2')
    args = parser.parse_args()
    width, height = map(int, args.size.split('x'))
    output = (args.output or Path(tempfile.mkdtemp(prefix='pp-menu-smoke-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = output/'runtime'
    if runtime.exists():
        raise SystemExit('Output runtime already exists; choose a new output folder.')
    base = runtime/'baseq2'
    base.mkdir(parents=True)
    client = args.client.resolve()
    build = client.parent
    # Copy executable/modules so a concurrent rebuild cannot alter this run.
    for source, dest in [(client, runtime/'quake2'),
                         (build/f'ref_{args.renderer}.so', runtime/f'ref_{args.renderer}.so'),
                         (build/'baseq2/game.so', base/'game.so')]:
        shutil.copy2(source, dest)
    for source in (ROOT/'baseq2').glob('*.pk3'):
        (base/source.name).symlink_to(source)
    (base/'maps.lst').write_text('pp_sandbox_coop1 "Sandbox co-op"\n')
    (base/'autoexec.cfg').write_text('set allow_download 0\n')
    symbols = {name: value for value, _, name in re.findall(
        r'^([0-9a-fA-F]+) ([a-zA-Z]) (\S+)$',
        subprocess.check_output(['nm', str(runtime/'quake2')], text=True), re.M)}
    required = ['Cbuf_AddText', 'M_ForceMenuOff', 'M_Keydown', 'm_menudepth', 'm_popup_string', *MENU_SYMBOLS.values()]
    missing = [name for name in required if name not in symbols]
    if missing:
        raise SystemExit('An unstripped current client is required; missing symbols: '+', '.join(missing))
    shim = output/'menu_driver.so'
    flags = subprocess.check_output(['sdl2-config', '--cflags', '--libs'], text=True).split()
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-shared', '-fPIC', '-O2',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"',
                    str(ROOT/'tests/menus/menu_driver.c'), '-ldl', *flags, '-o', str(shim)], check=True)
    entries = re.findall(r'Cmd_AddCommand\("menu_([^\"]+)"', (ROOT/'src/client/menu/menu.c').read_text())
    if set(entries) != set(MENU_SYMBOLS):
        raise SystemExit('Menu registration changed; update MENU_SYMBOLS to cover '+str(set(entries) ^ set(MENU_SYMBOLS)))
    script, captures, expectations = [], [], {}

    def action(op, text='', delay=120):
        script.append(f'{delay} {op} {text}')

    def capture(label, menu, delay=120):
        action('state', f'{label} {symbols[MENU_SYMBOLS[menu]]}', delay=delay)
        action('cmd', 'screenshot png 0')
        captures.append(label)
        expectations[label] = menu

    # Running a tiny isolated map exercises the real pause menu and enables Save.
    action('cmd', 'set joy_advanced 1', delay=4000)
    for menu in entries:
        action('open', 'menu_'+menu, delay=250)
        capture(menu, menu, delay=1800 if menu == 'credits' else 120)
        if menu == 'joinserver':
            capture('joinserver_list', menu, delay=2200)
        if menu in SCROLL_MENUS:
            action('bottom', symbols[MENU_SYMBOLS[menu]])
            capture(menu+'_bottom', menu)
    action('open', 'menu_keys', delay=250)
    action('key', 'enter')
    capture('binding_prompt', 'keys')
    action('key', 'escape')
    action('open', 'menu_savegame', delay=250)
    # Save menu remembers its last cursor; navigate to the first reserved slot.
    action('top', symbols[MENU_SYMBOLS['savegame']])
    action('key', 'enter')
    capture('reserved_save_popup', 'savegame')
    action('quit', delay=250)
    controls = output/'actions.txt'
    controls.write_text('\n'.join(script)+'\n')
    env = {**os.environ, 'SDL_VIDEODRIVER': 'offscreen', 'SDL_AUDIODRIVER': 'dummy',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2',
           'LD_PRELOAD': str(shim), 'PP_MENU_SCRIPT': str(controls),
           'PP_MENU_ADD_OFFSET': symbols['Cbuf_AddText'],
           'PP_MENU_CLOSE_OFFSET': symbols['M_ForceMenuOff'],
           'PP_MENU_KEY_OFFSET': symbols['M_Keydown'],
           'PP_MENU_DEPTH_OFFSET': symbols['m_menudepth'],
           'PP_MENU_POPUP_OFFSET': symbols['m_popup_string']}
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'vid_renderer', args.renderer, '+set', 'vid_fullscreen', '0',
               '+set', 'r_mode', '-1', '+set', 'r_customwidth', str(width),
               '+set', 'r_customheight', str(height), '+set', 'r_menuscale', '-1',
               '+set', 's_initsound', '0', '+set', 'r_vsync', '0',
               '+set', 'allow_download', '0', '+set', 'vid_maxfps', '60',
               '+set', 'logfile', '2', '+map', 'pp_sandbox_coop1']
    with (output/'console.log').open('w') as log:
        result = subprocess.run(command, cwd=runtime, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=180)
    log = (output/'console.log').read_text(errors='replace')
    snapshots = {state['label']: state for state in
                 (json.loads(line) for line in re.findall(r'PP_MENU_STATE (.+)', log))}
    errors, images = [], []

    def check(condition, message):
        if not condition:
            errors.append(message)

    screenshots = sorted((base/'scrnshot').glob('*.png'))
    check(len(screenshots) == len(captures), f'expected {len(captures)} screenshots; found {len(screenshots)}')
    for label, source in zip(captures, screenshots):
        dest = output/(label+'.png')
        shutil.copy2(source, dest)
        with dest.open('rb') as file:
            header = file.read(24)
        check(header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', header[16:24]) == (width, height),
              f'{label}: wrong PNG size')
        images.append(str(dest))
    for label, menu in expectations.items():
        state = snapshots.get(label)
        check(state is not None, f'{label}: missing menu state')
        if state:
            check(state['depth'] > 0, f'{label}: menu did not open')
            if menu not in ('credits', 'quit'):
                check(state['items'] > 0, f'{label}: no menu items')
                check(0 <= state['top'] <= state['cursor'] < state['items'], f'{label}: invalid selected row')
            if label.endswith('_bottom'):
                check(state['cursor'] >= snapshots[menu]['cursor'], f'{label}: navigation did not reach a later row')
                if width <= 400 and state['items'] > 7:
                    check(state['top'] > 0, f'{label}: long menu failed to scroll')
    check(result.returncode == 0, f'client exited {result.returncode}')
    check('PP_MENU_ERROR' not in log, 'runtime fixture reported an error')
    check(snapshots.get('binding_prompt', {}).get('value') == 'Press a button...', 'binding prompt did not become active')
    check('reserved' in snapshots.get('reserved_save_popup', {}).get('popup', ''), 'reserved-slot popup did not open')
    report = {'returncode': result.returncode, 'size': args.size, 'renderer': args.renderer,
              'registered_menus': entries, 'states': snapshots, 'screenshots': images, 'errors': errors}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'menus': len(entries), 'screenshots': len(images), 'errors': errors}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
