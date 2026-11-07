#!/usr/bin/env python3
"""Validate Sandstorm's compiled hulls, routes and mission entity graph.

This is independent of the generator. It reads the real IBSP38 collision brushes
and the authored MAP, not an idealized rectangle representation of the level.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import re

from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MAXS,
                            PLAYER_MINS, SOLID, enabled, entity_bounds, parse_entities, vec)

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(args):
    source = parse_entities(args.map.read_text())
    bsp = BSP(args.bsp)
    errors, placements, route_results, gates, difficulty, sightlines = [], [], [], [], [], []
    spawn_safety, blocked_probes = [], []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def normalized(entities):
        return Counter(tuple(sorted((k, v) for k, v in e['keys'].items()
                                    if k != 'model' and not k.startswith('_')))
                       for e in entities
                       if e['keys'].get('classname') not in ('worldspawn', 'light'))

    require(normalized(source) == normalized(bsp.entities),
            'Compiled gameplay entities do not match the current MAP')
    require(bool(bsp.lumps['visibility']) and bool(bsp.lumps['lighting']),
            'Release BSP must contain visibility and baked lighting')
    keys = [e['keys'] for e in source]
    byname = defaultdict(list)
    for k in keys:
        if k.get('targetname'):
            byname[k['targetname']].append(k)
    require(sum(k['classname'] == 'info_player_start' for k in keys) == 1,
            'Exactly one solo start is required')
    require(sum(k['classname'] == 'info_player_coop' for k in keys) >= 1,
            'At least one additional co-op start is required')
    for k in keys:
        for field in ('target', 'deathtarget', 'killtarget', 'combattarget', 'pathtarget'):
            if not k.get(field) or (field == 'target' and k['classname'] == 'target_spawner'):
                continue
            require(k[field] in byname,
                    f"Unresolved {field}={k[field]} on {k['classname']} {k.get('origin', '')}")

    radios = [k for k in keys if k['classname'] == 'func_explosive'
              and k.get('target') == 'radio_destroyed']
    require(len(radios) == 1, 'Exactly one destructible communications radio is required')
    for k in radios:
        require(not k.get('targetname') and float(k.get('health', 0)) > 0,
                'Radio must be shootable: positive health and no targetname')
    extraction = [k for k in keys if k['classname'] == 'trigger_platoon_extract']
    require(len(extraction) == 1, 'Exactly one all-player extraction trigger is required')
    for k in extraction:
        require(int(k.get('spawnflags', 0)) & 4 and k.get('targetname') == 'extraction_landed',
                'Extraction must start disabled and enable only after extraction_landed')
        require(k.get('target') == 'extraction_departure',
                'Extraction must start the departure sequence')

    explosive_names = ('breach_wall', 'roof_door_2', 'roof_door_3', 'roof_door_4')
    for name in explosive_names:
        matches = [model for e, model, _ in bsp.bmodels
                   if e['keys'].get('classname') == 'func_explosive'
                   and e['keys'].get('targetname') == name]
        require(len(matches) == 1, f'Expected one explosive brush for {name}')
        if len(matches) == 1:
            bsp.secret_models[name] = matches[0]
    require(any(k.get('classname') == 'trigger_relay' and k.get('targetname') == 'mission_start'
                and k.get('target') == 'insertion_flight' and float(k.get('delay',0)) >= 3
                for k in keys), 'Insertion helicopter must wait before takeoff')
    countdown = [k for k in keys if k.get('classname') == 'trigger_relay'
                 and k.get('targetname') == 'breach_arming' and k.get('message','').startswith('BREACH IN ')]
    require(sorted(int(float(k.get('delay',0))) for k in countdown) == [1,2,3],
            'Breach must show the timed countdown')
    for wave in (2,3,4):
        name=f'roof_door_{wave}'
        require(any(k.get('classname') == 'target_explosion' and k.get('targetname') == name
                    and float(k.get('dmg',0)) == 0 for k in keys),
                f'{name} needs a harmless visual explosion')
        require(any(k.get('classname') == 'trigger_relay' and k.get('targetname') == f'roof_wave_{wave}'
                    and k.get('target') == name and float(k.get('delay',0)) >= .2 for k in keys),
                f'{name} must blast after its defenders spawn')
    for number,lo,hi in [(2,(496*.6,1168*.6),(1040*.6,1552*.6)),
                         (3,(-320*.6,1168*.6),(352*.6,1552*.6)),
                         (4,(608*.6,2360*.6),(1040*.6,2712*.6))]:
        items = [k['classname'] for k in keys if k.get('classname') in ('ammo_bullets','ammo_shells')
                 and k.get('origin') and lo[0] < vec(k['origin'])[0] < hi[0]
                 and lo[1] < vec(k['origin'])[1] < hi[1] and vec(k['origin'])[2] > 224]
        require('ammo_bullets' in items and 'ammo_shells' in items,
                f'Rooftop room {number} needs both bullets and shells')
    for event in ('breach', 'yard'):
        reserves = [(e, model, offset) for e, model, offset in bsp.bmodels
                    if e['keys'].get('classname') == 'func_explosive'
                    and e['keys'].get('targetname') == event+'_reserve_doors']
        require(len(reserves) == 2, f'The {event} response needs two sealed deployment doors')
        for e, model, offset in reserves:
            bounds = bsp.models[model]
            side = 'west' if (bounds[0]+bounds[3])/2+offset[0] < 0 else 'east'
            bsp.secret_models[event+'_reserve_'+side] = model

    def active(k, skill):
        return not int(k.get('spawnflags', 0)) & (256 << skill)

    def reachable(start, skill):
        pending, seen, result = deque([start]), set(), []
        while pending:
            name = pending.popleft()
            if name in seen:
                continue
            seen.add(name)
            for k in byname[name]:
                if not active(k, skill):
                    continue
                result.append(k)
                # Death is a separate event, but is intentionally included when
                # checking whether a triggered encounter can lead to completion.
                for field in ('target', 'deathtarget', 'pathtarget'):
                    if k.get(field) and k['classname'] != 'target_spawner':
                        pending.append(k[field])
        return result

    for skill in range(3):
        live = [k for k in keys if active(k, skill)]
        monsters = [k for k in live if k['classname'].startswith('monster_')]
        counters = [k for k in live if k['classname'] == 'trigger_counter']
        checked = []
        for k in counters:
            name = k.get('targetname')
            inputs = [v for v in live if v.get('deathtarget') == name
                      or (v.get('target') == name and v['classname'] != 'target_spawner')]
            deaths = [v for v in inputs if v.get('deathtarget') == name
                      and v['classname'].startswith('monster_')]
            count = int(k.get('count', 2))
            require(count > 0 and len(inputs) >= count,
                    f'Skill {skill}: {name} needs {count} events but has {len(inputs)} sources')
            if deaths:
                require(len(deaths) == len(inputs) == count,
                        f'Skill {skill}: {name} kill count {count} differs from {len(deaths)} enemies')
            checked.append({'name': name, 'count': count, 'sources': len(inputs)})
        radio_chain = reachable('radio_destroyed', skill)
        doors = [k for k in radio_chain if k['classname'] == 'func_door']
        require(any(float(k.get('wait', 3)) < 0 for k in doors),
                f'Skill {skill}: radio must permanently open the roof security door')
        roof_chain = reachable('roof_wave_1', skill)
        require(any(k['classname'] == 'trigger_platoon_extract'
                    for k in roof_chain),
                f'Skill {skill}: roof encounter/helicopter chain cannot reach extraction')
        for wave, expected in enumerate((4, 6, 8, 4), 1):
            wave_monsters = [k for k in monsters if k.get('targetname') == f'roof_wave_{wave}']
            require(len(wave_monsters) == expected
                    and all(int(k.get('spawnflags', 0)) & 2
                            and k.get('deathtarget') == f'roof_down_{wave}' for k in wave_monsters),
                    f'Skill {skill}: roof wave {wave} must trigger {expected} counted enemies')
        ending = reachable('extraction_departure', skill)
        require(any(k['classname'] in ('target_changelevel', 'target_platoon_intermission') for k in ending),
                f'Skill {skill}: departure has no mission completion')
        breach_chain = reachable('breach_arming', skill)
        require(any(k.get('classname') == 'func_explosive' and k.get('targetname') == 'breach_wall'
                    for k in breach_chain), f'Skill {skill}: charge cannot open the breach')
        response = [k for k in monsters if k.get('targetname') == 'breach_alarm']
        require(len(response) == 4 and all(int(k.get('spawnflags', 0)) & 2 for k in response),
                f'Skill {skill}: loud breach must activate four extra defenders')
        require(any(k.get('classname') == 'trigger_relay' and k.get('target') == 'breach_reserve_doors'
                    and float(k.get('delay',0)) >= .2 for k in breach_chain),
                f'Skill {skill}: reserve doors must open after the squad materializes')
        yard_chain = reachable('compound_alert', skill)
        yard = [k for k in monsters if k.get('targetname') == 'yard_reinforcements']
        require(len(yard) == 4 and all(int(k.get('spawnflags', 0)) & 2 for k in yard),
                f'Skill {skill}: courtyard response must activate four protected defenders')
        require(any(k.get('classname') == 'trigger_relay' and k.get('target') == 'yard_reserve_doors'
                    and float(k.get('delay',0)) >= .2 for k in yard_chain),
                f'Skill {skill}: courtyard reserve doors must open after spawning')
        require(not any(k.get('targetname') == 'breach_alarm' for k in yard_chain),
                f'Skill {skill}: the ordinary courtyard response must not trigger the loud breach')
        require(any(k.get('classname') == 'misc_platoon_dropship' and k.get('deathtarget') == 'extract_liftoff'
                    for k in ending), f'Skill {skill}: extraction must launch the outbound helicopter')
        require(all(active(k, skill) for k in radios + extraction),
                f'Skill {skill}: a mandatory objective is filtered out')
        difficulty.append({'skill': skill, 'enemies': len(monsters), 'counters': checked})

    monster_hulls = []
    for entity in source:
        k = entity['keys']
        c = k['classname']
        if c in ('info_player_start', 'info_player_coop', 'info_player_deathmatch'):
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
        elif c.startswith('monster_'):
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK
            if c in ('monster_tank', 'monster_plastic_tank'):
                mins, maxs = (-32, -32, -16), (32, 32, 72)
            elif c == 'monster_ant':
                mins, maxs = (-24, -24, -24), (24, 24, 16)
            monster_hulls.append((entity, mins, maxs))
        elif c.startswith(('ammo_', 'weapon_', 'item_', 'key_')):
            mins, maxs, mask = (-15,) * 3, (15,) * 3, SOLID
        else:
            continue
        point = vec(k['origin'])
        hit = bsp.collision(point, mins, maxs, mask)
        require(not hit, f'{c} at {point} intersects {hit}')
        placements.append({'classname': c, 'point': point, 'blocker': hit})
    for index, (e, mins, maxs) in enumerate(monster_hulls):
        origin = vec(e['keys']['origin'])
        for other, omin, omax in monster_hulls[index + 1:]:
            if not any(enabled(e, s) and enabled(other, s) for s in range(3)):
                continue
            q = vec(other['keys']['origin'])
            overlaps = all(origin[j] + mins[j] < q[j] + omax[j]
                           and q[j] + omin[j] < origin[j] + maxs[j] for j in range(3))
            # Different waves may safely reuse a bay only after the earlier
            # occupants have died; authored explicit reuse marks that intent.
            reuse = e['keys'].get('_sandstorm_reuse') and other['keys'].get('_sandstorm_reuse')
            require(not overlaps or reuse, f'Overlapping enemy spawns at {origin} / {q}')

    document = json.loads(args.routes.read_text())
    require(bool(document.get('routes')), 'No authored walking routes to validate')

    # The drain encounter is a set of defenders who already exist when the
    # level starts, not monsters materializing in front of an advancing player.
    # Derive the corridor from its authored walking route so this stays valid
    # if the scale or the approach coordinates change.
    drain = next((r for r in document.get('routes', [])
                  if r.get('name') == 'underground infiltration to storage'), None)
    require(bool(drain and drain.get('points')), 'Missing underground route for defender audit')
    compiled = [e['keys'] for e in bsp.entities]
    if drain and drain.get('points'):
        arming = [e for e in source if e['keys'].get('classname') == 'trigger_once'
                  and e['keys'].get('target') == 'breach_arming']
        require(len(arming) == 1, 'Expected one one-shot breach approach trigger')
        if len(arming) == 1:
            bounds=entity_bounds(arming[0])
            safe=True
            if bounds:
                for a,b in zip(drain['points'],drain['points'][1:]):
                    steps=max(1,math.ceil(math.dist(a,b)/8))
                    for i in range(steps+1):
                        p=tuple(a[j]+(b[j]-a[j])*i/steps for j in range(3))
                        if all(p[j]+PLAYER_MAXS[j] > bounds[j] and p[j]+PLAYER_MINS[j] < bounds[j+3]
                               for j in range(3)):
                            safe=False
                            break
                    if not safe:
                        break
            require(bool(bounds) and safe, 'Quiet drain route must not touch the demolition trigger')
        points = drain['points']
        corridor_x = points[0][0]
        ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
        defenders = [k for k in compiled if k.get('classname') == 'monster_soldier'
                     and abs(vec(k['origin'])[0] - corridor_x) <= 80
                     and ymin <= vec(k['origin'])[1] <= ymax
                     and vec(k['origin'])[2] < -40]
        require(len(defenders) == 8, f'Expected eight drain defenders, found {len(defenders)}')
        for k in defenders:
            require(not int(k.get('spawnflags', 0)) & 2,
                    f"Drain defender is trigger-spawned: {k.get('origin')}")
            require(all(active(k, skill) for skill in range(3)),
                    f"Drain defender is excluded on a skill level: {k.get('origin')}")
    else:
        defenders = []

    # Find the authored scout patrol endpoints in the compiled BSP and test
    # their lines of sight to all initial player starts and nearby supplies.
    # Sampling between endpoints also catches a patrol briefly seeing the
    # spawn between two otherwise safe waypoints. Stock soldier FindTarget
    # rejects ranges >= 1000, and visible() traces eye-to-eye.
    starts = [vec(k['origin']) for k in compiled
              if k.get('classname') in ('info_player_start', 'info_player_coop')]
    nearby_supplies = [vec(k['origin']) for k in compiled
                       if k.get('classname', '').startswith(('ammo_', 'weapon_', 'item_'))
                       and starts and min(math.hypot(vec(k['origin'])[0]-p[0],
                                                    vec(k['origin'])[1]-p[1]) for p in starts) <= 550
                       and abs(vec(k['origin'])[2]-starts[0][2]) <= 50]
    require(bool(nearby_supplies), 'Could not identify starting supplies for scout-sight audit')
    compiled_names = {k['targetname']: k for k in compiled if k.get('targetname')}
    scouts = [k for k in compiled if k.get('classname') == 'monster_soldier_light'
              and k.get('target', '').startswith('scout_')]
    require(len(scouts) == 5, f'Expected five named scout patrols, found {len(scouts)}')
    targets = [('spawn', p) for p in starts]
    # A pickup sitting on a crate may have a raised origin; use the standing
    # player height at the nearby ground-level starts when checking its area.
    targets += [('supply', (p[0], p[1], starts[0][2])) for p in nearby_supplies] if starts else []
    for scout in scouts:
        name = scout['target']
        first = compiled_names.get(name)
        second = compiled_names.get(first.get('target')) if first else None
        if not first or not second or first.get('classname') != 'path_corner' or second.get('classname') != 'path_corner':
            require(False, f'Scout {name} has a missing patrol endpoint')
            continue
        require(second.get('target') == name, f'Scout {name} does not patrol back to its first endpoint')
        a, b = vec(first['origin']), vec(second['origin'])
        risks, checked = [], 0
        for i in range(11):
            origin = tuple(a[j] + (b[j]-a[j])*i/10 for j in range(3))
            for kind, player in targets:
                if math.dist(origin, player) >= 1000:
                    continue
                checked += 1
                eye = (origin[0], origin[1], origin[2] + 25)
                player_eye = (player[0], player[1], player[2] + 22)
                if not bsp.segment_hits(eye, player_eye):
                    risks.append({'patrol_fraction': i/10, 'target': kind, 'point': player})
        require(not risks, f'Scout {name} has sight of a spawn or supply position: {risks[:3]}')
        spawn_safety.append({'scout': name, 'in_range_tests': checked, 'unblocked': risks})
    for route in document.get('routes', []):
        opened = route.get('opened_doors', [])
        destroyed = route.get('destroyed_secrets', [])
        require(all(name in bsp.secret_models for name in destroyed),
                f"Route {route['name']} refers to an unknown explosive wall")
        previous, failures, samples = None, [], 0
        for start, end in zip(route['points'], route['points'][1:]):
            steps = max(1, math.ceil(math.dist(start, end) / 8))
            for i in range(steps + 1):
                point = tuple(start[j] + (end[j] - start[j]) * i / steps for j in range(3))
                hit = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed)
                if hit and previous:
                    for rise in range(1, 19):
                        raised = (point[0], point[1], point[2] + rise)
                        if raised[2] > previous[2] + 18.03125:
                            break
                        if bsp.collision(raised, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed):
                            continue
                        up = (previous[0], previous[1], max(previous[2], raised[2]))
                        sweep = [tuple(previous[j] + (up[j] - previous[j]) * t / 4
                                       for j in range(3)) for t in range(1, 5)]
                        sweep += [tuple(up[j] + (raised[j] - up[j]) * t / 4
                                        for j in range(3)) for t in range(1, 5)]
                        if any(bsp.collision(q, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed)
                               for q in sweep):
                            continue
                        point, hit = raised, None
                        break
                ladder = route.get('mode') == 'ladder' and bsp.collision(
                    point, (-20, -20, -28), (20, 20, 32), 0x20000000, opened, destroyed)
                in_water = route.get('mode') == 'swim' and bool(
                    bsp.point_contents((point[0], point[1], point[2]-23)) & 32)
                support = ladder or in_water or any(
                    bsp.collision((point[0], point[1], point[2] - dz),
                                  (-4, -4, -24), (4, 4, 32), PLAYER_MASK, opened, destroyed)
                    for dz in ((2, 8, 16, 24, 32) if route.get('mode') == 'ladder'
                               else (2, 8, 16, 24)))
                if (hit or not support) and len(failures) < 6:
                    failures.append({'point': point, 'blocker': hit or 'unsupported'})
                if not hit:
                    previous = point
                samples += 1
        require(not failures, f"Route {route['name']}: {failures}")
        route_results.append({'name': route['name'], 'samples': samples, 'failures': failures})
    for probe in document.get('water_probes', []):
        p = tuple(probe['origin'])
        feet = (p[0], p[1], p[2]-23)
        middle = (p[0], p[1], p[2]-1)
        require(bool(bsp.point_contents(feet) & 32) and bool(bsp.point_contents(middle) & 32),
                f"Water probe {probe['name']} does not reach swimming depth")
    # Use the actual compiled brush planes to prove the intended muzzle/fire
    # lanes. A traversable tower still fails its purpose if its rails block fire.
    for sightline in document.get('sightlines', []):
        start, end = tuple(sightline['start']), tuple(sightline['end'])
        hits = bsp.segment_hits(start, end, opened=sightline.get('opened_doors', []))
        require(not hits, f"Sightline {sightline['name']} blocked: {hits[:6]}")
        sightlines.append({'name': sightline['name'], 'start': start, 'end': end,
                           'hits': hits})
    probes = list(document.get('gate_probes', []))
    probe_names = {p['name'] for p in probes}
    # The mission must also prove its actual closed movers block passage, even
    # if a newly authored route file omitted its optional explicit gate probes.
    for entity, model, offset in bsp.bmodels:
        k = entity['keys']
        if k.get('classname') != 'func_door' or not k.get('targetname'):
            continue
        name = k['targetname']
        if name in probe_names:
            continue
        bounds = bsp.models[model]
        point = [(bounds[0] + bounds[3]) / 2 + offset[0],
                 (bounds[1] + bounds[4]) / 2 + offset[1], bounds[2] + 24 + offset[2]]
        probes.append({'name': name, 'point': point, 'opened_doors': [name]})
        probe_names.add(name)
    for gate in probes:
        point = tuple(gate['point'])
        closed = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        opened = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK,
                               gate['opened_doors'])
        require(bool(closed) and not opened,
                f"Gate {gate['name']} must block before activation and clear after: {closed}, {opened}")
        gates.append({'name': gate['name'], 'closed': closed, 'opened': opened})
    for name in explosive_names:
        if name not in bsp.secret_models:
            continue
        entity, model, offset = next((e,m,o) for e,m,o in bsp.bmodels if m == bsp.secret_models[name])
        bounds = bsp.models[model]
        point = ((bounds[0]+bounds[3])/2+offset[0], (bounds[1]+bounds[4])/2+offset[1],
                 bounds[2]+24+offset[2])
        closed = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        cleared = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, destroyed=[name])
        require(bool(closed) and not cleared,
                f'Explosive wall {name} must block initially and clear after the blast: {closed}, {cleared}')
        gates.append({'name':name,'closed':closed,'opened':cleared})
    for name in ('breach_reserve_west','breach_reserve_east','yard_reserve_west','yard_reserve_east'):
        if name not in bsp.secret_models:
            continue
        entity, model, offset = next((e,m,o) for e,m,o in bsp.bmodels if m == bsp.secret_models[name])
        bounds=bsp.models[model]
        point=((bounds[0]+bounds[3])/2+offset[0], (bounds[1]+bounds[4])/2+offset[1], bounds[2]+24+offset[2])
        closed=bsp.collision(point,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK)
        cleared=bsp.collision(point,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,destroyed=[name])
        require(bool(closed) and not cleared, f'Reserve door {name} does not block and clear correctly')
        gates.append({'name':name,'closed':closed,'opened':cleared})
        left, right = bounds[0]+offset[0], bounds[3]+offset[0]
        center = (left+right)/2
        event = 'breach_alarm' if name.startswith('breach') else 'yard_reinforcements'
        squad = [k for k in compiled if k.get('classname') == 'monster_soldier_ss'
                 and k.get('targetname') == event
                 and abs(vec(k['origin'])[0]-center) < (right-left)/2]
        require(len(squad)==2, f'{name} must contain two reserve soldiers')
        for soldier in squad:
            p=vec(soldier['origin'])
            eye=(p[0],p[1],p[2]+25)
            exits=[(p[0],bounds[1]+offset[1]-40,eye[2]),
                   (p[0],1304*.6+40,eye[2]),
                   (left-40,p[1],eye[2]),(right+40,p[1],eye[2]),
                   (p[0],p[1],184*.7+40)]
            require(all(bsp.segment_hits(eye,q) for q in exits),
                    f'{name} spawn at {p} is accessible before reinforcement deployment')
    # Optional sampled points in intentionally sealed perimeter areas: use a
    # full standing hull, and allow checking after named doors have opened.
    for probe in document.get('blocked_probes', []):
        point = tuple(probe['point'])
        hit = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK,
                            probe.get('opened_doors', []))
        require(bool(hit), f"Perimeter probe {probe['name']} is unexpectedly open at {point}")
        blocked_probes.append({'name': probe['name'], 'point': point, 'blocker': hit})
    if args.bsp_log.exists():
        log = args.bsp_log.read_text(errors='replace')
        require(not re.search(r'\bleaked\b|unbounded|bounds out of range|\bWARNING\b', log, re.I),
                'BSP compiler reported a leak or geometry warning')
    else:
        require(False, f'Missing BSP compile log: {args.bsp_log}')
    return {'passed': not errors, 'errors': errors, 'map_sha256': sha(args.map),
            'bsp_sha256': sha(args.bsp), 'routes_sha256': sha(args.routes),
            'difficulty': difficulty, 'placements': placements,
            'routes': route_results, 'gates': gates, 'sightlines': sightlines,
            'drain_defenders': len(defenders), 'spawn_safety': spawn_safety,
            'blocked_probes': blocked_probes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=ROOT / 'maps/source/pp_sandstorm.map')
    parser.add_argument('--bsp', type=Path, default=ROOT / 'build/sandstorm-candidate/maps/pp_sandstorm.bsp')
    parser.add_argument('--routes', type=Path, default=ROOT / 'tools/maps/sandstorm_routes.json')
    parser.add_argument('--bsp-log', type=Path, default=ROOT / 'build/maps/pp_sandstorm/bsp.log')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/maps/pp_sandstorm/verification.json')
    args = parser.parse_args()
    report = verify(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'errors': report['errors'],
                      'placement_hulls': len(report['placements']),
                      'routes': len(report['routes']), 'gate_probes': len(report['gates']),
                      'sightlines': len(report['sightlines']),
                      'drain_defenders': report['drain_defenders'],
                      'scout_patrols': len(report['spawn_safety']),
                      'blocked_probes': len(report['blocked_probes']),
                      'enemies_by_skill': [d['enemies'] for d in report['difficulty']]}, indent=2))
    raise SystemExit(not report['passed'])


if __name__ == '__main__':
    main()
