#!/usr/bin/env python3
"""Photograph real weapon-fired world models, flight samples and impacts.

Single-view close inspections pause a natively fired projectile and move only
the QA camera. Resuming preserves its original velocity, gravity, spin and
fuse. Impacts run at normal speed. Split mode uses a real second local player
and photographs the moving projectile without pausing the world.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from capture_pickup_lod import stage_runtime, virtual_pad_driver
from make_fixture import box, entity
from qa_controls import FileControls, compile_controls

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    'rocket': ('Rocket Launcher', 'v_rocket/', 'objects/rocket/tris.md2', 'rocket', 40.),
    'hand': ('Grenades', 'v_handgr/', 'objects/grenade2/tris.md2', 'hgrenade', 65.),
    'launcher': ('Grenade Launcher', 'v_launch/', 'objects/grenade/tris.md2', 'grenade', 40.),
    'mortar': ('Mortar Cannon', 'v_bfg/', 'objects/grenade/tris.md2', 'mortar', 200.),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output, tool):
    maps = output / 'maps'
    maps.mkdir()
    source = maps / 'pp_projectile_review.map'
    walls = [((-640,-512,-32),(640,512,0)), ((-640,-512,768),(640,512,800)),
             ((-672,-544,-32),(-640,544,800)), ((640,-544,-32),(672,544,800)),
             ((-640,-544,-32),(640,-512,800)), ((-640,512,-32),(640,544,800))]
    text = '{\n"classname" "worldspawn"\n"message" "Live projectile review"\n'
    text += ''.join(box(lo,hi,'sandbox/sand1') for lo,hi in walls) + '}\n'
    text += entity(dict(classname='info_player_start',origin='-400 0 24',angle='0'))
    text += entity(dict(classname='info_player_coop',origin='-400 -160 24',angle='0'))
    for x in (-480,-160,160,480):
        for y in (-320,0,320):
            text += entity(dict(classname='light',origin=f'{x} {y} 224',light='500'))
    source.write_text(text)
    bsp = source.with_suffix('.bsp')
    for stage in ('bsp','vis','rad'):
        result = subprocess.run([str(tool),'-'+stage,'-threads','2','-basedir',str(ROOT/'baseq2'),
                                 str(source if stage=='bsp' else bsp)],text=True,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (maps/('projectile-'+stage+'.log')).write_text(result.stdout)
        if result.returncode:
            raise RuntimeError('Fixture compile failed: '+stage)
    return bsp


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'release')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--renderer',choices=('gl1','gl3','soft'),default='gl3')
    p.add_argument('--map-file',type=Path)
    p.add_argument('--q2tool',type=Path,default=ROOT.parent/'q2tools-220/build/q2tool')
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--split',action='store_true')
    p.add_argument('--cases',nargs='+',choices=list(CASES),default=list(CASES))
    args=p.parse_args()
    out,source=args.output.resolve(),args.source.resolve()
    out.mkdir(parents=True,exist_ok=False)
    bsp=args.map_file.resolve() if args.map_file else prepare(out,args.q2tool.resolve())
    if args.prepare_only:
        print(bsp);return
    runtime=stage_runtime(source,out,{'projectiles':bsp})
    base=runtime/'baseq2'
    shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    overlays={}
    for path in (ROOT/'baseq2').glob('operation-*.pk3'):
        (base/path.name).symlink_to(path.resolve())
        overlays[path.name]=sha(path)
    library,offsets=compile_controls(source,out,[ROOT/'tests/input/projectiles_game.c'],['PP_PROJECTILE_QA'])
    pads=virtual_pad_driver(out) if args.split else None
    controls_path,logpath=out/'controls.txt',out/'console.log'
    controls_path.write_text('')
    shots=out/'screenshots';shots.mkdir()
    settings=dict(vid_renderer=args.renderer,r_mode=-1,r_customwidth=1280,r_customheight=720,
                  vid_fullscreen=0,r_vsync=0,vid_maxfps=120,cl_maxfps=120,s_initsound=0,
                  cheats=1,cl_predict=0,cl_gun=0,crosshair=0,r_hudscale=0,cl_blend=0,
                  cl_bob=0,cl_kickangles=0,cl_aimassist=0,cl_gamebird_autolevel=0,
                  con_notifytime=0,scr_showpause=0,r_novis=1,r_cull=1,in_grab=0,logfile=2)
    cfg=''.join(f'set {k} "{v}"\n' for k,v in settings.items())
    cfg+=('cl_bench_local 2 '+bsp.stem+'\n' if args.split else
          'set maxclients 1\nset coop 0\nset singleplayer 1\nset deathmatch 0\nmap '+bsp.stem+'\n')
    (base/'projectile-review.cfg').write_text(cfg)
    command=[str(runtime/'quake2'),'-portable','-datadir',str(runtime),
             '+set','vid_renderer',args.renderer,'+set','r_mode','-1',
             '+set','r_customwidth','1280','+set','r_customheight','720',
             '+set','s_initsound','0','+exec','projectile-review.cfg']
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',
             LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',XDG_CACHE_HOME=str(runtime/'cache'),
             LD_PRELOAD=':'.join(str(v)for v in (pads,library)if v),
             PP_COLOR_CONTROLS=str(controls_path),**offsets)
    report=dict(complete=False,passed=False,renderer=args.renderer,split=args.split,
                source='native weapon fire, no direct projectile spawning',
                flight_sampling_time_scale=.25,close_inspection='paused live projectile; camera only',
                impact_time_scale=1,views=[],cases={},mission_overlays=overlays,
                inputs_sha256={name:sha(runtime/name)for name in ('quake2','ref_'+args.renderer+'.so',
                                                                'baseq2/game.so','baseq2/plastic-platoon.pk3')})
    process=None
    try:
        with logpath.open('w')as log:
            process=subprocess.Popen(command,cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            controls=FileControls(controls_path,logpath,process)
            def wait(check,label,timeout=60):
                until=time.monotonic()+timeout
                while time.monotonic()<until:
                    result=check()
                    if result:return result
                    if process.poll()is not None:raise RuntimeError('Engine exited: '+label)
                    time.sleep(.025)
                raise RuntimeError('Timed out: '+label)
            def record(marker,label):
                def read():
                    for line in logpath.read_text(errors='replace').splitlines():
                        if marker not in line:continue
                        try:item=json.loads(line.split(marker,1)[1])
                        except json.JSONDecodeError:continue
                        if item.get('label')==label:return item
                return wait(read,label)
            def entities(label):return controls.record('projectiles','PP_PROJECTILE_STATE ',label)['projectiles']
            def camera(point,target):
                d=[b-a for a,b in zip(point,target)]
                pitch=-math.degrees(math.atan2(d[2],math.hypot(d[0],d[1])))
                yaw=math.degrees(math.atan2(d[1],d[0]))
                controls.action('camera_pose '+' '.join(str(v)for v in (*point,pitch,yaw)))
                time.sleep(.2)
                return controls.record('camera_state','PP_QA_CAMERA ')
            def photo(label,before=None,**metadata):
                if before is None:
                    before=set((base/'scrnshot').glob('*.png'))
                    controls.console('screenshot png')
                path=wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),label)
                wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'),label+' PNG')
                dest=shots/(label+'.png');shutil.copy2(path,dest)
                report['views'].append(dict(name=label,screenshot=dest.name,sha256=sha(dest),**metadata))
                print(dest,flush=True)
            for index,key in enumerate(args.cases):
                weapon,viewmodel,model,classname,height=CASES[key]
                controls.console('set paused 0');controls.console('set timescale 1')
                if index:
                    controls.console('gamemap '+bsp.stem);time.sleep(.8)
                players=2 if args.split else 1
                wait(lambda:all(c['spawned']for c in controls.state()['clients'][:players]),'spawn')
                controls.action('clientcmd 0 god')
                controls.action('clientcmd 0 give weapons')
                controls.action('clientcmd 0 give ammo')
                controls.action('equip 0 '+weapon)
                wait(lambda:viewmodel in controls.state()['clients'][0]['gunmodel'],'equip '+key)
                controls.console('cl_bench_pose 0 -400 0 14 0 0')
                time.sleep(.3);controls.action('clear_teleport 0')
                gate_x=-300 if key=='hand' else -180
                if args.split:
                    controls.action('observer 1')
                    controls.console(f'cl_bench_pose 1 {gate_x} -100 {height-32} 0 90')
                    time.sleep(.3);controls.action('clear_teleport 1')
                controls.console('set timescale .25')
                label=key+'-flight'
                before=set((base/'scrnshot').glob('*.png'))
                controls.action(f'captureflight {model} {gate_x} {0 if args.split else 1} {label}')
                controls.action('attack 0 1')
                if key=='hand':
                    wait(lambda:controls.state()['clients'][0]['server_gunframe']==11,'grenade release frame')
                    controls.action('attack 0 0')
                gate=record('PP_PROJECTILE_GATE ',label)
                controls.action('attack 0 0')
                first=next(e for e in record('PP_PROJECTILE_STATE ',label)['projectiles']if e['classname']==classname)
                if args.split:
                    photo(label,before,phase='unpaused live flight in two local views',projectile=first)
                    report['cases'][key]=dict(first=first,split_observer=True)
                    continue
                controls.console('set timescale 1')
                controls.action('clientcmd 0 noclip')
                point=first['origin']
                cam=camera([point[0]+10,point[1]-55,point[2]+12],point)
                photo(key+'-close',phase='paused natively fired projectile',projectile=first,camera=cam)
                cam=camera([point[0]-42,point[1]-42,point[2]+28],point)
                photo(key+'-oblique',phase='same live projectile, alternate camera',projectile=first,camera=cam)
                frozen=next(e for e in entities(key+'-pause-check') if e['classname']==classname)
                if frozen['origin']!=first['origin'] or frozen['angles']!=first['angles']:
                    raise RuntimeError('World did not remain paused: '+key+' '+str(frozen))
                label=key+'-later'
                controls.action(f'captureflight {model} {point[0]+80} 1 {label}')
                controls.console('set timescale .25');controls.console('set paused 0')
                record('PP_PROJECTILE_GATE ',label)
                second=next(e for e in record('PP_PROJECTILE_STATE ',label)['projectiles']if e['classname']==classname)
                controls.console('set timescale 1')
                point=second['origin']
                cam=camera([point[0]+10,point[1]-55,point[2]+12],point)
                photo(key+'-later',phase='second native flight/spin sample',projectile=second,camera=cam)
                camera([320,-500,180],[320,0,100])
                label=key+'-impact'
                before=set((base/'scrnshot').glob('*.png'))
                controls.action(f'captureimpact {model} {label}')
                controls.console('set timescale 1');controls.console('set paused 0')
                impact=record('PP_PROJECTILE_IMPACT ',label)
                photo(label,before,phase='normal-speed native impact/fuse expiry',impact=impact)
                checks=dict(displaced=first['origin']!=second['origin'],
                            spin_changed=(first['angles']!=second['angles']) if key!='rocket' else first['angles']==second['angles'],
                            removed=not any(e['classname']==classname for e in entities(key+'-removed')))
                if not all(checks.values()):
                    raise RuntimeError('Flight state checks failed: '+key+' '+str(checks))
                report['cases'][key]=dict(first=first,second=second,impact=impact,
                                         displaced=first['origin']!=second['origin'],
                                         spin_changed=first['angles']!=second['angles'],
                                         removed=checks['removed'])
            report.update(complete=True,passed=True)
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        if process and process.poll()is None:
            controls.console('set paused 0');controls.console('set timescale 1');controls.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
        report['returncode']=process.returncode if process else None
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')


if __name__=='__main__':main()
