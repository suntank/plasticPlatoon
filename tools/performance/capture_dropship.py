#!/usr/bin/env python3
"""Native friendly transport gallery, route animation and existing mission scenes.

The private QA library observes game/render state and invokes only the existing
misc_platoon_dropship use callback. Mission scene setup bypasses objective gates;
it does not constitute a complete mission playthrough. Existing maps are copied
without regeneration. Host captures are not target-device performance evidence.
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
import zipfile
import sys
from capture_pickup_lod import stage_runtime
from qa_controls import FileControls, compile_controls
from make_fixture import box, entity

ROOT = Path(__file__).resolve().parents[2]
BODY = 'models/vehicles/platoon_dropship/body.md2'
ROTOR = 'models/vehicles/platoon_dropship/main_rotor.md2'
FILES = (BODY, ROTOR, 'models/vehicles/platoon_dropship/green.png')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture():
    text = '{\n"classname" "worldspawn"\n"message" "Native friendly dropship QA"\n"_ambient" "30"\n'
    for lo, hi in [((-1200,-1000,-32),(1200,1000,0)),
                   ((-1200,-1000,900),(1200,1000,932)),
                   ((-1232,-1032,-32),(-1200,1032,932)),
                   ((1200,-1032,-32),(1232,1032,932)),
                   ((-1200,-1032,-32),(1200,-1000,932)),
                   ((-1200,1000,-32),(1200,1032,932))]:
        text += box(lo, hi, 'sandbox/sand1')
    text += '}\n' + entity(dict(classname='info_player_start', origin='500 -500 24', angle='135'))
    for x in (-700, 0, 700):
        for y in (-600, 0, 600):
            text += entity(dict(classname='light', origin=f'{x} {y} 420', light='1200'))
    text += entity(dict(classname='misc_platoon_dropship', origin='0 0 64', angle='0',
                        targetname='qa_ship', target='qa_lift', deathtarget='qa_depart', speed='240'))
    text += entity(dict(classname='path_corner', origin='0 0 220', targetname='qa_lift', target='qa_arrive'))
    text += entity(dict(classname='path_corner', origin='400 0 220', targetname='qa_arrive', wait='1'))
    text += entity(dict(classname='path_corner', origin='400 400 400', targetname='qa_depart'))
    return text


def prepare(out, tool, basedir):
    maps = out / 'maps'
    maps.mkdir()
    source = maps / 'pp_dropship_qa.map'
    source.write_text(fixture())
    for stage in ('bsp', 'vis', 'rad'):
        run = subprocess.run([str(tool), '-'+stage, '-threads', '2', '-basedir', str(basedir),
                              str(source if stage == 'bsp' else source.with_suffix('.bsp'))],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        (maps / (stage+'.log')).write_text(run.stdout)
        if run.returncode:
            raise RuntimeError('Fixture compile failed: ' + stage)
    return source.with_suffix('.bsp')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT/'release')
    p.add_argument('--package', type=Path)
    p.add_argument('--preview-assets', action='store_true', help='Overlay only the three current friendly assets into private runtime')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--renderer', choices=('gl1','gl3','soft'), default='gl3')
    p.add_argument('--fixture', type=Path, help='Reuse previously compiled isolated route fixture')
    p.add_argument('--q2tool', type=Path, default=ROOT.parent/'q2tools-220/build/q2tool')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--gallery-only', action='store_true')
    p.add_argument('--missions-only', action='store_true', help='Only the focused existing-BSP mission scenes')
    p.add_argument('--missions', action='store_true', help='Add scene captures using existing Sandstorm and Endline BSPs')
    args = p.parse_args()
    if args.missions_only:
        args.missions = True
    out, source = args.output.resolve(), args.source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture_path = args.fixture.resolve() if args.fixture else prepare(out, args.q2tool.resolve(), ROOT/'baseq2')
    if args.prepare_only:
        print(fixture_path)
        return
    maps = {'fixture':fixture_path}
    if args.missions:
        maps.update({name:ROOT/'baseq2/maps'/f'{name}.bsp' for name in ('pp_sandstorm','pp_endline')})
    runtime = stage_runtime(source, out, maps)
    base = runtime/'baseq2'
    if args.missions:
        # Reuse existing mission media verbatim; never invoke their map builders.
        for name in ('operation-endline.pk3','operation-sandstorm-preview.pk3'):
            origin = source/'baseq2'/name
            if not origin.exists():
                origin = ROOT/'baseq2'/name
            shutil.copy2(origin,base/name)
    if args.package:
        shutil.copy2(args.package.resolve(), base/'plastic-platoon.pk3')
    if args.preview_assets:
        pack = base/'plastic-platoon.pk3'
        with zipfile.ZipFile(pack) as archive:
            entries = [(info,archive.read(info.filename)) for info in archive.infolist() if info.filename not in FILES]
        with zipfile.ZipFile(pack, 'w', zipfile.ZIP_DEFLATED) as archive:
            for info, raw in entries:
                archive.writestr(info,raw)
            for name in FILES:
                archive.writestr(name,(ROOT/'baseq2'/name).read_bytes())
    library, offsets = compile_controls(source, out,
        [ROOT/'tests/input/projectiles_game.c',ROOT/'tests/input/dropship_game.c'],
        ['PP_PROJECTILE_QA','PP_DROPSHIP_QA'])
    control, logpath = out/'controls.txt',out/'console.log'
    control.write_text('')
    shots = out/'screenshots'
    shots.mkdir()
    config = dict(vid_renderer=args.renderer,vid_fullscreen=0,r_mode=-1,r_customwidth=1280,
        r_customheight=720,r_vsync=0,vid_maxfps=60,cl_maxfps=60,s_initsound=0,
        cheats=1,cl_gun=0,crosshair=0,r_hudscale=0,cl_blend=0,con_notifytime=0,
        cl_bob=0,cl_kickangles=0,cl_gamebird_autolevel=0,in_grab=0,logfile=2,
        scr_showpause=0,scr_centertime=0,maxclients=1,coop=0,singleplayer=1,deathmatch=0)
    (base/'dropship-review.cfg').write_text(''.join(f'set {k} "{v}"\n' for k,v in config.items()) +
                                          'map '+fixture_path.stem+'\n')
    command = [str(runtime/'quake2'),'-portable','-datadir',str(runtime),
               '+set','vid_renderer',args.renderer,'+set','r_mode','-1',
               '+set','r_customwidth','1280','+set','r_customheight','720',
               '+set','s_initsound','0','+exec','dropship-review.cfg']
    env = dict(os.environ, SDL_VIDEODRIVER='offscreen',SDL_AUDIODRIVER='dummy',
        LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',LD_PRELOAD=str(library),
        PP_COLOR_CONTROLS=str(control),XDG_CACHE_HOME=str(runtime/'cache'),**offsets)
    report = dict(complete=False,passed=False,renderer=args.renderer,host_timings_not_pi=True,
                  mission_scope='Native scene setup via the ship use callback; objective and combat gates are not a full playthrough',
                  preview_assets=args.preview_assets,views=[],checks=[],states=[],
                  inputs_sha256={name:sha(runtime/name) for name in
                    ('quake2','ref_'+args.renderer+'.so','baseq2/game.so','baseq2/plastic-platoon.pk3')},
                  maps_sha256={key:sha(path) for key,path in maps.items()},
                  mission_archives_sha256={name:sha(base/name) for name in
                    ('operation-endline.pk3','operation-sandstorm-preview.pk3') if (base/name).exists()})
    process = None
    try:
        with logpath.open('w') as log:
            process = subprocess.Popen(command,cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            controls = FileControls(control,logpath,process)
            def wait(check, label, timeout=40):
                end = time.monotonic()+timeout
                while time.monotonic()<end:
                    value = check()
                    if value:
                        return value
                    if process.poll() is not None:
                        raise RuntimeError('Engine exited: '+label)
                    time.sleep(.04)
                raise RuntimeError('Timed out: '+label)
            def ships():
                return controls.record('dropship_state','PP_DROPSHIP_STATE ')['dropships']
            def ship(name):
                return next((item for item in ships() if item['targetname']==name),None)
            def renders():
                return controls.record('dropship_render','PP_DROPSHIP_RENDER ')
            def pose(eye, target):
                delta = [b-a for a,b in zip(eye,target)]
                yaw = math.degrees(math.atan2(delta[1],delta[0]))
                pitch = -math.degrees(math.atan2(delta[2],math.hypot(*delta[:2])))
                origin = [eye[0],eye[1],eye[2]-32.]
                controls.console('cl_bench_pose 0 '+' '.join(str(v) for v in (*origin,pitch,yaw)))
                def settled():
                    camera = controls.record('camera_state','PP_QA_CAMERA ')
                    if max(abs(a-b) for a,b in zip(camera['origin'],eye))>.2:
                        return None
                    # Map loading can defer the ordinary benchmark teleport;
                    # clear its short freeze only after the new position lands.
                    controls.action('clear_teleport 0')
                    return camera if abs(camera['view'][0]-pitch)<.2 else None
                return wait(settled,'actual observer camera endpoint',15)
            def shot(name, camera=None, note=None):
                before = set((base/'scrnshot').glob('*.png'))
                controls.console('screenshot png')
                path = wait(lambda:next(iter(set((base/'scrnshot').glob('*.png'))-before),None),name)
                wait(lambda:path.read_bytes().endswith(b'IEND\xaeB`\x82'),name+' PNG')
                dest = shots/(name+'.png')
                shutil.copy2(path,dest)
                record = dict(name=name,screenshot=dest.name,sha256=sha(dest),camera=camera,
                              server=ships(),render=renders(),note=note)
                report['views'].append(record)
                (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
                print(dest,flush=True)
                return record
            def load(mapname):
                controls.console('map '+mapname)
                time.sleep(1.)
                wait(lambda:controls.state()['clients'][0]['spawned'],'spawn '+mapname,60)
                controls.action('observer 0')
                controls.action('clientcmd 0 god')
                time.sleep(.15)
            wait(lambda:controls.state()['clients'][0]['spawned'],'initial spawn',60)
            controls.action('observer 0')
            time.sleep(.15)
            if not args.missions_only:
                wait(lambda:ship('qa_ship'),'fixture ship')
                target = [-20,0,126]
                for name,eye in [('front',(200,-190,194)),('side',(-20,-240,169)),
                                 ('rear',(-250,180,184)),('overhead',(-40,-150,314)),
                                 ('underside',(-20,-220,84))]:
                    camera = pose(eye,target)
                    view = shot('gallery-'+name,camera)
                    models = {e['model'] for e in view['render']['entities']}
                    if models != {BODY,ROTOR}:
                        raise RuntimeError('Both friendly body and rotor were not rendered: '+str(models))
                first = renders();time.sleep(.034);second=renders()
                first_rotor = next(e for e in first['entities'] if e['model']==ROTOR)
                second_rotor = next(e for e in second['entities'] if e['model']==ROTOR)
                phase_delta = (second_rotor['angles'][1]-first_rotor['angles'][1])%360.
                report['checks'].append(dict(name='rotor advances while parked',first=first,second=second,
                    observed_yaw_delta=phase_delta,passed=.1<phase_delta<359.9))
                if not args.gallery_only:
                    controls.action('dropship_use qa_ship')
                    moving = wait(lambda:(item if (item:=ship('qa_ship')) and item['count']==1 and item['origin'][2]>100 else None),'native lift')
                    camera = pose((40,-470,250),(150,0,210))
                    shot('route-inbound',camera,note='Unpaused native path motion')
                    parked = wait(lambda:(item if (item:=ship('qa_ship')) and item['count']==2 else None),'inbound park')
                    report['checks'].append(dict(name='native inbound arrival',passed=parked['origin']==[400.,0.,220.],state=parked))
                    camera=pose((690,-230,365),(380,0,282));shot('route-parked',camera)
                    controls.action('dropship_use qa_ship')
                    departing=wait(lambda:(item if (item:=ship('qa_ship')) and item['count']==3 and item['origin'][1]>50 else None),'native outbound')
                    camera=pose((730,100,440),(400,220,370));shot('route-outbound',camera,note='Unpaused native path motion')
                    final=wait(lambda:(item if (item:=ship('qa_ship')) and item['count']==4 else None),'outbound park')
                    report['checks'].append(dict(name='native outbound arrival',passed=final['origin']==[400.,400.,400.],state=final))
            if args.missions:
                sys.path.insert(0,str(ROOT/'tools/maps'))
                from verify_sandkeep import BSP, SOLID
                def scene(mapname,shipname,name):
                    # Freeze only the photographic instant after observed native
                    # path movement. Camera selection reads the existing BSP.
                    controls.action('dropship_pause 1')
                    time.sleep(.15)
                    current=ship(shipname)
                    if not current:
                        raise RuntimeError('Ship departed before scene: '+name)
                    origin=current['origin'];target=[origin[0],origin[1],origin[2]+62]
                    bsp=BSP(maps[mapname])
                    yaw=current['angles'][1]
                    chosen=None
                    for distance in (200,240,280):
                        for height in (45,75,110):
                            for relative in (-90,90,-45,45,135,225,0,180):
                                angle=math.radians(yaw+relative)
                                eye=[target[0]+math.cos(angle)*distance,
                                     target[1]+math.sin(angle)*distance,target[2]+height]
                                if bsp.collision(eye,(-4,)*3,(4,)*3,SOLID) or bsp.segment_hits(eye,target):
                                    continue
                                chosen=eye
                                break
                            if chosen:break
                        if chosen:break
                    if not chosen:
                        raise RuntimeError('No unobstructed mission observer camera: '+name)
                    delta=[b-a for a,b in zip(chosen,target)]
                    camera_yaw=math.degrees(math.atan2(delta[1],delta[0]))
                    pitch=-math.degrees(math.atan2(delta[2],math.hypot(*delta[:2])))
                    controls.action('camera_pose '+' '.join(str(v) for v in (*chosen,pitch,camera_yaw)))
                    def camera_ready():
                        camera=controls.record('camera_state','PP_QA_CAMERA ')
                        return camera if max(abs(a-b) for a,b in zip(camera['origin'],chosen))<.2 and abs(camera['view'][0]-pitch)<.2 else None
                    camera=wait(camera_ready,'paused scene camera '+name)
                    wait(lambda: {e['model'] for e in renders()['entities']}=={BODY,ROTOR},'rendered scene body and rotor '+name)
                    view=shot(name,camera,note='Paused photographic instant at a native route position; private observer camera selected against existing BSP. Mission objective gates bypassed by native ship use only.')
                    view['paused_for_scene']=True
                    view['bsp_camera_clearance']=dict(eye=chosen,target=target,solid_hull_halfsize=4,line_of_sight_clear=True)
                    if {e['model'] for e in view['render']['entities']}!={BODY,ROTOR}:
                        raise RuntimeError('Scene lost visible transport: '+name)
                    controls.action('dropship_pause 0')
                    time.sleep(.1)
                for mapname, shipname in [('pp_sandstorm','insertion_flight'),('pp_endline','endline_insertion_flight')]:
                    load(mapname)
                    current=wait(lambda:ship(shipname),mapname+' insertion')
                    scene(mapname,shipname,mapname+'-insertion')
                    initial=ship(shipname)
                    controls.action('dropship_use '+shipname)
                    wait(lambda:(item if (item:=ship(shipname)) and item['count']==1 else None),mapname+' lifting')
                    time.sleep(.35)
                    moved=ship(shipname)
                    report['checks'].append(dict(name=mapname+' native insertion moves',passed=moved['origin']!=initial['origin'],before=initial,after=moved))
                    scene(mapname,shipname,mapname+'-insertion-flight')
                    if mapname=='pp_sandstorm':
                        controls.action('dropship_use extraction_ready')
                        landed=wait(lambda:(item if (item:=ship('extraction_ready')) and item['count']==2 else None),'Sandstorm extraction parked',40)
                        report['checks'].append(dict(name='Sandstorm extraction native arrival',passed=landed['origin']==[-456.,840.,280.] and landed['svflags']==0,state=landed))
                        scene(mapname,'extraction_ready','pp_sandstorm-extraction-parked')
                        controls.action('dropship_use extraction_ready')
                        wait(lambda:(item if (item:=ship('extraction_ready')) and item['count']==3 else None),'Sandstorm extraction liftoff')
                        time.sleep(.35)
                        outbound=ship('extraction_ready')
                        report['checks'].append(dict(name='Sandstorm extraction native departure',passed=outbound['origin']!=landed['origin'],before=landed,after=outbound))
                        scene(mapname,'extraction_ready','pp_sandstorm-extraction-flight')
            if not all(item['passed'] for item in report['checks']):
                raise RuntimeError('Native route or rotor check failed')
            report['passed']=True
            controls.console('quit')
            process.wait(timeout=20)
            report['returncode']=process.returncode
            report['complete']=True
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=5)
        if process:
            report['returncode']=process.returncode
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    main()
