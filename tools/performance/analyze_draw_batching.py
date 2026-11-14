#!/usr/bin/env python3
"""Summarize focused per-class Pi profiles and validate renderer-toggle pairs.

Inline IDs are read only from per-view CSV rows. Complete-frame model-ID sums
are deliberately ignored. Flush causes overlap and are never summed as draws.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import copy
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import struct
import sys
from urllib.parse import quote
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/performance'))
from analyze_pi_four_player import analyze_root,number,stats,values
from compare_pickup_lod import PERFORMANCE_PHASES,ACTION_PHASES,capture_validation,clock_summary

CLASSES=('world','inline','pickup','npc_body','npc_held','player_body','player_held',
         'viewweapon','alias_other','sprite','effects','other')
CAUSES=('type','color','lightmap','flags','alpha','vbo','capacity','explicit')
MACHINEGUN='models/weapons/v_machn/tris.md2'


def load(path,default=None):
    return json.loads(Path(path).read_text()) if path and Path(path).is_file() else default


def readcsv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))


def mean(c,key):return c['metrics'].get(key,{}).get('mean')
def fmt(n,digits=2):return f'{n:.{digits}f}' if n is not None else '—'


def inline_names(mapname,map_data):
    """Resolve *N to classname/targetname from the unchanged local BSP."""
    member='maps/'+mapname+'.bsp';data=None
    for archive in sorted(map_data.glob('*.pk3')):
        with zipfile.ZipFile(archive) as z:
            if member in z.namelist():data=z.read(member)
    loose=map_data/member
    if data is None and loose.is_file():data=loose.read_bytes()
    if data is None:return {},None
    offset,size=struct.unpack_from('<ii',data,8)
    result={}
    for block in re.findall(r'\{([^}]*)\}',data[offset:offset+size].decode('latin1')):
        entity=dict(re.findall(r'"([^"]*)"\s*"([^"]*)"',block))
        model=entity.get('model','')
        if re.fullmatch(r'\*\d+',model):
            result[int(model[1:])]=' '.join(filter(None,(entity.get('classname'),entity.get('targetname'))))
    return result,hashlib.sha256(data).hexdigest()


def profile_details(path,capture,warmup,map_data):
    all_frames=readcsv(path)
    frames=[r for r in all_frames[warmup:] if (number(r.get('frame_ms')) or 0)>0]
    retained={r['frame'] for r in frames}
    views=[r for r in readcsv(path.with_name(path.name.replace('-frames.csv','-views.csv'))) if r['frame'] in retained]
    classes={name:{kind:stats(values(frames,'dp_'+name+'_'+kind)) for kind in ('draws','ms')} for name in CLASSES}
    flushes={name:stats(values(frames,'dp_flush_'+name)) for name in CAUSES}
    names,map_sha=inline_names(capture['requested_map'],map_data)
    expected=set(capture.get('map_candidates_sha256',{}).values())
    if expected and map_sha not in expected:names={}
    grouped=defaultdict(lambda:dict(draws=0.0,ms=0.0,occurrences=0,slots=set()))
    for view in views:
        for rank in range(4):
            prefix=f'dp_inline_top{rank}_'
            model=number(view.get(prefix+'model'))
            if model is None or model<=0 or int(model)!=model:continue
            row=grouped[int(model)]
            row['draws']+=max(0,number(view.get(prefix+'draws')) or 0)
            row['ms']+=max(0,number(view.get(prefix+'ms')) or 0)
            row['occurrences']+=1;row['slots'].add(int(view['slot']))
    top=[]
    for model,row in grouped.items():
        top.append(dict(model=model,label=names.get(model,'*'+str(model)),
                        draws_per_display=row['draws']/len(frames) if frames else None,
                        ms_per_display=row['ms']/len(frames) if frames else None,
                        top_four_occurrences=row['occurrences'],slots=sorted(row['slots'])))
    top.sort(key=lambda r:r['ms_per_display'] or 0,reverse=True)
    aggregate_draws=mean(capture,'draws')
    class_total=sum(v['draws']['mean'] for v in classes.values() if v['draws'])
    return dict(classes=classes,flushes_nonexclusive=flushes,top_inline=top,
                class_draw_sum=class_total,aggregate_draws=aggregate_draws,
                class_draw_sum_matches=aggregate_draws is not None and abs(class_total-aggregate_draws)<.01,
                enabled=stats(values(frames,'dp_enabled')),
                inline_model_labels_sha256=map_sha,
                inline_scope='Only four costliest inline models per view are retained; grouped contributions are censored below that rank.')


def augment(root,warmup,map_data):
    metadata=load(root/'metadata.json',{});run=analyze_root(root,warmup,metadata.get('clock_ticks'))
    sessions={s['label']:s for s in metadata.get('sessions',[])}
    plans={s['label']:s for s in load(root/'plan.json',[])}
    run['runtime_hashes']=metadata.get('runtime_hashes',{})
    run['runtime_hashes_unchanged']=metadata.get('runtime_hashes_unchanged')
    run['runtime_source']=metadata.get('runtime_source')
    run['input_driver_sha256']=metadata.get('input_driver_sha256')
    run['clock_ticks']=metadata.get('clock_ticks')
    run['session_preparation']={label:{key:s[key] for key in ('deathmatch_preparation','functional_respawn_preparation') if key in s}
                                for label,s in sessions.items()}
    run['metadata_path']=str(root/'metadata.json')
    for c in run['captures']:
        label,phase_label=c['capture'].split('/',1);s=sessions.get(label,{})
        comparison=s.get('comparison') or plans.get(label,{}).get('comparison',{})
        phase=next((p for p in s.get('phases',[]) if p['label']==phase_label),{})
        c.update(comparison=comparison,phase_metadata=phase,
                 runtime_hashes=run['runtime_hashes'],game_clock=clock_summary(phase),
                 map_candidates_sha256=s.get('map_candidates_sha256',{}),
                 performance_phase=phase_label in PERFORMANCE_PHASES)
        validation_session=copy.deepcopy(s)
        validation_session['comparison']=dict(comparison,lod=1)
        issues=capture_validation(c,validation_session,phase,plans.get(label,{}))
        equipped=phase_label in ('roof-four-guns','boarding-clear-floor','bridge-four-guns','dm-separated','dm-four-guns-turning') or (c['requested_map']=='pp_sandbox2' and bool(comparison.get('spawn_scope')) and phase_label=='spawn')
        legacy_coop=bool(comparison.get('kind')=='profile' and c['requested_map']!='pp_sandbox2')
        identity_notes=[]
        if c['performance_phase'] or equipped:
            for when in ('state_before','state_after'):
                slots=(phase.get(when) or {}).get('slots',[])
                indices=[slot.get('gunindex',0) for slot in slots]
                if len(indices)!=4 or not all(index>0 for index in indices):
                    issues.append('All four players are not alive with visible weapons: '+when)
                if equipped:
                    if len(indices)!=4 or len(set(indices))!=1 or not all(index>0 for index in indices):
                        issues.append('All four equipped weapon indices do not match: '+when)
                    if len(slots)==4 and all('gunmodel' in slot for slot in slots):
                        if any(slot['gunmodel']!=MACHINEGUN for slot in slots):issues.append('Machinegun model path not verified: '+when)
                    elif legacy_coop:
                        identity_notes.append('Legacy co-op driver lacks model paths; matching positive map-dependent indices and the completed equip sequence are retained as indirect identity evidence.')
                    else:issues.append('Explicit gunmodel proof missing for fixed weapon workload: '+when)
        if c['requested_map']=='pp_sandbox2' and comparison.get('spawn_scope'):
            if not s.get('deathmatch_preparation',{}).get('passed'):
                issues.append('Sequential startup respawn/equipment preparation not verified')
            if phase_label=='functional-four-respawns' and not s.get('functional_respawn_preparation',{}).get('passed'):
                issues.append('Sequential normal-weapon functional respawn preparation not verified')
        c['weapon_identity_notes']=list(dict.fromkeys(identity_notes))
        expected_profile=1 if comparison.get('kind')=='profile' else 0
        if number(c['settings'].get('r_drawprofile'))!=expected_profile:
            issues.append('Actual r_drawprofile does not match profile/performance role')
        if number(c['settings'].get('r_pickup_lod'))!=1:issues.append('Pickup LOD must stay enabled')
        if comparison.get('kind')=='paired':
            if number(c['settings'].get(comparison.get('feature_cvar','')))!=comparison.get('feature'):
                issues.append('Actual optimization toggle does not match comparison metadata')
        elif comparison.get('kind')=='profile':
            c['profile']=profile_details(Path(c['source']),c,warmup,map_data)
            if not c['profile']['enabled'] or c['profile']['enabled']['mean']!=4:
                issues.append('Four enabled per-view draw profilers not verified')
            if not c['profile']['class_draw_sum_matches']:
                issues.append('Per-class draw sum does not equal aggregate draw count')
        else:issues.append('Missing comparison kind')
        c['validation_issues']=issues;c['valid']=not issues
    return run


def pairs(captures):
    groups=defaultdict(lambda:defaultdict(list))
    for c in captures:
        comp=c['comparison']
        if comp.get('kind')!='paired' or not c['performance_phase']:continue
        feature=number(c['settings'].get(comp.get('feature_cvar','')))
        if feature in (0,1):groups[(c['requested_map'],comp['quality'],c['capture'].split('/')[-1])][int(feature)].append(c)
    result=[]
    for key,sides in sorted(groups.items()):
        off=sides[0][0] if len(sides[0])==1 else None;on=sides[1][0] if len(sides[1])==1 else None
        issues=[]
        if not off or not on:issues.append('Expected one completed capture for each side')
        elif not off['valid'] or not on['valid']:issues.append('Capture validation failed')
        elif off['runtime_hashes']!=on['runtime_hashes'] or off['map_candidates_sha256']!=on['map_candidates_sha256']:
            issues.append('Binary/assets/maps differ between paired sides')
        random_spawn=key[0]=='pp_sandbox2' and key[2]=='spawn' and not (off and on and off['comparison'].get('spawn_scope') and on['comparison'].get('spawn_scope'))
        result.append(dict(map=key[0],quality=key[1],phase=key[2],off=off,on=on,valid=not issues,
                           validation_issues=issues,uncontrolled_random_spawn=random_spawn,
                           fps_change_percent=100*(on['throughput_fps']/off['throughput_fps']-1) if off and on and not random_spawn else None))
    return result


def summary(report):
    out=['PROFILING ON: attribution only; timings include profiler overhead and are not final playability measurements.']
    for run in report['runs']:
        for c in run['captures']:
            if 'profile' not in c or not c['performance_phase']:continue
            out.append(f"{c['capture']}: {fmt(c['throughput_fps'])} FPS, mean {fmt(c['frame_ms']['mean'])}ms, P95 {fmt(c['frame_ms']['p95'])}ms; valid={c['valid']}")
            for name,metrics in sorted(c['profile']['classes'].items(),key=lambda kv:(kv[1]['ms'] or {}).get('mean',0),reverse=True):
                if metrics['ms'] and (metrics['ms']['mean']>0 or (metrics['draws'] or {}).get('mean',0)>0):
                    out.append(f"  {name}: {fmt(metrics['ms']['mean'])}ms / {fmt((metrics['draws'] or {}).get('mean'),1)} draws per complete display")
            for row in c['profile']['top_inline'][:4]:
                out.append(f"  inline *{row['model']} {row['label']}: {fmt(row['ms_per_display'])}ms / {fmt(row['draws_per_display'],1)} draws, top-four sampled")
            out.append('  Nonexclusive flush causes: '+', '.join(f"{k}={fmt(v['mean'],1)}" for k,v in c['profile']['flushes_nonexclusive'].items() if v and v['mean']))
    return '\n'.join(out)+'\n'


def table(headers,rows):
    esc=lambda x:html.escape(str(x))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def render(report,outpath,jsonpath):
    text=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Plastic Platoon — focused draw profile and batching</title><style>body{font:15px/1.55 system-ui;background:#f7f9f5;color:#1e3024;margin:30px auto;max-width:1250px;padding:0 22px}table{border-collapse:collapse;width:100%;background:white;font-size:13px}th,td{padding:8px 10px;border-bottom:1px solid #dbe3d7;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#244c32;color:white}.scroll{overflow:auto}h2{margin-top:32px}.note{padding:14px;background:#e3edde}a{color:#285b3b}</style><h1>Four-player Pi draw profiling and renderer batching</h1>',
          '<p class="note">'+('All requested validation checks passed.' if report['complete_and_valid'] else 'Partial or unverified results: inspect validation issues before drawing conclusions.')+'</p>',
          '<p>Pickup LOD remains enabled and assets remain unchanged. Focused profiles enable draw counters and can incur substantial measurement overhead. Use their draw counts and scoped times to identify candidates, not as final playability measurements or predictions of an uninstrumented gain. Paired performance tests disable that profiler. CPU scope times include driver waiting, preparation and instrumentation; they are not GPU execution timings. HUD work is outside the per-view profiler.</p>',
          '<h2>Focused per-class profile</h2>']
    for run in report['runs']:
        for c in run['captures']:
            if 'profile' not in c or not c['performance_phase']:continue
            text.append('<h3>'+html.escape(c['capture'])+'</h3><p>FPS '+fmt(c['throughput_fps'])+'; mean '+fmt(c['frame_ms']['mean'])+' ms; P95 '+fmt(c['frame_ms']['p95'])+' ms; aggregate '+fmt(mean(c,'draws'),1)+' draws per complete display.</p>')
            rows=[]
            for name,v in sorted(c['profile']['classes'].items(),key=lambda kv:(kv[1]['ms'] or {}).get('mean',0),reverse=True):
                rows.append([name,fmt((v['ms'] or {}).get('mean')),fmt((v['draws'] or {}).get('mean'),1)])
            text.append(table(['Class scope','Mean CPU wall ms / display','Mean actual draws / display'],rows))
            text.append('<p>The pickup class covers the five LOD-targeted pickup paths. Other pickup models fall under alias_other. Deferred alpha inline work can be charged to world.</p>')
            text.append(table(['Inline model','Class / target','Top-four CPU ms / display','Top-four draws / display','View slots'],[[f"*{r['model']}",r['label'],fmt(r['ms_per_display']),fmt(r['draws_per_display'],1),','.join(map(str,r['slots']))] for r in c['profile']['top_inline']]))
            text.append('<p>Inline contributions include only each view’s four costliest models. Numeric IDs are read from per-view rows and resolved against the matching unchanged BSP; frame CSV IDs are ignored.</p>')
            text.append(table(['Nonexclusive flush cause','Mean events / display'],[[k,fmt(v['mean'],1)] for k,v in c['profile']['flushes_nonexclusive'].items() if v]))
    text.append('<h2>Profiler-off paired performance</h2>')
    rows=[]
    for pair in report['pairs']:
        off,on=pair['off'],pair['on']
        rows.append([pair['map']+' / '+pair['phase'],pair['quality'],fmt(off['throughput_fps']) if off else '—',fmt(on['throughput_fps']) if on else '—',fmt(pair['fps_change_percent'])+'%' if pair['fps_change_percent'] is not None else 'random spawn',fmt(off['frame_ms']['p95']) if off else '—',fmt(on['frame_ms']['p95']) if on else '—',fmt(on['frame_ms']['p99']) if on else '—',fmt(on['over_33_333_ms_percent'])+'%' if on else '—',fmt(on['over_50_ms_percent'])+'%' if on else '—',str(pair['valid'])])
    text.append(table(['Scene','Detail','Off FPS','On FPS','FPS change','Off P95 ms','On P95 ms','On P99 ms','On >33.3ms','On >50ms','Valid'],rows))
    text.append('<p>FPS uses the mean complete-display interval for four views and one presentation. A 30 FPS budget is 33.333 ms; 20 FPS is 50 ms. Corrected deathmatch initial captures use the same fixed separated positions after sequential respawn and equipment checks, rather than random spawn views. Any older random-spawn rows remain uncontrolled. Fixed deathmatch cameras, turning views and deterministic co-op starts retain live game-state variation; one pair per setting is not a confidence interval.</p>')
    text.append('<p>The optimization changes opaque inline-brush submission only. It does not reduce art detail or alter the world pass. A reduction in the train’s individual draw cost therefore does not eliminate world rendering, lightmap preparation or other model work.</p>')
    rows=[]
    for pair in report['pairs']:
        for side in ('off','on'):
            c=pair[side]
            if not c:continue
            t=c['telemetry'];clock=c['game_clock']
            rows.append([c['capture'],fmt(mean(c,'model_triangles'),0),fmt(mean(c,'world_triangles'),0),fmt(mean(c,'draws'),0),fmt(mean(c,'submit_ms')),fmt(t['process_cpu']['mean_percent_of_one_core'],1),fmt(c['rss_peak_mib'],1),fmt(t['process_swap_max_mib'],1),fmt(t['temperature_max_c'],1),t['system_vm_counter_deltas']['oom_kills'],fmt(clock['game_seconds_per_wall_second'],2) if clock else '—'])
    text.append('<h2>Geometry, submission and resources</h2>'+table(['Capture','Model tris','World tris','Draws','Submit ms','CPU % one core','Sampled RSS MiB','Sampled swap MiB','Max °C','Sampled OOM delta','Game/wall'],rows))
    text.append('<p>Memory maxima and OOM counters cover sampled intervals. Game time has one-second resolution and includes phase bookkeeping. Below ten display frames per second this listen client can advance game time more slowly than wall time. CPU timings are nested; do not add them.</p>')
    text.append('<h2>Validation and provenance</h2>')
    for run in report['runs']:
        text.append('<p>'+html.escape(run['root'])+': shell restored='+str(run['shell_restored'])+', saves unchanged='+str(run['save_hashes_unchanged'])+', installed package unchanged='+str(run['package_hashes_unchanged'])+', runtime unchanged='+str(run['runtime_hashes_unchanged'])+'.</p>')
    if report['validation_issues']:text.append('<ul>'+''.join('<li>'+html.escape(v)+'</li>' for v in report['validation_issues'])+'</ul>')
    if report.get('excluded_sessions'):
        text.append('<h3>Superseded captures retained for audit</h3><p>Initial deathmatch profiles included dead clients or mismatched weapons after simultaneous respawns. They remain in the raw evidence and JSON below but are excluded from the corrected assessment.</p>')
        text.append(table(['Run','Session','Excluded captures','Reason'],[[r['root'],r['session'],len(r['captures']),r['reason']] for r in report['excluded_sessions']]))
    for proof in report.get('qa',[]):
        link=quote(os.path.relpath(proof['path'],outpath.parent))
        text.append('<p><a href="'+link+'">'+html.escape(Path(proof['path']).parent.name+' QA')+'</a>: passed='+str(proof['data'].get('passed'))+'.</p>')
    if report.get('deployment'):
        proof=report['deployment'];link=quote(os.path.relpath(proof['path'],outpath.parent))
        text.append('<p><a href="'+link+'">Deployment record</a>: installed='+str(proof['data'].get('installed'))+'.</p>')
    text.append('<p>Endline bridge rows require verified train arrival and movement of all four riders. Functional deaths/respawns use raw-state assertions without a performance sample-size threshold. Four connected controller assignments include three virtual SDL pads; secondary held fields are injected by the test driver. HDMI, four physical controller event streams, complete missions and long-duration reliability are outside this test.</p>')
    text.append('<p>Corrected deathmatch startup parks living players, revives dead players one at a time through ordinary attack input, and immediately parks each revived player before enabling god mode and equipping all four Machineguns. Equipped phases verify the canonical weapon model path before and after capture. Functional respawns remain ordinary starting-weapon respawns. Earlier co-op profile identity uses consistent positive map-dependent gun indices plus the successful equip sequence; the older driver did not record model paths.</p>')
    text.append('<p><a href="'+quote(os.path.relpath(jsonpath,outpath.parent))+'">Complete JSON, settings, hashes, per-view inline profile and checks</a></p></html>')
    return ''.join(text)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('roots',nargs='+',type=Path)
    p.add_argument('--warmup',type=int,default=10)
    p.add_argument('--map-data',type=Path,default=ROOT/'release/baseq2')
    p.add_argument('--reference',type=Path,default=ROOT/'build/pi-pickup-lod-20261112/comparison.json')
    p.add_argument('--output',type=Path,help='HTML report; JSON uses same basename')
    p.add_argument('--qa',type=Path,action='append',default=[])
    p.add_argument('--deployment',type=Path)
    p.add_argument('--summary-only',action='store_true')
    p.add_argument('--exclude-session',action='append',default=[],help='Retain but exclude SESSION or ROOT_BASENAME:SESSION from the assessment')
    a=p.parse_args()
    if a.warmup<0:p.error('warmup must be nonnegative')
    if not a.output and not a.summary_only:p.error('--output or --summary-only is required')
    runs=[augment(root.resolve(),a.warmup,a.map_data.resolve()) for root in a.roots]
    excluded=[]
    for run in runs:
        kept=[]
        grouped=defaultdict(list)
        for capture in run['captures']:
            session=capture['capture'].split('/',1)[0]
            if session in a.exclude_session or Path(run['root']).name+':'+session in a.exclude_session:
                grouped[session].append(capture)
            else:kept.append(capture)
        run['captures']=kept
        for session,items in grouped.items():
            excluded.append(dict(root=run['root'],session=session,captures=items,
                reason='Superseded by sequential respawn and exact Machinegun identity checks; original dead/mixed-weapon state retained as audit evidence.'))
    captures=[c for run in runs for c in run['captures']];comparison=pairs(captures);issues=[]
    for run in runs:
        for key in ('shell_restored','save_hashes_unchanged','package_hashes_unchanged','runtime_hashes_unchanged'):
            if run.get(key) is not True:issues.append(Path(run['root']).name+': '+key+' not verified')
        if run['run_error'] or run['ended'] is None:issues.append(Path(run['root']).name+': incomplete or failed run')
        for c in run['captures']:issues += [c['capture']+': '+v for v in c['validation_issues']]
    for pair in comparison:issues += [pair['map']+'/'+pair['quality']+'/'+pair['phase']+': '+v for v in pair['validation_issues']]
    required={(mapname,quality,phase) for mapname,phases in {
        'pp_sandstorm':['spawn','roof-four-guns'],'pp_endline':['spawn','bridge-four-guns'],
        'pp_sandbox2':['spawn','dm-separated','dm-four-guns-turning']}.items()
        for quality in ('normal','low') for phase in phases}
    if comparison:
        observed={(r['map'],r['quality'],r['phase']) for r in comparison if r['valid']}
        for missing in sorted(required-observed):issues.append('Missing valid paired scene: '+' / '.join(missing))
    profile_captures=[c for c in captures if c['comparison'].get('kind')=='profile' and c['performance_phase']]
    if profile_captures:
        observed={(c['requested_map'],c['comparison'].get('quality'),c['capture'].split('/')[-1]) for c in profile_captures if c['valid']}
        for missing in sorted(required-observed):issues.append('Missing valid profile scene: '+' / '.join(missing))
    previous=load(a.reference,{}) or {};references=[r.get('runtime_hashes',{}) for r in previous.get('runs',[])]
    for run in runs:
        if references:
            for key,value in references[0].items():
                if key.endswith(('.pk3','.pak')) or key=='baseq2/game.so':
                    if run['runtime_hashes'].get(key)!=value:issues.append('Asset/game hash differs from prior LOD deployment: '+key)
    proofs=[]
    for path in a.qa:
        data=load(path,{})
        proofs.append(dict(path=str(path.resolve()),data=data,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        if data.get('passed') is not True:issues.append('QA proof did not pass: '+str(path))
    deployment=dict(path=str(a.deployment.resolve()),data=load(a.deployment,{})) if a.deployment else None
    paired_runs=[run for run in runs if any(c['comparison'].get('kind')=='paired' for c in run['captures'])]
    for proof in proofs:
        data=proof['data']
        if data.get('actual_pi'):
            for key in ('candidate_unchanged','shell_restored','save_hashes_unchanged','package_hashes_unchanged'):
                if data.get(key) is not True:issues.append('Native QA did not verify '+key+': '+proof['path'])
            for run in paired_runs:
                if run['runtime_hashes']!=data.get('candidate_hashes'):
                    issues.append('Paired runtime differs from the exact native QA candidate: '+run['root'])
    if deployment:
        data=deployment['data']
        for key in ('installed','assets_and_game_module_unchanged','saves_unchanged','shell_restored'):
            if data.get(key) is not True:issues.append('Deployment did not verify '+key)
        for run in paired_runs:
            if run['runtime_hashes']!=data.get('installed_hashes'):
                issues.append('Paired runtime differs from installed candidate: '+run['root'])
        for proof in proofs:
            if proof['data'].get('actual_pi') and proof['data'].get('candidate_hashes')!=data.get('installed_hashes'):
                issues.append('Native QA candidate differs from installed candidate')
    report=dict(schema=1,complete_and_valid=not issues,validation_issues=issues,warmup_frames=a.warmup,
                runs=runs,pairs=comparison,reference_path=str(a.reference.resolve()),
                qa=proofs,deployment=deployment,
                excluded_sessions=excluded,
                profiler_semantics='Per-class CPU wall scopes include driver waiting. Draws are actual per-view GL calls; flush causes overlap. Inline IDs are per-view only.')
    print(summary(report))
    if a.output:
        output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True);jsonpath=output.with_suffix('.json')
        jsonpath.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');output.write_text(render(report,output,jsonpath))
        print(json.dumps(dict(html=str(output),json=str(jsonpath),valid=report['complete_and_valid'],pairs=len(comparison),issues=len(issues)),indent=2))


if __name__=='__main__':main()
