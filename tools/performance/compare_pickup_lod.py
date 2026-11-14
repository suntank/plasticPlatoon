#!/usr/bin/env python3
"""Build a validated four-player Pi pickup-LOD JSON and self-contained HTML report.

The causal comparison uses one new binary/archive with r_pickup_lod 0 versus 1.
Historical captures remain descriptive context, never an equivalent-state A/B.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import hashlib
import html
import json
import os
from pathlib import Path
import statistics
from urllib.parse import quote

from analyze_pi_four_player import analyze_root, number

ROOT=Path(__file__).resolve().parents[2]
PERFORMANCE_PHASES={'spawn','roof-four-guns','bridge-four-guns','dm-separated','dm-four-guns-turning'}
ACTION_PHASES=PERFORMANCE_PHASES-{'spawn','dm-separated'}


def load(path, default=None):
    if not path or not Path(path).is_file():
        return default
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_state(state, attack=False):
    slots=(state or {}).get('slots',[])
    return len(slots)==4 and all(s.get('active') and s.get('device_connected') and
        not s.get('menu_open') and s.get('connection')==4 and s.get('snapshot') and
        (not attack or (s.get('cmd_buttons',0)&1)) for s in slots)


def clock_summary(phase):
    before=phase.get('game_clock_before') or {}
    after=phase.get('game_clock_after') or {}
    if any(number(d.get(k)) is None for d,k in ((before,'server_seconds'),(after,'server_seconds'),
                                               (before,'wall_monotonic'),(after,'wall_monotonic'))):
        return None
    game=after['server_seconds']-before['server_seconds']
    wall=after['wall_monotonic']-before['wall_monotonic']
    return dict(game_seconds=game,wall_seconds=wall,
                game_seconds_per_wall_second=game/wall if wall>0 else None,
                clock_resolution_seconds=1,
                scope='Whole phase including capture bookkeeping; integer player-list game clock.')


def capture_validation(capture, session, phase, plan):
    issues=[]
    phase_label=capture['capture'].split('/')[-1]
    performance=phase_label in PERFORMANCE_PHASES
    lod=number(capture['settings'].get('r_pickup_lod'))
    requested=(session.get('comparison') or plan.get('comparison') or {})
    if lod not in (0,1) or lod!=requested.get('lod'):
        issues.append('Actual r_pickup_lod does not match the comparison metadata')
    quality=requested.get('quality')
    if quality not in ('normal','low'):
        issues.append('Missing normal/low comparison quality')
    elif number(capture['settings'].get('gl1_picmip'))!=int(quality=='low') or number(capture['settings'].get('gl1_dynamic'))!=int(quality=='normal'):
        issues.append('Actual picmip/dynamic settings do not match quality')
    if not capture['actual_modes_match_requested']:
        issues.append('Map/player/mode settings failed validation')
    if performance:
        if capture['observed_views_per_frame']!=[4.0] or capture['unexpected_view_row_frames']:
            issues.append('Timed frames do not contain four complete local views')
        if capture['framebuffers']!=[('240','240')]:
            issues.append('Unexpected complete framebuffer dimensions')
        if len(capture['viewports'])!=4 or any((v['width'],v['height'])!=('120','120') for v in capture['viewports']):
            issues.append('Unexpected per-camera dimensions')
    elif capture['total_frames']<=0:
        issues.append('Functional capture has no recorded raw display frames')
    if not phase:
        issues.append('Capture has no completed metadata phase')
    else:
        if not phase.get('assertions') or not all(phase['assertions'].values()):
            issues.append('Runner assertions missing or failed')
        for when in ('state_before','state_after'):
            if not valid_state(phase.get(when),phase_label in ACTION_PHASES):
                issues.append('Four attached, active, unpaused clients/actions not verified: '+when)
        if phase_label in ('functional-four-deaths','functional-four-respawns'):
            alive=phase_label=='functional-four-respawns'
            slots=(phase.get('state_after') or {}).get('slots',[])
            if len(slots)!=4 or not all((s.get('gunindex',0)>0)==alive for s in slots):
                issues.append('Four-player death/respawn weapon state not verified')
            if phase.get('assertions',{}).get('all_four_weapon_state') is not True:
                issues.append('Runner death/respawn state assertion missing or failed')
        if capture['capture'].endswith('/bridge-four-guns'):
            if not phase.get('assertions',{}).get('all_four_carried') or not phase.get('assertions',{}).get('train_at_bridge'):
                issues.append('Endline train motion/bridge arrival not verified')
    if performance and capture['timed_frames']<20:
        issues.append('Fewer than twenty retained positive display intervals')
    return issues


def augment(root, warmup):
    metadata=load(root/'metadata.json',{})
    run=analyze_root(root,warmup,metadata.get('clock_ticks'))
    sessions={s['label']:s for s in metadata.get('sessions',[])}
    plans={s['label']:s for s in load(root/'plan.json',[])}
    run['runtime_hashes']=metadata.get('runtime_hashes',{})
    run['runtime_hashes_unchanged']=metadata.get('runtime_hashes_unchanged')
    run['metadata_path']=str(root/'metadata.json')
    for capture in run['captures']:
        label,phase_label=capture['capture'].split('/',1)
        session=sessions.get(label,{})
        phase=next((p for p in session.get('phases',[]) if p['label']==phase_label),{})
        capture['comparison']=session.get('comparison') or plans.get(label,{}).get('comparison',{})
        capture['phase_metadata']=phase
        capture['game_clock']=clock_summary(phase)
        capture['map_candidates_sha256']=session.get('map_candidates_sha256',{})
        capture['validation_issues']=capture_validation(capture,session,phase,plans.get(label,{}))
        capture['valid']=not capture['validation_issues']
        capture['performance_phase']=phase_label in PERFORMANCE_PHASES
        capture['functional_or_diagnostic']=not capture['performance_phase']
    return run


def mean(capture,key):
    return capture['metrics'].get(key,{}).get('mean')


def delta_percent(off,on):
    return 100*(on/off-1) if off is not None and on is not None and off else None


def paired(captures):
    groups=defaultdict(lambda:defaultdict(list))
    for capture in captures:
        if not capture['performance_phase']:
            continue
        quality=capture['comparison'].get('quality')
        phase=capture['capture'].split('/')[-1]
        lod=number(capture['settings'].get('r_pickup_lod'))
        if quality in ('normal','low') and lod in (0,1):
            groups[(capture['requested_map'],quality,phase)][int(lod)].append(capture)
    result=[]
    for (mapname,quality,phase),sides in sorted(groups.items()):
        problems=[]
        if any(len(sides.get(lod,[]))!=1 for lod in (0,1)):
            problems.append('Expected exactly one completed capture on each side')
        off=sides[0][0] if len(sides[0])==1 else None
        on=sides[1][0] if len(sides[1])==1 else None
        if off and on:
            if not off['valid'] or not on['valid']:
                problems.append('One or both captures failed validation')
            if off['runtime_hashes']!=on['runtime_hashes']:
                problems.append('Binary/archive runtime hashes differ between sides')
            if off['map_candidates_sha256']!=on['map_candidates_sha256']:
                problems.append('Map candidates differ between sides')
        row=dict(map=mapname,quality=quality,phase=phase,off=off,on=on,valid=not problems,
                 validation_issues=problems,
                 uncontrolled_random_spawn=mapname=='pp_sandbox2' and phase=='spawn')
        if off and on:
            row.update(fps_change_percent=delta_percent(off['throughput_fps'],on['throughput_fps']),
                       model_triangle_change_percent=delta_percent(mean(off,'model_triangles'),mean(on,'model_triangles')),
                       p95_change_percent=delta_percent(off['frame_ms']['p95'],on['frame_ms']['p95']),
                       lod1_p95_within_30fps=on['frame_ms']['p95']<=1000/30,
                       lod1_p95_within_20fps=on['frame_ms']['p95']<=50)
            if row['uncontrolled_random_spawn']:
                row['observed_fps_change_percent']=row['fps_change_percent']
                row['observed_model_triangle_change_percent']=row['model_triangle_change_percent']
                row['fps_change_percent']=row['model_triangle_change_percent']=None
                row['comparison_scope']='Uncontrolled random deathmatch spawn cameras; descriptive only, no causal LOD gain.'
        result.append(row)
    return result


def esc(value):
    return html.escape(str(value))


def fmt(value,digits=1):
    return f'{value:.{digits}f}' if value is not None else '—'


def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def relative_link(path,output,label):
    return '<a href="'+quote(os.path.relpath(path,output.parent))+'">'+esc(label)+'</a>'


def render(report,output,json_path):
    performance=[c for run in report['runs'] for c in run['captures'] if c['performance_phase']]
    valid_pairs=[p for p in report['pairs'] if p['valid']]
    action=[p for p in valid_pairs if p['phase'] in ACTION_PHASES]
    if not report['complete_and_valid']:
        conclusion='Some required captures or validation checks are incomplete. Treat this as a partial report.'
    elif action and all(not p['lod1_p95_within_20fps'] for p in action):
        conclusion='All tested four-player action samples still miss the 20 FPS P95 frame budget with pickup LOD enabled.'
    elif action and all(not p['lod1_p95_within_30fps'] for p in action):
        conclusion='Pickup LOD does not establish 30 FPS: every tested action sample still exceeds the 30 FPS P95 frame budget.'
    else:
        conclusion='See each scene’s complete-frame distribution; a short sample within budget does not establish sustained playability.'
    pieces=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Plastic Platoon — pickup LOD on Pi Zero 2 W</title><style>body{font:15px/1.55 system-ui,sans-serif;background:#f6f8f4;color:#1d2c22;max-width:1250px;margin:32px auto;padding:0 22px}h1{line-height:1.15}h2{margin-top:32px}table{border-collapse:collapse;background:white;width:100%;font-size:13px}th,td{padding:8px 10px;border-bottom:1px solid #d8e0d5;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#21452e;color:#fff}.scroll{overflow:auto}.callout{padding:15px 18px;background:#e3eddf;border-left:5px solid #527348}code{background:#e7eee2;padding:2px 4px}a{color:#245c37}.fine{font-size:13px;color:#425345}.qaimg{max-width:480px;width:100%;height:auto}li{margin:5px 0}</style><h1>Five pickup LODs: four-player Raspberry Pi Zero 2 W test</h1>',
            '<p class="callout"><b>'+esc(conclusion)+'</b></p>',
            '<p>The paired comparison uses the same new client, renderer, maps and asset archive. Only <code>r_pickup_lod</code> changes between 0 and 1. Normal and low detail remain separate. FPS is 1000 / mean complete-display frame time, including all four cameras and one presentation.</p>']
    headers=['Map / scene','Detail','LOD off FPS','LOD on FPS','FPS Δ','Off P95 ms','On P95 ms','On P99 ms','On >33.3 ms','On >50 ms','On P95 ≤50 ms','Valid']
    for group,title in (({'spawn'},'Spawn views'),(PERFORMANCE_PHASES-{'spawn'},'Active scenes and separated deathmatch views')):
        rows=[]
        for pair in report['pairs']:
            if pair['phase'] not in group:
                continue
            off,on=pair['off'],pair['on']
            rows.append([pair['map']+' / '+pair['phase'],pair['quality'],fmt(off['throughput_fps']) if off else '—',fmt(on['throughput_fps']) if on else '—',fmt(pair.get('fps_change_percent'))+'%',fmt(off['frame_ms']['p95']) if off else '—',fmt(on['frame_ms']['p95']) if on else '—',fmt(on['frame_ms']['p99']) if on else '—',fmt(on['over_33_333_ms_percent'])+'%' if on else '—',fmt(on['over_50_ms_percent'])+'%' if on else '—','yes' if pair.get('lod1_p95_within_20fps') else 'no',str(pair['valid'])])
        pieces += ['<h2>'+title+'</h2>',table(headers,rows)]
    pieces += ['<p class="fine">A 30 FPS budget is 33.333 ms; 20 FPS is 50 ms. P95 is the interval below which 95% of retained frames fall. “P95 ≤50 ms” describes this sample only. Screenshots precede timed capture; the first '+str(report['warmup_frames'])+' CSV rows are excluded.</p>',
               '<p class="fine">Deathmatch spawn cameras are random and are not matched between sessions. Their spawn rows are uncontrolled descriptive samples; percentage gains are suppressed. Fixed-pose deathmatch separated/firing scenes provide the feature comparison. Co-op spawn positions are deterministic, with live AI variation.</p>',
               '<h2>Geometry and renderer work</h2>']
    rows=[]
    for pair in report['pairs']:
        off,on=pair['off'],pair['on']
        if not off or not on:
            continue
        rows.append([pair['map']+' / '+pair['phase'],pair['quality'],fmt(mean(off,'model_triangles'),0),fmt(mean(on,'model_triangles'),0),fmt(pair['model_triangle_change_percent'])+'%',fmt(mean(off,'world_triangles'),0),fmt(mean(on,'world_triangles'),0),fmt(mean(off,'draws'),0),fmt(mean(on,'draws'),0),fmt(mean(off,'submit_ms')),fmt(mean(on,'submit_ms'))])
    pieces += [table(['Map / scene','Detail','Off model tris','On model tris','Model Δ','Off world tris','On world tris','Off draws','On draws','Off submit ms','On submit ms'],rows),
               '<p>LOD replaces five small world pickup meshes only when each camera is at least 256 units away and their original projected diameter is at most 12 pixels. Nearby pickups use their original models. Enemy/player bodies, held guns, first-person weapons, collision and mission populations are unchanged. Simpler meshes do not automatically remove draw calls. Model, world and draw counts above are per complete display frame.</p>',
               '<h2>Resources, slow frames and game clock</h2>']
    rows=[]
    for capture in performance:
        t=capture['telemetry'];vm=t['system_vm_counter_deltas'];clock=capture['game_clock']
        rows.append([capture['capture'],fmt(capture['throughput_fps']),fmt(capture['frame_ms']['p99']),fmt(t['process_cpu']['mean_percent_of_one_core']),fmt(capture['rss_peak_mib']),fmt(t['process_swap_max_mib']),fmt(t['temperature_max_c']),','.join(t['throttled_flags_observed']) or '—',vm['oom_kills'] if vm['oom_kills'] is not None else '—',fmt(clock['game_seconds_per_wall_second'],2) if clock else '—',fmt(mean(capture,'server_ms')),fmt(mean(capture,'present_ms'))])
    pieces += [table(['Capture','FPS','P99 ms','CPU % one core','Sampled RSS MiB','Sampled swap MiB','Max °C','Throttle flags','Sampled OOM Δ','Game / wall','Server ms','Present ms'],rows),
               '<p class="fine">CPU 100% means one occupied core, including process threads. RSS and swap maxima are sampled, not exact peaks. OOM deltas cover telemetry sample intervals. Nested CPU timing columns must not be added. Driver submission can include waiting, so it is not an isolated GPU execution measurement. The integer game clock has one-second resolution and includes phase bookkeeping.</p>',
               '<p>Below ten display frames per second, this listen client can advance its fixed 100 ms server ticks more slowly than wall time. A higher displayed FPS therefore needs to be considered alongside the game/wall ratio. Each player receives a 120×120 viewport on the tested 240×240 panel; legibility remains a separate limitation.</p>',
               '<h2>Validation and evidence</h2>']
    geometry_proof=next((q['data'] for q in report['qa'] if q['data'].get('sizes') and q['data'].get('scenes')),None)
    if geometry_proof:
        asset_rows=[]
        for name,size in geometry_proof['sizes'].items():
            checks=geometry_proof['scenes'][name].get('checks',{})
            asset_rows.append([name,size['high'],size['low'],str(checks.get('near_unchanged')),
                               str(checks.get('far_reduction_exact')),str(checks.get('missing_falls_back'))])
        pieces.append(table(['Pickup','Original tris','Distant LOD tris','Near unchanged','Far delta exact','Missing-file fallback'],asset_rows))
        pieces.append('<p class="fine">Isolated fixtures contain one pickup and two actual local cameras at different distances. Per-view counters identify the exact mesh reduction; restart, map reload and returning LOD off are also checked. Canonical model hashes and tested archive hashes are retained in the linked QA JSON.</p>')
    for run in report['runs']:
        pieces.append('<p>'+relative_link(Path(run['metadata_path']),output,Path(run['root']).name+' metadata')+': shell restored='+esc(run['shell_restored'])+', saves unchanged='+esc(run['save_hashes_unchanged'])+', installed package unchanged='+esc(run['package_hashes_unchanged'])+', staged runtime unchanged='+esc(run['runtime_hashes_unchanged'])+'.</p>')
    for proof in report['qa']:
        pieces.append('<p>'+relative_link(Path(proof['path']),output,Path(proof['path']).parent.name+' QA')+': passed='+esc(proof['passed'])+'. '+esc(proof.get('scope',''))+'</p>')
        image=Path(proof['path']).parent/'contact-sheet.png'
        if image.is_file():
            pieces.append('<img class="qaimg" alt="Actual pickup LOD comparison captures" src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'">')
    if report.get('deployment'):
        deployment=report['deployment']
        pieces.append('<p>'+relative_link(Path(deployment['path']),output,'Deployment record')+': installed='+esc(deployment['data'].get('installed'))+'; original archive payloads unchanged='+esc(deployment['data'].get('original_assets_unchanged'))+'.</p>')
    pieces += ['<p>Functional checks retain four connected, unpaused clients and their actual command states. Endline action results require all four camera positions to move with the train and its entity origin to reach the bridge. Deathmatch includes four deaths and respawns. Three virtual SDL controllers plus the handheld controller establish assignments; secondary held fields are supplied by a test-only driver. This does not measure four physical USB/Bluetooth event streams.</p>',
               '<p>Live AI, shots, camera state and game-clock progression can differ between fresh sessions. There is one pair per scene/detail setting, without repeated randomized trials or a confidence interval. Short tests do not establish a complete human playthrough, HDMI performance or ten-minute reliability.</p>']
    if report['validation_issues']:
        pieces.append('<ul>'+''.join('<li>'+esc(v)+'</li>' for v in report['validation_issues'])+'</ul>')
    pieces.append('<h2>Earlier binary: historical context</h2><p>These earlier valid captures use a previous binary/archive and live scene. They are shown separately; their FPS differences must not be attributed solely to this LOD change. The paired new-build LOD-off captures above provide the feature baseline.</p>')
    pieces.append(table(['Earlier capture','Map','FPS','P95 ms','Model tris'],[[c['capture'],c['requested_map'],fmt(c['throughput_fps']),fmt(c['frame_ms']['p95']),fmt(mean(c,'model_triangles'),0)] for c in report['historical']]))
    pieces.append('<p>'+relative_link(json_path,output,'Complete JSON, settings, hashes and validation')+'</p></html>')
    return ''.join(pieces)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('roots',type=Path,nargs='+',help='Completed Pi suite directories')
    p.add_argument('--historical',type=Path,default=ROOT/'build/pi-four-player-20261112/analysis.json')
    p.add_argument('--qa',type=Path,action='append',default=[])
    p.add_argument('--deployment',type=Path)
    p.add_argument('--warmup',type=int,default=10)
    p.add_argument('--output',type=Path,required=True,help='Self-contained HTML report')
    p.add_argument('--json',type=Path,help='JSON output; default same basename as HTML')
    a=p.parse_args()
    if a.warmup<0:
        p.error('warmup must be nonnegative')
    a.output=a.output.resolve();json_path=(a.json or a.output.with_suffix('.json')).resolve()
    runs=[augment(root.resolve(),a.warmup) for root in a.roots]
    captures=[];issues=[]
    for run in runs:
        for capture in run['captures']:
            capture['runtime_hashes']=run['runtime_hashes'];captures.append(capture)
            issues += [capture['capture']+': '+v for v in capture['validation_issues']]
        for key in ('shell_restored','save_hashes_unchanged','package_hashes_unchanged','runtime_hashes_unchanged'):
            if run.get(key) is not True:
                issues.append(Path(run['root']).name+': '+key+' not verified')
        if run['run_error'] or run['ended'] is None:
            issues.append(Path(run['root']).name+': run incomplete or reported error')
    pairs=paired(captures)
    for pair in pairs:
        issues += [pair['map']+'/'+pair['quality']+'/'+pair['phase']+': '+v for v in pair['validation_issues']]
    required={(m,q,phase) for m,phase_list in {'pp_sandstorm':['spawn','roof-four-guns'],
                'pp_endline':['spawn','bridge-four-guns'],
                'pp_sandbox2':['spawn','dm-separated','dm-four-guns-turning']}.items()
                for q in ('normal','low') for phase in phase_list}
    observed={(r['map'],r['quality'],r['phase']) for r in pairs if r['valid']}
    for missing in sorted(required-observed):
        issues.append('Missing valid pair: '+' / '.join(missing))
    historical=[]
    for run in (load(a.historical,{}) or {}).get('runs',[]):
        for capture in run.get('captures',[]):
            if not capture.get('excluded_from_playability') and (capture.get('primary_comparison') or capture['capture'].endswith('/spawn-valid-controllers')):
                historical.append(capture)
    proofs=[]
    for path in a.qa:
        data=load(path,{})
        proofs.append(dict(path=str(path.resolve()),passed=data.get('passed'),sha256=sha(path),
                           scope=data.get('input_scope') or 'Renderer/asset correctness proof; inspect source for backend and device.',
                           data=data))
        if data.get('passed') is not True:
            issues.append('QA proof did not pass: '+str(path))
    deployment=dict(path=str(a.deployment.resolve()),data=load(a.deployment,{}),sha256=sha(a.deployment)) if a.deployment else None
    for proof in proofs:
        archive=proof['data'].get('inputs_sha256',{}).get('baseq2/plastic-platoon.pk3')
        if archive and any(run['runtime_hashes'].get('baseq2/plastic-platoon.pk3')!=archive for run in runs):
            issues.append('Tested runtime archive differs from QA archive: '+proof['path'])
    if deployment:
        installed=deployment['data'].get('installed_hashes') or deployment['data'].get('stage_hashes') or {}
        for run in runs:
            for name in ('quake2','ref_gl1.so','baseq2/game.so','baseq2/plastic-platoon.pk3'):
                if installed.get(name) and run['runtime_hashes'].get(name)!=installed[name]:
                    issues.append('Runtime differs from deployment record: '+name)
    report=dict(schema=1,warmup_frames=a.warmup,complete_and_valid=not issues,validation_issues=issues,
                causal_comparison='Same new binary/assets with r_pickup_lod 0 versus 1; one live pair per setting.',
                runs=runs,pairs=pairs,qa=proofs,deployment=deployment,historical=historical,
                historical_path=str(a.historical.resolve()))
    a.output.parent.mkdir(parents=True,exist_ok=True);json_path.parent.mkdir(parents=True,exist_ok=True)
    json_path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    a.output.write_text(render(report,a.output,json_path))
    print(json.dumps(dict(html=str(a.output),json=str(json_path),valid=report['complete_and_valid'],
                          pairs=len(pairs),issues=len(issues)),indent=2))


if __name__=='__main__':
    main()
