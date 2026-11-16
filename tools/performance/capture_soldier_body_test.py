#!/usr/bin/env python3
"""Isolated native A/B photos and quick-grenade checks; never edits user settings.

Private photography controls freeze existing actors at original frame indices.
They do not change the shipped game or claim an animation gameplay playthrough.
"""
import argparse,json,os,shutil,subprocess,time,math
from pathlib import Path
from capture_pickup_lod import stage_runtime
from make_fixture import box,entity
from qa_controls import FileControls,compile_controls
ROOT=Path(__file__).resolve().parents[2]

def prepare(out):
    maps=out/'maps';maps.mkdir();p=maps/'pp_soldier_body_review.map'
    text='{\n"classname" "worldspawn"\n"message" "Soldier body A B"\n'
    for lo,hi in [((-256,-256,-32),(256,256,0)),((-256,-256,192),(256,256,224)),
                  ((-288,-288,-32),(-256,288,224)),((256,-288,-32),(288,288,224)),
                  ((-256,-288,-32),(256,-256,224)),((-256,256,-32),(256,288,224))]:text+=box(lo,hi,'sandbox/sand1')
    text+='}\n'+entity(dict(classname='info_player_start',origin='-140 -70 24',angle='0'))
    text+=entity(dict(classname='monster_soldier',origin='0 0 24',angle='0'))
    for x in (-128,128):
        for y in (-128,128):text+=entity(dict(classname='light',origin=f'{x} {y} 128',light='250'))
    p.write_text(text)
    for stage in ('bsp','vis','rad'):
        r=subprocess.run([str(ROOT.parent/'q2tools-220/build/q2tool'),'-'+stage,'-threads','2','-basedir',str(ROOT/'baseq2'),str(p if stage=='bsp' else p.with_suffix('.bsp'))],capture_output=True,text=True,timeout=120)
        (maps/(stage+'.log')).write_text(r.stdout+r.stderr);r.check_returncode()
    return p.with_suffix('.bsp')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--renderer',default='gl3',choices=('gl1','gl3','soft'));p.add_argument('--map',type=Path);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);bsp=a.map.resolve() if a.map else prepare(out)
    runtime=stage_runtime(ROOT/'release',out,{'review':bsp});base=runtime/'baseq2';shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    lib,offsets=compile_controls(ROOT/'release',out,defines=['PP_SOLDIER_QA'])
    control=out/'controls.txt';control.write_text('');logpath=out/'console.log';shots=out/'screenshots';shots.mkdir()
    settings=dict(vid_renderer=a.renderer,vid_fullscreen=0,r_mode=-1,r_customwidth=1280,r_customheight=720,r_vsync=0,vid_maxfps=60,cl_maxfps=60,s_initsound=0,cheats=1,cl_gun=0,crosshair=0,r_hudscale=0,cl_blend=0,con_notifytime=0,cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,in_grab=0,logfile=2,cl_aimassist=0,r_fullbright=1)
    (base/'body-review.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in settings.items())+'set maxclients 2\nset coop 1\nset singleplayer 0\nset deathmatch 0\nmap '+bsp.stem+'\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',LD_PRELOAD=str(lib),PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    report=dict(passed=False,views=[],checks=[],renderer=a.renderer,diagnostic_fullbright=True)
    from hashlib import sha256
    report['inputs_sha256']={str(n):sha256((runtime/n).read_bytes()).hexdigest() for n in ('quake2','baseq2/game.so','baseq2/plastic-platoon.pk3')}
    with logpath.open('w') as log:
        process=subprocess.Popen([str(runtime/'quake2'),'-portable','-datadir',str(runtime),
            '+set','s_initsound','0','+set','vid_renderer',a.renderer,'+set','r_mode','-1',
            '+set','r_customwidth','1280','+set','r_customheight','720','+exec','body-review.cfg'],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
        c=FileControls(control,logpath,process)
        def wait(fn,what,limit=30):
            until=time.monotonic()+limit
            while time.monotonic()<until:
                v=fn()
                if v:return v
                if process.poll() is not None:raise RuntimeError('Engine exited: '+what)
                time.sleep(.04)
            raise RuntimeError('Timed out: '+what)
        def shot(name):
            before=set((base/'scrnshot').glob('*.png'));c.console('screenshot png')
            f=wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
            wait(lambda:f.read_bytes().endswith(b'IEND\xaeB`\x82'),name)
            shutil.copy2(f,shots/(name+'.png'));report['views'].append(name)
        def camera(eye):
            yaw=math.degrees(math.atan2(-eye[1],-eye[0]));pitch=-math.degrees(math.atan2(35-eye[2],math.hypot(eye[0],eye[1])))
            c.console('cl_bench_pose 0 '+' '.join(map(str,(*eye[:2],eye[2]-32,pitch,yaw))))
            wait(lambda:sum(abs(v-w) for v,w in zip(c.record('camera_state','PP_QA_CAMERA ')['origin'],eye))<.6,'camera position')
            c.action('clear_teleport 0');time.sleep(.3)
        def body(kind,frame,mode,name):
            c.action(f'body_pose {kind} {frame}');c.console(f'set cl_soldier_body_test {mode}');time.sleep(.3)
            r=c.record('body_render','PP_BODY_RENDER ')
            expected=('models/experimental/soldier/'+kind+'.md2') if mode else {'enemy':'models/monsters/soldier/tris.md2','enemy_tall':'models/monsters/soldier/tall/tris.md2','player':'players/soldier/tris.md2','player_pistol':'players/soldier/tris_pistol.md2'}[kind]
            assert any(e['model']==expected and e['frame']==frame for e in r['bodies']),(expected,r)
            shot(name);report['checks'].append(dict(name=name,model=expected,frame=frame))
        try:
            wait(lambda:c.state()['clients'][0]['spawned'],'spawn',60);time.sleep(.5)
            initial=c.record('body_render','PP_BODY_RENDER ')
            assert any(e['model']=='models/experimental/soldier/enemy_tall.md2' for e in initial['bodies']),initial
            report['checks'].append(dict(name='lower-poly body selected by default without a config override',passed=True))
            c.action('clientcmd 0 give health 9999');c.action('clientcmd 0 notarget');c.action('clientcmd 0 noclip');time.sleep(.2)
            cases=[('enemy_tall',146,'standing')]
            if not a.smoke:cases += [('enemy',146,'standard'),('enemy_tall',97,'running'),('enemy_tall',45,'crouching'),('enemy_tall',0,'firing')]
            camera((90,-35,35))
            for kind,frame,label in cases:
                for mode in (0,1):body(kind,frame,mode,label+('-original' if not mode else '-trial'))
            body('enemy_tall',146,0,'restored')
            c.console('set cl_mflash_tune_mode 1');c.console('set cl_mflash_tune_cam_back -80');c.console('set cl_mflash_tune_cam_right 40');c.console('set cl_mflash_tune_cam_up 8');c.console('set cl_mflash_tune_target_up 3')
            c.console('cl_bench_pose 0 -140 -70 14 0 0');time.sleep(.3);c.action('clear_teleport 0')
            c.action('clientcmd 0 give weapons');c.action('clientcmd 0 give ammo');time.sleep(.3)
            for gun,kind in [('Rifle','player'),('Pistol','player_pistol')]:
                c.action('clientcmd 0 use '+gun);time.sleep(.8)
                for mode in (0,1):
                    c.action('body_pose player 0');c.console(f'set cl_soldier_body_test {mode}');time.sleep(.3)
                    r=c.record('body_render','PP_BODY_RENDER ');prefix='models/experimental/soldier/'+kind+'.md2' if mode else 'players/soldier/'+('tris.md2' if kind=='player' else 'tris_pistol.md2')
                    assert any(e['model']==prefix and e['frame']==0 for e in r['bodies']),(prefix,r)
                    shot(kind+('-original' if not mode else '-trial'))
            c.console('set cl_mflash_tune_mode 0');c.console('set cl_soldier_body_test 0');time.sleep(.3)
            before=c.state()['clients'][0]['gunmodel'];ammo=c.record('ammo_state','PP_AMMO_INVENTORY ')['counts']['Grenades']
            c.action('clientcmd 0 quickgrenade');time.sleep(.25)
            after=c.state()['clients'][0]['gunmodel'];left=c.record('ammo_state','PP_AMMO_INVENTORY ')['counts']['Grenades']
            assert before==after and left==ammo-1,(before,after,ammo,left)
            c.action('clientcmd 0 use Grenades');time.sleep(.3);assert c.state()['clients'][0]['gunmodel']==before
            for _ in range(12):
                c.action('clientcmd 0 weapnext');time.sleep(.25);assert '/v_handgr/' not in c.state()['clients'][0]['gunmodel']
            time.sleep(.8)
            c.action('equip 0 Grenades');time.sleep(.6)
            assert '/v_handgr/' not in c.state()['clients'][0]['gunmodel']
            report['checks'].append(dict(name='legacy equipped-grenade state automatically returns to a firearm',passed=True))
            c.action('legacy_cook');time.sleep(.3)
            assert '/v_handgr/' in c.state()['clients'][0]['gunmodel']
            wait(lambda:'/v_handgr/' not in c.state()['clients'][0]['gunmodel'],'legacy live throw completes',5)
            report['checks'].append(dict(name='legacy live throw completes before automatic firearm recovery',passed=True))
            report['checks'].append(dict(name='quick grenade keeps firearm and consumes one round; direct selection and cycling exclude grenades',before=before,after=after,ammo_before=ammo,ammo_after=left))
            report['passed']=True
        except BaseException as e:report['error']=repr(e);raise
        finally:
            if process.poll() is None:c.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            report['returncode']=process.returncode;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')

if __name__=='__main__':main()
