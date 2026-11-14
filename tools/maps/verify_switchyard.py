#!/usr/bin/env python3
"""Check Switchyard's compiled routes, empty building floors and Temple budget.

Walking and floor checks read actual IBSP38 collision brushes. The separately
authored route document defines intended floor heights and usable open areas;
no level-generator code is imported.
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

from verify_sandkeep import BSP, PLAYER_MINS, PLAYER_MAXS, parse_entities, vec
from verify_temple import Collision

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/performance'))
from map_inventory import bsp_inventory

FLOOR_TOLERANCE = .6
AREA_GRID = 64


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Checks:
    def __init__(self):
        self.errors, self.warnings, self.results = [], [], {}

    def require(self, condition, message):
        if not condition:
            self.errors.append(message)


def point(value):
    result = tuple(map(float, value))
    if len(result) != 3 or not all(math.isfinite(x) for x in result):
        raise ValueError(f'invalid three-dimensional point {value!r}')
    return result


def geometry_budget(bsp):
    face_triangles = [max(0, face[3]-2) for face in bsp.faces]
    rendered_models = {0}
    rendered_models.update(model for entity, model, offset in bsp.bmodels)
    rendered_faces = {i for model in rendered_models
                      for i in range(bsp.models[model][10],
                                     bsp.models[model][10]+bsp.models[model][11])
                      if not bsp.texinfo[bsp.faces[i][4]][8] & (4 | 128)}
    return {'compiled_faces': len(bsp.faces),
            'all_compiled_fan_triangles': sum(face_triangles),
            'renderable_compiled_fan_triangles': sum(face_triangles[i] for i in rendered_faces),
            'renderable_compiled_faces': len(rendered_faces)}


def floor_probe(collision, floor):
    hit = collision.ray((floor[0], floor[1], floor[2]+2),
                        (floor[0], floor[1], floor[2]-2))
    error = abs(hit['point'][2]-floor[2]) if hit else None
    return {'point': floor, 'clear': error is not None and error <= FLOOR_TOLERANCE,
            'height_error': error, 'hit': hit}


def supported_walk(collision, points):
    walk = collision.walk(points)
    errors, samples, unsupported_count, maximum = [], 0, 0, 0.
    for start, end in zip(points, points[1:]):
        steps = max(1, math.ceil(math.dist(start, end)/6))
        for index in range(steps+1):
            sample = tuple(start[j]+(end[j]-start[j])*index/steps for j in range(3))
            probe = floor_probe(collision, sample)
            samples += 1
            if probe['height_error'] is not None:
                maximum = max(maximum, probe['height_error'])
            if not probe['clear']:
                unsupported_count += 1
                if len(errors) < 12:
                    errors.append(probe)
    walk.update(floor_samples=samples, maximum_floor_error=maximum,
                unsupported_samples=unsupported_count, unsupported=errors)
    walk['clear'] = walk['clear'] and not errors
    return walk


def entity_checks(source, bsp, document, collision, checks):
    for name, entities in (('source', source), ('compiled', bsp.entities)):
        counts = Counter(entity['keys'].get('classname', '') for entity in entities)
        checks.require(counts['info_player_deathmatch'] == 8,
                       f'{name} must contain eight deathmatch spawns, found {counts["info_player_deathmatch"]}')
        checks.require(not counts['func_door'] and not counts['func_door_rotating'],
                       f'{name} contains doors; the arena routes must remain open')
        checks.require(not any(k.startswith('monster_') and v for k, v in counts.items()),
                       f'{name} contains monsters in a deathmatch arena')
        weapons = sum(v for k, v in counts.items() if k.startswith('weapon_'))
        checks.require(weapons == 8, f'{name} must contain eight weapons, found {weapons}')
        checks.results[name+'_entity_counts'] = dict(sorted(counts.items()))
    def logic(entities):
        return Counter(tuple(sorted((k, v) for k, v in entity['keys'].items()
                                    if k != 'model' and not k.startswith('_')))
                       for entity in entities if entity['keys'].get('classname') not in
                       ('worldspawn', 'light', 'info_null', 'func_group'))
    checks.require(logic(source) == logic(bsp.entities), 'compiled gameplay entities differ from source MAP')
    declared_spawns = document['spawns']
    spawns = [entity['keys'] for entity in bsp.entities
              if entity['keys'].get('classname') == 'info_player_deathmatch']
    checks.require(len(declared_spawns) == 8, 'route document must declare all eight spawns')
    remaining = spawns[:]
    placements = []
    for index, spawn in enumerate(declared_spawns):
        origin = point(spawn['origin'])
        matches = [item for item in remaining if math.dist(vec(item['origin']), origin) <= .15]
        checks.require(len(matches) == 1, f'declared spawn {index} does not identify one unique compiled spawn')
        if matches:
            actual = matches[0]
            remaining.remove(actual)
            difference = (float(actual.get('angle', 0))-float(spawn['angle'])+180) % 360 - 180
            checks.require(abs(difference) <= .01, f'spawn {index} facing differs from the route document')
        blocker = collision.hit(origin)
        checks.require(not blocker, f'spawn {index} intersects {blocker}')
        placements.append({'kind': 'spawn', 'index': index, 'origin': origin,
                           'clear': not blocker, 'blocker': blocker})
    checks.require(not remaining, 'compiled BSP contains undeclared deathmatch spawn positions')
    pickups = [entity['keys'] for entity in bsp.entities
               if entity['keys'].get('classname', '').startswith(('weapon_', 'item_', 'ammo_'))]
    checks.require(len(pickups) == len(document['pickups']),
                   f'compiled pickup count {len(pickups)} differs from {len(document["pickups"])} declared pickups')
    remaining = pickups[:]
    for index, pickup in enumerate(document['pickups']):
        origin, classname = point(pickup['origin']), pickup['classname']
        matches = [item for item in remaining if item['classname'] == classname
                   and math.dist(vec(item['origin']), origin) <= .15]
        checks.require(bool(matches), f'pickup {index} {classname} is absent or moved in the compiled BSP')
        if matches:
            remaining.remove(matches[0])
        blocker = collision.hit(origin, (-15., -15., -15.), (15., 15., 15.))
        checks.require(not blocker, f'pickup {index} {classname} intersects {blocker}')
        placements.append({'kind': classname, 'index': index, 'origin': origin,
                           'clear': not blocker, 'blocker': blocker})
    checks.require(not remaining, 'compiled BSP contains undeclared pickup positions')
    checks.results['placements'] = placements


def route_checks(document, collision, checks):
    nodes = {name: point(p) for name, p in document['nodes'].items()}
    checks.require(bool(nodes), 'route document must contain navigation nodes')
    graph = {name: set() for name in nodes}
    probes = []
    for name, floor in nodes.items():
        probe = floor_probe(collision, floor)
        standing, rise, blocker = collision.standing(floor)
        probe.update(name=name, standing=standing, step_lift=rise, blocker=blocker)
        checks.require(probe['clear'] and standing is not None, f'node {name} has no clear supported standing position: {probe}')
        probes.append(probe)
    routes = []
    checks.require(bool(document['routes']), 'route document must contain navigation connections')
    for route in document['routes']:
        a, b = route['from'], route['to']
        if a not in nodes or b not in nodes:
            checks.require(False, f'route {route["name"]} refers to an unknown node')
            continue
        points = [point(p) for p in route['points']]
        checks.require(len(points) >= 2, f'route {route["name"]} needs at least two floor points')
        if len(points) < 2:
            continue
        checks.require(math.dist(points[0], nodes[a]) <= .15 and math.dist(points[-1], nodes[b]) <= .15,
                       f'route {route["name"]} endpoints differ from its declared nodes')
        for first, second in zip(points, points[1:]):
            horizontal = math.dist(first[:2], second[:2])
            checks.require(abs(first[2]-second[2]) <= horizontal*.5001+.01,
                           f'route {route["name"]} exceeds the intended 1:2 ramp slope')
        checks.require(route.get('bidirectional') is True, f'route {route["name"]} must declare bidirectional traversal')
        forward, reverse = supported_walk(collision, points), supported_walk(collision, points[::-1])
        clear = forward['clear'] and reverse['clear']
        if not clear:
            def summary(result):
                return {key: result[key] for key in ('blocker', 'floor', 'unsupported_samples') if key in result}
            checks.require(False, f'route {route["name"]} is obstructed or unsupported: '
                                  f'forward={summary(forward)}, reverse={summary(reverse)}; see route details')
        routes.append({'name': route['name'], 'from': a, 'to': b, 'clear': clear,
                       'forward': forward, 'reverse': reverse})
        if clear:
            graph[a].add(b)
            graph[b].add(a)
    visited, pending = set(), deque([next(iter(nodes))] if nodes else [])
    while pending:
        name = pending.popleft()
        if name in visited:
            continue
        visited.add(name)
        pending.extend(graph[name]-visited)
    checks.require(visited == set(nodes), f'navigation graph disconnects nodes {sorted(set(nodes)-visited)}')
    connections = []
    for index, spawn in enumerate(document['spawns']):
        origin = point(spawn['origin'])
        floor = (origin[0], origin[1], origin[2]-24.1)
        # Spawn Z may use the normal 1/8-unit placement grid.
        ray = collision.ray((floor[0], floor[1], floor[2]+1),
                            (floor[0], floor[1], floor[2]-1))
        if ray and abs(ray['point'][2]-floor[2]) <= FLOOR_TOLERANCE:
            floor = (floor[0], floor[1], ray['point'][2])
        connection = None
        for name in sorted(visited, key=lambda n: math.dist(nodes[n], floor)):
            walk = supported_walk(collision, [floor, nodes[name]])
            if walk['clear']:
                connection = {'spawn': index, 'node': name, **walk}
                break
        checks.require(connection is not None, f'spawn {index} has no supported walking connection to the navigation graph')
        connections.append(connection or {'spawn': index, 'clear': False})
    checks.results.update(nodes=probes, routes=routes,
                          navigation={'nodes': len(nodes), 'connected_nodes': sorted(visited),
                                      'spawn_connections': connections})


def open_floor_checks(document, collision, checks):
    probes = []
    for requested in document['floor_probes']:
        probe = floor_probe(collision, point(requested['point']))
        probe['name'] = requested['name']
        checks.require(probe['clear'], f'floor probe {requested["name"]} differs from its intended height: {probe}')
        probes.append(probe)
    areas = []
    checks.results['empty_floor_guarantee'] = {
        'declared_areas': len(document['open_build_areas']),
        'scope': 'Only declared pads must remain empty; remove furnished pads from the route document.'}
    for area in document['open_build_areas']:
        lo, hi, height = area['min'], area['max'], float(area['z'])
        checks.require(len(lo) == len(hi) == 2 and all(hi[i]-lo[i] > 48 for i in range(2)),
                       f'building floor {area["name"]} has invalid or unusably small bounds')
        axes = []
        for index in range(2):
            start, end = float(lo[index])+24, float(hi[index])-24
            axes.append(sorted(set([start, end, (start+end)/2]
                                   + [start+AREA_GRID*i for i in range(max(0, math.floor((end-start)/AREA_GRID))+1)])))
        samples, failures, maximum = 0, [], 0.
        for x in axes[0]:
            for y in axes[1]:
                floor = (x, y, height)
                probe = floor_probe(collision, floor)
                blocker = collision.hit((x, y, height+24.1))
                samples += 1
                if probe['height_error'] is not None:
                    maximum = max(maximum, probe['height_error'])
                if not probe['clear'] or blocker:
                    failures.append({'point': floor, 'floor': probe, 'blocker': blocker})
        checks.require(not failures, f'building floor {area["name"]} contains clutter, gaps or incorrect heights: {failures[:4]}')
        areas.append({'name': area['name'], 'grid': AREA_GRID, 'player_edge_inset': 24,
                      'samples': samples, 'clear': not failures, 'maximum_floor_error': maximum,
                      'failures': failures})
    checks.results.update(floor_probes=probes, open_build_areas=areas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=ROOT/'maps/source/pp_switchyard.map')
    parser.add_argument('--bsp', type=Path, default=ROOT/'baseq2/maps/pp_switchyard.bsp')
    parser.add_argument('--routes', type=Path, default=ROOT/'tools/maps/switchyard_routes.json')
    parser.add_argument('--baseline-bsp', type=Path, default=ROOT/'baseq2/maps/pp_temple.bsp')
    parser.add_argument('--bsp-log', type=Path, default=ROOT/'build/maps/pp_switchyard/bsp.log')
    parser.add_argument('--output', type=Path, default=ROOT/'build/maps/pp_switchyard/verification.json')
    args = parser.parse_args()
    checks = Checks()
    try:
        source = parse_entities(args.map.read_text())
        document = json.loads(args.routes.read_text())
        bsp, baseline = BSP(args.bsp), BSP(args.baseline_bsp)
        collision = Collision(bsp)
        checks.results.update(map_sha256=sha(args.map), bsp_sha256=sha(args.bsp),
                              routes_sha256=sha(args.routes), baseline_bsp_sha256=sha(args.baseline_bsp))
        inventory = bsp_inventory(args.bsp)
        checks.require(inventory['release_lumps_present'], 'compiled map needs completed VIS and baked lighting')
        if inventory['release_lumps_present']:
            bsp_inventory(args.bsp, require_release=True)
        checks.results['bsp'] = {'sha256': sha(args.bsp), 'bytes': len(bsp.raw),
                                 'clusters': inventory['clusters'],
                                 'pvs_visible_clusters_mean': inventory['pvs_visible_clusters_mean'],
                                 'pvs_visible_clusters_max': inventory['pvs_visible_clusters_max'],
                                 'lighting_bytes': len(bsp.lumps['lighting']),
                                 'vis_bytes': len(bsp.lumps['visibility'])}
        actual, reference = geometry_budget(bsp), geometry_budget(baseline)
        budgets = {}
        for key in ('compiled_faces', 'all_compiled_fan_triangles', 'renderable_compiled_fan_triangles'):
            maximum = math.floor(reference[key]*7/6)
            checks.require(actual[key] <= maximum,
                           f'{key} budget exceeded: {actual[key]} > {maximum} (Temple {reference[key]} × 7/6)')
            budgets[key] = {'actual': actual[key], 'temple': reference[key], 'maximum': maximum,
                            'passed': actual[key] <= maximum}
        checks.results['geometry_budget'] = budgets
        entity_checks(source, bsp, document, collision, checks)
        route_checks(document, collision, checks)
        open_floor_checks(document, collision, checks)
        textures = sorted({texture for entity in source for texture in entity['textures']})
        for texture in textures:
            valid = len(texture) <= 31 and bool(re.fullmatch(r'[A-Za-z0-9_/-]+', texture)) and '..' not in texture
            checks.require(valid and (ROOT/'baseq2/textures'/f'{texture}.wal').is_file(),
                           f'missing or invalid map material {texture!r}')
        checks.results['textures'] = textures
        if args.bsp_log.is_file():
            suspect = [line for line in args.bsp_log.read_text(errors='replace').splitlines()
                       if re.search(r'\bwarning\b|\bleaked\b|no entities in empty space|'
                                    r'couldn.t (?:locate texture|load.*(?:texture|\.wal|colormap)|'
                                    r'open.*(?:texture|\.wal|colormap))', line, re.I)]
            checks.require(not suspect, f'BSP compiler warnings/errors: {suspect[:8]}')
            checks.results['bsp_compile_warning_lines'] = suspect
        else:
            checks.warnings.append('BSP log missing; compiler leak/material warnings were not checked')
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError, struct.error) as error:
        checks.errors.append(f'validation input could not be read: {error}')
    report = {'passed': not checks.errors, 'errors': checks.errors, 'warnings': checks.warnings,
              **checks.results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': report['passed'], 'errors': checks.errors, 'warnings': checks.warnings,
                      'report': str(args.output), 'geometry_budget': checks.results.get('geometry_budget'),
                      'routes': len(checks.results.get('routes', [])),
                      'open_build_areas': len(checks.results.get('open_build_areas', []))}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
