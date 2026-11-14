#!/usr/bin/env python3
"""Build editable Temple brushes from the measured N64 room surfaces.

The JSON reference preserves coordinates, not GoldenEye texture pixels. All
visible brush materials are existing Plastic Platoon artwork. Source triangle
winding faces into playable air; solids extend behind that surface only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Original nominal eye: 175 world units, Temple BG scale: 33/70.
# Quake II standing eye: 24 origin-to-floor + 22 origin-to-eye.
SCALE = 46 / (175 * (33 / 70))
# Original overlapping room shells can be only a few units apart. Thick
# normal extrusions can push a lower sloped ceiling through an upper floor.
THICKNESS = 1
WALL = 'sandkeep/sand_wall'
FLOOR = 'sandkeep/sand'
CEILING = 'endline/concrete'
SKY = 'sandkeep/sky'


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def normal(poly):
    n = cross(sub(poly[1], poly[0]), sub(poly[2], poly[0]))
    length = math.sqrt(dot(n, n))
    return tuple(x/length for x in n)


def transform(p):
    x, y, z = p
    return (x*SCALE, -z*SCALE, y*SCALE)


def point(p):
    return '( ' + ' '.join(f'{v:.6f}' for v in p) + ' )'


def convex(polygons, texture, *, detail=False):
    vertices = [p for poly in polygons for p in poly]
    center = tuple(sum(p[i] for p in vertices)/len(vertices) for i in range(3))
    faces = []
    for poly in polygons:
        a, b, c = poly[:3]
        # MAP's plane winding is opposite the conventional triangle winding.
        n = cross(sub(a, b), sub(c, b))
        if dot(n, sub(center, b)) > 0:
            a, c = c, a
        flags = 4 if texture == SKY else 0
        faces.append(' '.join(point(p) for p in (a, b, c))
                     + f' {texture} 0 0 0 1 1 {134217728 if detail else 0} {flags} 0\n')
    return '{\n' + ''.join(faces) + '}\n'


def slab(poly, texture, *, thickness=THICKNESS):
    n = normal(poly)
    back = [tuple(p[i]-n[i]*thickness for i in range(3)) for p in poly]
    sides = [[poly[i], back[i], back[(i+1) % len(poly)], poly[(i+1) % len(poly)]]
             for i in range(len(poly))]
    return convex([poly, back, *sides], texture)


def box(lo, hi, texture):
    x, y, z = lo
    X, Y, Z = hi
    return convex([[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z)],
                   [(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)],
                   [(x,y,z),(X,y,z),(X,y,Z),(x,y,Z)],
                   [(x,Y,z),(X,Y,z),(X,Y,Z),(x,Y,Z)],
                   [(x,y,z),(x,Y,z),(x,Y,Z),(x,y,Z)],
                   [(X,y,z),(X,Y,z),(X,Y,Z),(X,y,Z)]], texture)


def entity(classname, origin=None, brushes='', **keys):
    props = {'classname': classname, **keys}
    if origin is not None:
        props['origin'] = ' '.join(f'{v:.6f}' for v in origin)
    return '{\n' + ''.join(f'"{k}" "{v}"\n' for k,v in props.items()) + brushes + '}\n'


def merge_polygons(polys):
    """Join adjacent coplanar faces only when their union remains convex."""
    groups = {}
    for poly in polys:
        n = normal(poly)
        key = tuple(round(v, 5) for v in (*n, dot(n, poly[0])))
        groups.setdefault(key, []).append(poly)
    result = []
    for pending in groups.values():
        # Unused collinear corner vertices are removed after every merge.
        def simplify(poly):
            return [b for a,b,c in zip(poly[-1:]+poly[:-1], poly, poly[1:]+poly[:1])
                    if dot(cross(sub(b,a),sub(c,b)), cross(sub(b,a),sub(c,b))) > 1e-10]
        pending = [list(poly) for poly in pending]
        changed = True
        while changed:
            changed = False
            for i in range(len(pending)):
                edges = [(a,b) for a,b in zip(pending[i],pending[i][1:]+pending[i][:1])]
                for j in range(i+1,len(pending)):
                    other = [(a,b) for a,b in zip(pending[j],pending[j][1:]+pending[j][:1])]
                    shared = set(edges) & {(b,a) for a,b in other}
                    if not shared:
                        continue
                    boundary = [e for e in edges if e not in shared] + [e for e in other if (e[1],e[0]) not in shared]
                    chain = [boundary.pop(0)[0]]
                    current = chain[0]
                    all_edges = [e for e in edges if e not in shared] + [e for e in other if (e[1],e[0]) not in shared]
                    by_start = {a:b for a,b in all_edges}
                    if len(by_start) != len(all_edges):
                        continue
                    for _ in range(len(all_edges)-1):
                        current = by_start.get(current)
                        if current is None or current == chain[0]:
                            break
                        chain.append(current)
                    if len(chain) != len(all_edges) or by_start.get(chain[-1]) != chain[0]:
                        continue
                    chain = simplify(chain)
                    if len(chain) < 3:
                        continue
                    n = normal(chain)
                    turns = [dot(n,cross(sub(b,a),sub(c,b))) for a,b,c in
                             zip(chain[-1:]+chain[:-1],chain,chain[1:]+chain[:1])]
                    if min(turns) < -1e-5:
                        continue
                    pending[i] = chain
                    pending.pop(j)
                    changed = True
                    break
                if changed:
                    break
        result.extend(pending)
    return result


def generate(layout):
    brushes, entities, surfaces = [], [], []
    for room in layout['rooms']:
        by_texture = {}
        for tri, texture_id in zip(room['triangles'], room['triangle_texture_ids']):
            poly = tuple(tuple(transform(room['vertices'][i])) for i in tri)
            n = normal(poly)
            texture = FLOOR if n[2] > .65 else CEILING if n[2] < -.65 else WALL
            by_texture.setdefault(texture, []).append(poly)
        for texture, polygons in by_texture.items():
            for poly in merge_polygons(polygons):
                brushes.append(f'// N64 room {room["id"]}\n'+slab(poly, texture))
                surfaces.append(dict(room=room['id'], texture=texture, vertices=poly))

    # The original render mesh has open sky/backdrop edges and touching sheets
    # that are not a volumetric BSP seal. Keep the original surfaces intact;
    # seal the unreachable exterior with a sky shell behind the whole mesh.
    all_points = [transform(p) for r in layout['rooms'] for p in r['vertices']]
    lo = [math.floor(min(p[i] for p in all_points)/64)*64-64 for i in range(3)]
    hi = [math.ceil(max(p[i] for p in all_points)/64)*64+64 for i in range(3)]
    for axis in range(3):
        for side in (0,1):
            a,b = lo.copy(),hi.copy()
            if side == 0:
                b[axis] = lo[axis]+16
            else:
                a[axis] = hi[axis]-16
            brushes.append('// Exterior sky seal beyond source mesh\n'+box(a,b,SKY))

    pads = {p['id']:p for p in layout['pads']}
    spawns = []
    for i, pid in enumerate(layout['spawn_pad_ids']):
        pad = pads[pid]
        x,y,z = transform(pad['floor_position'])
        z += 24.125
        look = pad['look']
        angle = math.degrees(math.atan2(-look[2],look[0])) % 360
        spawns.append([x,y,z])
        entities.append(entity('info_player_deathmatch',(x,y,z),angle=f'{angle:.6f}'))
        if i == 0:
            entities.append(entity('info_player_start',(x,y,z),angle=f'{angle:.6f}'))
        elif i < 4:
            entities.append(entity('info_player_coop',(x,y,z),angle=f'{angle:.6f}'))

    # Preserve the original eight weapon locations and power ordering, using
    # the weapons that exist in Plastic Platoon. No extra arena furniture.
    weapons = ['weapon_shotgun','weapon_shotgun','weapon_supershotgun',
               'weapon_machinegun','weapon_machinegun','weapon_chaingun',
               'weapon_grenadelauncher','weapon_rocketlauncher']
    pickups = []
    def pickup(classname,pid):
        x,y,z = transform(pads[pid]['floor_position'])
        z += 24
        entities.append(entity(classname,(x,y,z)))
        pickups.append(dict(classname=classname,pad=pid,origin=[x,y,z]))
    ammo = ['ammo_shells','ammo_shells','ammo_shells','ammo_shells',
            'ammo_bullets','ammo_bullets','ammo_bullets','ammo_bullets',
            'ammo_bullets','ammo_bullets','ammo_bullets','ammo_bullets',
            'ammo_grenades','ammo_grenades','ammo_rockets','ammo_rockets']
    # Keep the original shared locations, including double ammunition crates.
    ammo_index = 0
    for prop in layout['props']:
        if 'weapon_slot' in prop:
            pickup(weapons[prop['weapon_slot']],prop['pad'])
        elif prop['kind'] == 'AmmoBox':
            pickup(ammo[ammo_index],prop['pad'])
            ammo_index += 1
        elif prop['kind'] == 'Armour':
            pickup('item_armor_body',prop['pad'])

    # Six vertically sliding doors at the original bound-pad apertures.
    # Their speed/touch interaction uses the host game's normal door rules.
    for i,pad in enumerate(layout['bound_pads']):
        points = [transform(pad['world_min']),transform(pad['world_max'])]
        low = [min(p[j] for p in points) for j in range(3)]
        high = [max(p[j] for p in points) for j in range(3)]
        entities.append(entity('func_door',brushes=box(low,high,'sandkeep/wood'),
                               angle=-1,speed=110,wait=25,lip=4,dmg=0,sounds=1,
                               targetname=f'temple_door_{i+1}'))
        # A targetname suppresses Quake's automatic touch field. Explicit touch
        # volumes let both sides operate the door without a new use binding.
        touchlo = [low[0]-48,low[1]-48,low[2]]
        touchhi = [high[0]+48,high[1]+48,high[2]]
        entities.append(entity('trigger_multiple',brushes=box(touchlo,touchhi,WALL),
                               target=f'temple_door_{i+1}',wait=1))

    # Invisible point lights preserve the empty architecture. Source floor
    # centroids choose only navigable positions, clustered on a 200-unit grid.
    lights = {}
    for tile in layout['stan_tiles']:
        pts = [transform(p) for p in tile['vertices']]
        center = tuple(sum(p[i] for p in pts)/len(pts) for i in range(3))
        key = (tile['room'],round(center[0]/200),round(center[1]/200),round(center[2]/96))
        lights.setdefault(key,center)
    light_positions = []
    for key,(x,y,z) in lights.items():
        pos = (x,y,z+96)
        entities.append(entity('light',pos,light=240,_color='1 .92 .78'))
        light_positions.append(pos)
    entities.append(entity('info_player_intermission',
                           (spawns[4][0],spawns[4][1],spawns[4][2]+96),angles='18 90 0'))
    world = ('// GoldenEye N64 Temple: measured room surfaces, PP materials.\n'
             '// Regenerate with tools/maps/generate_temple.py. See maps/README-temple.md.\n'
             '{\n"classname" "worldspawn"\n"message" "Temple"\n"sky" "sandkeep"\n'
             '"sounds" "0"\n' + ''.join(brushes) + '}\n')
    report = dict(scale=SCALE,coordinate_transform='(x,-z,y) * scale',
                  source_rooms=len(layout['rooms']),source_triangles=sum(len(r['triangles']) for r in layout['rooms']),
                  brushes=len(brushes),entities=len(entities),spawns=spawns,pickups=pickups,
                  surfaces=surfaces,lights=light_positions,sky_bounds=[lo,hi])
    return world+''.join(entities),report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,default=ROOT/'tools/maps/temple_layout.json')
    p.add_argument('--output',type=Path,default=ROOT/'maps/source/pp_temple.map')
    args=p.parse_args()
    layout=json.loads(args.reference.read_text())
    text,report=generate(layout)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(text)
    build=ROOT/'build/maps/pp_temple'
    build.mkdir(parents=True,exist_ok=True)
    report['reference_sha256']=hashlib.sha256(args.reference.read_bytes()).hexdigest()
    report['map_sha256']=hashlib.sha256(args.output.read_bytes()).hexdigest()
    (build/'layout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{args.output}: {report["source_rooms"]} rooms, {report["brushes"]} brushes, {report["entities"]} entities; scale {SCALE:.9f}')


if __name__=='__main__':
    main()
