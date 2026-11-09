#!/usr/bin/env python3
"""Isolated, real-engine third-person muzzle alignment review captures.

Uses the player's native firing path and the existing side-view tuning camera.
Only the isolated copy's client archive third-person flash duration is extended to
1500 ms, making individual projectile-weapon shots reviewable in a screenshot.
This is visual QA, not a combat or performance benchmark.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WEAPONS = {
    'pistol': 'Pistol', 'rifle': 'Rifle', 'heavy': 'Heavy Machinegun',
    'shotgun': 'Shotgun', 'double': 'Double Barrel Shotgun',
    'grenade': 'Grenade Launcher', 'rocket': 'Rocket Launcher',
    'flame': 'M1 Flamethrower', 'sniper': 'Sniper Rifle', 'mortar': 'Mortar Cannon',
}
POSES = {'level': (0, False), 'down': (60, False),
         'up': (-60, False), 'crouch': (0, True)}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def wait_for(check, process, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        if process.poll() is not None:
            raise RuntimeError('engine exited before ' + message)
        time.sleep(.03)
    raise RuntimeError(message)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True)
    p.add_argument('--source', type=Path, default=ROOT / 'release')
    p.add_argument('--assets', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--weapons', nargs='+', choices=WEAPONS, default=list(WEAPONS))
    p.add_argument('--poses', nargs='+', choices=POSES, default=list(POSES))
    p.add_argument('--backend', choices=['wayland', 'offscreen', 'x11'], default='wayland')
    p.add_argument('--renderer', choices=['gl1', 'gl3'], default='gl1')
    p.add_argument('--split', action='store_true', help='First-person shooter plus a real second local observer')
    args = p.parse_args()
    if not args.label.replace('-', '').replace('_', '').isalnum():
        p.error('plain label required')
    out = ROOT / 'build/muzzle-qa' / args.label
    if out.exists():
        p.error('use a fresh label')
    base = out / 'runtime/baseq2'
    base.mkdir(parents=True)
    runtime = base.parent
    shots = out / 'screenshots'; shots.mkdir()
    # Portable mode writes beside its executable, even with a separate datadir.
    # Always COPY both executable and renderer into this isolated runtime.
    for name in ('quake2', 'ref_gl1.so', 'ref_gl3.so'):
        shutil.copy2(args.source / name, runtime / name)
    shutil.copy2(args.source / 'baseq2/game.so', base / 'game.so')
    for path in args.assets.glob('*.pk3'):
        shutil.copy2(path, base / path.name)
    shutil.copytree(args.assets / 'tuning', base / 'tuning')
    # Only the client sprite duration changes, in a private archive; balancing
    # and first-person settings stay byte-for-byte semantically unchanged.
    tuning = json.loads((args.assets / 'tuning/default.json').read_text())
    for weapon in tuning['weapon_overrides'].values():
        for section in ('muzzle_flash_thirdperson', 'muzzle_flash2_thirdperson'):
            if section in weapon: weapon[section]['duration_ms'] = 1500
    original_project_sha256 = digest(base / 'plastic-platoon.pk3')
    modified = base / 'qa-project.tmp'
    # Named package ordering is filesystem-dependent in this engine. Replace
    # only the client tuning entry inside the copied archive, rather than
    # relying on a lexically-later overlay to win precedence.
    with zipfile.ZipFile(base / 'plastic-platoon.pk3') as old, zipfile.ZipFile(modified, 'w') as package:
        package.comment = old.comment
        for info in old.infolist():
            data = json.dumps(tuning).encode() if info.filename == 'tuning/default.json' else old.read(info)
            package.writestr(info, data)
    modified.replace(base / 'plastic-platoon.pk3')
    token = secrets.token_hex(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    settings = dict(name='MuzzleQA', skin='soldier/green', vid_renderer=args.renderer,
        vid_fullscreen=0, r_mode=-1, r_customwidth=1280, r_customheight=720,
        r_vsync=0, vid_maxfps=60, cl_maxfps=60, cl_async=1, s_initsound=0,
        cheats=1, skill=1, maxclients=2, coop=1, singleplayer=0, deathmatch=0,
        cl_mflash_tune_mode=0 if args.split else 1, cl_mflash_tune_cam_back=0,
        cl_mflash_tune_cam_right=90, cl_mflash_tune_cam_up=0,
        cl_mflash_tune_target_up=12, cl_mflash_tune_lookat=1,
        cl_mflash_tune_show_viewmodel=0, crosshair=0, cl_blend=0, cl_kickangles=0,
        r_hudscale=0, con_notifytime=0, r_fullbright=0, r_novis=0, r_cull=1,
        r_msaa_samples=0, r_anisotropic=0, in_grab=0, logfile=2,
        rcon_password=token)
    cfg = '\n'.join(f'set {k} "{v}"' for k,v in settings.items()) + ('\ncl_bench_local 2 pp_sandstorm\n' if args.split else '\nmap pp_sandstorm\n')
    (base / 'muzzle-qa.cfg').write_text(cfg)
    (out / 'settings.cfg').write_text(cfg.replace(token, 'LOCAL_RCON_TOKEN'))
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
        '+set','ip','127.0.0.1','+set','port',str(port)]
    for key in ('vid_renderer','vid_fullscreen','r_mode','r_customwidth','r_customheight','s_initsound'):
        command += ['+set',key,str(settings[key])]
    command += ['+exec','muzzle-qa.cfg']
    env = {**os.environ, 'SDL_VIDEODRIVER': args.backend,
           'XDG_CACHE_HOME': str(runtime/'cache')}
    if args.backend == 'offscreen':
        env.update(LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='2')
    manifest = dict(binary_sha256=digest(runtime/'quake2'),
        renderer_sha256=digest(runtime/('ref_'+args.renderer+'.so')),
        original_project_pk3_sha256=original_project_sha256,
        project_pk3_sha256=digest(base/'plastic-platoon.pk3'), backend=args.backend,
        duration_override_ms=1500, split=args.split, map='pp_sandstorm', views=[])
    process = None
    def rcon(command):
        # A new socket prevents delayed reply fragments from a previous command
        # from being mistaken for an acknowledgement of the next one.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(.25)
            s.sendto(b'\xff'*4+b'rcon '+token.encode()+b' '+command.encode()+b'\n', ('127.0.0.1',port))
            replies=[]
            while True:
                try: replies.append(s.recv(65535).decode(errors='replace')); s.settimeout(.025)
                except socket.timeout: break
            return '\n'.join(replies)
    try:
        with (out/'console.log').open('w') as log:
            process = subprocess.Popen(command,cwd=runtime,stdout=log,stderr=subprocess.STDOUT,
                env=env,start_new_session=True)
            wait_for(lambda: any('[loopback-client1]' in l and 'CNCT' not in l and 'ZMBI' not in l
                for l in rcon('status').splitlines()), process,45,'local player spawn')
            for c in ('notarget','give weapons','give ammo','give health 10000'):
                rcon(c)
            rcon('cl_bench_pose 0 -38.4 -1670.4 24 0 90')
            if args.split:rcon('cl_bench_pose 1 60 -1660 24 4 180')
            time.sleep(1)
            for key in args.weapons:
                rcon('-attack');rcon('-movedown');rcon('use '+WEAPONS[key]);time.sleep(1)
                duration_reply='1500 ms in isolated QA archive'
                for pose in args.poses:
                    pitch,crouch=POSES[pose]
                    rcon('-attack');rcon('-movedown')
                    rcon(f'cl_bench_pose 0 -38.4 -1670.4 24 {pitch} 90')
                    if crouch:rcon('+movedown')
                    time.sleep(.5)
                    rcon('+attack')
                    time.sleep(1.5 if key=='mortar' else .8 if key in ('pistol','sniper') else .12)
                    before=set((base/'scrnshot').glob('*.png'))
                    rcon('screenshot png')
                    shot=wait_for(lambda: next(iter(set((base/'scrnshot').glob('*.png'))-before),None),process,8,'screenshot')
                    wait_for(lambda:shot.read_bytes().endswith(b'IEND\xaeB`\x82'),process,5,'complete PNG')
                    name=f'{key}-{pose}.png';shutil.copy2(shot,shots/name)
                    rcon('-attack')
                    manifest['views'].append(dict(weapon=key,item=WEAPONS[key],pose=pose,
                        pitch=pitch,crouch=crouch,screenshot=name,sha256=digest(shots/name),
                        duration_reply=duration_reply))
                    print(name,flush=True)
                    time.sleep(.2)
            rcon('-movedown');rcon('quit');process.wait(timeout=10)
            if process.returncode:raise RuntimeError(f'engine exited {process.returncode}')
        manifest['complete']=True
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
