#!/usr/bin/env python3
"""Native boss gallery, both rocket volleys, crash and the unchanged Sandkeep arena."""
import argparse,json,math,os,shutil,subprocess,time,zipfile
from pathlib import Path
from hashlib import sha256
from capture_pickup_lod import stage_runtime
from capture_dropship import fixture
from qa_controls import compile_controls,FileControls
ROOT=Path(__file__).resolve().parents[2]
BODY='models/monsters/plastic_boss/body.md2'
ROTOR='models/monsters/plastic_boss/main_rotor.md2'


def prepare(out):
    maps=out/'maps';maps.mkdir();p=maps/'pp_boss_qa.map'
    p.write_text(fixture().replace('misc_platoon_dropship','monster_boss2'))
    for stage in ('bsp','vis','rad'):
        r=subprocess.run([str(ROOT.parent/'q2tools-220/build/q2tool'),'-'+stage,'-threads','2',
            '-basedir',str(ROOT/'baseq2'),str(p if stage=='bsp' else p.with_suffix('.bsp'))],capture_output=True,text=True,timeout=180)
        (maps/(stage+'.log')).write_text(r.stdout+r.stderr);r.check_returncode()
    return p.with_suffix('.bsp')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--renderer',choices=('gl1','gl3','soft'),default='gl3');p.add_argument('--map',type=Path)
    p.add_argument('--smoke',action='store_true',help='Two gallery angles and native attacks/crash; omit existing arena scene')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    bsp=a.map.resolve() if a.map else prepare(out)
    runtime=stage_runtime(ROOT/'release',out,{'gallery':bsp});base=runtime/'baseq2'
    shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    operation=ROOT/'baseq2/operation-sandkeep.pk3'
    shutil.copy2(operation,base/operation.name)
    library,offsets=compile_controls(ROOT/'release',out,[ROOT/'tests/input/boss_helicopter_game.c'],['PP_BOSS_QA'])
    control,logpath=out/'controls.txt',out/'console.log';control.write_text('');shots=out/'screenshots';shots.mkdir()
    settings=dict(vid_renderer=a.renderer,vid_fullscreen=0,r_mode=-1,r_customwidth=1280,r_customheight=720,
        r_vsync=0,vid_maxfps=60,cl_maxfps=60,s_initsound=0,cheats=1,cl_gun=0,crosshair=0,r_hudscale=0,
        cl_blend=0,con_notifytime=0,cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,in_grab=0,
        logfile=2,cl_aimassist=0,maxclients=2,coop=1,singleplayer=0,deathmatch=0)
    (base/'boss-review.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in settings.items())+'map '+bsp.stem+'\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',LIBGL_ALWAYS_SOFTWARE='1',
        LP_NUM_THREADS='2',LD_PRELOAD=str(library),PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    report=dict(passed=False,renderer=a.renderer,views=[],checks=[],
        sandkeep_archive_sha256=sha256(operation.read_bytes()).hexdigest(),
        inputs_sha256={n:sha256((runtime/n).read_bytes()).hexdigest() for n in ('quake2','baseq2/game.so','baseq2/plastic-platoon.pk3')})
    with logpath.open('w') as log:
        process=subprocess.Popen([str(runtime/'quake2'),'-portable','-datadir',str(runtime),'+set','s_initsound','0',
            '+set','vid_renderer',a.renderer,'+set','r_mode','-1','+set','r_customwidth','1280','+set','r_customheight','720',
            '+exec','boss-review.cfg'],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
        c=FileControls(control,logpath,process)
        def wait(fn,label,timeout=30):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                value=fn()
                if value:return value
                if process.poll() is not None:raise RuntimeError('Engine exited: '+label)
                time.sleep(.04)
            raise RuntimeError('Timed out: '+label)
        def state():return c.record('boss_state','PP_BOSS_STATE ')
        def boss():return next(iter(state()['bosses']),None)
        def render():return c.record('boss_render','PP_BOSS_RENDER ')
        def entities():return c.record('enemy_state','PP_COLOR_ENEMIES ')['entities']
        def shot(name):
            before=set((base/'scrnshot').glob('*.png'));c.console('screenshot png')
            path=wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
            wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'),name+' PNG')
            shutil.copy2(path,shots/(name+'.png'));report['views'].append(name)
        def pose(eye,target):
            d=[b-a for a,b in zip(eye,target)]
            yaw=math.degrees(math.atan2(d[1],d[0]));pitch=-math.degrees(math.atan2(d[2],math.hypot(*d[:2])))
            c.console('cl_bench_pose 0 '+' '.join(map(str,(*eye[:2],eye[2]-32,pitch,yaw))))
            time.sleep(.25);c.action('clear_teleport 0');time.sleep(.25)
        def setup_player():
            c.action('clientcmd 0 god');c.action('clientcmd 0 notarget');c.action('clientcmd 0 noclip');time.sleep(.2)
        def check_models(damaged=False):
            r=render();models={e['model'] for e in r['entities']}
            assert models=={BODY,ROTOR},r
            for e in r['entities']:
                assert e['frame']==0,e
                wanted='models/monsters/plastic_boss/colors/'+('body_red_1.png' if damaged else 'body_red.png') if e['model']==BODY else 'models/monsters/plastic_boss/colors/main_rotor_red.png'
                assert e['skin']==wanted,(wanted,e)
            return r
        try:
            wait(lambda:c.state()['clients'][0]['spawned'],'spawn',60);setup_player()
            wait(boss,'boss spawn');c.action('boss freeze');time.sleep(.2)
            b=boss();assert b['health']==4000 and b['max_health']==4000,b
            center=[b['origin'][0],b['origin'][1],b['origin'][2]+65]
            views=[('front',(240,-210,25)),('side',(0,-310,15))]
            if not a.smoke:views += [('rear',(-260,170,35)),('overhead',(130,-160,230)),('underside',(220,-150,-50))]
            for name,delta in views:
                pose([x+y for x,y in zip(center,delta)],center);check_models();shot(name)
            first=check_models();time.sleep(.16);second=check_models()
            rotor_a=next(e for e in first['entities'] if e['model']==ROTOR)
            rotor_b=next(e for e in second['entities'] if e['model']==ROTOR)
            assert rotor_a['angles']!=rotor_b['angles']
            report['checks'].append(dict(name='4000 health, actual red body/rotor skins and native rotor spin',state=b))
            c.action('boss phase');time.sleep(.2);check_models(True);shot('damaged')
            pose((center[0]-650,center[1]-450,center[2]),center)
            c.action('boss fire');time.sleep(.3)
            assert not any(e['model']=='models/objects/rocket/tris.md2' for e in entities())
            seen=set();end=time.monotonic()+3
            while time.monotonic()<end:
                seen.update(e['number'] for e in entities() if e['model']=='models/objects/rocket/tris.md2')
                if len(seen)>=8:break
                time.sleep(.03)
            assert len(seen)>=8,seen
            report['checks'].append(dict(name='phase two native wind-up and two four-rocket salvos',rocket_entities=sorted(seen)))
            c.action('boss freeze');c.action('boss kill')
            wait(lambda:not boss(),'native crash cleanup',8)
            report['checks'].append(dict(name='native crash and cleanup',state=state()))
            shot('after-crash')
            if not a.smoke:
                c.console('map pp_sandkeep');time.sleep(.8)
                wait(lambda:c.state()['clients'][0]['spawned'],'Sandkeep spawn',60)
                c.action('clientcmd 0 god');c.action('clientcmd 0 notarget')
                if c.state()['clients'][0]['pm_type']!=1:c.action('clientcmd 0 noclip')
                b=wait(boss,'existing Sandkeep boss');assert b['health']==4000 and b['deathtarget']=='boss_down',b
                pose((0,2100,250),(0,2528,240));c.action('boss wake')
                wait(lambda:(v if (v:=boss()) and not v['svflags']&1 and v['solid']==2 else None),'existing boss wake',8)
                c.action('boss freeze');time.sleep(.3);check_models();shot('sandkeep-boss')
                report['checks'].append(dict(name='unmodified Sandkeep BSP uses new boss and retains boss_down objective',state=boss()))
            report['passed']=True
        except BaseException as e:report['error']=repr(e);raise
        finally:
            if process.poll() is None:c.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            report['returncode']=process.returncode;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')
if __name__=='__main__':main()
