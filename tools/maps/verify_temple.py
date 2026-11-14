#!/usr/bin/env python3
"""Independently compare Temple's compiled collision with its N64 reference.

This verifier reads IBSP38 planes/brushes rather than generator output. Surface,
floor and walking probes are derived directly from the archived BG/STAN data.
Its walking checks use Quake II's standing AABB and 18-unit step allowance.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

from verify_sandkeep import (BSP, PLAYER_MASK, PLAYER_MAXS, PLAYER_MINS,
                            SOLID, parse_entities, vec)

ROOT = Path(__file__).resolve().parents[2]
# 46 Quake eye units / (175 cm Bond height * 33/70 original world scale).
# This is deliberately independent of the level generator's scale constant.
SCALE = 46 / (175 * 33 / 70)
FLOOR_TOLERANCE = .6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(point):
    x, y, z = point
    return (x * SCALE, -z * SCALE, y * SCALE)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, scale):
    return tuple(x * scale for x in a)


def mean(points):
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def reference_floor(reference, x, y, near):
    """Interpolate STAN floors beneath a point, preserving stacked levels."""
    heights = []
    for tile in reference['stan_tiles']:
        a, b, c = [convert(p) for p in tile['vertices']]
        determinant = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(determinant) < 1e-8:
            continue
        u = ((b[1]-c[1])*(x-c[0]) + (c[0]-b[0])*(y-c[1])) / determinant
        v = ((c[1]-a[1])*(x-c[0]) + (a[0]-c[0])*(y-c[1])) / determinant
        if min(u, v, 1-u-v) >= -1e-5:
            heights.append(u*a[2] + v*b[2] + (1-u-v)*c[2])
    return min(heights, key=lambda z: abs(z-near)) if heights else None


def normal(points):
    a, b = sub(points[1], points[0]), sub(points[2], points[0])
    n = (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])
    return mul(n, 1 / math.sqrt(sum(x*x for x in n)))


class Checks:
    def __init__(self):
        self.errors, self.warnings, self.results = [], [], {}

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)


class Collision:
    """Compiled brush queries with a BSP broad phase and all doors opened."""
    def __init__(self, bsp):
        self.bsp = bsp
        self.models = []
        for entity, model, offset in bsp.bmodels:
            if entity['keys'].get('classname') == 'func_door':
                offset = bsp.open_door_offset(entity, model, offset)
            self.models.append((entity, model, offset))

    def candidates(self, point, mins, maxs):
        center = tuple(point[i] + (mins[i] + maxs[i])/2 for i in range(3))
        extents = tuple((maxs[i] - mins[i])/2 for i in range(3))
        nodes, brushes = [self.bsp.models[0][9]], set()
        while nodes:
            node = nodes.pop()
            if node < 0:
                leaf = self.bsp.leaves[-node-1]
                first, count = leaf[-2:]
                brushes.update(self.bsp.leafbrushes[first:first+count])
                continue
            plane, front, back = self.bsp.nodes[node]
            n = self.bsp.planes[plane]
            distance = sum(n[i] * center[i] for i in range(3)) - n[3]
            radius = sum(abs(n[i]) * extents[i] for i in range(3)) + .001
            if distance + radius >= 0:
                nodes.append(front)
            if distance - radius <= 0:
                nodes.append(back)
        return brushes

    def hit(self, point, mins=PLAYER_MINS, maxs=PLAYER_MAXS, models=True):
        if self.bsp.point_contents(point) & SOLID:
            return 'world solid at origin'
        for index in self.candidates(point, mins, maxs):
            if self.bsp.brush_overlaps(index, point, mins, maxs, PLAYER_MASK):
                return f'world brush {index}'
        if models:
            for entity, model, offset in self.models:
                local = sub(point, offset)
                for index in self.bsp.model_brushes[model]:
                    if self.bsp.brush_overlaps(index, local, mins, maxs, PLAYER_MASK):
                        return f"{entity['keys'].get('classname')} model {model} brush {index}"
        return None

    def ray(self, start, end):
        """First world-solid entry; door models are intentionally excluded."""
        low = tuple(min(a, b) for a, b in zip(start, end))
        high = tuple(max(a, b) for a, b in zip(start, end))
        hit = None
        for index in self.candidates((0, 0, 0), low, high):
            first, count, contents = self.bsp.brushes[index]
            if not contents & SOLID:
                continue
            enter, leave = 0., 1.
            for side in self.bsp.sides[first:first+count]:
                n = self.bsp.planes[side[0]]
                a = sum(n[i] * start[i] for i in range(3)) - n[3]
                b = sum(n[i] * end[i] for i in range(3)) - n[3]
                if a > 0 and b > 0:
                    enter = 2.
                    break
                if a > b:
                    enter = max(enter, a / (a-b))
                elif b > a:
                    leave = min(leave, a / (a-b))
                if enter > leave:
                    break
            if enter <= leave and enter <= 1 and (hit is None or enter < hit['fraction']):
                hit = {'fraction': enter, 'brush': index,
                       'point': add(start, mul(sub(end, start), enter))}
        return hit

    def standing(self, floor):
        nominal = add(floor, (0, 0, 24.1))
        blocker = self.hit(nominal)
        if not blocker:
            return nominal, 0, None
        for rise in range(1, 19):
            point = add(nominal, (0, 0, rise))
            if not self.hit(point):
                return point, rise, blocker
        return None, None, blocker

    def walk(self, floors):
        previous, samples, rises = None, 0, 0
        for start, end in zip(floors, floors[1:]):
            count = max(1, math.ceil(math.dist(start, end) / 6))
            for t in range(count + 1):
                floor = add(start, mul(sub(end, start), t/count))
                point, rise, blocker = self.standing(floor)
                samples += 1
                if point is None:
                    return {'clear': False, 'samples': samples, 'floor': floor, 'blocker': blocker}
                if previous is not None and point[2] - previous[2] > 18.03125:
                    return {'clear': False, 'samples': samples, 'floor': floor,
                            'blocker': 'rise exceeds the engine step height'}
                previous = point
                rises += bool(rise)
        return {'clear': True, 'samples': samples, 'raised_samples': rises}


def entity_checks(source, bsp, reference, checks):
    expected = {'info_player_deathmatch': 5, 'func_door': 6}
    for name, entities in (('source', source), ('compiled', bsp.entities)):
        counts = Counter(e['keys'].get('classname', '') for e in entities)
        for classname, count in expected.items():
            checks.require(counts[classname] == count,
                           f'{name} has {counts[classname]} {classname} entities; expected {count}')
        weapons = sum(count for classname, count in counts.items() if classname.startswith('weapon_'))
        armor = sum(count for classname, count in counts.items() if classname.startswith('item_armor_'))
        checks.require(weapons == 8, f'{name} has {weapons} weapons; expected eight original weapon locations')
        checks.require(armor == 1, f'{name} has {armor} armor pickups; expected one')
        checks.results[name + '_entity_counts'] = dict(sorted(counts.items()))
    def logic(entities):
        return Counter(tuple(sorted((k, v) for k, v in entity['keys'].items()
                                    if k != 'model' and not k.startswith('_')))
                       for entity in entities if entity['keys'].get('classname') not in
                       ('worldspawn', 'light', 'info_null', 'func_group'))
    checks.require(logic(source) == logic(bsp.entities), 'compiled gameplay entities differ from source MAP')
    pads = {pad['id']: pad for pad in reference['pads']}
    spawns = [vec(e['keys']['origin']) for e in bsp.entities
              if e['keys'].get('classname') == 'info_player_deathmatch']
    spawn_probes = []
    for pad_id in reference['spawn_pad_ids']:
        expected = convert(pads[pad_id]['position'])
        distance = min((math.dist(expected[:2], origin[:2]) for origin in spawns), default=math.inf)
        checks.require(distance <= .01, f'original spawn pad {pad_id} moved horizontally by {distance:g} units')
        spawn_probes.append({'pad': pad_id, 'reference_xy': expected[:2], 'nearest_xy_error': distance})
    checks.results['spawn_reference_probes'] = spawn_probes


def surface_checks(reference, collision, checks):
    blocked, missing, count = [], [], 0
    for room in reference['rooms']:
        vertices = [convert(p) for p in room['vertices']]
        for index, triangle in enumerate(room['triangles']):
            points = [vertices[i] for i in triangle]
            center, inward = mean(points), normal(points)
            probe = add(center, mul(inward, .15))
            count += 1
            if collision.bsp.point_contents(probe) & SOLID:
                blocked.append({'room': room['id'], 'triangle': index, 'probe': probe})
            ray = collision.ray(add(center, mul(inward, .8)), add(center, mul(inward, -.8)))
            if ray is None or math.dist(ray['point'], center) > FLOOR_TOLERANCE:
                missing.append({'room': room['id'], 'triangle': index, 'center': center, 'hit': ray})
    checks.require(not blocked, f'{len(blocked)} original surface front probes are in world solid; first: {blocked[:3]}')
    checks.require(not missing, f'{len(missing)} original surfaces lack a matching compiled collision plane; first: {missing[:3]}')
    checks.results['surface_parity'] = {'triangles': count, 'front_offset': .15,
                                       'tolerance': FLOOR_TOLERANCE, 'blocked': blocked,
                                       'missing_or_displaced': missing}


def tile_checks(reference, collision, checks):
    probes, selected, floor_errors = [], {}, []
    for tile in reference['stan_tiles']:
        points = [convert(p) for p in tile['vertices']]
        center = mean(points)
        ray = collision.ray(add(center, (0, 0, 2)), add(center, (0, 0, -2)))
        error = abs(ray['point'][2] - center[2]) if ray else None
        if error is None or error > FLOOR_TOLERANCE:
            floor_errors.append({'tile': tile['id'], 'reference_floor': center, 'height_error': error, 'hit': ray})
        weights = [math.dist(points[(i+1)%3], points[(i+2)%3]) for i in range(3)]
        incenter = tuple(sum(points[j][i] * weights[j] for j in range(3)) / sum(weights) for i in range(3))
        candidates = [center, incenter] + [mean([center, vertex]) for vertex in points]
        record = {'tile': tile['id'], 'room': tile['room'], 'center': center,
                  'floor_height_error': error, 'samples_attempted': 0, 'clear': False}
        for index, floor in enumerate(candidates):
            point, rise, blocker = collision.standing(floor)
            record['samples_attempted'] += 1
            if index == 0:
                record['nominal_center_blocker'] = blocker
            if point is not None:
                selected[tile['id']] = floor
                record.update(clear=True, sample=floor, origin=point,
                              candidate_index=index, step_lift=rise)
                break
        probes.append(record)
    bad = [p for p in probes if not p['clear']]
    checks.require(not floor_errors, f'{len(floor_errors)} STAN floor samples differ from compiled floor; first: {floor_errors[:3]}')
    checks.require(not bad, f'{len(bad)} STAN tiles have no clear standing sample: {[p["tile"] for p in bad]}')
    checks.results['floor_parity'] = {'tiles': len(probes), 'tolerance': FLOOR_TOLERANCE, 'errors': floor_errors}
    checks.results['standing_tiles'] = probes
    return selected


def navigation_checks(reference, selected, collision, checks):
    tiles = {tile['id']: tile for tile in reference['stan_tiles']}
    graph, blocked, edges = {i: set() for i in selected}, [], []
    for tile_id, tile in tiles.items():
        # STAN neighbor links are 16-byte header + four-word triangle records.
        for offset in tile['neighbor_offsets']:
            if not offset:
                continue
            neighbor = (offset - 16) // 4
            checks.require(offset >= 16 and offset % 4 == 0 and neighbor in tiles,
                           f'tile {tile_id} has invalid STAN neighbor offset {offset}')
            if neighbor <= tile_id or neighbor not in selected or tile_id not in selected:
                continue
            shared = sorted(set(map(tuple, tile['vertices'])) & set(map(tuple, tiles[neighbor]['vertices'])))
            if len(shared) < 2:
                blocked.append({'tiles': [tile_id, neighbor], 'blocker': 'neighbor tiles do not share a complete edge'})
                continue
            crossing = mean([convert(p) for p in shared])
            result = collision.walk([selected[tile_id], crossing, selected[neighbor]])
            result['tiles'] = [tile_id, neighbor]
            edges.append(result)
            if result['clear']:
                graph[tile_id].add(neighbor)
                graph[neighbor].add(tile_id)
            else:
                blocked.append(result)
    groups, seen = [], set()
    for start in graph:
        if start in seen:
            continue
        pending, group = deque([start]), []
        while pending:
            node = pending.popleft()
            if node in seen:
                continue
            seen.add(node)
            group.append(node)
            pending.extend(graph[node] - seen)
        groups.append(group)
    checks.require(len(groups) == 1 and len(seen) == len(tiles),
                   f'compiled walking graph has {len(groups)} components covering {len(seen)}/{len(tiles)} tiles')
    if blocked:
        checks.warnings.append(f'{len(blocked)} STAN adjacency edges fail standing-hull traversal; see navigation.blocked_edges')
    checks.results['navigation'] = {'tiles': len(graph), 'tested_edges': len(edges),
                                     'components': groups, 'blocked_edges': blocked,
                                     'edge_results': edges}


def portal_checks(reference, collision, checks):
    results = []
    for portal in reference['portals']:
        vertices = [convert(p) for p in portal['vertices']]
        low = tuple(min(p[i] for p in vertices) for i in range(3))
        high = tuple(max(p[i] for p in vertices) for i in range(3))
        center = mean(vertices)
        axis = min(range(3), key=lambda i: high[i] - low[i])
        record = {'id': portal['id'], 'rooms': portal['rooms'], 'bounds': [low, high]}
        direction = tuple(1 if i == axis else 0 for i in range(3))
        if axis == 2:
            record['kind'] = 'horizontal visibility opening'
            start, end = add(center, mul(direction, 1)), add(center, mul(direction, -1))
            record['clear'] = collision.ray(start, end) is None
        else:
            # Probe the aperture center and floor levels found in compiled
            # world geometry; tall portals may contain an ascending ramp.
            floor_hit = collision.ray((center[0], center[1], high[2] - 56.1),
                                      (center[0], center[1], low[2] - .6))
            floor_z = floor_hit['point'][2] if floor_hit else low[2]
            floor = (center[0], center[1], floor_z)
            route = []
            reference_heights = []
            unsupported = 0
            for amount in range(-24, 25, 6):
                point = add(floor, mul(direction, amount))
                height = reference_floor(reference, point[0], point[1], floor_z)
                reference_heights.append(height)
                # Several original portals are high windows, while two upper
                # gallery entrances open onto a drop. Their BG apertures must
                # admit a standing hull, but a straight walking route cannot
                # follow the much lower STAN floor across the air gap.
                if height is None or abs(height - floor_z) > 18.03125:
                    unsupported += 1
                    height = floor_z
                route.append((point[0], point[1], height))
            if unsupported == len(route):
                record['kind'] = 'high window outside original floor navigation'
            elif unsupported:
                record['kind'] = 'standing doorway opening onto ledge/drop'
            else:
                record['kind'] = 'standing doorway'
            record.update(collision.walk(route))
            record['floor'] = floor
            record['reference_floor_levels'] = reference_heights
            record['unsupported_aperture_samples'] = unsupported
        checks.require(record['clear'], f'original portal {portal["id"]} ({portal["rooms"]}) is obstructed: {record}')
        results.append(record)
    checks.results['portals'] = results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=ROOT / 'maps/source/pp_temple.map')
    parser.add_argument('--bsp', type=Path, default=ROOT / 'baseq2/maps/pp_temple.bsp')
    parser.add_argument('--reference', type=Path, default=ROOT / 'tools/maps/temple_layout.json')
    parser.add_argument('--bsp-log', type=Path, default=ROOT / 'build/maps/pp_temple/bsp.log')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/maps/pp_temple/verification.json')
    args = parser.parse_args()
    checks = Checks()
    try:
        reference = json.loads(args.reference.read_text())
        counts = {'rooms': len(reference['rooms']),
                  'triangles': sum(len(room['triangles']) for room in reference['rooms']),
                  'tiles': len(reference['stan_tiles']), 'portals': len(reference['portals'])}
        checks.require(counts == {'rooms': 25, 'triangles': 1014, 'tiles': 204, 'portals': 37},
                       f'unexpected Temple reference inventory: {counts}')
        source = parse_entities(args.map.read_text())
        bsp = BSP(args.bsp)
        collision = Collision(bsp)
        checks.results.update(map_sha256=sha(args.map), bsp_sha256=sha(args.bsp),
                              reference_sha256=sha(args.reference), reference_inventory=counts,
                              scale=SCALE, coordinate_transform='(x,y,z) -> (x*S,-z*S,y*S)')
        checks.require(bool(bsp.lumps['visibility']), 'compiled BSP has no VIS data')
        checks.require(bool(bsp.lumps['lighting']), 'compiled BSP has no baked lighting')
        checks.results['bsp'] = {'sha256': sha(args.bsp), 'bytes': len(bsp.raw),
                                 'vis_bytes': len(bsp.lumps['visibility']),
                                 'lighting_bytes': len(bsp.lumps['lighting']),
                                 'world_collision_brushes': len(bsp.model_brushes[0])}
        entity_checks(source, bsp, reference, checks)
        surface_checks(reference, collision, checks)
        selected = tile_checks(reference, collision, checks)
        navigation_checks(reference, selected, collision, checks)
        portal_checks(reference, collision, checks)
        placements = []
        for entity in bsp.entities:
            classname = entity['keys'].get('classname', '')
            if classname == 'info_player_deathmatch':
                origin = vec(entity['keys']['origin'])
                blocker = collision.hit(origin)
                checks.require(not blocker, f'deathmatch spawn {origin} starts inside {blocker}')
                placements.append({'origin': origin, 'clear': not blocker, 'blocker': blocker})
        checks.results['spawn_placements'] = placements
        if args.bsp_log.is_file():
            suspect = [line for line in args.bsp_log.read_text(errors='replace').splitlines()
                       if re.search(r'\bwarning\b|\bleaked\b|no entities in empty space|'
                                    r'couldn.t (?:locate texture|load.*(?:texture|\.wal|colormap)|'
                                    r'open.*(?:texture|\.wal|colormap))', line, re.I)]
            checks.require(not suspect, f'BSP compiler reported warnings/errors: {suspect[:8]}')
            checks.results['bsp_compile_warning_lines'] = suspect
        else:
            checks.warnings.append('BSP compiler log unavailable; leak/missing-texture log checks were not performed')
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError, struct.error) as error:
        checks.errors.append(f'validation input could not be read: {error}')
    report = {'passed': not checks.errors, 'errors': checks.errors, 'warnings': checks.warnings,
              **checks.results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'errors': checks.errors, 'warnings': checks.warnings,
                      'report': str(args.output),
                      'surface_triangles': checks.results.get('surface_parity', {}).get('triangles'),
                      'floor_tiles': checks.results.get('floor_parity', {}).get('tiles'),
                      'portals': len(checks.results.get('portals', []))}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
