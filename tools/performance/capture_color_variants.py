#!/usr/bin/env python3
"""Real renderer material review in an isolated portable runtime.

Exercises actual networked clientinfo refresh and local split-screen players.
The preload fixture only provides test controls through existing game APIs;
no production models, textures, combat rules or renderer settings are patched.
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

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WEAPONS = {
    'pistol': 'Pistol', 'rifle': 'Rifle', 'heavy': 'Heavy Machinegun',
    'shotgun': 'Shotgun', 'double': 'Double Barrel Shotgun',
    'handgrenade': 'Grenades', 'grenade': 'Grenade Launcher',
    'rocket': 'Rocket Launcher', 'flame': 'M1 Flamethrower',
    'sniper': 'Sniper Rifle', 'mortar': 'Mortar Cannon',
}
COLORS = ['green', 'blue', 'pink', 'red', 'tan', 'orange', 'purple', 'gray', 'white', 'skin']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True)
    p.add_argument('--renderer', choices=['gl1', 'gl3', 'soft'], default='gl1')
    p.add_argument('--scope', choices=['all', 'weapons', 'bodies', 'split', 'enemies'], default='all')
    p.add_argument('--fullbright', action='store_true', help='Diagnostic indexed-color review without dynamic lighting')
    args = p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        p.error('plain label required')
    if args.scope == 'all':
        for scope in ['weapons', 'bodies', 'split', 'enemies']:
            subprocess.run([os.sys.executable, str(Path(__file__).resolve()),
                '--label', args.label+'-'+scope, '--renderer', args.renderer,
                '--scope', scope]+(['--fullbright'] if args.fullbright else []), check=True)
        return
    out = ROOT / 'build/color-qa' / args.label
    if out.exists():
        p.error('use a fresh label')
    base = out / 'runtime/baseq2'
    base.mkdir(parents=True)
    runtime = base.parent
    shots = out / 'screenshots'
    shots.mkdir()
    for name in ['quake2', 'ref_'+args.renderer+'.so']:
        shutil.copy2(ROOT/'release'/name, runtime/name)
    shutil.copy2(ROOT/'release/baseq2/game.so', base/'game.so')
    for path in (ROOT/'release/baseq2').glob('*.pk3'):
        # Archives are read-only for this review. A link saves redundant copies.
        (base/path.name).symlink_to(path.resolve())
    shutil.copytree(ROOT/'baseq2/tuning', base/'tuning')
    symbols = subprocess.check_output(['nm', str(runtime/'quake2')], text=True)
    names = ['cl', 'cls', 'svs', 'ge', 'maxclients', 'Cmd_TokenizeString',
             'Info_SetValueForKey', 'SS_GetSlot', 'Cvar_Set', 'Cbuf_AddText']
    offsets = {name: re.search(r'^([0-9a-fA-F]+) [a-zA-Z] '+name+r'$', symbols, re.M)[1]
               for name in names}
    game_symbols=subprocess.check_output(['nm', str(base/'game.so')], text=True)
    game_offsets={name:re.search(r'^([0-9a-fA-F]+) [a-zA-Z] '+name+r'$',game_symbols,re.M)[1]
                  for name in ['FindItem','ChangeWeapon']}
    shim = out/'color_runtime.so'
    flags = subprocess.check_output(['pkg-config', '--cflags', 'sdl2'], text=True).split()
    subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-D_DEFAULT_SOURCE',
                    '-DYQ2ARCH="test"', '-DYQ2OSTYPE="test"', *flags,
                    str(ROOT/'tests/input/color_variants_runtime.c'),
                    str(ROOT/'tests/input/color_variants_game.c'), '-ldl', '-o', str(shim)], check=True)
    controls = out/'controls.txt'
    controls.write_text('')
    token = secrets.token_hex(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    settings = dict(vid_renderer=args.renderer, vid_fullscreen=0, r_mode=-1,
        r_customwidth=960, r_customheight=720, r_vsync=0, vid_maxfps=60,
        cl_maxfps=60, s_initsound=0, cheats=1, skill=0, cl_bob=0,
        cl_mflash_tune_mode=0, cl_mflash_tune_cam_back=0,
        cl_mflash_tune_cam_right=80, cl_mflash_tune_cam_up=0,
        cl_mflash_tune_target_up=12, cl_mflash_tune_lookat=1,
        cl_mflash_tune_show_viewmodel=0, crosshair=1, cl_blend=0,
        cl_kickangles=0, r_hudscale=1, con_notifytime=0, r_fullbright=int(args.fullbright),
        r_msaa_samples=0, r_anisotropic=0, in_grab=0, logfile=2,
        cl_aimassist=0, rcon_password=token, skin='soldier/green')
    players = 4 if args.scope == 'split' else 1
    # A listening coop server keeps local UDP RCON available for single-view QA.
    # True single-player (maxclients1) intentionally closes that socket.
    startup = ('cl_bench_local 4 pp_ant_test' if players == 4 else
               'set maxclients 2\nset coop 1\nset singleplayer 0\nset deathmatch 0\nmap pp_ant_test')
    cfg = '\n'.join(f'set {k} "{v}"' for k,v in settings.items())+'\n'+startup+'\n'
    (base/'colors-qa.cfg').write_text(cfg)
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
        '+set', 'ip', '127.0.0.1', '+set', 'port', str(port)]
    for key in ['vid_renderer','vid_fullscreen','r_mode','r_customwidth','r_customheight','s_initsound']:
        command += ['+set', key, str(settings[key])]
    command += ['+exec', 'colors-qa.cfg']
    env = {**os.environ, 'SDL_VIDEODRIVER':'offscreen', 'SDL_AUDIODRIVER':'dummy',
           'LIBGL_ALWAYS_SOFTWARE':'1', 'LP_NUM_THREADS':'2', 'LD_PRELOAD':str(shim),
           'XDG_CACHE_HOME':str(runtime/'cache'), 'PP_COLOR_CONTROLS':str(controls),
           **{'PP_COLOR_'+k:v for k,v in offsets.items()},
           **{'PP_COLOR_GAME_'+k:v for k,v in game_offsets.items()}}
    manifest = dict(renderer=args.renderer, scope=args.scope, fullbright=args.fullbright,
        executable_sha256=sha(runtime/'quake2'), game_sha256=sha(base/'game.so'),
        renderer_sha256=sha(runtime/('ref_'+args.renderer+'.so')),
        project_sha256=sha(base/'plastic-platoon.pk3'), views=[], states={})
    log_path = out/'console.log'
    process = None

    def wait(check, message, timeout=15):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            if process.poll() is not None:
                raise RuntimeError('engine exited before '+message)
            time.sleep(.04)
        raise RuntimeError('timed out: '+message)

    def rcon(cmd):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(.25)
            s.sendto(b'\xff'*4+b'rcon '+token.encode()+b' '+cmd.encode()+b'\n', ('127.0.0.1', port))
            replies=[]
            while True:
                try:
                    replies.append(s.recv(65535).decode(errors='replace'))
                    s.settimeout(.02)
                except socket.timeout:
                    return '\n'.join(replies)

    def action(cmd):
        with controls.open('a') as f:
            f.write(cmd+'\n')

    def state(label, enemies=False):
        action(('enemy_state ' if enemies else 'state ')+label)
        prefix = 'PP_COLOR_ENEMIES ' if enemies else 'PP_COLOR_STATE '
        def read():
            for line in log_path.read_text(errors='replace').splitlines():
                if prefix in line:
                    try:
                        item = json.loads(line.split(prefix,1)[1])
                    except json.JSONDecodeError:
                        # The engine is still appending the current record.
                        continue
                    if item['label'] == label:
                        return item
        item = wait(read, label)
        manifest['states'][label] = item
        return item

    def screenshot(name, **metadata):
        time.sleep(.35)
        before = set((base/'scrnshot').glob('*.png'))
        rcon('screenshot png')
        path = wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None), name)
        wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'), 'complete PNG')
        target = shots/(name+'.png')
        shutil.copy2(path,target)
        manifest['views'].append(dict(name=name, screenshot=target.name, sha256=sha(target), **metadata))
        print(name, flush=True)

    def pose(slot, x, y, z, pitch, yaw):
        rcon(f'cl_bench_pose {slot} {x} {y} {z} {pitch} {yaw}')

    def assert_body(player, color):
        assert player['body_image'] == f'players/soldier/colors/body_{color}.png', player
        # RF_SHELL_RED/GREEN/BLUE obscure the texture under a bright shell.
        assert not player['server_flags'] & 0x1c00, player

    try:
        with log_path.open('w') as log:
            process = subprocess.Popen(command, cwd=runtime, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            wait(lambda:'pp_ant_test' in rcon('status'), 'local server',60)
            for attempt in range(80):
                ready=state('ready-'+str(attempt))
                if ready['connection']==4 and all(c['spawned'] for c in ready['clients'][:players]):
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('not all local players spawned')
            for slot in range(players):
                for cmd in ['notarget','give weapons','give ammo']:
                    action(f'clientcmd {slot} {cmd}')
            pose(0,0,-1488,24,0,90)
            for slot in range(1,players):
                pose(slot,700+slot*80,-1488,24,0,90)
            if args.scope in ['all','weapons']:
                for i,(key,item) in enumerate(WEAPONS.items()):
                    color=COLORS[i%len(COLORS)]
                    action(f'skin 0 {color}')
                    action(('equip 0 ' if key=='handgrenade' else 'clientcmd 0 use ')+item)
                    time.sleep(.7)
                    rcon('set cl_mflash_tune_mode 0')
                    screenshot(key+'-fp-'+color,weapon=key,view='fp',color=color)
                    rcon('set cl_mflash_tune_mode 1')
                    screenshot(key+'-tp-'+color,weapon=key,view='tp',color=color)
                    rcon('set cl_mflash_tune_mode 0')
                    rcon('+ads')
                    screenshot(key+'-ads-'+color,weapon=key,view='ads',color=color)
                    rcon('-ads')
                    current=state('weapon-'+key)['clients'][0]
                    assert current['weaponcolor']==color,current
                    if key=='handgrenade':assert '/v_handgr/' in current['gunmodel'],current
                # Exercise late skin changes and the green unsupported fallback.
                for color in COLORS+['unsupported']:
                    action(f'skin 0 {color}')
                    action('clientcmd 0 use Rifle')
                    time.sleep(.35)
                    rcon('set cl_mflash_tune_mode 1')
                    screenshot('palette-'+color,color=color,view='palette')
                    state('palette-'+color)
                rcon('set cl_mflash_tune_mode 0')
            if args.scope in ['all','bodies']:
                rcon('set cl_mflash_tune_mode 1')
                for color in COLORS:
                    action(f'skin 0 {color}')
                    for key in ['rifle','pistol']:
                        action(f'clientcmd 0 use {WEAPONS[key]}')
                        time.sleep(.5)
                        name = f'body-{key}-{color}'
                        screenshot(name, weapon=key, view='bodies', color=color)
                        current = state(name)['clients'][0]
                        assert current['weaponcolor'] == color, current
                        assert_body(current, color)
                # An unavailable selected skin resolves to the complete green
                # player, including the generated body and linked weapon.
                action('skin 0 unsupported')
                time.sleep(.5)
                fallback = state('body-unsupported-fallback')['clients'][0]
                assert fallback['weaponcolor'] == 'green', fallback
                assert_body(fallback, 'green')
                rcon('set cl_mflash_tune_mode 0')
            if args.scope in ['all','split']:
                for slot,color in enumerate(['green','blue','pink','white']):
                    action(f'skin {slot} {color}')
                    pose(slot,(slot%2)*80,-1488+(slot//2)*100,24,0,90 if slot<2 else 270)
                for key,item in WEAPONS.items():
                    for slot in range(4):
                        action((f'equip {slot} ' if key=='handgrenade' else f'clientcmd {slot} use ')+item)
                    time.sleep(.7)
                    screenshot('split-'+key,view='split',weapon=key,colors=['green','blue','pink','white'])
                    current=state('split-'+key)
                    assert [c['weaponcolor'] for c in current['clients']]==['green','blue','pink','white'], current
                    assert len({c['gunmodel'] for c in current['clients']})==1, current
                    for player, color in zip(current['clients'], ['green','blue','pink','white']):
                        assert_body(player, color)
                action('skin 1 purple')
                time.sleep(.5)
                screenshot('split-skin-refresh',view='split-refresh')
                current=state('split-refresh')
                assert [c['weaponcolor'] for c in current['clients']]==['green','purple','pink','white'], current
                for player, color in zip(current['clients'], ['green','purple','pink','white']):
                    assert_body(player, color)
                for slot in range(4):action(f'ads {slot} 1')
                screenshot('split-ads',view='split-ads')
                for slot in range(4):action(f'ads {slot} 0')
            if args.scope in ['all','enemies']:
                for classname in ['monster_soldier_light','monster_soldier',
                    'monster_soldier_ss','monster_soldier_heavy','monster_soldier_rocket',
                    'monster_tank','monster_plastic_helicopter','monster_boss2',
                    'monster_ant','monster_spider']:
                    rcon('map pp_ant_test')
                    wait(lambda:'pp_ant_test' in rcon('status'), 'map reload')
                    time.sleep(1)
                    action('clientcmd 0 notarget')
                    action('clientcmd 0 god')
                    rcon('set cl_gun 0')
                    small=any(s in classname for s in ['soldier','ant','spider'])
                    pitch=8 if classname in ['monster_ant','monster_spider'] else 0
                    pose(0,600,-1400,24,pitch,90)
                    y=-1280 if small else -1140
                    rcon(f'spawnentity {classname} 600 {y} 24 0 270 0 1')
                    time.sleep(2)
                    screenshot(classname,view='enemy',classname=classname)
                    state(classname,enemies=True)
                    if classname in ['monster_soldier_heavy','monster_ant','monster_spider']:
                        action('gib '+classname)
                        screenshot(classname+'-gibs',view='enemy-gibs',classname=classname)
                        state(classname+'-gibs',enemies=True)
            manifest['image_list']=rcon('imagelist')
            rcon('quit')
            process.wait(timeout=10)
            if process.returncode:
                raise RuntimeError(f'engine exited {process.returncode}')
            manifest['complete']=True
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for view in ['fp','tp','ads','palette','bodies','split','enemy']:
            entries=[e for e in manifest['views'] if e['view']==view]
            if not entries:continue
            sheet=Image.new('RGB',(4*320,((len(entries)+3)//4)*265),(32,32,35))
            draw=ImageDraw.Draw(sheet)
            for n,e in enumerate(entries):
                with Image.open(shots/e['screenshot']) as im:
                    im.thumbnail((320,240))
                    x,y=(n%4)*320,(n//4)*265
                    sheet.paste(im,(x,y))
                draw.text((x+3,y+242),e['name'],fill='white')
            sheet.save(out/(view+'-review.png'))
    print(out/'manifest.json')


if __name__=='__main__':
    main()
