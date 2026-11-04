#!/usr/bin/env python3
"""Independently check Sandkeep's entity logic and compiled Q2 collision hulls.

No generator code is imported. Geometry checks operate on the compiled IBSP38
planes, nodes, leaves and brushes, using Quake II's box/convex-brush test.
Optional route JSON contains {"routes": [{"name": "...", "points": [[x,y,z]],
"opened_doors": ["targetname"], "destroyed_secrets": ["cache_one"]}]}.
Optional "secret_probes" entries have a name, outside, inside, and rewards list.
Optional "outdoor_probes" entries have a name and point at the player's eye.
Points are player origins, not foot positions. Secret walls are identified in
the source MAP by the editor-only _sandkeep_secret property, never targetname
(targetnamed func_explosive entities cannot take damage in this engine).
This is static validation, not a substitute for a gameplay or frame-rate test.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
LUMPS = ('entities planes vertexes visibility nodes texinfo faces lighting '
         'leafs leaffaces leafbrushes edges surfedges models brushes brushsides '
         'pop areas areaportals').split()
PLAYER_MINS = (-16., -16., -24.)
PLAYER_MAXS = (16., 16., 32.)
SOLID = 1 | 2
PLAYER_MASK = SOLID | 0x10000
MONSTER_MASK = SOLID | 0x20000
EPSILON = 0.03125


def parse_entities(text):
    entities, current, depth = [], None, 0
    for lineno, raw in enumerate(text.replace('\x00', '').splitlines(), 1):
        line = raw.split('//', 1)[0].strip()
        if not line:
            continue
        if line == '{':
            depth += 1
            if depth == 1:
                current = {'keys': {}, 'textures': [], 'brush_count': 0, 'brushes': [],
                           'line': lineno, 'index': len(entities)}
            elif depth == 2:
                current['brush_count'] += 1
                current['brushes'].append([])
            else:
                raise ValueError(f'unsupported nested brush at line {lineno}')
        elif line == '}':
            if depth == 1:
                entities.append(current)
            depth -= 1
            if depth < 0:
                raise ValueError(f'unbalanced closing brace at line {lineno}')
        elif depth == 1:
            match = re.fullmatch(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s+"(.*)"', line)
            if not match:
                raise ValueError(f'malformed entity property at line {lineno}')
            if match[1] in current['keys']:
                raise ValueError(f'duplicate property {match[1]!r} at line {lineno}')
            current['keys'][match[1]] = match[2]
        elif depth == 2:
            match = re.match(r'(?:\(\s*[^)]+\)\s*){3}(\S+)\s+', line)
            if not match:
                raise ValueError(f'malformed brush face at line {lineno}')
            current['textures'].append(match[1])
            points = [vec(p) for p in re.findall(r'\(\s*([^)]+)\)', line)[:3]]
            fields = line[match.end():].split()
            current['brushes'][-1].append({'points': points, 'texture': match[1],
                                           'mapping': tuple(map(float, fields[:5])), 'line': lineno})
        else:
            raise ValueError(f'text outside entity at line {lineno}')
    if depth:
        raise ValueError('unbalanced MAP braces')
    return entities


def vec(value):
    result = tuple(map(float, value.split()))
    if len(result) != 3 or not all(math.isfinite(x) for x in result):
        raise ValueError(f'invalid origin {value!r}')
    return result


def flags(entity):
    return int(entity['keys'].get('spawnflags', '0'))


def label(entity):
    k = entity['keys']
    return f"#{entity['index']} {k.get('classname')} {k.get('targetname', k.get('origin', ''))}".strip()


def enabled(entity, skill):
    return not flags(entity) & (256, 512, 1024)[skill]


def entity_bounds(entity):
    points = [p for brush in entity.get('brushes', ()) for face in brush for p in face['points']]
    if not points:
        return None
    return tuple(min(p[i] for p in points) for i in range(3)) + tuple(max(p[i] for p in points) for i in range(3))


def source_brush_checks(entities, checks):
    """Check actual face records, independently of generator helper functions."""
    brushes, secret_walls = 0, {}
    for entity in entities:
        seen = set()
        for brush in entity.get('brushes', ()):
            brushes += 1
            signature = []
            checks.require(len(brush) >= 4, f'{label(entity)} has a brush with fewer than four faces')
            for face in brush:
                p0, p1, p2 = face['points']
                a, b = [p0[i] - p1[i] for i in range(3)], [p2[i] - p1[i] for i in range(3)]
                n = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
                length = math.sqrt(sum(v*v for v in n))
                checks.require(length > 0, f"degenerate face at MAP line {face['line']}")
                if length:
                    normal = tuple(v / length for v in n)
                    distance = sum(normal[i] * p0[i] for i in range(3))
                    signature.append(tuple(round(v, 5) for v in (*normal, distance)))
                mapping = face['mapping']
                checks.require(len(mapping) == 5 and all(math.isfinite(v) for v in mapping)
                               and mapping[3] != 0 and mapping[4] != 0,
                               f"invalid texture mapping at MAP line {face['line']}")
            signature = tuple(sorted(signature))
            checks.require(signature not in seen, f'{label(entity)} contains an exact duplicate brush')
            seen.add(signature)
        name = entity['keys'].get('_sandkeep_secret')
        if name:
            checks.require(name not in secret_walls, f'duplicate secret wall marker {name!r}')
            secret_walls[name] = entity
            checks.require(entity['keys'].get('classname') == 'func_explosive',
                           f'{label(entity)} secret cover must be func_explosive')
            checks.require(not entity['keys'].get('targetname'),
                           f'{label(entity)} secret cover is targetnamed and cannot be shot')
            checks.require(not flags(entity) & 1, f'{label(entity)} secret cover starts invisible')
            checks.require(float(entity['keys'].get('health', '100')) > 0,
                           f'{label(entity)} secret cover has nonpositive health')
            triggers = [e for e in entities if e['keys'].get('classname') == 'trigger_once'
                        and e['keys'].get('target') == name]
            secrets = [e for e in entities if e['keys'].get('classname') == 'target_secret'
                       and e['keys'].get('targetname') == name]
            checks.require(len(triggers) == 1 and len(secrets) == 1,
                           f'secret {name!r} needs one interior trigger_once and one target_secret')
            checks.require(entity['keys'].get('target') != name,
                           f'secret {name!r} is awarded by breaking the cover instead of entering the room')
            if len(triggers) == 1:
                wall, trigger = entity_bounds(entity), entity_bounds(triggers[0])
                if wall and trigger:
                    separation = max(max(wall[i] - trigger[i+3], trigger[i] - wall[i+3]) for i in range(3))
                    checks.require(separation >= 24, f'secret {name!r} trigger is too close to its closed cover')
    checks.require(len(secret_walls) >= 2, 'at least two marked, destructible secret covers are required')
    checks.results['source_geometry'] = {'brushes': brushes, 'marked_secret_walls': sorted(secret_walls)}
    return secret_walls


class Checks:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.results = {}

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)
        return condition


def graph_checks(entities, checks, map_name):
    by_name = defaultdict(list)
    for entity in entities:
        if entity['keys'].get('targetname'):
            by_name[entity['keys']['targetname']].append(entity)

    def reachable(start, key='target', skill=None):
        first = start['keys'].get(key)
        queue = deque(by_name.get(first, ()))
        visited, found = set(), []
        while queue:
            entity = queue.popleft()
            if entity['index'] in visited or (skill is not None and not enabled(entity, skill)):
                continue
            visited.add(entity['index'])
            found.append(entity)
            queue.extend(by_name.get(entity['keys'].get('target'), ()))
        return found

    for entity in entities:
        k = entity['keys']
        for key in ('target', 'deathtarget', 'killtarget', 'pathtarget', 'combattarget'):
            if not k.get(key) or (key == 'target' and k.get('classname') == 'target_spawner'):
                continue
            checks.require(k[key] in by_name, f'{label(entity)} has unresolved {key}={k[key]}')

    starts = [e for e in entities if e['keys'].get('classname') == 'info_player_start']
    coop = [e for e in entities if e['keys'].get('classname') == 'info_player_coop']
    checks.require(len(starts) == 1, 'exactly one single-player start is required')
    checks.require(len(coop) >= 3, 'at least three co-op starts are required')
    for e in starts + coop:
        checks.require(not e['keys'].get('targetname'), f'{label(e)} must be unnamed for direct map loading')
        checks.require(not flags(e) & (256 | 512 | 1024), f'{label(e)} is excluded on a skill')
    if starts:
        start = vec(starts[0]['keys']['origin'])
        for e in coop:
            checks.require(math.dist(start, vec(e['keys']['origin'])) < 550,
                           f'{label(e)} is more than 550 units from main start')
    for e in starts + coop:
        checks.require(vec(e['keys']['origin'])[1] < -2112,
                       f'{label(e)} must begin outside the southern sandbox rim')
    checks.require(not any(t == 'sandkeep/sign_start' for e in entities for t in e['textures']),
                   'the removed insertion sign_start graphic must not be present')

    boss_list = [e for e in entities if e['keys'].get('classname') == 'monster_boss2']
    checks.require(len(boss_list) == 1, 'exactly one placed helicopter boss is required')
    exits = [e for e in entities if e['keys'].get('classname') == 'target_changelevel']
    checks.require(bool(exits), 'a target_changelevel exit is required')
    for e in exits:
        checks.require(e['keys'].get('map', '').lstrip('*') == map_name,
                       f'{label(e)} must loop to the installed {map_name} map')
        exit_name = e['keys'].get('targetname')
        exit_triggers = [trigger for trigger in entities
                         if trigger['keys'].get('classname') in ('trigger_once', 'trigger_multiple')
                         and exit_name and trigger['keys'].get('target') == exit_name]
        checks.require(bool(exit_triggers), f'{label(e)} needs a physical exterior extraction trigger')
        for trigger in exit_triggers:
            bounds = entity_bounds(trigger)
            checks.require(bounds is not None and (bounds[1] + bounds[4]) / 2 > 3136,
                           f'{label(trigger)} extraction trigger must be beyond the northern sandbox rim')

    progress = []
    counters = [e for e in entities if e['keys'].get('classname') == 'trigger_counter']
    for counter in counters:
        incoming = [e for e in entities if e['keys'].get('classname') == 'func_button'
                    and counter in reachable(e)]
        if len(incoming) == 2 and int(counter['keys'].get('count', '2')) == 2:
            keep_doors = [e for e in reachable(counter) if e['keys'].get('classname') == 'func_door']
            checks.require(bool(keep_doors), f'{label(counter)} does not open a keep gate')
            for e in incoming:
                checks.require(float(e['keys'].get('wait', '3')) < 0,
                               f'{label(e)} must be one-shot to prevent repeat counter inputs')
                checks.require(not e['keys'].get('targetname') or float(e['keys'].get('health', '0')) > 0,
                               f'{label(e)} has no touch or shoot activation')
            for door in keep_doors:
                checks.require(float(door['keys'].get('wait', '3')) < 0,
                               f'{label(door)} must remain open for co-op respawns')
            for skill in range(3):
                for button in incoming:
                    checks.require(enabled(button, skill) and counter in reachable(button, skill=skill),
                                   f'objective button/counter chain breaks on skill {skill}')
                checks.require(enabled(counter, skill) and all(door in reachable(counter, skill=skill) for door in keep_doors),
                               f'counter/keep gate chain breaks on skill {skill}')
            progress.append({'counter': label(counter), 'buttons': [label(e) for e in incoming],
                             'gates': [label(e) for e in keep_doors]})
    checks.require(bool(progress), 'no two distinct one-shot objective buttons feed a count-2 keep gate counter')

    if boss_list:
        boss = boss_list[0]
        checks.require(bool(flags(boss) & 2) and bool(boss['keys'].get('targetname')),
                       'helicopter must be a named trigger-spawn monster')
        checks.require(not flags(boss) & 1, 'boss ambush flag prevents immediate activation against trigger player')
        checks.require(bool(boss['keys'].get('deathtarget')), 'boss requires an explicit deathtarget')
        for skill in range(3):
            checks.require(enabled(boss, skill), f'boss is missing on skill {skill}')
            activators = [e for e in entities if e['keys'].get('classname') in ('trigger_once', 'func_button')
                          and enabled(e, skill) and boss in reachable(e, skill=skill)]
            checks.require(bool(activators), f'boss has no player activation chain on skill {skill}')
            death_chain = reachable(boss, key='deathtarget', skill=skill)
            doors = [e for e in death_chain if e['keys'].get('classname') == 'func_door']
            checks.require(bool(doors), f'boss death has no exit gate on skill {skill}')
            for door in doors:
                checks.require(float(door['keys'].get('wait', '3')) < 0,
                               f'{label(door)} must remain permanently open after boss death')
            checks.require(all(enabled(e, skill) for e in exits), f'exit is disabled on skill {skill}')

    classes = Counter(e['keys'].get('classname', '') for e in entities)
    checks.results['entity_counts'] = dict(sorted(classes.items()))
    checks.results['objective_chains'] = progress
    checks.results['monsters_by_skill'] = {str(skill): sum(e['keys'].get('classname', '').startswith('monster_')
                                          and enabled(e, skill) for e in entities) for skill in range(3)}


class BSP:
    def __init__(self, path):
        self.raw = Path(path).read_bytes()
        if len(self.raw) < 160 or struct.unpack_from('<4si', self.raw) != (b'IBSP', 38):
            raise ValueError('expected Quake II IBSP38')
        self.lumps = {}
        for i, name in enumerate(LUMPS):
            start, size = struct.unpack_from('<ii', self.raw, 8 + i * 8)
            if start < 0 or size < 0 or start + size > len(self.raw):
                raise ValueError(f'{name} lump exceeds BSP file')
            self.lumps[name] = self.raw[start:start + size]
        self.entities = parse_entities(self.lumps['entities'].decode('utf-8'))
        self.planes = [record[:4] for record in struct.iter_unpack('<4fi', self.lumps['planes'])]
        self.nodes = [record[:3] for record in struct.iter_unpack('<iii6h2H', self.lumps['nodes'])]
        self.leaves = list(struct.iter_unpack('<ihh6h4H', self.lumps['leafs']))
        self.leafbrushes = [v[0] for v in struct.iter_unpack('<H', self.lumps['leafbrushes'])]
        self.brushes = list(struct.iter_unpack('<iii', self.lumps['brushes']))
        self.sides = list(struct.iter_unpack('<Hh', self.lumps['brushsides']))
        self.models = list(struct.iter_unpack('<9f3i', self.lumps['models']))
        self.vertexes = list(struct.iter_unpack('<3f', self.lumps['vertexes']))
        self.edges = list(struct.iter_unpack('<2H', self.lumps['edges']))
        self.surfedges = [v[0] for v in struct.iter_unpack('<i', self.lumps['surfedges'])]
        self.faces = list(struct.iter_unpack('<Hhihh4Bi', self.lumps['faces']))
        self.texinfo = list(struct.iter_unpack('<8fii32si', self.lumps['texinfo']))
        self.model_brushes = [self.collect_brushes(model[9]) for model in self.models]
        self.secret_models = {}
        self.bmodels = []
        for e in self.entities:
            k = e['keys']
            if not k.get('model', '').startswith('*') or k.get('classname', '').startswith('trigger_'):
                continue
            if k.get('classname') in ('func_areaportal', 'func_water'):
                continue
            if k.get('classname') == 'func_wall' and flags(e) & 1 and not flags(e) & 4:
                continue
            if k.get('classname') == 'func_door' and flags(e) & 1:
                continue
            self.bmodels.append((e, int(k['model'][1:]), vec(k.get('origin', '0 0 0'))))

    def collect_brushes(self, headnode):
        found, seen, pending = set(), set(), [headnode]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            if node < 0:
                leaf = self.leaves[-node - 1]
                first, count = leaf[-2:]
                found.update(self.leafbrushes[first:first + count])
            else:
                pending.extend(self.nodes[node][1:])
        return tuple(sorted(found))

    def point_contents(self, point):
        node = self.models[0][9]
        while node >= 0:
            plane_i, front, back = self.nodes[node]
            nx, ny, nz, distance = self.planes[plane_i]
            d = point[0] * nx + point[1] * ny + point[2] * nz - distance
            node = front if d >= 0 else back
        return self.leaves[-node - 1][0]

    def brush_overlaps(self, index, point, mins, maxs, mask):
        first, count, contents = self.brushes[index]
        if not count or not contents & mask:
            return False
        for side in self.sides[first:first + count]:
            nx, ny, nz, distance = self.planes[side[0]]
            normal = (nx, ny, nz)
            low = sum(normal[j] * (point[j] + (maxs[j] if normal[j] < 0 else mins[j])) for j in range(3))
            # Treat mere surface contact within the engine's 1/32-unit epsilon
            # as nonpenetrating. This avoids false positives on a resting floor.
            if low >= distance - EPSILON:
                return False
        return True

    def collision(self, point, mins, maxs, mask, opened=(), destroyed=()):
        if self.point_contents(point) & SOLID:
            return 'world solid/void at origin'
        for index in self.model_brushes[0]:
            if self.brush_overlaps(index, point, mins, maxs, mask):
                return f'world brush {index}'
        for entity, model, offset in self.bmodels:
            if entity['keys'].get('classname') == 'func_door' and entity['keys'].get('targetname') in opened:
                offset = self.open_door_offset(entity, model, offset)
            if model in {self.secret_models[name] for name in destroyed if name in self.secret_models}:
                continue
            local = tuple(point[j] - offset[j] for j in range(3))
            for index in self.model_brushes[model]:
                if self.brush_overlaps(index, local, mins, maxs, mask):
                    return f'{label(entity)} brush {index}'
        return None

    def open_door_offset(self, entity, model, offset):
        k = entity['keys']
        angle = float(k.get('angle', '0'))
        direction = ((0., 0., 1.) if angle == -1 else (0., 0., -1.) if angle == -2
                     else (math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0.))
        bounds = self.models[model]
        # A literal zero selects the engine default; it cannot request zero lip.
        lip = float(k.get('lip', '8')) or 8.
        # CMod_LoadSubmodels expands each bound by one unit before setmodel;
        # SP_func_door calculates its travel from that expanded entity size.
        distance = sum(abs(direction[i]) * (bounds[i+3] - bounds[i] + 2) for i in range(3)) - lip
        return tuple(offset[i] + direction[i] * distance for i in range(3))

    def segment_hits(self, start, end, opened=(), destroyed=()):
        """Return brush models intersecting a ray, using convex-plane clipping."""
        hits = []
        models = [(None, 0, (0., 0., 0.)), *self.bmodels]
        removed = {self.secret_models[name] for name in destroyed if name in self.secret_models}
        for entity, model, offset in models:
            if model in removed:
                continue
            if entity and entity['keys'].get('classname') == 'func_door' and entity['keys'].get('targetname') in opened:
                offset = self.open_door_offset(entity, model, offset)
            a = tuple(start[i] - offset[i] for i in range(3))
            b = tuple(end[i] - offset[i] for i in range(3))
            for index in self.model_brushes[model]:
                first, count, contents = self.brushes[index]
                if not count or not contents & SOLID:
                    continue
                enter, leave = 0., 1.
                for side in self.sides[first:first+count]:
                    nx, ny, nz, distance = self.planes[side[0]]
                    da = a[0]*nx + a[1]*ny + a[2]*nz - distance
                    db = b[0]*nx + b[1]*ny + b[2]*nz - distance
                    if da > -EPSILON and db > -EPSILON:
                        enter = 2.
                        break
                    if da > db:
                        enter = max(enter, (da + EPSILON) / (da - db))
                    elif db > da:
                        leave = min(leave, (da - EPSILON) / (da - db))
                    if enter > leave:
                        break
                if enter <= leave and enter <= 1:
                    hits.append({'fraction': max(0., enter), 'model': model, 'brush': index,
                                 'entity': label(entity) if entity else 'world'})
        return sorted(hits, key=lambda hit: hit['fraction'])


def bind_secret_models(bsp, source_walls, checks):
    for name, entity in source_walls.items():
        bounds = entity_bounds(entity)
        # Match the source envelope instead of relying on entity order or
        # unsupported game keys; allow the compiler's small bound tolerance.
        matches = [model for e, model, offset in bsp.bmodels
                   if e['keys'].get('classname') == 'func_explosive'
                   and all(abs(bsp.models[model][i] + offset[i % 3] - bounds[i]) <= 1.1
                           for i in range(6))]
        if checks.require(len(matches) == 1, f'secret {name!r} does not match exactly one compiled breakable model'):
            bsp.secret_models[name] = matches[0]


def secret_geometry_checks(bsp, document, checks):
    results = []
    probes = document.get('secret_probes', ())
    seen = set()
    for probe in probes:
        name, outside, inside = probe['name'], probe['outside'], probe['inside']
        seen.add(name)
        if not checks.require(name in bsp.secret_models, f'secret probe {name!r} has no compiled wall'):
            continue
        for point_name, point in (('outside', outside), ('inside', inside)):
            checks.require(not bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK),
                           f'secret {name!r} {point_name} probe begins inside collision')
        closed_hits = bsp.segment_hits(outside, inside)
        checks.require(bool(closed_hits) and closed_hits[0]['model'] == bsp.secret_models[name],
                       f'secret {name!r} approach is not concealed by its breakable cover')
        opened_hits = bsp.segment_hits(outside, inside, destroyed=(name,))
        checks.require(not opened_hits, f'secret {name!r} remains sealed after cover breaks: {opened_hits[:2]}')
        samples, blockers = max(1, math.ceil(math.dist(outside, inside) / 8)), []
        for i in range(samples + 1):
            point = tuple(outside[j] + (inside[j] - outside[j]) * i / samples for j in range(3))
            hit = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, destroyed=(name,))
            if hit and len(blockers) < 4:
                blockers.append({'origin': point, 'blocker': hit})
        checks.require(not blockers, f'secret {name!r} entrance blocks the player after cover breaks: {blockers}')
        rewards = []
        eye = tuple(outside[i] + (22 if i == 2 else 0) for i in range(3))
        for reward in probe.get('rewards', ()):
            hidden = bool(bsp.segment_hits(eye, reward))
            revealed = not bsp.segment_hits(eye, reward, destroyed=(name,))
            checks.require(hidden, f'secret {name!r} reward {reward} can be seen through the closed wall')
            checks.require(revealed, f'secret {name!r} reward {reward} stays obscured after the wall breaks')
            rewards.append({'origin': reward, 'hidden_closed': hidden, 'visible_open': revealed})
        results.append({'name': name, 'model': bsp.secret_models[name], 'closed_blocked': bool(closed_hits),
                        'open_clear': not opened_hits and not blockers, 'player_samples': samples+1,
                        'rewards': rewards})
    checks.require(seen == set(bsp.secret_models), 'each marked secret cover requires an independent secret probe')
    checks.results['secrets'] = results


def outdoor_geometry_checks(bsp, document, checks):
    """Check that the exterior spawn, breaches and rally point stay open air."""
    required = {'entry_breach', 'exterior_start', 'extraction'}
    seen, results = set(), []
    for probe in document.get('outdoor_probes', ()):
        name, point = probe['name'], tuple(probe['point'])
        checks.require(name not in seen, f'duplicate outdoor probe {name!r}')
        seen.add(name)
        checks.require(len(point) == 3 and all(math.isfinite(v) for v in point),
                       f'outdoor probe {name!r} must contain a finite three-dimensional point')
        if len(point) != 3 or not all(math.isfinite(v) for v in point):
            continue
        point_clear = not bsp.collision(point, (0.,)*3, (0.,)*3, SOLID)
        checks.require(point_clear, f'outdoor probe {name!r} is inside solid geometry')
        end = (point[0], point[1], bsp.models[0][5] + 16)
        hits = bsp.segment_hits(point, end)
        first = hits[0] if hits else None
        sky = False
        if first:
            start, count, _ = bsp.brushes[first['brush']]
            sky = count > 0 and all(side[1] >= 0 and bsp.texinfo[side[1]][8] & 4
                                    for side in bsp.sides[start:start+count])
        checks.require(sky, f'outdoor probe {name!r} has no unobstructed sky overhead: {first}')
        results.append({'name': name, 'point': point, 'clear': point_clear,
                        'open_sky': sky, 'overhead_surface': first})
    checks.require(required <= seen, f'missing required outdoor probes: {sorted(required-seen)}')

    breaches = []
    for name, y0, y1 in (('southern_entry', -2112, -2048), ('northern_exit', 3072, 3136)):
        # Independent standing-player cross-sections at three lateral positions
        # verify usable width, rather than just an empty ray through each crack.
        blockers, samples, step_adjustments, floor_heights = [], 0, 0, []
        for x in (-112., 0., 112.):
            previous = None
            for i in range(13):
                point = (x, y0-16 + (y1-y0+32)*i/12, 24.)
                samples += 1
                hit = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
                resolved = None
                # Breaches contain spilled sand above the nominal ground.
                # Resolve its real supported height with the same 18-unit
                # limit as player movement. Every candidate still uses the
                # complete standing hull, preserving the lateral width test.
                for rise in range(19):
                    raised = (point[0], point[1], point[2]+rise)
                    if bsp.collision(raised, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
                        continue
                    below = (raised[0], raised[1], raised[2]-1)
                    if not bsp.collision(below, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
                        continue
                    if previous is not None:
                        if raised[2] > previous[2]+18+EPSILON:
                            continue
                        up = (previous[0], previous[1], max(previous[2], raised[2]))
                        across = (raised[0], raised[1], up[2])
                        trajectory = [tuple(previous[j]+(up[j]-previous[j])*t/4 for j in range(3))
                                      for t in range(1,5)]
                        trajectory += [tuple(up[j]+(across[j]-up[j])*t/4 for j in range(3))
                                       for t in range(1,5)]
                        trajectory += [tuple(across[j]+(raised[j]-across[j])*t/4 for j in range(3))
                                       for t in range(1,5)]
                        if any(bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK) for p in trajectory):
                            continue
                    resolved = raised
                    step_adjustments += bool(rise)
                    floor_heights.append(rise)
                    previous = raised
                    break
                if resolved is None and len(blockers) < 6:
                    blockers.append({'origin': point, 'blocker': hit or 'no supported standing origin within 18-unit step'})
        checks.require(not blockers, f'{name} exterior breach obstructs a standing player: {blockers[:2]}')
        breaches.append({'name': name, 'samples': samples, 'clear': not blockers, 'blockers': blockers,
                         'step_adjustments': step_adjustments,
                         'floor_height_range': [min(floor_heights),max(floor_heights)] if floor_heights else None})
    checks.results['outdoor_probes'] = results
    checks.results['exterior_breaches'] = breaches


def polygon_area(poly):
    return sum(a[0]*b[1] - a[1]*b[0] for a, b in zip(poly, poly[1:]+poly[:1])) / 2


def clip_polygon(subject, clip):
    if polygon_area(clip) < 0:
        clip = list(reversed(clip))
    output = subject
    for a, b in zip(clip, clip[1:]+clip[:1]):
        incoming, output = output, []
        if not incoming:
            break
        side = lambda p: (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])
        previous, prev_side = incoming[-1], side(incoming[-1])
        for point in incoming:
            point_side = side(point)
            if (point_side >= 0) != (prev_side >= 0):
                t = prev_side / (prev_side - point_side)
                output.append(tuple(previous[j] + (point[j]-previous[j])*t for j in range(2)))
            if point_side >= 0:
                output.append(point)
            previous, prev_side = point, point_side
    return output


def surface_overlap_checks(bsp, checks):
    """Find rendered, exposed coplanar overlap between independent BSP models.

    World CSG removes hidden world/world faces. Moving and breakable models are
    compiled separately, so their same-facing coplanar surfaces need this check.
    This catches real depth-buffer conflicts without flagging shared brush edges.
    """
    planes, conflicts = defaultdict(list), []
    drawable_models = {0, *(model for _, model, _ in bsp.bmodels)}
    for model_i, model in enumerate(bsp.models):
        if model_i not in drawable_models:
            continue
        for face_i in range(model[10], model[10]+model[11]):
            plane_i, side, first_edge, num_edges, tex_i, *_ = bsp.faces[face_i]
            tex = bsp.texinfo[tex_i]
            if tex[8] & (4 | 128):  # SURF_SKY / SURF_NODRAW
                continue
            sign = -1 if side else 1
            normal = tuple(v*sign for v in bsp.planes[plane_i][:3])
            distance = bsp.planes[plane_i][3]*sign
            dropped = max(range(3), key=lambda i: abs(normal[i]))
            axes = [i for i in range(3) if i != dropped]
            poly = []
            for edge_i in bsp.surfedges[first_edge:first_edge+num_edges]:
                vertex_i = bsp.edges[abs(edge_i)][0 if edge_i >= 0 else 1]
                vertex = bsp.vertexes[vertex_i]
                poly.append((vertex[axes[0]], vertex[axes[1]]))
            if len(poly) < 3:
                continue
            bounds = tuple(min(p[i] for p in poly) for i in range(2)) + tuple(max(p[i] for p in poly) for i in range(2))
            key = tuple(round(v, 5) for v in (*normal, distance))
            for other_model, other_face, other_poly, other_bounds in planes[key]:
                if other_model == model_i or any(bounds[i] >= other_bounds[i+2]-EPSILON
                                                  or other_bounds[i] >= bounds[i+2]-EPSILON for i in range(2)):
                    continue
                overlap = clip_polygon(poly, other_poly)
                area = abs(polygon_area(overlap)) if len(overlap) >= 3 else 0
                if area < 0.25:
                    continue
                uv = tuple(sum(p[i] for p in overlap) / len(overlap) for i in range(2))
                point = [0., 0., 0.]
                for i, axis in enumerate(axes):
                    point[axis] = uv[i]
                point[dropped] = (distance - sum(normal[a]*point[a] for a in axes)) / normal[dropped]
                exposed_point = tuple(point[i]+normal[i]*0.5 for i in range(3))
                # Ignore surfaces buried inside static structural geometry.
                if any(bsp.brush_overlaps(index, exposed_point, (0.,)*3, (0.,)*3, SOLID)
                       for index in bsp.model_brushes[0]):
                    continue
                conflicts.append({'models': [other_model, model_i], 'faces': [other_face, face_i],
                                  'overlap_area': round(area, 3), 'point': tuple(round(v, 3) for v in point)})
            planes[key].append((model_i, face_i, poly, bounds))
    checks.require(not conflicts, f'exposed coplanar surfaces can z-fight: {conflicts[:6]}')
    checks.results['coplanar_surface_conflicts'] = conflicts


def texture_fit_checks(bsp, checks):
    """Verify that signs, switches, gate panels and the pad fit one tile.

    Texture coordinates come from compiled texinfo, so this tests the compiler's
    actual axis/sign convention and includes any lightmap-driven face splits.
    """
    groups = defaultdict(list)
    for model_i, model in enumerate(bsp.models):
        for face_i in range(model[10], model[10]+model[11]):
            plane_i, side, first_edge, num_edges, tex_i, *_ = bsp.faces[face_i]
            tex = bsp.texinfo[tex_i]
            name = tex[10].split(b'\0', 1)[0].decode('ascii')
            if not (name.startswith(('sandkeep/sign_', 'sandkeep/switch_'))
                    or name == 'sandkeep/helipad'
                    or (name == 'sandkeep/gate_wood' and model_i > 0)):
                continue
            for edge_i in bsp.surfedges[first_edge:first_edge+num_edges]:
                vertex_i = bsp.edges[abs(edge_i)][0 if edge_i >= 0 else 1]
                v = bsp.vertexes[vertex_i]
                groups[(model_i, plane_i, side, tex_i, name)].append(
                    (sum(v[i]*tex[i] for i in range(3))+tex[3],
                     sum(v[i]*tex[i+4] for i in range(3))+tex[7]))
    results = []
    for (model, plane, side, tex_i, name), coords in groups.items():
        path = next((ROOT / folder / 'textures' / f'{name}.wal' for folder in ('baseq2', 'release/baseq2')
                     if (ROOT / folder / 'textures' / f'{name}.wal').exists()), None)
        if not checks.require(path is not None, f'cannot verify graphic fit without WAL dimensions for {name}'):
            continue
        dimensions = struct.unpack_from('<2I', path.read_bytes(), 32)
        lo = tuple(min(p[i] for p in coords) for i in range(2))
        hi = tuple(max(p[i] for p in coords) for i in range(2))
        fits = all(abs((hi[i]-lo[i])-dimensions[i]) < .1
                   and abs(lo[i]/dimensions[i]-round(lo[i]/dimensions[i])) < .001 for i in range(2))
        checks.require(fits, f'{name} on model {model} is cropped/repeated: UV {lo}..{hi}, graphic {dimensions}')
        results.append({'texture': name, 'model': model, 'uv_mins': lo, 'uv_maxs': hi,
                        'dimensions': dimensions, 'one_tile_fit': fits})
    checks.results['graphic_texture_fits'] = results


def geometry_checks(bsp, source, checks, routes_path, secret_walls):
    checks.require(bool(bsp.lumps['visibility']), 'compiled map has no visibility lump')
    checks.require(bool(bsp.lumps['lighting']), 'compiled map has no baked lightmap lump')
    bounds = {'mins': bsp.models[0][0:3], 'maxs': bsp.models[0][3:6]}
    checks.require(all(math.isfinite(v) and abs(v) <= 4096 for v in (*bounds['mins'], *bounds['maxs'])),
                   f'compiled world bounds exceed the intended +/-4096-unit envelope: {bounds}')
    source_logic = Counter(tuple(sorted((k, v) for k, v in e['keys'].items()
                           if k != 'model' and not k.startswith('_')))
                           for e in source if e['keys'].get('classname') not in
                           ('worldspawn', 'light', 'info_null', 'func_group'))
    bsp_logic = Counter(tuple(sorted((k, v) for k, v in e['keys'].items()
                        if k != 'model' and not k.startswith('_')))
                        for e in bsp.entities if e['keys'].get('classname') not in
                        ('worldspawn', 'light', 'info_null', 'func_group'))
    checks.require(source_logic == bsp_logic, 'compiled BSP gameplay entities differ from source MAP')
    bind_secret_models(bsp, secret_walls, checks)
    surface_overlap_checks(bsp, checks)
    texture_fit_checks(bsp, checks)
    placements = []
    for entity in bsp.entities:
        k, mask = entity['keys'], SOLID
        classname = k.get('classname', '')
        if classname in ('info_player_start', 'info_player_coop'):
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
        elif classname == 'monster_boss2':
            mins, maxs, mask = (-56., -56., 0.), (56., 56., 80.), MONSTER_MASK
        elif classname in ('monster_soldier_light', 'monster_soldier', 'monster_soldier_ss',
                           'monster_infantry', 'monster_gunner'):
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK
        elif classname.startswith(('item_', 'weapon_', 'ammo_')):
            mins, maxs = (-15., -15., -15.), (15., 15., 15.)
        else:
            continue
        point = vec(k['origin'])
        hit = bsp.collision(point, mins, maxs, mask)
        checks.require(not hit, f'{label(entity)} starts inside {hit}')
        placements.append({'entity': label(entity), 'origin': point, 'clear': not bool(hit), 'blocker': hit})
    checks.results['collision_placements'] = placements
    route_results = []
    if routes_path and routes_path.exists():
        route_document = json.loads(routes_path.read_text())
        secret_geometry_checks(bsp, route_document, checks)
        outdoor_geometry_checks(bsp, route_document, checks)
        for route in route_document['routes']:
            points, opened = route['points'], set(route.get('opened_doors', ()))
            destroyed = set(route.get('destroyed_secrets', ()))
            checks.require(destroyed <= set(bsp.secret_models),
                           f"route {route['name']} refers to unknown destroyed secret covers")
            checks.require(len(points) >= 2, f"route {route['name']} has fewer than two points")
            samples, blockers, unsupported, step_adjustments = 0, [], [], 0
            previous = None
            for start, end in zip(points, points[1:]):
                steps = max(1, math.ceil(math.dist(start, end) / 8))
                for i in range(steps + 1):
                    point = tuple(start[j] + (end[j] - start[j]) * i / steps for j in range(3))
                    samples += 1
                    hit = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed)
                    if hit and previous is not None:
                        # Waypoints encode nominal walking height, while the
                        # full hull reaches each stair before its center does.
                        # Resolve only low obstacles reachable by the engine's
                        # 18-unit step (src/common/pmove.c), checking the raised
                        # trajectory rather than ignoring the intersected brush.
                        for rise in range(1, 19):
                            raised = (point[0], point[1], point[2] + rise)
                            if raised[2] > previous[2] + 18 + EPSILON:
                                break
                            if bsp.collision(raised, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed):
                                continue
                            up_at_previous = (previous[0], previous[1], max(previous[2], raised[2]))
                            trajectory = [tuple(previous[j] + (up_at_previous[j] - previous[j]) * t / 4
                                                for j in range(3)) for t in range(1, 5)]
                            trajectory += [tuple(up_at_previous[j] + (raised[j] - up_at_previous[j]) * t / 4
                                                 for j in range(3)) for t in range(1, 5)]
                            if any(bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened, destroyed)
                                   for p in trajectory):
                                continue
                            point, hit = raised, None
                            step_adjustments += 1
                            break
                    if hit:
                        if len(blockers) < 8:
                            blockers.append({'origin': point, 'blocker': hit})
                        continue
                    previous = point
                    # A nearby solid floor must support the center footprint;
                    # this catches paths across voids while accepting stairs.
                    support = any(bsp.collision((point[0], point[1], point[2] - dz),
                                                (-4., -4., -24.), (4., 4., 32.), PLAYER_MASK, opened, destroyed)
                                  for dz in (2, 8, 16, 24))
                    if not support and not route.get('allow_airborne', False) and len(unsupported) < 8:
                        unsupported.append(point)
            checks.require(not blockers, f"route {route['name']} collides: {blockers[:2]}")
            checks.require(not unsupported, f"route {route['name']} lacks nearby floor: {unsupported[:2]}")
            route_results.append({'name': route['name'], 'samples': samples, 'opened_doors': sorted(opened),
                                  'destroyed_secrets': sorted(destroyed),
                                  'clear': not blockers and not unsupported,
                                  'step_adjustments': step_adjustments,
                                  'blockers': blockers, 'unsupported': unsupported})
    else:
        checks.warnings.append('no route waypoint file supplied; continuous route clearance was not checked')
    checks.results['routes'] = route_results
    checks.results['bsp'] = {'bytes': len(bsp.raw), 'sha256': hashlib.sha256(bsp.raw).hexdigest(),
                             'world_bounds': bounds,
                             'world_collision_brushes': len(bsp.model_brushes[0]),
                             'brush_models': len(bsp.models), 'vis_bytes': len(bsp.lumps['visibility']),
                             'lighting_bytes': len(bsp.lumps['lighting'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=ROOT / 'maps/source/pp_sandkeep.map')
    parser.add_argument('--bsp', type=Path)
    parser.add_argument('--routes', type=Path)
    parser.add_argument('--bsp-log', type=Path, help='check the completed compiler log for geometry warnings')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/maps/pp_sandkeep/verification.json')
    args = parser.parse_args()
    checks = Checks()
    source = []
    try:
        source_text = args.map.read_text()
        source = parse_entities(source_text)
        graph_checks(source, checks, args.map.stem)
        secret_walls = source_brush_checks(source, checks)
        known_classes = set(re.findall(r'\{\s*"([^"]+)"\s*,\s*SP_', (ROOT / 'src/game/g_spawn.c').read_text()))
        known_classes.update(re.findall(r'QUAKED\s+(\w+)', (ROOT / 'src/game/g_items.c').read_text()))
        for entity in source:
            checks.require(entity['keys'].get('classname') in known_classes,
                           f"{label(entity)} is not a known engine classname")
            if flags(entity) & 4096:
                checks.warnings.append(f'{label(entity)} uses ignored NOT_COOP exclusion flag')
        reference = parse_entities((ROOT / 'maps/source/pp_sandbox_coop1.map').read_text())
        known_textures = {t for e in reference for t in e['textures']}
        known_textures.update(('common/trigger', 'common/clip', 'common/monsterclip', 'common/hint', 'common/skip', 'common/nodraw'))
        textures = sorted({t for e in source for t in e['textures']})
        for texture in textures:
            checks.require(len(texture) <= 31 and bool(re.fullmatch(r'[A-Za-z0-9_/.-]+', texture))
                           and '..' not in texture, f'invalid Q2 texture name {texture!r}')
            present = any((ROOT / folder / 'textures' / f'{texture}.{suffix}').exists()
                          for folder in ('baseq2', 'release/baseq2') for suffix in ('wal', 'png', 'tga'))
            checks.require(texture in known_textures or present,
                           f'texture {texture!r} is neither in the reference map nor supplied assets')
        checks.results['textures'] = textures
        checks.results['map_sha256'] = hashlib.sha256(source_text.encode()).hexdigest()
        if args.bsp:
            geometry_checks(BSP(args.bsp), source, checks, args.routes, secret_walls)
            log_path = args.bsp_log or args.output.parent / 'bsp.log'
            if log_path.exists():
                suspect = [line for line in log_path.read_text(errors='replace').splitlines()
                           if re.search(r'\bwarning\b|out of.*range|outside.*world|unbounded|\bleaked\b', line, re.I)]
                checks.require(not suspect, f'BSP compiler reports geometry warnings: {suspect[:8]}')
                checks.results['bsp_compile_warning_lines'] = suspect
            else:
                checks.warnings.append('BSP compiler log unavailable; compiler warnings were not checked')
        else:
            checks.warnings.append('no BSP supplied; collision geometry and compile/source consistency not checked')
    except (OSError, ValueError, struct.error, UnicodeError) as error:
        checks.errors.append(f'validation input could not be read: {error}')
    report = {'passed': not checks.errors, 'errors': checks.errors, 'warnings': checks.warnings, **checks.results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'errors': checks.errors, 'warnings': checks.warnings,
                      'report': str(args.output), 'entities': len(source),
                      'placement_checks': len(checks.results.get('collision_placements', ())),
                      'routes': checks.results.get('routes', ())}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
