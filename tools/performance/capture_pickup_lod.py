#!/usr/bin/env python3
"""Verify five pickup LODs in real mixed near/far views and isolated runtimes.

Host captures are functional/visual evidence, never Raspberry Pi timings. Each
fixture contains one pickup, so the far-view triangle difference identifies
that pickup rather than inferring its cost from a populated mission.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import statistics
import struct
import subprocess
import time
import zipfile

from make_fixture import box, entity

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    'ammo_bullets': 'models/items/ammo/bullets/medium/tris.md2',
    'ammo_shells': 'models/items/ammo/shells/medium/tris.md2',
    'ammo_grenades': 'models/items/ammo/grenades/medium/tris.md2',
    'item_armor_shard': 'models/items/armor/shard/tris.md2',
    'item_health_small': 'models/items/healing/stimpack/tris.md2',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command_triangles(data):
    header = struct.unpack_from('<17i', data)
    at, limit, triangles = header[15], header[15] + header[9]*4, 0
    while at+4 <= limit:
        count = struct.unpack_from('<i', data, at)[0]
        at += 4
        if not count:
            return triangles
        triangles += abs(count)-2
        at += abs(count)*12
    raise ValueError('Unterminated MD2 command stream')


def fixture(classname):
    walls = [((-1408,-512,-32),(256,512,0)), ((-1408,-512,320),(256,512,352)),
             ((-1440,-544,-32),(-1408,544,352)), ((256,-544,-32),(288,544,352)),
             ((-1408,-544,-32),(256,-512,352)), ((-1408,512,-32),(256,544,352))]
    text = '{\n"classname" "worldspawn"\n"message" "Isolated pickup LOD fixture"\n'
    text += ''.join(box(lo, hi, 'sandbox/sand1') for lo, hi in walls) + '}\n'
    for i, y in enumerate((-320, -256)):
        text += entity(dict(classname='info_player_start' if not i else 'info_player_coop',
                            origin=f'-1200 {y} 24', angle='0'))
    for x in (-1200, -800, -400, 128):
        for y in (-240, 240):
            text += entity(dict(classname='light', origin=f'{x} {y} 224', light='500'))
    return text + entity(dict(classname=classname, origin='0 0 32'))


def compile_fixtures(output, tool, basedir):
    maps = output/'maps'
    maps.mkdir(parents=True, exist_ok=True)
    result = {}
    for index, classname in enumerate(TARGETS):
        name = f'pp_pickup_lod_{index}'
        source = maps/(name+'.map')
        source.write_text(fixture(classname))
        bsp = source.with_suffix('.bsp')
        if not bsp.exists():
            for stage in ('bsp', 'vis', 'rad'):
                cmd = [str(tool), '-'+stage, '-threads', '2', '-basedir', str(basedir),
                       str(source if stage == 'bsp' else bsp)]
                run = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=120)
                (maps/(name+'-'+stage+'.log')).write_text(run.stdout)
                if run.returncode:
                    raise RuntimeError(f'{name} {stage} failed; inspect retained log')
        result[classname] = bsp
    return result


def stage_runtime(source, output, maps, missing=False):
    runtime = output/('runtime-missing' if missing else 'runtime')
    runtime.mkdir(exist_ok=False)
    base = runtime/'baseq2'
    (base/'maps').mkdir(parents=True)
    for name in ('quake2', 'ref_gl1.so', 'ref_gl3.so', 'ref_gles1.so', 'ref_soft.so'):
        if (source/name).exists():
            shutil.copy2(source/name, runtime/name)
    shutil.copy2(source/'baseq2/game.so', base/'game.so')
    archive = source/'baseq2/plastic-platoon.pk3'
    if missing:
        excluded = {str(Path(path).with_name('lod1.md2')) for path in TARGETS.values()}
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(base/archive.name, 'w', zipfile.ZIP_DEFLATED) as dst:
            for entry in src.infolist():
                if entry.filename not in excluded:
                    dst.writestr(entry, src.read(entry.filename))
    else:
        shutil.copy2(archive, base/archive.name)
    for bsp in maps.values():
        shutil.copy2(bsp, base/'maps'/bsp.name)
    return runtime


def virtual_pad_driver(output):
    """Attach two real SDL virtual devices; no engine state or symbol offsets."""
    source = output/'virtual-pads.c'
    library = output/'virtual-pads.so'
    source.write_text(r'''#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
static int attached;
int SDL_Init(Uint32 flags) {
    static int (*real_init)(Uint32);
    if (!real_init) real_init=dlsym(RTLD_NEXT,"SDL_Init");
    int result=real_init(flags);
    if (!result && !attached && (flags&SDL_INIT_GAMECONTROLLER)) {
        attached=1;
        for(int i=0;i<2;i++) {
            SDL_VirtualJoystickDesc d={0}; d.version=SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
            d.type=SDL_JOYSTICK_TYPE_GAMECONTROLLER;d.naxes=SDL_CONTROLLER_AXIS_MAX;
            d.nbuttons=SDL_CONTROLLER_BUTTON_MAX;d.button_mask=(1U<<SDL_CONTROLLER_BUTTON_MAX)-1;
            d.axis_mask=(1U<<SDL_CONTROLLER_AXIS_MAX)-1;d.name="Pickup LOD QA Pad";
            int device=SDL_JoystickAttachVirtualEx(&d);SDL_Joystick *pad=SDL_JoystickOpen(device);
            if(device<0 || !pad){fprintf(stderr,"PP_LOD_PAD_ERROR %s\n",SDL_GetError());exit(90);}
            SDL_JoystickSetVirtualAxis(pad,SDL_CONTROLLER_AXIS_TRIGGERLEFT,-32768);
            SDL_JoystickSetVirtualAxis(pad,SDL_CONTROLLER_AXIS_TRIGGERRIGHT,-32768);
            fprintf(stderr,"PP_LOD_PAD_CONNECTED %d\n",SDL_IsGameController(device));
        }
    }
    return result;
}
''')
    flags = subprocess.check_output(['sdl2-config','--cflags','--libs'],text=True).split()
    subprocess.run(['cc','-std=c11','-shared','-fPIC','-O2',str(source),'-ldl',*flags,'-o',str(library)],check=True)
    return library


def exercise(runtime, mapname, output, renderer, backend, missing=False,
             shadows=0, virtual_pads=None):
    output.mkdir(exist_ok=False)
    base = runtime/'baseq2'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    token = secrets.token_hex(16)
    settings = dict(vid_renderer=renderer, r_mode=-1, r_customwidth=240,
                    r_customheight=240, vid_fullscreen=0, r_vsync=0, vid_maxfps=30,
                    cl_maxfps=60, s_initsound=0, r_perf=1, r_perf_gpu=0,
                    r_shadows=shadows, cl_gun=0, cheats=1, logfile=2,
                    rcon_password=token, r_pickup_lod=0, con_notifytime=0)
    cfg = ''.join(f'set {k} "{v}"\n' for k,v in settings.items())
    cfg += f'cl_bench_local 2 {mapname}\n'
    (base/'lod-qa.cfg').write_text(cfg)
    command = [str(runtime/'quake2'), '-portable', '-datadir', str(runtime),
               '+set', 'ip', '127.0.0.1', '+set', 'port', str(port),
               '+set', 'vid_renderer', renderer, '+set', 'r_mode', '-1',
               '+set', 'r_customwidth', '240', '+set', 'r_customheight', '240',
               '+set', 's_initsound', '0', '+exec', 'lod-qa.cfg']
    if backend == 'xvfb':
        command = ['xvfb-run', '-a', '-s', '-screen 0 240x240x24'] + command
    env = dict(os.environ, XDG_CACHE_HOME=str(runtime/'cache'))
    if virtual_pads:
        env['LD_PRELOAD']=str(virtual_pads)
    if backend == 'offscreen':
        env.update(SDL_VIDEODRIVER='offscreen', LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='2')
    log = (output/'console.log').open('w')
    process = subprocess.Popen(command, cwd=runtime, env=env, stdout=log,
                               stderr=subprocess.STDOUT, start_new_session=True)
    actions, phases = [], {}

    def wait(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Engine exited {process.returncode}; inspect {output}')
            time.sleep(min(.1, max(.001, deadline-time.monotonic())))

    def cmd(command):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as request:
            request.settimeout(.8)
            request.sendto(b'\xff'*4+b'rcon '+token.encode()+b' '+command.encode()+b'\n', ('127.0.0.1',port))
            try:
                reply = request.recv(65535)[4:].decode(errors='replace')
            except socket.timeout:
                reply = ''
        actions.append(dict(command=command, reply=reply))
        return reply

    def poses():
        # Both look at the same pickup. The far view also sees the near
        # player's model, whose geometry is constant in both LOD settings.
        cmd('cl_bench_pose 0 -96 64 24 0 -33.6900675')
        cmd('cl_bench_pose 1 -1024 -64 24 0 3.5763344')
        wait(.5)

    def capture(label, lod):
        cmd(f'set r_pickup_lod {lod}')
        poses()
        shots = set((base/'scrnshot').glob('*.png'))
        cmd('screenshot png')
        wait(.3)
        newshots = set((base/'scrnshot').glob('*.png'))-shots
        if len(newshots) != 1:
            raise RuntimeError('Expected one new screenshot')
        shutil.copy2(newshots.pop(), output/(label+'.png'))
        label = mapname+'-'+label
        cmd('cl_perf_start '+label)
        wait(1.2)
        cmd('cl_perf_stop')
        wait(.1)
        path = base/'perf'/(label+'-views.csv')
        views = list(csv.DictReader(path.open()))
        # Drop the first five distinct display frames in this capture.
        keep = set(sorted({int(v['frame']) for v in views})[5:])
        views = [v for v in views if int(v['frame']) in keep]
        if not views or {int(v['slot']) for v in views} != {0,1}:
            raise RuntimeError('Both local views must have retained frames')
        if any((int(v['width']),int(v['height'])) != (240,120) for v in views):
            raise RuntimeError('Unexpected mixed-view dimensions')
        result = {str(slot): dict(model_triangles=statistics.median(float(v['model_triangles']) for v in views if int(v['slot'])==slot),
                                 origin=[statistics.median(float(v[k]) for v in views if int(v['slot'])==slot) for k in ('x','y','z')]) for slot in range(2)}
        phases[label] = result
        for suffix in ('-frames.csv','-views.csv','-settings.txt'):
            shutil.copy2(base/'perf'/(label+suffix), output/(label+suffix))
        return result

    try:
        deadline = time.monotonic()+60
        while True:
            status = cmd('status')
            clients = [l for l in status.splitlines() if '[loopback-client' in l]
            if len(clients)==2 and all('CNCT' not in l and 'ZMBI' not in l for l in clients):
                break
            if time.monotonic()>deadline:
                raise RuntimeError('Local clients did not connect')
            wait(.2)
        wait(1)
        off = capture('off',0)
        on = capture('on',1)
        if not missing:
            cmd('vid_restart');wait(2)
            restarted = capture('restarted',1)
            cmd('gamemap '+mapname);wait(2)
            reloaded = capture('reloaded',1)
            again = capture('off-again',0)
        else:
            restarted = reloaded = again = None
        return dict(off=off,on=on,restarted=restarted,reloaded=reloaded,off_again=again,
                    phases=phases,command=command)
    finally:
        if process.poll() is None:
            cmd('quit')
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=4)
        log.close()
        (output/'actions.json').write_text(json.dumps(actions,indent=2)+'\n')
        (base/'lod-qa.cfg').write_text(cfg.replace(token,'LOCAL_RCON_TOKEN'))
        text = (output/'console.log').read_text(errors='replace')
        (output/'console.log').write_text(text.replace(token,'LOCAL_RCON_TOKEN'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'release')
    parser.add_argument('--q2tool',type=Path,default=Path('/home/austin-morgan/q2tools-220/build/q2tool'))
    parser.add_argument('--compile-assets',type=Path,default=ROOT/'baseq2')
    parser.add_argument('--output',type=Path,default=ROOT/'build/pi-pickup-lod-20261112/pickup-lod-visual-qa')
    parser.add_argument('--renderer',choices=('gl1','gl3'),default='gl1')
    parser.add_argument('--backend',choices=('offscreen','xvfb','current'),default='offscreen')
    parser.add_argument('--original-hashes',type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.source = args.source.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    maps = compile_fixtures(args.output,args.q2tool,args.compile_assets)
    with zipfile.ZipFile(args.source/'baseq2/plastic-platoon.pk3') as archive:
        originals = {path:digest(archive.read(path)) for path in TARGETS.values()}
        sizes = {}
        for classname,path in TARGETS.items():
            lowpath = str(Path(path).with_name('lod1.md2'))
            sizes[classname] = dict(high=command_triangles(archive.read(path)),
                                   low=command_triangles(archive.read(lowpath)) if lowpath in archive.namelist() else None)
    reference = args.original_hashes or args.output/'original-model-hashes.json'
    if not reference.exists():
        reference.write_text(json.dumps(originals,indent=2)+'\n')
    if json.loads(reference.read_text()) != originals:
        raise RuntimeError('Canonical pickup models changed versus original hash reference')
    if args.prepare_only:
        print(json.dumps(dict(prepared_maps={k:str(v) for k,v in maps.items()},original_reference=str(reference)),indent=2))
        return
    if any(v['low'] is None for v in sizes.values()):
        raise RuntimeError('Package is missing one or more five pickup LOD models')
    report = dict(passed=False,renderer=args.renderer,backend=args.backend,
                  host_timings_not_pi=True,original_hashes=originals,
                  original_reference=str(reference),sizes=sizes,checks=[],scenes={},
                  inputs_sha256={name:digest((args.source/name).read_bytes()) for name in
                                ('quake2','ref_'+args.renderer+'.so','baseq2/game.so','baseq2/plastic-platoon.pk3')},
                  fixture_sha256={name:digest(path.read_bytes()) for name,path in maps.items()})
    try:
        pad_driver=virtual_pad_driver(args.output)
        normal = stage_runtime(args.source,args.output,maps)
        absent = stage_runtime(args.source,args.output,maps,True)
        for classname,bsp in maps.items():
            expected = sizes[classname]['high']-sizes[classname]['low']
            result = exercise(normal,bsp.stem,args.output/classname,args.renderer,args.backend,virtual_pads=pad_driver)
            missing = exercise(absent,bsp.stem,args.output/(classname+'-missing'),args.renderer,args.backend,True,virtual_pads=pad_driver)
            checks = dict(near_unchanged=result['off']['0']['model_triangles']==result['on']['0']['model_triangles'],
                          far_reduction_exact=result['off']['1']['model_triangles']-result['on']['1']['model_triangles']==expected,
                          restart_preserved=result['restarted']==result['on'],
                          map_reload_preserved=result['reloaded']==result['on'],
                          off_restored=result['off_again']==result['off'],
                          missing_falls_back=missing['off']==missing['on'] and missing['off']==result['off'])
            report['scenes'][classname] = dict(result=result,missing=missing,expected_far_triangle_reduction=expected,checks=checks)
            log_text=(args.output/classname/'console.log').read_text(errors='replace')
            report['scenes'][classname]['context']={key:re.findall(r'^'+key+r': (.+)$',log_text,re.M)[0]
                                                 for key in ('GL_VENDOR','GL_RENDERER','GL_VERSION')
                                                 if re.findall(r'^'+key+r': (.+)$',log_text,re.M)}
            report['checks'].append(dict(classname=classname,passed=all(checks.values()),checks=checks))
            print(classname+': '+json.dumps(checks),flush=True)
        report['passed'] = all(c['passed'] for c in report['checks'])
        if not report['passed']:
            raise RuntimeError('LOD runtime verification failed; inspect report')
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(args.output/'report.json')


if __name__ == '__main__':
    main()
