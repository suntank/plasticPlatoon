#!/usr/bin/env python3
"""Native fragment gallery plus actual soldier, ant and spider death bursts."""
import argparse,json,math,os,shutil,subprocess,time
from pathlib import Path
from hashlib import sha256
from capture_pickup_lod import stage_runtime
from make_fixture import box,entity
from qa_controls import FileControls,compile_controls
ROOT=Path(__file__).resolve().parents[2]


def prepare(out,models):
    maps=out/'maps';maps.mkdir();path=maps/'pp_body_parts_review.map'
    text='{\n"classname" "worldspawn"\n"message" "Body parts review"\n'
    walls=[((-640,-512,-32),(640,640,0)),((-640,-512,288),(640,640,320)),
           ((-672,-544,-32),(-640,672,320)),((640,-544,-32),(672,672,320)),
           ((-640,-544,-32),(640,-512,320)),((-640,640,-32),(640,672,320))]
    text+=''.join(box(a,b,'sandbox/sand1') for a,b in walls)+'}\n'
    text+=entity(dict(classname='info_player_start',origin='0 -400 24',angle='90'))
    for x in (-480,-240,0,240,480):
        for y in (-320,0,320,560):text+=entity(dict(classname='light',origin=f'{x} {y} 224',light='320'))
    for i,e in enumerate(models):
        z=32-e['after']['bounds'][0][2]
        text+=entity(dict(classname='misc_tank',model=e['path'],origin=f'{i%5*110-220} {i//5*140} {z}'))
    path.write_text(text)
    for stage in ('bsp','vis','rad'):
        p=subprocess.run([str(ROOT.parent/'q2tools-220/build/q2tool'),'-'+stage,'-threads','2',
            '-basedir',str(ROOT/'baseq2'),str(path if stage=='bsp' else path.with_suffix('.bsp'))],
            capture_output=True,text=True,timeout=120)
        (maps/(stage+'.log')).write_text(p.stdout+p.stderr);p.check_returncode()
    return path.with_suffix('.bsp')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--renderer',choices=('gl1','gl3','soft'),default='gl3');p.add_argument('--map',type=Path)
    p.add_argument('--diagnostic-lighting',action='store_true',help='Uniform entity lighting through the existing private photography hook')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    models=json.loads((ROOT/'tools/assets/body-parts-manifest.json').read_text())['models']
    bsp=a.map.resolve() if a.map else prepare(out,models)
    runtime=stage_runtime(ROOT/'release',out,{'gallery':bsp});base=runtime/'baseq2'
    shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    defines=['PP_BODY_PARTS_QA']+(['PP_SOLDIER_QA'] if a.diagnostic_lighting else [])
    library,offsets=compile_controls(ROOT/'release',out,defines=defines)
    control,logpath=out/'controls.txt',out/'console.log';control.write_text('')
    shots=out/'screenshots';shots.mkdir()
    settings=dict(vid_renderer=a.renderer,vid_fullscreen=0,r_mode=-1,r_customwidth=1280,r_customheight=720,
        r_vsync=0,vid_maxfps=60,cl_maxfps=60,s_initsound=0,cheats=1,cl_gun=0,crosshair=0,r_hudscale=0,
        cl_blend=0,con_notifytime=0,cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,in_grab=0,
        logfile=2,cl_aimassist=0,maxclients=2,coop=1,singleplayer=0,deathmatch=0)
    (base/'parts-review.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in settings.items())+'map '+bsp.stem+'\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',LIBGL_ALWAYS_SOFTWARE='1',
        LP_NUM_THREADS='2',LD_PRELOAD=str(library),PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    report=dict(passed=False,renderer=a.renderer,diagnostic_lighting=a.diagnostic_lighting,views=[],bursts=[],
        inputs_sha256={n:sha256((runtime/n).read_bytes()).hexdigest() for n in ('quake2','baseq2/game.so','baseq2/plastic-platoon.pk3')})
    with logpath.open('w') as log:
        process=subprocess.Popen([str(runtime/'quake2'),'-portable','-datadir',str(runtime),'+set','s_initsound','0',
            '+set','vid_renderer',a.renderer,'+set','r_mode','-1','+set','r_customwidth','1280','+set','r_customheight','720',
            '+exec','parts-review.cfg'],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
        c=FileControls(control,logpath,process)
        def wait(fn,label,timeout=30):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                value=fn()
                if value:return value
                if process.poll() is not None:raise RuntimeError('Engine exited: '+label)
                time.sleep(.04)
            raise RuntimeError('Timed out: '+label)
        def entities():return c.record('enemy_state','PP_COLOR_ENEMIES ')['entities']
        def pose(eye,target):
            d=[b-a for a,b in zip(eye,target)];yaw=math.degrees(math.atan2(d[1],d[0]));pitch=-math.degrees(math.atan2(d[2],math.hypot(*d[:2])))
            c.console('cl_bench_pose 0 '+' '.join(map(str,(*eye[:2],eye[2]-32,pitch,yaw))))
            time.sleep(.25);c.action('clear_teleport 0');time.sleep(.25)
        def shot(name):
            before=set((base/'scrnshot').glob('*.png'));c.console('screenshot png')
            path=wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
            wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'),name+' PNG')
            shutil.copy2(path,shots/(name+'.png'));report['views'].append(name)
        try:
            wait(lambda:c.state()['clients'][0]['spawned'],'spawn',60)
            c.action('clientcmd 0 notarget');c.action('clientcmd 0 noclip');time.sleep(.3)
            displayed={e['model']:e for e in entities()}
            for entry in models:
                prop=displayed[entry['path']];lo,hi=entry['after']['bounds']
                center=[prop['origin'][i]+(lo[i]+hi[i])/2 for i in range(3)]
                distance=max(35,max(b-a for a,b in zip(lo,hi))*2.4)
                pose([center[0]+distance*.65,center[1]-distance*.8,center[2]+distance*.45],center)
                shot(entry['kind'])
            # The private controller invokes the existing native die callback;
            # model selection, fragment counts, physics and colors stay native.
            for classname,expected in [('monster_soldier',{'sm_meat/tris.md2':3,'chest/tris.md2':1,'head2/tris.md2':1}),
                    ('monster_ant',{'ant/chunk.md2':4,'ant/leg.md2':4}),
                    ('monster_spider',{'spider/chunk.md2':5,'spider/leg.md2':6})]:
                pose((330,-120,58),(330,40,30))
                before={e['number'] for e in entities()}
                c.console(f'spawnentity {classname} 330 40 24 0 270 0 1');time.sleep(.3)
                spawned=wait(lambda:[e for e in entities() if e['number'] not in before and e['model'].startswith('models/monsters/')],classname)
                actor=spawned[0]['number'];c.action('gib '+classname)
                def burst():
                    parts=[e for e in entities() if (e['number'] not in before or e['number']==actor) and e['model'].startswith('models/objects/gibs/')]
                    return parts if all(sum(e['model'].endswith(name) for e in parts)>=count for name,count in expected.items()) else None
                parts=wait(burst,classname+' native fragments',5)
                report['bursts'].append(dict(classname=classname,expected=expected,parts=parts))
                shot(classname+'-burst')
            before={e['number'] for e in entities()}
            c.action('clientcmd 0 noclip');time.sleep(.15)
            c.action('gib player')
            def player_burst():
                parts=[e for e in entities() if e['number'] not in before and e['model'].startswith('models/objects/gibs/')]
                return parts if len(parts)>=5 else None
            parts=wait(player_burst,'native green player fragments',5)
            assert all(e['skinnum'] & 0x20000000 for e in parts),parts
            report['bursts'].append(dict(classname='player',parts=parts,green_override=True))
            shot('player-burst')
            report['passed']=True
        except BaseException as e:report['error']=repr(e);raise
        finally:
            if process.poll() is None:c.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            report['returncode']=process.returncode;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')


if __name__=='__main__':main()
