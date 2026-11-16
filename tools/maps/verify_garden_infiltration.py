#!/usr/bin/env python3
"""Independently audit Garden Infiltration's source, mission graph and BSP hulls.

No generator is imported. Original face records (including flags and texture
mapping) and entity records are preserved in order. Collision uses the actual
compiled world and solid brush models. Walking routes are sampled every eight
units, grounded on the compiled brushes, and checked with the 18-unit step limit.
This static audit does not replace live mission or Pi frame-rate testing.
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

from verify_sandkeep import (BSP, EPSILON, MONSTER_MASK, PLAYER_MASK,
                            PLAYER_MAXS, PLAYER_MINS, SOLID, enabled,
                            parse_entities, vec)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/performance'))
from map_inventory import bsp_inventory

ENEMIES = {'monster_soldier_light', 'monster_soldier'}
PICKUPS = {'ammo_grenades', 'weapon_shotgun', 'ammo_shells',
           'item_health_small', 'item_health', 'item_armor_shard',
           'item_armor_jacket'}
STARTS = {'info_player_start', 'info_player_coop'}
TARGET_FIELDS = ('target', 'deathtarget', 'killtarget', 'pathtarget', 'combattarget')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hull_origin(keys):
    point = vec(keys['origin'])
    # SelectSpawnPoint adds nine units, and PutClientInServer adds one more
    # before linking the player (src/game/player/client.c). Preserve authored
    # start records while testing the hull at the actual linked spawn origin.
    return (point[0], point[1], point[2] + 10) if keys.get('classname') in STARTS else point


def records(text):
    """Keep complete authored brush records; the shared parser omits flags."""
    result, current, brush, depth = [], None, None, 0
    for raw in text.splitlines():
        line = raw.split('//', 1)[0].strip()
        if not line:
            continue
        if line == '{':
            depth += 1
            if depth == 1:
                current = {'properties': [], 'brushes': []}
            elif depth == 2:
                brush = []
            else:
                raise ValueError('Unsupported MAP nesting')
        elif line == '}':
            if depth == 2:
                current['brushes'].append(tuple(brush))
            elif depth == 1:
                result.append(current)
            else:
                raise ValueError('Unbalanced MAP brace')
            depth -= 1
        elif depth == 1:
            current['properties'].append(line)
        elif depth == 2:
            brush.append(' '.join(line.split()))
        else:
            raise ValueError('MAP content outside an entity')
    if depth:
        raise ValueError('Unclosed MAP entity')
    return result


def ordered_subset(original, candidate):
    cursor = 0
    for record in candidate:
        if cursor < len(original) and record == original[cursor]:
            cursor += 1
    return cursor == len(original), cursor


def samples(a, b, spacing=8):
    count = max(1, math.ceil(math.dist(a, b) / spacing))
    for i in range(count + 1):
        yield tuple(x + (y - x) * i / count for x, y in zip(a, b))


def project_route(point, points):
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    nearest, along, traversed = math.inf, 0., 0.
    for a, b in zip(points, points[1:]):
        delta = tuple(b[i] - a[i] for i in range(3))
        squared = sum(v * v for v in delta)
        t = max(0., min(1., sum((point[i] - a[i]) * delta[i]
                               for i in range(3)) / squared)) if squared else 0.
        projected = tuple(a[i] + delta[i] * t for i in range(3))
        distance = math.dist(point, projected)
        if distance < nearest:
            nearest, along = distance, traversed + math.sqrt(squared) * t
        traversed += math.sqrt(squared)
    return {'route_length': length, 'distance_from_route': nearest,
            'distance_along_route': along, 'fraction': along / length if length else 0.}


def texture_vectors(face):
    """Quake II's axial projection and rotation, independently of the translator."""
    p0, p1, p2 = face['points']
    a = tuple(p0[i] - p1[i] for i in range(3))
    b = tuple(p2[i] - p1[i] for i in range(3))
    normal = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    bases = (((0, 0, 1), (1, 0, 0), (0, -1, 0)),
             ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
             ((1, 0, 0), (0, 1, 0), (0, 0, -1)),
             ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
             ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
             ((0, -1, 0), (1, 0, 0), (0, 0, -1)))
    _, s, t = max(bases, key=lambda basis: sum(x*y for x, y in zip(basis[0], normal)))
    sv, tv = next(i for i, v in enumerate(s) if v), next(i for i, v in enumerate(t) if v)
    authored_rotation, scale_s, scale_t = face['mapping'][2:]
    # This q2tool's classic MAP parser stores rotation and both shifts as
    # integers (truncate toward zero), verified against compiled texinfo.
    rotation = int(authored_rotation)
    if not scale_s or not scale_t:
        raise ValueError(f'Zero texture scale at line {face["line"]}')
    cosine, sine = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    vectors = []
    for axis, scale in ((s, scale_s), (t, scale_t)):
        rotated = list(axis)
        rotated[sv] = cosine * axis[sv] - sine * axis[tv]
        rotated[tv] = sine * axis[sv] + cosine * axis[tv]
        vectors.append(tuple(v / scale for v in rotated))
    return vectors


