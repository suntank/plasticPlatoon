#!/usr/bin/env python3
"""Photograph the shared barrel in a native test room, then shoot it to destruction."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from capture_pickup_lod import compile_fixtures, stage_runtime
from qa_controls import FileControls, compile_controls

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'models/objects/barrels/tris.md2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--renderer',choices=('gl1','gl3','soft'),default='gl3')
    parser.add_argument('--map',type=Path)
    args = parser.parse_args()
    out = args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    maps = {'misc_explobox':args.map.resolve()} if args.map else compile_fixtures(
        out,ROOT.parent/'q2tools-220/build/q2tool',ROOT/'baseq2',{'misc_explobox':MODEL})
    runtime = stage_runtime(ROOT/'release',out,maps);base = runtime/'baseq2'
    shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    library,offsets = compile_controls(ROOT/'release',out)
    control,logpath = out/'controls.txt',out/'console.log';control.write_text('')
    shots = out/'screenshots';shots.mkdir()
    settings = dict(vid_renderer=args.renderer,vid_fullscreen=0,r_mode=-1,
        r_customwidth=1280,r_customheight=720,r_vsync=0,vid_maxfps=60,cl_maxfps=60,
        s_initsound=0,cheats=1,cl_gun=0,crosshair=0,r_hudscale=0,cl_blend=0,
        con_notifytime=0,cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,
        in_grab=0,logfile=2,cl_aimassist=0,maxclients=2,coop=1,singleplayer=0,deathmatch=0)
    (base/'barrel-review.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in settings.items())+
        'map '+maps['misc_explobox'].stem+'\n')
    env = dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',
        LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',LD_PRELOAD=str(library),
        PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    report = dict(passed=False,renderer=args.renderer,views=[],checks=[],
        inputs_sha256={n:hashlib.sha256((runtime/n).read_bytes()).hexdigest()
                       for n in ('quake2','baseq2/game.so','baseq2/plastic-platoon.pk3')})
    with logpath.open('w') as log:
        process = subprocess.Popen([str(runtime/'quake2'),'-portable','-datadir',str(runtime),
            '+set','s_initsound','0','+set','vid_renderer',args.renderer,'+exec','barrel-review.cfg'],
            cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
        c = FileControls(control,logpath,process)
        def wait(fn,label,timeout=30):
            deadline = time.monotonic()+timeout
            while time.monotonic()<deadline:
                value = fn()
                if value:return value
                if process.poll() is not None:raise RuntimeError('Engine exited: '+label)
                time.sleep(.04)
            raise RuntimeError('Timed out: '+label)
        def entities():return c.record('enemy_state','PP_COLOR_ENEMIES ')['entities']
        def barrel():return next((e for e in entities() if e['model']==MODEL),None)
        def pose(eye,target):
            delta = [b-a for a,b in zip(eye,target)]
            yaw = math.degrees(math.atan2(delta[1],delta[0]))
            pitch = -math.degrees(math.atan2(delta[2],math.hypot(*delta[:2])))
            c.console('cl_bench_pose 0 '+' '.join(map(str,(*eye[:2],eye[2]-32,pitch,yaw))))
            time.sleep(.3);c.action('clear_teleport 0');time.sleep(.3)
            camera = c.record('camera_state','PP_QA_CAMERA ')
            assert sum(abs(a-b) for a,b in zip(camera['origin'],eye))<.6,camera
        def shot(name):
            before = set((base/'scrnshot').glob('*.png'));c.console('screenshot png')
            path = wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
            wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'),name+' PNG')
            shutil.copy2(path,shots/(name+'.png'));report['views'].append(name)
        try:
            wait(lambda:c.state()['clients'][0]['spawned'],'spawn',60)
            item = wait(barrel,'shared barrel');time.sleep(.5)
            assert item['solid']==2,item
            report['checks'].append(dict(name='native barrel uses shared model and solid bounding box',entity=item))
            c.action('clientcmd 0 noclip');time.sleep(.2)
            center = [*item['origin'][:2],item['origin'][2]+20]
            for name,offset in [('front',(0,-95,7)),('back',(0,95,7)),
                                ('side',(-95,0,7)),('lid',(35,-55,65)),('far',(0,-350,35))]:
                pose([a+b for a,b in zip(center,offset)],center);shot(name)
            c.action('clientcmd 0 give health 9999');c.action('clientcmd 0 use Pistol');time.sleep(.8)
            pose([center[0],center[1]-150,center[2]],center)
            c.action('attack 0 1')
            try:wait(lambda:not barrel(),'barrel destroyed by normal gunfire',12)
            finally:c.action('attack 0 0')
            debris = wait(lambda:[e for e in entities() if e['model'].startswith('models/objects/debris')],
                          'native explosion debris',3)
            report['checks'].append(dict(name='normal gunfire destroys barrel and creates native debris',debris=debris))
            time.sleep(.4);shot('destroyed')
            report['passed'] = True
        except BaseException as e:
            report['error'] = repr(e);raise
        finally:
            if process.poll() is None:c.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            report['returncode'] = process.returncode
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')


if __name__ == '__main__':main()
