#!/usr/bin/env python3
"""Observe actual rendered ADS firing motion for all nine guns and the M16 control."""
import argparse,json,os,shutil,subprocess,time,math
from pathlib import Path
from hashlib import sha256
import numpy as np
from capture_pickup_lod import stage_runtime
from qa_controls import compile_controls,FileControls
ROOT=Path(__file__).resolve().parents[2]
WEAPONS={'Pistol':('blast',.35),'Shotgun':('shotg',.60),'Double Barrel Shotgun':('shotg2',.70),
 'Heavy Machinegun':('chain',.25),'Grenade Launcher':('launch',.55),'Rocket Launcher':('rocket',.50),
 'Sniper Rifle':('rail',.30),'M1 Flamethrower':('hyperb',.08),'Mortar Cannon':('bfg',.65),'Rifle':('machn',0)}


def local_pose(row):
    pitch,yaw,roll=np.radians(row['viewangles']);sp,cp=np.sin(pitch),np.cos(pitch);sy,cy=np.sin(yaw),np.cos(yaw);sr,cr=np.sin(roll),np.cos(roll)
    forward=np.array([cp*cy,cp*sy,-sp]);right=np.array([-sr*sp*cy+cr*sy,-sr*sp*sy-cr*cy,-sr*cp]);up=np.cross(right,forward)
    # The renderer adds a fixed world-space 1/16-unit BSP-plane bias after
    # placing the gun. Remove that camera-only bias before comparing kicks,
    # especially when the mortar's gameplay camera kick changes the basis.
    delta=np.array(row['origin'])-row['camera']+1/16
    return np.array([delta@forward,delta@right,delta@up]),(np.array(row['angles'])-row['viewangles']+180)%360-180


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--four',action='store_true');p.add_argument('--weapons',nargs='+',choices=list(WEAPONS),default=list(WEAPONS))
    p.add_argument('--map',type=Path,default=ROOT/'build/rlauncher-qa-gl3-final/runtime/baseq2/maps/pp_m16_review.bsp')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runtime=stage_runtime(ROOT/'release',out,{'review':a.map.resolve()});base=runtime/'baseq2'
    shutil.copytree(ROOT/'baseq2/tuning',base/'tuning')
    lib,offsets=compile_controls(runtime,out,defines=['PP_ADS_RECOIL_QA'])
    control,logpath=out/'controls.txt',out/'console.log';control.write_text('');shots=out/'screenshots';shots.mkdir()
    settings=dict(vid_renderer='gl3',vid_fullscreen=0,r_mode=-1,r_customwidth=1280,r_customheight=720,
        r_vsync=0,vid_maxfps=120,cl_maxfps=120,s_initsound=0,cheats=1,cl_gun=1,crosshair=0,r_hudscale=0,
        cl_blend=0,con_notifytime=0,cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,in_grab=0,
        logfile=2,cl_aimassist=0,cl_mflash_tune_mode=0,maxclients=4 if a.four else 2,coop=1,singleplayer=0,deathmatch=0)
    startup=('cl_bench_local 4 '+a.map.stem) if a.four else ('map '+a.map.stem)
    (base/'ads-recoil.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in settings.items())+startup+'\n')
    env=dict(os.environ,SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',
        LD_PRELOAD=str(lib),PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    count=4 if a.four else 1
    report=dict(passed=False,players=count,weapons=[],inputs_sha256={n:sha256((runtime/n).read_bytes()).hexdigest()
        for n in ('quake2','baseq2/game.so','baseq2/plastic-platoon.pk3')})
    with logpath.open('w') as log:
        process=subprocess.Popen([str(runtime/'quake2'),'-portable','-datadir',str(runtime),'+set','s_initsound','0',
            '+set','vid_renderer','gl3','+set','r_mode','-1','+set','r_customwidth','1280','+set','r_customheight','720',
            '+exec','ads-recoil.cfg'],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT)
        c=FileControls(control,logpath,process)
        def wait(fn,label,timeout=30):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                result=fn()
                if result:return result
                if process.poll() is not None:raise RuntimeError('Engine exited: '+label)
                time.sleep(.04)
            raise RuntimeError('Timed out: '+label)
        def rows(label):
            result=[]
            for line in logpath.read_text(errors='replace').splitlines():
                if 'PP_ADS_RECOIL ' not in line:continue
                try:r=json.loads(line.split('PP_ADS_RECOIL ',1)[1])
                except json.JSONDecodeError:continue
                if r['label']==label:result.append(r)
            return result
        def shot(name):
            before=set((base/'scrnshot').glob('*.png'));c.console('screenshot png')
            f=wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
            wait(lambda:f.read_bytes().endswith(b'IEND\xaeB`\x82'),name+' PNG');shutil.copy2(f,shots/(name+'.png'))
        try:
            wait(lambda:all(v['spawned'] for v in c.state()['clients'][:count]),'players spawn',60)
            for slot in range(count):
                for cmd in ('notarget','give health 9999','give weapons','give ammo','noclip'):c.action(f'clientcmd {slot} {cmd}')
                c.console(f'cl_bench_pose {slot} {-800+slot*200} -1400 24 0 90')
                c.action(f'clear_teleport {slot}')
            for index,weapon in enumerate(a.weapons):
                model,limit=WEAPONS[weapon];path='models/weapons/v_'+model+'/tris.md2'
                for slot in range(count):
                    c.action(f'ads {slot} 0');c.action(f'attack {slot} 0');c.action(f'equip {slot} {weapon}')
                wait(lambda:all(v['gunmodel']==path for v in c.state()['clients'][:count]),weapon+' equip')
                time.sleep(.7)
                for slot in range(count):c.action(f'ads {slot} 1')
                wait(lambda:all(v['model_ads_blend']==1 for v in c.state()['clients'][:count]),weapon+' ADS')
                time.sleep(.3);idle=f'w{index}-idle';fire=f'w{index}-fire';recovery=f'w{index}-recovery'
                c.action('ads_watch '+idle);time.sleep(.3);c.action('ads_watch off');time.sleep(.08)
                shot(f'{index:02}-{model}-idle')
                before=c.record('ammo_state','PP_AMMO_INVENTORY ')['counts']
                c.action('ads_watch '+fire)
                for slot in range(count):c.action(f'attack {slot} 1')
                time.sleep(2.4 if model in ('bfg','rail','launch','rocket') else 1.8)
                shot(f'{index:02}-{model}-firing')
                for slot in range(count):c.action(f'attack {slot} 0')
                c.action('ads_watch off');time.sleep(.1)
                after=c.record('ammo_state','PP_AMMO_INVENTORY ')['counts']
                # The starting pistol is unlimited, and mortar rounds use a
                # separate pool outside the legacy seven-ammo probe. Native
                # muzzle events witness actual firing for either case.
                consumed=any(after[name]<value for name,value in before.items())
                fired=any(r['recoil']>0 for r in rows(fire)) or len({r.get('muzzle_seq',0)
                    for r in rows(idle)+rows(fire) if r['slot']==0})>1
                assert consumed or fired,(weapon,before,after)
                c.action('ads_watch '+recovery);time.sleep(.8);c.action('ads_watch off');time.sleep(.08)
                result=dict(weapon=weapon,model=path,limit=limit,ammo_before=before,ammo_after=after,slots=[])
                for slot in range(count):
                    idle_rows=[r for r in rows(idle) if r['slot']==slot and r['model']==path and r['blend']==1]
                    fire_rows=[r for r in rows(fire) if r['slot']==slot and r['model']==path and r['blend']==1]
                    assert len(idle_rows)>=2 and len(fire_rows)>=5,(weapon,slot,len(idle_rows),len(fire_rows))
                    assert len({r.get('muzzle_seq',0) for r in idle_rows+fire_rows})>1 or any(r['recoil']>0 for r in fire_rows),(weapon,slot,'no firing observed')
                    baseline=np.median([local_pose(r)[0] for r in idle_rows],axis=0)
                    motion=np.array([local_pose(r)[0]-baseline for r in fire_rows])
                    angles=np.array([local_pose(r)[1] for r in fire_rows])
                    if limit:
                        assert motion[:,0].min()>=-limit-.015,(weapon,slot,motion.min(0))
                        assert np.abs(motion[:,1:]).max()<.015,(weapon,slot,motion.max(0))
                        assert np.abs(angles).max()<.015,(weapon,slot,angles.max(0))
                    result['slots'].append(dict(slot=slot,frames=len(fire_rows),peak_back=float(-motion[:,0].min()),
                        max_side_or_lift=float(np.abs(motion[:,1:]).max()),max_angle=float(np.abs(angles).max()),
                        observed_recoil=float(max(r['recoil'] for r in fire_rows)),
                        model_frames=sorted({r['frame'] for r in fire_rows})))
                report['weapons'].append(result);print(weapon+' passed',flush=True)
            report['passed']=True
        except BaseException as e:report['error']=repr(e);raise
        finally:
            if process.poll() is None:c.console('quit')
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            report['returncode']=process.returncode;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out/'report.json')
if __name__=='__main__':main()