def audit_translation(source, runtime, source_records, runtime_records, delta, edited_source=False):
    errors, faces, origins, max_error, max_uv_error = [], 0, 0, 0., 0.
    outlying_plane_points = 0
    bounds_low, bounds_high = [math.inf] * 3, [-math.inf] * 3

    def check(ok, message):
        if not ok and len(errors) < 30:
            errors.append(message)

    def bound(point, label, plane_point=False):
        nonlocal outlying_plane_points
        for i in range(3):
            bounds_low[i], bounds_high[i] = min(bounds_low[i], point[i]), max(bounds_high[i], point[i])
        if edited_source and plane_point and any(abs(v)>4032 for v in point):
            # Plane-defining MAP points need not lie on the bounded brush.
            # The compiled BSP vertices below establish actual geometry bounds.
            outlying_plane_points += 1
            return
        check(all(abs(v) <= 4032 for v in point), f'Runtime coordinate exceeds safe ±4032: {label} {point}')

    check(len(source) == len(runtime), 'Runtime translation changed entity count')
    for original, moved, raw_original, raw_moved in zip(source, runtime, source_records, runtime_records):
        keys, moved_keys = original['keys'], moved['keys']
        index = original['index']
        expected_keys=dict(keys)
        if edited_source and index>0 and keys.get('classname')=='worldspawn':
            expected_keys['classname']='func_group'
        check({k: v for k, v in expected_keys.items() if k != 'origin'} ==
              {k: v for k, v in moved_keys.items() if k != 'origin'},
              f'Runtime translation changed non-origin properties of entity #{index}')
        check(('origin' in keys) == ('origin' in moved_keys), f'Runtime origin added/removed on entity #{index}')
        if 'origin' in keys and 'origin' in moved_keys:
            a, b = vec(keys['origin']), vec(moved_keys['origin'])
            error = max(abs(b[i] - a[i] - delta[i]) for i in range(3))
            max_error = max(max_error, error)
            check(error <= 1e-5, f'Runtime entity #{index} origin is not source + translation: {a} → {b}')
            bound(b, f'entity #{index}')
            origins += 1
        check(len(original['brushes']) == len(moved['brushes']), f'Runtime brush count changed on entity #{index}')
        for brush_index, (a_brush, b_brush) in enumerate(zip(original['brushes'], moved['brushes'])):
            check(len(a_brush) == len(b_brush), f'Runtime face count changed on entity #{index} brush {brush_index}')
            for face_index, (a_face, b_face) in enumerate(zip(a_brush, b_brush)):
                label = f'entity #{index} brush {brush_index} face {face_index}'
                faces += 1
                check(a_face['texture'] == b_face['texture'], f'Runtime material changed: {label}')
                check(a_face['mapping'][2:] == b_face['mapping'][2:], f'Runtime rotation/scale changed: {label}')
                # The complete source face tails retain contents/surface/value
                # flags omitted by the shared geometry parser.
                a_tail = re.sub(r'^(?:\(\s*[^)]+\)\s*){3}\S+\s+', '',
                                raw_original['brushes'][brush_index][face_index]).split()
                b_tail = re.sub(r'^(?:\(\s*[^)]+\)\s*){3}\S+\s+', '',
                                raw_moved['brushes'][brush_index][face_index]).split()
                check(a_tail[5:] == b_tail[5:], f'Runtime contents/surface flags changed: {label}')
                a_vectors, b_vectors = texture_vectors(a_face), texture_vectors(b_face)
                texture_file = ROOT / 'baseq2/textures' / (a_face['texture'] + '.wal')
                dimensions = struct.unpack_from('<II', texture_file.read_bytes(), 32)
                for a, b in zip(a_face['points'], b_face['points']):
                    error = max(abs(b[i] - a[i] - delta[i]) for i in range(3))
                    max_error = max(max_error, error)
                    check(error <= 1e-5, f'Runtime face point is not source + translation: {label}: {a} → {b}')
                    bound(b, label, plane_point=True)
                    for uv in range(2):
                        old_uv = sum(a[i] * a_vectors[uv][i] for i in range(3)) + int(a_face['mapping'][uv])
                        new_uv = sum(b[i] * b_vectors[uv][i] for i in range(3)) + int(b_face['mapping'][uv])
                        difference = new_uv - old_uv
                        period = dimensions[uv]
                        uv_error = abs(difference - round(difference / period) * period) if period else abs(difference)
                        max_uv_error = max(max_uv_error, uv_error)
                        # A rigid translation generally requires fractional
                        # shifts. This compiler only stores integer shifts;
                        # nearest-integer compensation is within half a texel.
                        check(uv_error <= .501, f'Runtime texture alignment changed by {difference:.6f} texels: {label} axis {uv}')
    return {'passed': not errors, 'translation': delta, 'faces_checked': faces,
            'origins_checked': origins, 'maximum_coordinate_error': max_error,
            'maximum_uv_error_texels': max_uv_error, 'runtime_bounds': [bounds_low, bounds_high],
            'outlying_plane_definition_points': outlying_plane_points,
            'uv_quantization_tolerance_texels': .501,
            'texture_projection_uses_truncated_rotation_and_shift': True,
            'coordinate_limit': 4032, 'errors': errors}


