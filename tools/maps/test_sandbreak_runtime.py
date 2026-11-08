#!/usr/bin/env python3
"""Exercise vehicle deaths and exit progression in the real isolated game.

Uses god mode and teleports for setup, then lets the tank engage before firing
the quad sniper. The helicopter is killed by telefrag (real T_Damage/death
logic), and every gate is tested by ordinary forward movement with noclip off.
This is progression validation, not a combat balance or multiplayer playthrough.
"""
from __future__ import annotations
import argparse
import csv
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
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label',required=True)
    p.add_argument('--game',type=Path,default=ROOT/'release/baseq2/game.so')
    p.add_argument('--map',type=Path,default=ROOT/'baseq2/maps/pp_sandbreak.bsp')
    p.add_argument('--egl-device',type=int,default=1,help='SDL offscreen EGL device; 1 is the development host software device')
    p.add_argument('--expect-delay-bug',action='store_true',help='baseline expects tank gate to remain closed briefly after death')
    p.add_argument('--keep-runtime',action='store_true')
    a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.label): p.error('label must be a simple name')
    if a.egl_device<0:p.error('EGL device must be nonnegative')
    out=ROOT/'build/sandbreak-qa'/a.label;out.mkdir(parents=True,exist_ok=False)
    runtime=Path(tempfile.mkdtemp(prefix='pp-sandbreak-progression-'))
    base=runtime/'baseq2';(base/'maps').mkdir(parents=True)
    for n in ('quake2','ref_gl3.so'):shutil.copy2(ROOT/'release'/n,runtime/n)
    shutil.copy2(a.game,base/'game.so')
    shutil.copy2(a.map,base/'maps/pp_sandbreak.bsp')
    shutil.copy2(ROOT/'baseq2/maps/pp_sandbreak_end.bsp',base/'maps/pp_sandbreak_end.bsp')
    for name in ('plastic-platoon.pk3',):
        (base/name).symlink_to(ROOT/'baseq2'/name)
    for directory in ('textures','env','tuning'):
        shutil.copytree(ROOT/'baseq2'/directory,base/directory)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    token=secrets.token_hex(16)
    settings=dict(name='Player',vid_renderer='gl3',vid_fullscreen=0,r_mode=-1,r_customwidth=960,r_customheight=540,
                  r_farsee=1,r_vsync=0,vid_maxfps=60,cl_maxfps=60,s_initsound=0,
                  cheats=1,coop=1,deathmatch=0,singleplayer=0,maxclients=2,skill=1,
                  logfile=2,rcon_password=token,con_notifytime=0,cl_gun=1)
    cfg='\n'.join(f'set {k} "{v}"' for k,v in settings.items())+'\nmap pp_sandbreak\n'
    (base/'qa.cfg').write_text(cfg)
    (out/'settings.cfg').write_text(cfg.replace(token,'LOCAL_RCON_TOKEN'))
    cmd=[str(runtime/'quake2'),'-portable','-datadir',str(runtime),'+set','ip','127.0.0.1',
         '+set','port',str(port),'+set','vid_renderer','gl3','+set','vid_fullscreen','0',
         '+set','s_initsound','0','+exec','qa.cfg']
    env={**os.environ,'SDL_VIDEODRIVER':'offscreen','SDL_HINT_EGL_DEVICE':str(a.egl_device),
         'LIBGL_ALWAYS_SOFTWARE':'1','LP_NUM_THREADS':'2','XDG_CACHE_HOME':str(runtime/'cache')}
    report=dict(passed=False,expected_delay_bug=a.expect_delay_bug,map_sha256=sha(a.map),
                game_sha256=sha(a.game),egl_device=a.egl_device,runtime=str(runtime),checks=[],actions=[],screenshots=[])
    proc=None;control=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);control.settimeout(.4)
    started=time.monotonic()
    def run(command,wait=.15):
        control.sendto(b'\xff\xff\xff\xffrcon '+token.encode()+b' '+command.encode()+b'\n',('127.0.0.1',port))
        try:reply=control.recvfrom(65535)[0].decode(errors='replace')
        except socket.timeout:reply='No acknowledgement'
        report['actions'].append(dict(command=command,seconds=round(time.monotonic()-started,2),reply=reply))
        time.sleep(wait)
        return reply
    def console():
        q=base/'qconsole.log';return q.read_text(errors='replace') if q.exists() else ''
    def until(test,seconds,reason):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if proc.poll() is not None:raise RuntimeError(f'Engine exited {proc.returncode}: {reason}')
            v=test()
            if v:return v
            time.sleep(.1)
        raise RuntimeError(reason)
    def check(name,condition,**evidence):
        report['checks'].append(dict(name=name,passed=bool(condition),**evidence))
        print(name, 'PASS' if condition else 'FAIL',evidence,flush=True)
        if not condition:raise RuntimeError(name)
    def pose(x,y,z,pitch=0,yaw=90):
        run(f'cl_bench_pose 0 {x} {y} {z} {pitch} {yaw}',.5)
    def measure(name):
        run('cl_perf_start '+name,.25);run('cl_perf_stop',.3)
        rows=list(csv.DictReader((base/'perf'/f'{name}-views.csv').open()))
        r={k:float(rows[-1][k]) for k in ('x','y','z','pitch','yaw')}
        before=set((base/'scrnshot').glob('*.png'));run('screenshot png',.25)
        shot=until(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),5,'Missing screenshot')
        until(lambda:shot.read_bytes().endswith(b'IEND\xaeB`\x82'),5,'Incomplete screenshot')
        shutil.copy2(shot,out/f'{name}.png');report['screenshots'].append(str(out/f'{name}.png'))
        return r
    def gate_probe(name,y,walk_seconds=1.2):
        pose(100,y,24);run('+forward',walk_seconds);run('-forward',.2)
        return measure(name)
    try:
        with (out/'console.log').open('w') as log:
            proc=subprocess.Popen(cmd,cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            until(lambda:any('Player' in x and 'CNCT' not in x and 'ZMBI' not in x for x in run('status',0).splitlines()),50,'Local player did not spawn')
            run('god');run('give all');run('notarget')
            before=gate_probe('tank_gate_before',800)
            check('Tank gate starts closed',900<before['y']<950,eye=before)
            # Remain visible and stationary long enough for combat attack state
            # to set the old absolute aiming deadline in edict.delay.
            pose(0,-384,24);run('notarget',20)
            measure('tank_engaged')
            run('give Quad Damage');run('use Quad Damage');run('use Sniper Rifle',1)
            run('+attack',7);run('-attack',.2)
            measure('tank_after_fire')
            after=gate_probe('tank_gate_after_death',800)
            if a.expect_delay_bug:
                check('Reproduced delayed tank gate',900<after['y']<950,eye=after)
                # Observe eventual opening to distinguish the reported delay
                # from missing weapon damage or a disconnected target graph.
                until(lambda:'TANK DESTROYED' in console(),70,'Old delayed target never fired')
                time.sleep(3)
                later=gate_probe('tank_gate_eventually',800)
                check('Old tank target eventually opens gate',later['y']>1000,eye=later)
            else:
                check('Tank death promptly opens gate',after['y']>1000,eye=after)
            # The helicopter has not acquired this player across the closed
            # castle wall. Telefrag gives deterministic lethal T_Damage without
            # calling a door/relay use function or bypassing the death handler.
            run('notarget')
            before=gate_probe('helicopter_gate_before',2560)
            check('Helicopter gate starts closed',2650<before['y']<2710,eye=before)
            pose(0,2144,374)
            run('teleport 0 2144 374',2)
            pose(100,2560,24)
            # Stop before the extraction trigger at y=2848 so the gate can be
            # measured before intermission closes world-view capture.
            after=gate_probe('helicopter_gate_after_death',2560,.7)
            check('Helicopter death opens extraction gate',after['y']>2752,eye=after)
            pose(0,2780,24);run('+forward',1.2);run('-forward',.2)
            until(lambda:'OPERATION SANDBREAK COMPLETE' in console(),6,'Extraction goal was not awarded')
            time.sleep(6);run('+attack',.3);run('-attack',.2)
            until(lambda:'pp_sandbreak_end' in run('status',.1),20,'Debrief map did not load')
            check('Extraction advances to debrief',True)
            measure('debrief')
            report['passed']=True
            run('quit',.1);proc.wait(timeout=10)
    except Exception as e:
        report['error']=str(e)
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        control.close()
        if (base/'qconsole.log').exists():
            (out/'qconsole.log').write_text(console().replace(token,'LOCAL_RCON_TOKEN'))
        console_path=out/'console.log'
        if console_path.exists():
            console_path.write_text(console_path.read_text(errors='replace').replace(token,'LOCAL_RCON_TOKEN'))
        if (base/'perf').exists():shutil.copytree(base/'perf',out/'poses')
        report['seconds']=round(time.monotonic()-started,2)
        (out/'run.json').write_text(json.dumps(report,indent=2)+'\n')
        if not a.keep_runtime:shutil.rmtree(runtime)
    print(json.dumps({k:report[k] for k in ('passed','checks')},indent=2))
    if report.get('error'):print(report['error'])
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
