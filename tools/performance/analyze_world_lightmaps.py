#!/usr/bin/env python3
"""World/lightmap extension of the validated four-player draw-batching analyzer.

The original analyzer remains unchanged. This adapter keeps its state, weapon,
train, sample-size, binary, deployment and functional-respawn checks, and adds
the world profiler fields plus complete asset/BSP-lump identity checks.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/performance'))
import analyze_draw_batching as base

FIELDS=('world_mark_ms','brush_light_ms','brush_light_models',
    'brush_light_surface_tests','brush_light_dlight_tests','lm_regen_ms',
    'lm_regen_runs','lm_atlases_scanned','lm_surfaces_scanned',
    'lm_changed_surfaces','lm_build_ms','lm_build_calls','lm_build_texels',
    'lm_upload_ms','lm_upload_calls','lm_upload_bytes','world_chain_ms',
    'world_chain_draws','world_blend_ms','world_blend_draws','world_sky_ms',
    'world_sky_draws','world_alpha_ms','world_alpha_draws',
    'world_visible_surfaces','mtex_enabled','lm_copy_enabled')
TIMES=('world_mark_ms','brush_light_ms','lm_regen_ms','lm_build_ms',
       'lm_upload_ms','world_chain_ms','world_blend_ms','world_sky_ms','world_alpha_ms')
LABELS={'world_mark_ms':'World visibility / chain marking',
        'brush_light_ms':'Brush dynamic-light marking',
        'lm_regen_ms':'Lightmap regeneration (includes build / uploads)',
        'lm_build_ms':'Actual lightmap builds (nested)',
        'lm_upload_ms':'Actual texture uploads (nested)',
        'world_chain_ms':'Opaque world texture chains',
        'world_blend_ms':'World lightmap blend pass',
        'world_sky_ms':'World sky pass',
        'world_alpha_ms':'Deferred alpha (includes inline alpha)'}
ORIGINAL_PROFILE=base.profile_details
ORIGINAL_AUGMENT=base.augment
ORIGINAL_SUMMARY=base.summary
ORIGINAL_RENDER=base.render
CONTENT_REFERENCE=None
CONTEXT_DIAGNOSTICS=[]
TOGGLE_PROBES=[]


def audit_toggle_probe(root,report):
    """Audit the diagnostic separately; baseline profile rules stay strict."""
    from compare_pickup_lod import valid_state
    metadata=base.load(root/'metadata.json',{})
    run=base.analyze_root(root,report['warmup_frames'],metadata.get('clock_ticks'))
    sessions={s['label']:s for s in metadata.get('sessions',[])}
    plans={s['label']:s for s in base.load(root/'plan.json',[])}
    issues=[]
    for key in ('shell_restored','save_hashes_unchanged','package_hashes_unchanged','runtime_hashes_unchanged','assets_maps_visibility_unchanged'):
        if metadata.get(key) is not True:issues.append(key+' not verified')
    if run['run_error'] or not run['ended']:issues.append('Diagnostic run incomplete or failed')
    if len(sessions)!=1 or len(run['captures'])!=6:issues.append('Expected one same-context session with six captures')
    identity=metadata.get('content_identity',{})
    if not identity.get('files') or identity!=metadata.get('content_identity_after'):issues.append('Diagnostic content changed or identity missing')
    if CONTENT_REFERENCE:
        ref=base.load(CONTENT_REFERENCE,{});ref=ref.get('content_identity',ref)
        if content_diff(ref,identity):issues.append('Diagnostic assets/maps differ from native reference')
    deployment=(report.get('deployment') or {}).get('data',{})
    if not deployment or metadata.get('runtime_hashes')!=deployment.get('installed_hashes'):
        issues.append('Diagnostic runtime not verified against installed deployment')
    camera_signatures=set();visibility_signatures=set();triangles={}
    ordered=[]
    for session in sessions.values():
        ordered.extend((p['label'],p) for p in session.get('phases',[]))
    captures={c['capture'].split('/')[-1]:c for c in run['captures']}
    rows=[]
    for phase_label,phase in ordered:
        c=captures.get(phase_label)
        if not c:continue
        session_label=c['capture'].split('/')[0];plan=plans.get(session_label,{})
        intended=next((p for p in plan.get('phases',[]) if p['label']==phase_label),{})
        local=[]
        if not phase.get('assertions') or not all(phase['assertions'].values()):local.append('Runner assertions missing/failed')
        for key,value in intended.get('expected_settings',{}).items():
            if base.number(c['settings'].get(key))!=value:local.append('Actual setting mismatch: '+key)
        if not intended.get('expected_settings'):local.append('Explicit diagnostic settings missing')
        if not c['actual_modes_match_requested'] or c['timed_frames']<20 or c['observed_views_per_frame']!=[4.0] or c['unexpected_view_row_frames']:
            local.append('Map/mode/four-view/timed sample validation failed')
        if c['framebuffers']!=[('240','240')] or len(c['viewports'])!=4 or any((v['width'],v['height'])!=('120','120') for v in c['viewports']):local.append('Unexpected framebuffer/viewport')
        for when in ('state_before','state_after'):
            state=phase.get(when,{})
            if not valid_state(state,False) or any(s.get('gunindex',0)<=0 or s.get('gunmodel')!='models/weapons/v_blast/tris.md2' for s in state.get('slots',[])):
                local.append('Four ready living Blaster clients not verified: '+when)
        path=Path(c['source']);frames=[r for r in base.readcsv(path)[report['warmup_frames']:] if (base.number(r.get('frame_ms')) or 0)>0]
        retained={r['frame'] for r in frames}
        views=[r for r in base.readcsv(path.with_name(path.name.replace('-frames.csv','-views.csv'))) if r['frame'] in retained]
        cameras=tuple(sorted({tuple(v[k] for k in ('slot','x','y','z','pitch','yaw','roll')) for v in views}))
        visible=tuple(sorted({(v['slot'],v['dp_world_visible_surfaces']) for v in views}))
        camera_signatures.add(cameras);visibility_signatures.add(visible)
        if len(cameras)!=4 or len(visible)!=4:local.append('Cameras/visible surface counts changed during capture')
        c['map_candidates_sha256']=sessions.get(session_label,{}).get('map_candidates_sha256',{})
        c['profile']=profile_details(path,c,report['warmup_frames'],ROOT/'release/baseq2')
        p=c['profile']['world_lightmaps'];m=p['metrics']
        if not p['required_columns_present'] or (c['profile']['enabled'] or {}).get('mean')!=4 or not c['profile']['class_draw_sum_matches']:local.append('Four complete profiler views/counter sums not verified')
        if any(base.number(r.get('dp_lm_copy_enabled'))!=0 or base.number(r.get('dp_mtex_enabled'))!=4 or base.number(r.get('dp_lm_upload_bytes'))!=0 for r in frames):local.append('Actual mtex/copies/dynamic-lightmap diagnostic state differs')
        entities=int(c['settings']['r_drawentities']);triangles.setdefault(entities,set()).add(base.mean(c,'world_triangles'))
        row=dict(capture=c['capture'],feature=int(c['settings']['r_gl1_batch_world']),entities=entities,
            frame_ms=c['frame_ms'],chain_ms=m['world_chain_ms'],chain_draws=m['world_chain_draws'],
            world_triangles=base.mean(c,'world_triangles'),profile=c['profile'],settings=c['settings'],
            timed_frames=c['timed_frames'],validation_issues=local,valid=not local)
        rows.append(row);issues.extend(c['capture']+': '+x for x in local)
    if [(r['entities'],r['feature']) for r in rows]!=[(1,0),(1,1),(1,0),(1,1),(0,0),(0,1)]:issues.append('Expected full-entity ABAB then world-only AB sequence')
    if len(camera_signatures)!=1 or len(visibility_signatures)!=1 or any(len(t)!=1 for t in triangles.values()):issues.append('Camera/visibility/geometry signatures differ across diagnostic toggles')
    return dict(root=str(root),passed=not issues,validation_issues=issues,captures=rows,
        runtime_hashes=metadata.get('runtime_hashes'),content_identity=identity,
        same_camera_and_visibility=len(camera_signatures)==len(visibility_signatures)==1,
        scope=metadata.get('diagnostic_scope') or 'Same-context diagnostic: profiling on, dynamic lightmaps off, god/notarget, normal Blasters; full entities ABAB then world-only AB. Advancing animation/AI; not final live-combat playability.')


def profile_details(path,capture,warmup,map_data):
    result=ORIGINAL_PROFILE(path,capture,warmup,map_data)
    raw=base.readcsv(path)
    frames=[r for r in raw[warmup:] if (base.number(r.get('frame_ms')) or 0)>0]
    retained={r['frame'] for r in frames}
    views=[r for r in base.readcsv(path.with_name(path.name.replace('-frames.csv','-views.csv')))
           if r['frame'] in retained]
    metrics={name:base.stats(base.values(frames,'dp_'+name)) for name in FIELDS}
    result['world_lightmaps']=dict(
        metrics=metrics,
        flushes_nonexclusive={name:base.stats(base.values(frames,'dp_world_flush_'+name))
                             for name in base.CAUSES},
        physical_atlases_per_view=base.stats(base.values(views,'dp_lm_atlas_count')),
        per_view_flags={name:base.stats(base.values(views,'dp_'+name))
                        for name in ('mtex_enabled','lm_copy_enabled')},
        required_columns_present=bool(raw) and all('dp_'+f in raw[0] for f in FIELDS)
            and all('dp_world_flush_'+f in raw[0] for f in base.CAUSES)
            and bool(views) and all('dp_lm_atlas_count' in v for v in views),
        upload_bytes_match_legacy_counter=all(
            base.number(r.get('dp_lm_upload_bytes'))==base.number(r.get('lightmap_bytes'))
            for r in frames) if frames and 'lightmap_bytes' in frames[0] else None,
        semantics='Complete-display sums across four views. Physical atlas count is read only from per-view rows; frame atlas=-1 is ignored. Regeneration includes build/upload subscopes; nested times must not be added. Upload CPU wall includes driver waiting and is not synchronized GPU time.')
    return result


def content_diff(expected,actual):
    issues=[]
    for kind in ('files','maps'):
        before=expected.get(kind,{});after=actual.get(kind,{})
        for key in sorted(set(before)|set(after)):
            if before.get(key)!=after.get(key):issues.append(kind+': '+key)
    return issues


def augment(root,warmup,map_data):
    run=ORIGINAL_AUGMENT(root,warmup,map_data)
    metadata=base.load(root/'metadata.json',{})
    plans={s['label']:s for s in base.load(root/'plan.json',[])}
    before=metadata.get('content_identity',{})
    after=metadata.get('content_identity_after',{})
    run['content_identity']=before
    run['content_identity_after']=after
    run['assets_maps_visibility_unchanged']=metadata.get('assets_maps_visibility_unchanged')
    run['content_reference_path']=str(CONTENT_REFERENCE) if CONTENT_REFERENCE else None
    global_issues=[]
    if not before.get('files') or not before.get('maps'):
        global_issues.append('Full asset and BSP-lump identity evidence is missing')
    if run['assets_maps_visibility_unchanged'] is not True or before!=after:
        global_issues.append('Assets/maps/visibility byte identity before and after run was not verified')
    if CONTENT_REFERENCE:
        ref=base.load(CONTENT_REFERENCE,{})
        ref=ref.get('content_identity',ref)
        differences=content_diff(ref,before)
        run['content_reference_differences']=differences
        if differences:global_issues.append('Runtime content differs from native baseline: '+', '.join(differences))
    for capture in run['captures']:
        issues=capture['validation_issues']
        issues.extend(global_issues)
        if base.number(capture['settings'].get('r_gl1_batch_inline'))!=1:
            issues.append('Existing inline batching must stay enabled')
        if capture['comparison'].get('kind')=='paired' and capture['comparison'].get('feature_cvar')!='gl1_lightmapcopies':
            if base.number(capture['settings'].get('gl1_lightmapcopies'))!=0:
                issues.append('Lightmap copies must remain disabled for world-batching pairs')
        if capture['comparison'].get('kind')=='profile':
            feature=capture['comparison'].get('feature_cvar','')
            planned=plans.get(capture['capture'].split('/',1)[0],{}).get('settings',{})
            actual=capture['settings'].get(feature)
            # Initial profiles precede the new candidate's implementation and
            # CL_PerfSettings registration. The frozen copied plan explicitly
            # sets its provisional cvar to0; paired tests require actual logs.
            capture['candidate_baseline_proof']='actual settings' if actual is not None else 'copied plan; candidate not yet implemented'
            if base.number(actual if actual is not None else planned.get(feature))!=0:
                issues.append('Focused baseline profile must explicitly disable the candidate')
            details=capture['profile']['world_lightmaps']
            if not details['required_columns_present']:
                issues.append('New world/lightmap profiler columns are missing')
            if details['upload_bytes_match_legacy_counter'] is False:
                issues.append('Actual upload bytes differ from legacy lightmap byte counter')
        capture['valid']=not issues
    return run


def decorate(report):
    report['scope']='Four-player Pi world/lightmap round; all assets and compiled map lumps remain byte-identical.'
    report['profiler_semantics']='Profile-on captures identify CPU wall scopes and actual draws. Timings include instrumentation and driver waiting; nested scopes must not be added. Main pairs disable profiling. Physical atlas counts are per-view only; flush causes overlap.'
    signatures={r.get('content_identity',{}).get('signature_sha256') for r in report['runs']}
    signatures.discard(None)
    report['cross_run_content_identical']=len(signatures)==1
    issue='Asset/map/visibility identity differs across supplied runs'
    if len(signatures)>1 and issue not in report['validation_issues']:
        report['validation_issues'].append(issue)
    report['context_diagnostics']=[]
    report['retained_initial_visual_attempts']=[]
    for proof in report.get('qa',[]):
        initial=Path(proof['path']).parent.parent/'initial-qa/visual-qa/report.json'
        if initial.is_file():
            data=base.load(initial,{})
            report['retained_initial_visual_attempts'].append(dict(path=str(initial),
                sha256=hashlib.sha256(initial.read_bytes()).hexdigest(),
                passed=data.get('passed'),error=data.get('error'),checks=data.get('checks',{})))
    for path in CONTEXT_DIAGNOSTICS:
        data=base.load(path,{})
        report['context_diagnostics'].append(dict(path=str(path),data=data,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        if not (data.get('passed') is True and data.get('diagnostic_only') is True
                and data.get('legacy_only') is True):
            issue='Previous-renderer context diagnostic did not pass its declared controls: '+str(path)
            if issue not in report['validation_issues']:report['validation_issues'].append(issue)
    report['toggle_probes']=[audit_toggle_probe(root,report) for root in TOGGLE_PROBES]
    for probe in report['toggle_probes']:
        for detail in probe['validation_issues']:
            issue='Toggle diagnostic: '+detail
            if issue not in report['validation_issues']:report['validation_issues'].append(issue)
    report['complete_and_valid']=not report['validation_issues']


def summary(report):
    decorate(report)
    lines=[ORIGINAL_SUMMARY(report).rstrip(),'WORLD / LIGHTMAP COMPONENTS: nested CPU scopes; do not add.']
    for probe in report.get('toggle_probes',[]):
        lines.append('SAME-CONTEXT TOGGLE DIAGNOSTIC passed='+str(probe['passed'])+'; '+str(probe['scope']))
        for c in probe['captures']:
            lines.append(c['capture']+': frame '+base.fmt(c['frame_ms']['mean'])+'ms; chain '+base.fmt(c['chain_ms']['mean'])+'ms / '+base.fmt(c['chain_draws']['mean'],1)+'draws')
    for run in report['runs']:
        for c in run['captures']:
            profile=c.get('profile',{}).get('world_lightmaps')
            if not profile or not c['performance_phase']:continue
            lines.append(c['capture']+':')
            m=profile['metrics']
            for name in TIMES:
                lines.append('  '+name+'='+base.fmt((m[name] or {}).get('mean'))+' ms/display')
            counts=('world_visible_surfaces','brush_light_surface_tests','brush_light_dlight_tests',
                    'lm_atlases_scanned','lm_surfaces_scanned','lm_changed_surfaces',
                    'lm_build_calls','lm_build_texels','lm_upload_calls','lm_upload_bytes',
                    'world_chain_draws','world_blend_draws','world_sky_draws','world_alpha_draws')
            lines.append('  Counts/display: '+', '.join(n+'='+base.fmt((m[n] or {}).get('mean'),1) for n in counts))
            lines.append('  World-only nonexclusive flushes: '+', '.join(n+'='+base.fmt((v or {}).get('mean'),1) for n,v in profile['flushes_nonexclusive'].items()))
            atlas=(profile['physical_atlases_per_view'] or {}).get('mean')
            lines.append('  Physical atlas count/view='+base.fmt(atlas,0)+'; actual mtex/copies flags/view='+', '.join(n+'='+base.fmt((v or {}).get('mean'),0) for n,v in profile['per_view_flags'].items()))
    return '\n'.join(lines)+'\n'


def render(report,outpath,jsonpath):
    document=ORIGINAL_RENDER(report,outpath,jsonpath)
    document=document.replace('Plastic Platoon — focused draw profile and batching','Plastic Platoon — world and lightmaps')
    document=document.replace('Four-player Pi draw profiling and renderer batching','Four-player Pi world and lightmap profiling')
    document=document.replace('The optimization changes opaque inline-brush submission only. It does not reduce art detail or alter the world pass. A reduction in the train’s individual draw cost therefore does not eliminate world rendering, lightmap preparation or other model work.',
        'This round holds pickup LOD and inline batching enabled and compares the declared world/lightmap candidate off and on in fresh captures. Maps, PVS/visibility, lighting lumps, models, textures and other game assets remain byte-identical. Historical reports provide context; they are not an additional matched performance pair.')
    blocks=['<h2>World and lightmap components</h2><p>All values below sum the four camera views for one complete display. Lightmap regeneration includes its build and upload subscopes; do not sum nested times. Upload wall time can include driver waiting. The profiler adds overhead, so these rows identify work rather than predict final FPS.</p>']
    for run in report['runs']:
        for c in run['captures']:
            p=c.get('profile',{}).get('world_lightmaps')
            if not p or not c['performance_phase']:continue
            m=p['metrics'];blocks.append('<h3>'+html.escape(c['capture'])+'</h3>')
            blocks.append(base.table(['CPU scope','Mean ms/display','P95 ms/display'],[
                [LABELS[n],base.fmt((m[n] or {}).get('mean')),base.fmt((m[n] or {}).get('p95'))] for n in TIMES]))
            blocks.append(base.table(['Counter','Mean/display'],[
                [n,base.fmt((v or {}).get('mean'),1)] for n,v in m.items() if not n.endswith('_ms')]))
            blocks.append(base.table(['World-only flush cause (nonexclusive)','Mean/display'],[
                [n,base.fmt((v or {}).get('mean'),1)] for n,v in p['flushes_nonexclusive'].items()]))
            flags=', '.join(n+'='+base.fmt((v or {}).get('mean'),0) for n,v in p['per_view_flags'].items())
            blocks.append('<p>Physical registered atlases per view: '+base.fmt((p['physical_atlases_per_view'] or {}).get('mean'),0)+'. Actual flags per view: '+html.escape(flags)+'.</p>')
    controlled=[p for p in report.get('qa',[])+report.get('context_diagnostics',[])
                if p['data'].get('context_controls_enabled')]
    if controlled:
        blocks.append('<h2>Visual validation and context controls</h2><p>Optimization OFF/ON images must match exactly within each renderer context, including after restart and map reload. Cross-context resets are assessed separately: the full signed channel-change pattern must match between the OFF and ON controls. Raw images from different contexts can show small color drift. The previous renderer diagnostic provides independent evidence that this drift also occurs before world batching.</p>')
        rows=[]
        for proof in controlled:
            data=proof['data'];name=Path(proof['path']).parent.name
            link=quote(os.path.relpath(proof['path'],outpath.parent))
            blocks.append('<p><a href="'+link+'">'+html.escape(name)+'</a>: '+html.escape(data.get('validation_policy',''))+'; passed='+str(data.get('passed'))+'.</p>')
            for transition,details in data.get('context_transitions',{}).items():
                legacy=details.get('legacy',{})
                rows.append([name,transition,legacy.get('different_pixels'),legacy.get('different_channels'),legacy.get('max_channel_delta'),details.get('exact_transition_deltas_match')])
        blocks.append(base.table(['Proof','Context transition','Changed pixels','Changed channels','Maximum channel delta','Full OFF/ON transition deltas match'],rows))
        blocks.append('<p>These checks cover the controlled four-camera fixture with matching geometry, camera positions and lightmap work. They do not assert identical raw screenshots across renderer contexts or across live gameplay sessions.</p>')
        for initial in report.get('retained_initial_visual_attempts',[]):
            link=quote(os.path.relpath(initial['path'],outpath.parent))
            changed=max((initial.get('checks',{}).get(n,{}).get('pixels',{}).get('different_channels',0) for n in ('restart','reload')),default=0)
            blocks.append('<p>The <a href="'+link+'">initial strict visual attempt</a> remains available for audit (passed='+str(initial.get('passed'))+'). Its raw restart/reload comparisons recorded up to '+str(changed)+' changed channels. The subsequent controlled rerun compares OFF/ON within each context and verifies the complete transition deltas.</p>')
    for probe in report.get('toggle_probes',[]):
        blocks.append('<h2>Same-context toggle diagnostic</h2><p>'+html.escape(str(probe['scope']))+'</p><p>Audit passed='+str(probe['passed'])+'; fixed cameras and visible surfaces='+str(probe['same_camera_and_visibility'])+'. This separately audited probe is excluded from the fourteen main scene pairs. Fewer calls can save a few milliseconds in this phase while leaving most complete-frame work unchanged.</p>')
        blocks.append(base.table(['Diagnostic capture','Entities','Toggle','Mean frame ms','Mean chain CPU ms','Chain draws','World triangles','Valid'],[[c['capture'],c['entities'],c['feature'],base.fmt(c['frame_ms']['mean']),base.fmt(c['chain_ms']['mean']),base.fmt(c['chain_draws']['mean'],0),base.fmt(c['world_triangles'],0),c['valid']] for c in probe['captures']]))
    blocks.append('<h2>Byte identity</h2><p>Every runtime baseq2 asset file, each compiled BSP, and all nineteen BSP lumps (including visibility and lighting) are hashed. Generated configs, logs, screenshots, performance output and saves are excluded. Native baseline identity is authoritative; a host reference is only a separate audit when native modules/configuration differ.</p>')
    blocks.append(base.table(['Run','Before/after asset + map identity','Content SHA-256'],[
        [r['root'],r.get('assets_maps_visibility_unchanged'),r.get('content_identity',{}).get('signature_sha256','missing')] for r in report['runs']]))
    return document.replace('<h2>Profiler-off paired performance</h2>',''.join(blocks)+'<h2>Profiler-off paired performance</h2>')


def main():
    global CONTENT_REFERENCE,CONTEXT_DIAGNOSTICS,TOGGLE_PROBES
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--content-reference',type=Path,help='Native metadata.json or its content_identity object; never compare a host game.so to native')
    parser.add_argument('--context-diagnostic',type=Path,action='append',default=[],help='Previous-renderer visual context diagnostic; separate from exact-candidate --qa')
    parser.add_argument('--toggle-probe',type=Path,action='append',default=[],help='Separately audited same-context ABAB diagnostic root, excluded from baseline profiles/main pairs')
    own,remaining=parser.parse_known_args()
    CONTENT_REFERENCE=own.content_reference.resolve() if own.content_reference else None
    CONTEXT_DIAGNOSTICS=[p.resolve() for p in own.context_diagnostic]
    TOGGLE_PROBES=[p.resolve() for p in own.toggle_probe]
    if CONTENT_REFERENCE and not CONTENT_REFERENCE.is_file():parser.error('Content reference file does not exist')
    if any(not p.is_file() for p in CONTEXT_DIAGNOSTICS):parser.error('Context diagnostic file does not exist')
    if any(not (p/'metadata.json').is_file() for p in TOGGLE_PROBES):parser.error('Toggle probe metadata does not exist')
    base.profile_details=profile_details
    base.augment=augment
    base.summary=summary
    base.render=render
    sys.argv=[sys.argv[0]]+remaining
    base.main()


if __name__=='__main__':main()