class Hulls:
    """Find grounded box positions from the compiled convex-brush intervals."""
    def __init__(self, bsp):
        self.bsp = bsp
        self.solids = [(i, (0., 0., 0.)) for i in bsp.model_brushes[0]]
        self.solids += [(i, offset) for _, model, offset in bsp.bmodels
                        for i in bsp.model_brushes[model]]

    def ground_candidates(self, point, mins, maxs, mask, low, high):
        tops = set()
        for index, offset in self.solids:
            first, count, contents = self.bsp.brushes[index]
            if not count or not contents & mask:
                continue
            x, y = point[0] - offset[0], point[1] - offset[1]
            bottom, top = -math.inf, math.inf
            for plane_index, _ in self.bsp.sides[first:first + count]:
                normal = self.bsp.planes[plane_index][:3]
                distance = self.bsp.planes[plane_index][3]
                hull_offset = sum(normal[i] * (maxs[i] if normal[i] < 0 else mins[i])
                                  for i in range(3))
                remaining = distance - normal[0] * x - normal[1] * y - hull_offset
                if abs(normal[2]) < 1e-9:
                    if remaining <= EPSILON:
                        break
                elif normal[2] > 0:
                    top = min(top, remaining / normal[2])
                else:
                    bottom = max(bottom, remaining / normal[2])
                if bottom >= top:
                    break
            else:
                z = top + offset[2]
                if math.isfinite(z) and low - EPSILON <= z <= high + EPSILON:
                    tops.add(round(z, 6))
        candidates = []
        for z in sorted(tops):
            p = (point[0], point[1], z)
            if not self.bsp.collision(p, mins, maxs, mask) and self.bsp.collision(
                    (p[0], p[1], p[2] - .125), mins, maxs, mask):
                candidates.append(p)
        return candidates

    def sweep(self, a, b, mins=PLAYER_MINS, maxs=PLAYER_MAXS, mask=PLAYER_MASK):
        for p in samples(a, b, 2):
            hit = self.bsp.collision(p, mins, maxs, mask)
            if hit:
                return hit
        return None

    def walk(self, points):
        previous, failures, count, maximum_step = None, [], 0, 0.
        failed_segments, blocked_samples = Counter(), 0
        for segment, (a, b) in enumerate(zip(points, points[1:])):
            for nominal in samples(a, b):
                count += 1
                candidates = self.ground_candidates(nominal, PLAYER_MINS, PLAYER_MAXS,
                                                     PLAYER_MASK, nominal[2] - 64, nominal[2] + 32)
                candidates.sort(key=lambda p: abs(p[2] - (previous[2] if previous else nominal[2])))
                accepted, reason = None, 'No clear supported standing hull near route height'
                for p in candidates:
                    if previous is None:
                        accepted = p
                        break
                    rise = abs(p[2] - previous[2])
                    if rise > 18 + EPSILON:
                        reason = f'Ground-height change {rise:.2f} exceeds 18-unit step'
                        continue
                    hit = None
                    # Try ordinary movement first, then the engine's full
                    # 18-unit up/forward/down step. Raising only to the next
                    # endpoint height falsely clips a convex terrain ridge
                    # lying between the eight-unit samples.
                    for height in (max(previous[2], p[2]), previous[2] + 18):
                        corner = (previous[0], previous[1], height)
                        other = (p[0], p[1], height)
                        hit = (self.sweep(previous, corner) or self.sweep(corner, other)
                               or self.sweep(other, p))
                        if not hit:
                            break
                    if hit:
                        reason = f'Player step sweep hits {hit}'
                        continue
                    maximum_step = max(maximum_step, rise)
                    accepted = p
                    break
                if accepted is None:
                    blocked_samples += 1
                    failed_segments[segment] += 1
                    if failed_segments[segment] <= 2:
                        failures.append({'segment': segment, 'point': nominal, 'reason': reason})
                    # Keep failures local rather than cascading from a distant point.
                    previous = None
                else:
                    previous = accepted
        return {'passed': not failures, 'samples': count, 'spacing': 8,
                'blocked_samples': blocked_samples, 'failed_segments': dict(failed_segments),
                'maximum_sample_step': maximum_step, 'failures': failures}


