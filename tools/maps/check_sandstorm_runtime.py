#!/usr/bin/env python3
"""Exercise Sandstorm's mission chain in the real two-player engine.

This is a cheat-assisted integration smoke test, not a combat playthrough.
It fires the player's weapon at the radio, saves/reloads, touches the roof
entry, and telefrags already activated defenders to test real death counters.
One living player stays away until the landing check proves squad gating.
The existing capture harness isolates all settings and saves in /tmp.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from verify_sandkeep import entity_bounds, parse_entities, vec

ROOT = Path(__file__).resolve().parents[2]


def helicopter_motion(output, before, after, players):
    """Measure green pixels moving upward in each fixed, local-player view.

    Subtracting masks removes stationary vegetation and scene props. The crop
    covers the center of each viewport, where both authored helicopter paths
    are framed. This validates visible translation rather than just a rotor
    animation or a successful trigger message.
    """
    from PIL import Image
    images = [Image.open(output / 'screenshots' / (name + '.png')).convert('RGB')
              for name in (before, after)]
    width, height = images[0].size
    assert images[1].size == (width, height) and height % players == 0
    viewport = height // players
    results = []
    for slot in range(players):
        masks = []
        for im in images:
            pixels = im.load()
            mask = set()
            for y in range(slot*viewport, (slot+1)*viewport):
                for x in range(int(width*.27), int(width*.73)):
                    r,g,b = pixels[x,y]
                    if g > 75 and g > 1.12*r and g > 1.12*b:
                        mask.add((x, y-slot*viewport))
            masks.append(mask)
        left = masks[0]-masks[1]
        right = masks[1]-masks[0]
        def center_y(points):
            return sum(y for _,y in points)/len(points) if points else None
        old_y,new_y = center_y(left),center_y(right)
        rise = old_y-new_y if old_y is not None and new_y is not None else 0
        results.append({'slot':slot, 'disappeared_green_pixels':len(left),
                        'appeared_green_pixels':len(right), 'rise_pixels':round(rise,2),
                        'visible_liftoff':len(left)>=300 and len(right)>=100 and rise>=viewport*.04})
    return results


def helicopter_wait(output, players):
    """Confirm the insertion model remains in place during the waiting beat."""
    from PIL import Image
    images = [Image.open(output/'screenshots'/(name+'.png')).convert('RGB')
              for name in ('insertion_wait', 'insertion_still_waiting')]
    width, height = images[0].size
    viewport = height//players
    centers = []
    counts = []
    for im in images:
        pixels = im.load()
        points = [(x,y) for y in range(viewport) for x in range(int(width*.27),int(width*.73))
                  if (lambda p: p[1]>75 and p[1]>1.12*p[0] and p[1]>1.12*p[2])(pixels[x,y])]
        counts.append(len(points))
        centers.append((sum(x for x,_ in points)/len(points),sum(y for _,y in points)/len(points))
                       if points else None)
    distance = math.dist(*centers) if all(centers) else float('inf')
    return {'slot':0,'green_pixel_counts':counts,'center_shift_pixels':round(distance,2),
            'visible_wait':min(counts)>=100 and distance<=viewport*.03}


def interactions(players=2):
    source = parse_entities((ROOT / 'maps/source/pp_sandstorm.map').read_text())
    entities = [e['keys'] for e in source]
    def one(predicate):
        matches = [e for e in source if predicate(e['keys'])]
        assert len(matches) == 1, f'Expected one matching mission entity, found {len(matches)}'
        return matches[0]

    start = vec(one(lambda k: k['classname'] == 'info_player_start')['keys']['origin'])
    coop = next(vec(k['origin']) for k in entities if k['classname'] == 'info_player_coop')
    intermission = vec(one(lambda k: k['classname'] == 'info_player_intermission')['keys']['origin'])
    extraction = entity_bounds(one(lambda k: k['classname'] == 'trigger_platoon_extract'))
    assert extraction is not None
    pad_x = (extraction[0] + extraction[3]) / 2
    pad_y = (extraction[1] + extraction[4]) / 2
    # The pad surface sits slightly above the extraction brush's floor.
    pad_z = extraction[2] + 27
    roof_entry = entity_bounds(one(lambda k: k['classname'] == 'trigger_once'
                                   and k.get('target') == 'roof_wave_1'))
    assert roof_entry is not None
    # The outer end of the trigger lies on the roof, beyond the stair opening.
    roof_pose = [roof_entry[3] - 10, (roof_entry[1] + roof_entry[4]) / 2,
                 extraction[2] + 24, 0, 180]
    # Aim at the body, not the taller antenna. The first brush is the body.
    radio = one(lambda k: k['classname'] == 'func_explosive' and k.get('target') == 'radio_destroyed')
    body = entity_bounds({'brushes': radio['brushes'][:1]})
    assert body is not None
    # The benchmark camera in noclip sits 32 units above its teleport origin.
    # Center the actual view on the scaled receiver; aiming from the old high
    # pose can fire above the smaller radio after ceiling/furniture reductions.
    radio_z = max(24, (body[2] + body[5]) / 2 - 32)
    radio_y = body[1] - 105.6
    radio_pose = [(body[0] + body[3]) / 2, radio_y, radio_z, 0, 90]
    # This open roof position overlooks the helipad without occupying it.
    standby = [-240, 1080, extraction[2] + 26.8, 0, 230]
    pad = [pad_x, pad_y, pad_z, 0, 90]
    insertion = vec(one(lambda k: k['classname'] == 'misc_platoon_dropship'
                        and k.get('targetname') == 'insertion_flight')['keys']['origin'])
    dx, dy = insertion[0]-start[0], insertion[1]-start[1]
    insertion_yaw = math.degrees(math.atan2(dy, dx))
    # The aircraft model is 36–96 units above its entity origin.
    insertion_pitch = -math.degrees(math.atan2(insertion[2]+66-(start[2]+22), math.hypot(dx,dy))) - 10
    insertion_pose = [*start, insertion_pitch, insertion_yaw]
    insertion_bounds = {'x':[start[0]-5,start[0]+5], 'y':[start[1]-5,start[1]+5],
                        'z':[start[2]+10,start[2]+40]}
    slot1_drop = f'cl_bench_pose 1 {coop[0]:g} {coop[1]:g} {coop[2]:g} 0 90'
    slot1_pad = f'cl_bench_pose 1 {pad_x+48:g} {pad_y:g} {pad_z:g} 0 90'
    views = [
        dict(name='insertion_wait', pose=insertion_pose,
             # The general capture harness enables noclip, which deliberately
             # does not touch triggers. Briefly stand at the start to arm the
             # real mission-start trigger, then restore noclip for later QA.
             after_pose=([dict(command=slot1_drop, wait=.2)] if players == 2 else []) +
                        [dict(command='noclip', wait=.3), dict(command='noclip', wait=.1)],
             expect_eye_bounds=insertion_bounds),
        dict(name='insertion_still_waiting', after_pose=[dict(wait=1)], expect_eye_bounds=insertion_bounds),
        # Capture a short burst spanning the five-second start delay. Render
        # and screenshot overhead vary, so a single frame can miss the ascent
        # entirely on a fast or busy machine.
        dict(name='insertion_ascent_1', after_pose=[dict(wait=1)], expect_eye_bounds=insertion_bounds),
        dict(name='insertion_ascent_2', expect_eye_bounds=insertion_bounds),
        dict(name='insertion_ascent_3', expect_eye_bounds=insertion_bounds),
        dict(name='insertion_ascent_4', expect_eye_bounds=insertion_bounds),
        dict(name='radio_intact', pose=radio_pose, commands=['give all', 'use Machinegun']),
        dict(name='radio_destroyed', pose=radio_pose,
             after_pose=[dict(command='+attack', wait=10), dict(command='-attack', wait=3)],
             expect_log=['RADIO DESTROYED - ROOF ACCESS OPEN']),
    ]
    if players == 1:
        views.append(dict(name='radio_saved_reloaded', pose=[105.6, 1584, 26.8, 0, 90],
             after_pose=[dict(command='save sandstorm_smoke', wait=.5),
                         dict(command='load sandstorm_smoke', wait=4)]))
    views += [
        dict(name='roof_entry_wave', pose=roof_pose,
             after_pose=[dict(command='noclip', wait=.5), dict(command='noclip', wait=.5),
                         dict(command='echo QA_SHUTTERS_BASE', wait=.1),
                         dict(command='listentities all', wait=.2)]),
    ]
    for wave in range(1, 5):
        enemies = [e for e in entities if e['classname'].startswith('monster_')
                   and e.get('targetname') == f'roof_wave_{wave}']
        assert len(enemies) == (4, 6, 8, 4)[wave - 1]
        actions = [dict(wait=1)]  # Previous kill activates the next wave on a later frame.
        for enemy in enemies:
            x, y, z = vec(enemy['origin'])
            actions.append(dict(command=f'cl_bench_pose 0 {x:g} {y:g} {z:g} 0 90', wait=.35))
        actions += [dict(command='cl_bench_pose 0 ' + ' '.join(f'{v:g}' for v in standby), wait=1)]
        if wave <= 3:
            actions += [dict(command=f'echo QA_SHUTTERS_{wave}', wait=.1),
                        dict(command='listentities all', wait=.2)]
        views.append(dict(name=f'roof_wave_{wave}_cleared', pose=standby,
                          after_pose=actions))
    views += [
        dict(name='helicopter_landed', pose=standby,
             after_pose=[dict(wait=8)], expect_log=['EXTRACTION READY']),
    ]
    if players == 2:
        views.append(
        dict(name='one_player_waits_for_squad', pose=pad,
             after_pose=[dict(wait=5)],
             expect_eye_bounds={'y': [pad_y-10, pad_y+10], 'z': [pad_z-4, pad_z+50]}))
    views += [
        dict(name='squad_extracted', pose=pad,
             after_pose=[dict(command=slot1_pad, wait=.2)] if players == 2 else [dict(wait=.2)],
             expect_log=['MISSION COMPLETE'],
             expect_eye_bounds={'x': [intermission[0]-10, intermission[0]+10],
                                'y': [intermission[1]-10, intermission[1]+10],
                                'z': [intermission[2]+10, intermission[2]+40]}),
        dict(name='departure_in_flight', after_pose=[dict(wait=1.2)],
             expect_eye_bounds={'x': [intermission[0]-10, intermission[0]+10],
                                'y': [intermission[1]-10, intermission[1]+10],
                                'z': [intermission[2]+10, intermission[2]+40]}),
        dict(name='early_skip_blocked',
             after_pose=[dict(command='+attack', wait=4.5), dict(command='-attack', wait=.2)],
             expect_eye_bounds={'x': [intermission[0]-10, intermission[0]+10],
                                'y': [intermission[1]-10, intermission[1]+10],
                                'z': [intermission[2]+10, intermission[2]+40]}),
    ]
    return views


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp', type=Path, required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--renderer', choices=('gl1', 'gl3'), default='gl3')
    p.add_argument('--players', type=int, choices=(1, 2), default=2)
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', a.label):
        p.error('label must be a simple directory basename')
    generated = ROOT / 'build/maps/pp_sandstorm' / ('runtime_interactions_' + a.label + '.json')
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(json.dumps(interactions(a.players), indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/maps/capture_sandkeep.py'),
                    '--map-name', 'pp_sandstorm', '--map', str(a.bsp),
                    '--materials', str(ROOT / 'baseq2'), '--assets', str(ROOT / 'baseq2'),
                    '--players', str(a.players), '--renderer', a.renderer,
                    '--label', a.label, '--output-root', str(ROOT / 'build/sandstorm-qa'),
                    '--views', str(generated), '--size', '1280x720', '--keep-runtime'], check=True)
    report = json.loads((ROOT / 'build/sandstorm-qa' / a.label / 'run.json').read_text())
    if a.players == 1:
        saved = Path(report['runtime']) / 'baseq2/save/sandstorm_smoke/pp_sandstorm.sav'
        assert saved.is_file() and saved.stat().st_size > 0, 'Native save file was not written'
    output = ROOT / 'build/sandstorm-qa' / a.label
    # The insertion is framed for slot 0; the co-op partner remains at spawn.
    insertion_candidates = [helicopter_motion(output, 'insertion_wait',
                            f'insertion_ascent_{i}', a.players)[0] for i in range(1,5)]
    insertion = [max(insertion_candidates, key=lambda result:
                     (result['visible_liftoff'],result['rise_pixels']))]
    departure = helicopter_motion(output, 'squad_extracted', 'departure_in_flight', a.players)
    waiting = helicopter_wait(output, a.players)
    report['cinematic_motion'] = {'insertion_wait':waiting, 'insertion':insertion,
                                   'insertion_candidates':insertion_candidates, 'departure':departure}
    failures = [f'{phase} slot {r["slot"]}: helicopter liftoff not visually verified'
                for phase,results in (('insertion',insertion),('departure',departure))
                for r in results if not r['visible_liftoff']]
    if not waiting['visible_wait']:
        failures.append('insertion slot 0: helicopter did not remain visible and stationary during the waiting beat')
    # The stock debug list prints one line per live entity. Since the smoke
    # bypasses all optional triggers, each successive roof encounter should
    # remove exactly one targeted func_explosive shutter from the world.
    counts = {key:0 for key in ('BASE','1','2','3')}
    seen = set()
    current = None
    for line in (output/'qconsole.log').read_text(errors='replace').splitlines():
        marker = re.search(r'QA_SHUTTERS_(BASE|1|2|3)\b', line)
        if marker:
            current = marker.group(1)
            seen.add(current)
        elif current and line.startswith('func_explosive: '):
            counts[current] += 1
    shutter_ok = len(seen)==4 and all(counts[str(i)]==counts['BASE']-i for i in (1,2,3))
    report['shutter_checks'] = {'entity_counts':counts, 'seen_markers':sorted(seen),
                                'all_three_removed':shutter_ok}
    if not shutter_ok:
        failures.append(f'roof shutter entity counts did not decrease once per wave: {counts}')
    if failures:
        report['complete'] = False
        report.setdefault('validation_errors', []).extend(failures)
    (output/'run.json').write_text(json.dumps(report, indent=2)+'\n')
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    main()