def verify(args):
    errors, warnings = [], []
    report = {'source': str(args.source), 'base': str(args.base), 'bsp': str(args.bsp),
              'errors': errors, 'warnings': warnings,
              'edited_source': args.edited_source,
              'diagnostic': args.geometry_only, 'geometry_only': args.geometry_only,
              'limitations': ['Static compiled collision and entity checks do not prove AI navigation, '
                              'stealth behavior, mission completion, or Pi FPS; retain live tests.']}

    def require(condition, message):
        if not condition:
            errors.append(message)
        return bool(condition)

    base_sha = sha(args.base)
    source_text, base_text = args.source.read_text(), args.base.read_text()
    source, base = parse_entities(source_text), parse_entities(base_text)
    authored, original = records(source_text), records(base_text)
    design = json.loads(args.design.read_text())
    report.update(source_sha256=sha(args.source), base_sha256=base_sha,
                  design_sha256=sha(args.design), bsp_sha256=sha(args.bsp))
    require(args.source.resolve() != args.base.resolve(), 'Mission source must be separate from original Garden')
    require(design.get('base_source_sha256') == base_sha,
            'Original Garden hash differs from design.base_source_sha256')
    require(source[0]['keys'].get('classname') == base[0]['keys'].get('classname') == 'worldspawn',
            'First source entity must remain worldspawn')
    ok, preserved = ordered_subset(original[0]['brushes'], authored[0]['brushes'])
    world_preserved=ok
    preservation_check = warnings.append if args.edited_source else lambda message: require(False,message)
    if not ok:
        preservation_check(f'Original world brushes changed, removed or reordered; only {preserved}/{len(original[0]["brushes"])} preserved in sequence')
    ok, entities_preserved = ordered_subset(original[1:], authored[1:])
    if not ok:
        preservation_check(f'Original entities changed, removed or reordered; only {entities_preserved}/{len(original)-1} preserved in sequence')
    if args.edited_source:
        # Manual variants retain the exact original starts, but can edit the
        # terrain and move brush geometry into the world for visibility.
        for entity,raw in zip(base,original):
            if entity['keys'].get('classname') in STARTS:
                require(raw in authored,'Original player start changed in edited mission')
    old_world, new_world = base[0]['keys'], source[0]['keys']
    changes = {key: {'before': old_world.get(key), 'after': new_world.get(key)}
               for key in old_world.keys() | new_world.keys() if old_world.get(key) != new_world.get(key)}
    for key in changes:
        lighting_key = key.lstrip('_').startswith(('sun', 'ambient', 'minlight', 'light', 'color'))
        require(key == 'message' or lighting_key, f'Original non-lighting world property changed: {key}')
    report['preservation'] = {'original_world_brushes': len(original[0]['brushes']),
                              'strict_additive_contract_passed': world_preserved and ok,
                              'mode': 'edited-source' if args.edited_source else 'strict-additive',
                              'world_brushes_preserved_in_order': preserved,
                              'original_nonworld_entities': len(original) - 1,
                              'entities_preserved_in_order': entities_preserved,
                              'world_property_changes': changes}

    default_runtime = ROOT / 'build/maps/pp_garden_infiltration/runtime-source/pp_garden_infiltration.map'
    runtime_path = args.runtime_source or (default_runtime if default_runtime.is_file() else args.source)
    runtime_text = runtime_path.read_text()
    runtime_source = parse_entities(runtime_text)
    delta = tuple(map(float, design.get('runtime_translation', (0, 0, 0))))
    require(len(delta) == 3 and all(math.isfinite(v) for v in delta), 'Invalid runtime_translation vector')
    report.update(runtime_source=str(runtime_path), runtime_source_sha256=sha(runtime_path),
                  runtime_translation=delta)
    if runtime_path.resolve() != args.source.resolve():
        require('runtime_translation' in design, 'Runtime source requires design.runtime_translation')
        translation_check = audit_translation(source, runtime_source, authored, records(runtime_text), delta,args.edited_source)
        report['runtime_rebase'] = translation_check
        errors.extend(translation_check['errors'])
    else:
        require(not any(delta), 'Nonzero runtime_translation requires a separate runtime source')

    keys = [e['keys'] for e in source]
    counts = Counter(k.get('classname') for k in keys)
    report['entity_counts'] = dict(sorted(counts.items()))
    named = defaultdict(list)
    for e in source:
        if e['keys'].get('targetname'):
            named[e['keys']['targetname']].append(e)
    for e in source:
        k, c = e['keys'], e['keys'].get('classname', '')
        label = f'#{e["index"]} {c} {k.get("targetname", k.get("origin", ""))}'
        if c.startswith('monster_'):
            require(c in ENEMIES, f'Forbidden enemy: {label}')
        if c.startswith(('ammo_', 'weapon_', 'item_', 'key_')):
            require(c in PICKUPS, f'Forbidden pickup: {label}')
        if k.get('item'):
            require(k['item'] in PICKUPS, f'Forbidden enemy/item drop {k["item"]}: {label}')
        if c == 'target_spawner':
            require(k.get('target') in ENEMIES, f'Forbidden spawned class {k.get("target")}: {label}')
        require(c not in ('target_changelevel', 'trigger_changelevel', 'target_platoon_intermission'),
                f'Mission must retain playable in-level completion: {label}')
        for field in TARGET_FIELDS:
            if k.get(field) and not (c == 'target_spawner' and field == 'target'):
                require(k[field] in named, f'Unresolved {field}={k[field]} on {label}')
        if c == 'item_armor_jacket':
            require(float(k.get('count', 25)) in (0, 25), f'Jacket armor must retain its normal 25-point amount: {label}')
        if c in STARTS or c in PICKUPS:
            require(not int(k.get('spawnflags', 0)) & (256 | 512 | 1024), f'Start/supply is missing on a difficulty: {label}')
    require(counts['info_player_start'] == 1 and counts['info_player_coop'] == 3,
            'Mission needs the original one solo and three co-op starts')
    require(counts['misc_platoon_dropship'] > 0, 'Missing insertion helicopter')
    require(counts['target_goal'] > 0, 'Missing in-level target_goal completion')
    require(counts['weapon_shotgun'] > 0, 'Missing halfway shotgun pickup')
    for skill in range(3):
        for e in source:
            k = e['keys']
            if k.get('classname') != 'trigger_counter' or not enabled(e, skill):
                continue
            name = k.get('targetname')
            incoming = [other for other in source if enabled(other, skill) and any(
                other['keys'].get(field) == name for field in ('target', 'deathtarget', 'pathtarget'))
                and other['keys'].get('classname') != 'target_spawner']
            require(len(incoming) >= int(k.get('count', 2)),
                    f'Skill {skill}: counter {name} needs {k.get("count", 2)} sources but has {len(incoming)}')

    def leads_to_completion(start):
        pending, seen = deque([start]), set()
        while pending:
            e = pending.popleft()
            if e['index'] in seen:
                continue
            seen.add(e['index'])
            if e['keys'].get('classname') == 'target_goal':
                return True
            pending.extend(named.get(e['keys'].get('target'), ()))
        return False

    finishes = [e for e in source if e['keys'].get('classname') == 'trigger_platoon_extract']
    require(bool(finishes), 'Missing all-living-player completion trigger')
    require(any(leads_to_completion(e) for e in finishes),
            'All-player completion trigger has no target chain to target_goal')
    report['target_graph'] = {'named_targets': len(named), 'completion_triggers': len(finishes)}
    if 'mission_finish' in design and 'sandbox_boundary_x' in design:
        require(design['mission_finish'][0] < design['sandbox_boundary_x'],
                'Mission finish must remain outside the sandbox boundary')

    inventory = bsp_inventory(args.bsp, require_release=not args.geometry_only)
    report['bsp_inventory'] = inventory
    if not args.geometry_only and (any(delta) or args.compile_manifest):
        manifest_path = args.compile_manifest or (
            ROOT / 'build/garden-infiltration-runtime-build' / args.bsp.stem / 'manifest.json')
        manifest = json.loads(manifest_path.read_text())
        stages = manifest.get('stages', [])
        build_checks = {
            'runtime_source_matches': manifest.get('source_sha256') == report['runtime_source_sha256'],
            'bsp_matches': manifest.get('bsp_inventory', {}).get('sha256') == report['bsp_sha256'],
            'release_profile': manifest.get('profile') == 'release' and not manifest.get('diagnostic'),
            'bsp_full_vis_rad_passed': [s.get('name') for s in stages] == ['bsp', 'vis', 'rad']
                and all(s.get('returncode') == 0 and '-fast' not in s.get('command', []) for s in stages),
            'published': manifest.get('published') is True,
        }
        require(all(build_checks.values()), f'Compile receipt does not bind this runtime source to this full release BSP: {build_checks}')
        report['compile_receipt'] = {'path': str(manifest_path), 'sha256': sha(manifest_path),
                                     'checks': build_checks}
    bsp, hull_results = BSP(args.bsp), []
    grass_flags = Counter()
    for face in bsp.faces:
        plane = bsp.planes[face[0]]
        if plane[2] * (-1 if face[1] else 1) <= .5:
            continue
        texinfo = bsp.texinfo[face[4]]
        material = texinfo[10].split(b'\0')[0].decode('ascii')
        if material == 'sandkeep/grass':
            grass_flags[texinfo[8]] += 1
    report['rendered_grass_floor'] = {'upward_face_flags': dict(grass_flags),
                                       'sky_faces': sum(v for flags, v in grass_flags.items() if flags & 4)}
    require(bool(grass_flags) and not any(flags & 4 for flags in grass_flags),
            f'Compiled grass floors must render as ordinary surfaces, not SKY: {dict(grass_flags)}')

    def compiled_signature(entities):
        return Counter(tuple(sorted((k, v) for k, v in e['keys'].items()
                                    if k != 'model' and not k.startswith('_')))
                       for e in entities if e['keys'].get('classname') not in ('worldspawn', 'light', 'func_group'))

    require(compiled_signature(runtime_source) == compiled_signature(bsp.entities),
            'Compiled gameplay entity keys do not match current runtime source')
    if any(delta):
        require(all(all(abs(v) <= 4032 for v in vertex) for vertex in bsp.vertexes),
                'Compiled BSP contains vertices outside safe ±4032 runtime bounds')
    hulls = Hulls(bsp)
    actor_hulls = []
    for e in runtime_source:
        k, c = e['keys'], e['keys'].get('classname', '')
        if c in STARTS or c in ENEMIES:
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK if c in ENEMIES else PLAYER_MASK
            actor_hulls.append((e, mins, maxs))
        elif c in PICKUPS:
            mins, maxs, mask = (-15.,) * 3, (15.,) * 3, SOLID
        else:
            continue
        if not require('origin' in k, f'Entity #{e["index"]} {c} lacks origin'):
            continue
        point = hull_origin(k)
        hit = bsp.collision(point, mins, maxs, mask)
        grounded = hulls.ground_candidates(point, mins, maxs, mask,
                                          point[2] - (128 if c in PICKUPS else 64), point[2] + EPSILON)
        resting = max(grounded, key=lambda p: p[2]) if grounded else None
        drop_hit = hulls.sweep(point, resting, mins, maxs, mask) if resting and not hit else None
        require(not hit, f'#{e["index"]} {c} at {point} intersects {hit}')
        require(resting is not None, f'#{e["index"]} {c} at {point} has no clear ground support below')
        require(not drop_hit, f'#{e["index"]} {c} ground-drop path blocked by {drop_hit}')
        hull_results.append({'entity': e['index'], 'classname': c, 'origin': point,
                             'authored_runtime_origin': vec(k['origin']),
                             'blocker': hit, 'grounded_origin': resting, 'drop_blocker': drop_hit})
    for i, (e, mins, maxs) in enumerate(actor_hulls):
        if 'origin' not in e['keys']:
            continue
        a = hull_origin(e['keys'])
        for other, omin, omax in actor_hulls[i + 1:]:
            if 'origin' not in other['keys'] or not any(enabled(e, s) and enabled(other, s) for s in range(3)):
                continue
            b = hull_origin(other['keys'])
            overlap = all(a[j] + mins[j] < b[j] + omax[j] and b[j] + omin[j] < a[j] + maxs[j] for j in range(3))
            require(not overlap, f'Overlapping actor spawns #{e["index"]} at {a} / #{other["index"]} at {b}')
    report['placements'] = hull_results

    routes = design.get('routes', [])
    require(bool(routes), 'No authored mission routes in design JSON')
    route_results = []
    for route in routes:
        points = [tuple(map(float, p)) for p in route.get('points', [])]
        valid = len(points) >= 2 and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in points)
        if not require(valid, f'Invalid route points: {route.get("name")}'):
            continue
        runtime_points = [tuple(p[i] + delta[i] for i in range(3)) for p in points]
        result = hulls.walk(runtime_points)
        result['coordinate_space'] = 'runtime'
        for failure in result['failures']:
            failure['source_point'] = tuple(failure['point'][i] - delta[i] for i in range(3))
        result['name'] = route.get('name', 'unnamed')
        result['length'] = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
        route_results.append(result)
        require(result['passed'], f'Route {result["name"]} blocked/unsupported: {result["failures"]}')
    report['routes'] = route_results
    if routes and route_results:
        primary = max(routes, key=lambda r: sum(math.dist(a, b) for a, b in zip(r['points'], r['points'][1:])))
        origin = design.get('shotgun_origin')
        if require(isinstance(origin, list) and len(origin) == 3, 'Missing design.shotgun_origin'):
            shotgun = [e for e in source if e['keys'].get('classname') == 'weapon_shotgun'
                       and math.dist(vec(e['keys']['origin']), origin) <= .01]
            require(bool(shotgun), 'Authored halfway shotgun does not match design.shotgun_origin')
            progress = project_route(origin, primary['points'])
            progress['route'] = primary.get('name')
            report['shotgun_progress'] = progress
            require(.45 <= progress['fraction'] <= .60,
                    f'Shotgun is at {progress["fraction"]:.1%} of primary route; expected 45–60%')
            require(progress['distance_from_route'] <= 256,
                    f'Shotgun is {progress["distance_from_route"]:.1f} units from primary route')
    require(sha(args.base) == base_sha, 'Original Garden changed during verification')
    require(sha(args.source) == report['source_sha256'], 'Mission source changed during verification; rerun audit')
    require(sha(args.design) == report['design_sha256'], 'Mission design changed during verification; rerun audit')
    require(sha(runtime_path) == report['runtime_source_sha256'], 'Runtime source changed during verification; rerun audit')
    report['passed'] = not errors
    report['release_ready'] = report['passed'] and not args.geometry_only
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'maps/source/pp_garden_infiltration.map')
    parser.add_argument('--base', type=Path, default=ROOT / 'baseq2/maps/pp_garden.map')
    parser.add_argument('--bsp', type=Path, default=ROOT / 'baseq2/maps/pp_garden_infiltration.bsp')
    parser.add_argument('--design', type=Path, default=ROOT / 'maps/source/pp_garden_infiltration.design.json')
    parser.add_argument('--edited-source', action='store_true',
                        help='Report original-preservation drift while retaining mission, translation, route and collision checks')
    parser.add_argument('--runtime-source', type=Path,
                        help='Translated compile MAP; defaults to build/maps/pp_garden_infiltration/runtime-source when present')
    parser.add_argument('--compile-manifest', type=Path,
                        help='Compile receipt binding runtime MAP hash to full BSP/VIS/RAD output')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/maps/pp_garden_infiltration/verification.json')
    parser.add_argument('--geometry-only', action='store_true',
                        help='Diagnostic preview audit without requiring lighting; never release-ready')
    args = parser.parse_args()
    try:
        report = verify(args)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        report = {'passed': False, 'release_ready': False, 'diagnostic': args.geometry_only,
                  'geometry_only': args.geometry_only,
                  'errors': [f'{type(error).__name__}: {error}'], 'warnings': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'errors': report['errors'],
                      'warnings': report['warnings'], 'output': str(args.output)}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
