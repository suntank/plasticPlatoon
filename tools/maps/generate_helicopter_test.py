#!/usr/bin/env python3
"""Reproduce and independently verify the tan helicopter flight range."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "pp_helicopter_test"
# Original box layout in world units. Surface flag 4 is the stock Quake II sky.
BRUSHES = [((-1440, -1632, -64), (1440, 1632, 0), 'sandkeep/sand', 0, 0, 0),
 ((-1440, -1632, 832), (1440, 1632, 864), 'sandkeep/wood_end', 0, 4, 0),
 ((-1440, -1632, 0), (-1408, 1632, 832), 'sandkeep/wood', 0, 0, 0),
 ((1408, -1632, 0), (1440, 1632, 832), 'sandkeep/wood', 0, 0, 0),
 ((-1408, -1632, 0), (1408, -1600, 832), 'sandkeep/wood', 0, 0, 0),
 ((-1408, 1600, 0), (1408, 1632, 832), 'sandkeep/wood', 0, 0, 0),
 ((-1408, -1600, 176), (-1384, 1600, 200), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-1408, -1504, 0), (-1384, -1472, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-1408, -864, 0), (-1384, -832, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-1408, -224, 0), (-1384, -192, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-1408, 416, 0), (-1384, 448, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-1408, 1056, 0), (-1384, 1088, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-1408, 1536, 0), (-1384, 1568, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, -1600, 176), (1408, 1600, 200), 'sandkeep/wood_end', 134217728, 0, 0),
 ((1384, -1504, 0), (1408, -1472, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, -864, 0), (1408, -832, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, -224, 0), (1408, -192, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, 416, 0), (1408, 448, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, 1056, 0), (1408, 1088, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((1384, 1536, 0), (1408, 1568, 288), 'sandkeep/trim', 134217728, 0, 0),
 ((-560, -1112, 0), (560, -1064, 208), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((-560, -1600, 208), (560, -1064, 232), 'sandkeep/wood_end', 0, 0, 0),
 ((-560, -1600, 0), (-528, -1360, 208), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((-560, -1200, 0), (-528, -1112, 208), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((528, -1600, 0), (560, -1360, 208), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((528, -1200, 0), (560, -1112, 208), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((-240, -848, 0), (240, -752, 192), 'sandkeep/plastic_blue_smooth', 0, 0, 0),
 ((-244, -852, 176), (244, -748, 192), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-960, -480, 0), (-736, -384, 224), 'sandkeep/plastic_red', 0, 0, 0),
 ((-964, -484, 208), (-732, -380, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((704, -416, 0), (960, -320, 224), 'sandkeep/plastic_blue_smooth', 0, 0, 0),
 ((700, -420, 208), (964, -316, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-960, 224, 0), (-384, 288, 224), 'sandkeep/wood', 0, 0, 0),
 ((-964, 220, 208), (-380, 292, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((384, 320, 0), (960, 384, 224), 'sandkeep/wood', 0, 0, 0),
 ((380, 316, 208), (964, 388, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-208, 704, 0), (208, 800, 192), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((-212, 700, 176), (212, 804, 192), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-960, 1184, 0), (-736, 1280, 224), 'sandkeep/plastic_blue_smooth', 0, 0, 0),
 ((-964, 1180, 208), (-732, 1284, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((736, 1200, 0), (960, 1296, 224), 'sandkeep/plastic_red', 0, 0, 0),
 ((732, 1196, 208), (964, 1300, 224), 'sandkeep/wood_end', 134217728, 0, 0),
 ((-1248, -192, 176), (-992, 32, 200), 'sandkeep/wood_end', 0, 0, 0),
 ((-1248, 0, 0), (-992, 32, 176), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((-1248, -192, 0), (-1224, 0, 176), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((992, 704, 176), (1248, 928, 200), 'sandkeep/wood_end', 0, 0, 0),
 ((992, 896, 0), (1248, 928, 176), 'sandkeep/plastic_green_smooth', 0, 0, 0),
 ((992, 704, 0), (1016, 896, 176), 'sandkeep/plastic_green_smooth', 0, 0, 0)]

ENTITIES = [{'classname': 'worldspawn', 'message': 'Plastic Helicopter Test Range', 'sounds': '0', 'sky': 'unit1_',
             '_sun': 'range_sun_target', '_sun_light': '70',
             '_sun_ambient': '24', '_sun_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '256 -384 768', 'target': 'range_sun_target'},
 {'classname': 'info_null', 'origin': '0 0 32', 'targetname': 'range_sun_target'},
 {'classname': 'light', 'origin': '-352 -1392 144', 'light': '400', '_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '352 -1392 144', 'light': '400', '_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '0 -1248 144', 'light': '400', '_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '-1120 -96 128', 'light': '260', '_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '1120 800 128', 'light': '260', '_color': '1 .98 .94'},
 {'classname': 'light', 'origin': '-1024 -1376 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-352 -1376 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '352 -1376 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '1024 -1376 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-1024 -736 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-352 -736 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '352 -736 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '1024 -736 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-1024 -96 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-352 -96 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '352 -96 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '1024 -96 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-1024 544 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-352 544 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '352 544 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '1024 544 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-1024 1184 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '-352 1184 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '352 1184 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'light', 'origin': '1024 1184 600', 'light': '640', '_color': '1 .94 .83'},
 {'classname': 'monster_plastic_helicopter',
  'origin': '0 -224 288',
  'angle': '270',
  'deathtarget': 'helicopter_down'},
 {'classname': 'light', 'origin': '0 -336 224', 'light': '340', '_color': '.82 .90 1'},
 {'classname': 'monster_plastic_helicopter',
  'origin': '-672 608 336',
  'angle': '270',
  'deathtarget': 'helicopter_down'},
 {'classname': 'light', 'origin': '-672 496 224', 'light': '340', '_color': '.82 .90 1'},
 {'classname': 'monster_plastic_helicopter',
  'origin': '672 1024 384',
  'angle': '270',
  'deathtarget': 'helicopter_down'},
 {'classname': 'light', 'origin': '672 912 224', 'light': '340', '_color': '.82 .90 1'},
 {'classname': 'info_player_start', 'origin': '0 -1488 24', 'angle': '90'},
 {'classname': 'info_player_coop', 'origin': '96 -1488 24', 'angle': '90'},
 {'classname': 'info_player_coop', 'origin': '-96 -1488 24', 'angle': '90'},
 {'classname': 'info_player_coop', 'origin': '192 -1488 24', 'angle': '90'},
 {'classname': 'weapon_rocketlauncher', 'origin': '-192 -1408 32'},
 {'classname': 'weapon_chaingun', 'origin': '192 -1408 32'},
 {'classname': 'item_armor_body', 'origin': '0 -1408 32'},
 {'classname': 'item_health_large', 'origin': '-400 -1408 32'},
 {'classname': 'item_health_large', 'origin': '400 -1408 32'},
 {'classname': 'item_health_large', 'origin': '-1120 -48 32'},
 {'classname': 'ammo_rockets', 'origin': '-1120 48 32'},
 {'classname': 'ammo_bullets', 'origin': '-1024 -48 32'},
 {'classname': 'item_health_large', 'origin': '1120 848 32'},
 {'classname': 'ammo_rockets', 'origin': '1120 752 32'},
 {'classname': 'ammo_bullets', 'origin': '1064 848 32'},
 {'classname': 'ammo_rockets', 'origin': '-384 -1280 32'},
 {'classname': 'ammo_rockets', 'origin': '-384 -1184 32'},
 {'classname': 'ammo_rockets', 'origin': '-256 -1280 32'},
 {'classname': 'ammo_rockets', 'origin': '-256 -1184 32'},
 {'classname': 'ammo_rockets', 'origin': '-128 -1280 32'},
 {'classname': 'ammo_rockets', 'origin': '-128 -1184 32'},
 {'classname': 'ammo_bullets', 'origin': '128 -1280 32'},
 {'classname': 'ammo_bullets', 'origin': '128 -1184 32'},
 {'classname': 'ammo_bullets', 'origin': '256 -1280 32'},
 {'classname': 'ammo_bullets', 'origin': '256 -1184 32'},
 {'classname': 'ammo_bullets', 'origin': '384 -1280 32'},
 {'classname': 'ammo_bullets', 'origin': '384 -1184 32'},
 {'classname': 'trigger_counter',
  'targetname': 'helicopter_down',
  'count': '3',
  'spawnflags': '1',
  'target': 'range_complete'},
 {'classname': 'trigger_relay',
  'targetname': 'range_complete',
  'target': 'range_goal',
  'message': 'AIR RANGE CLEAR\\nAll three helicopters defeated.\\nConsole: map pp_helicopter_test to reset.'},
 {'classname': 'target_goal', 'origin': '0 1504 48', 'targetname': 'range_goal'},
 {'classname': 'target_help',
  'targetname': 'range_help',
  'spawnflags': '1',
  'message': 'HELICOPTER TEST\\nThree tan gunships patrol above the toy range.\\nWatch the main and tail '
             'rotors turn.\\nCollect the M60, rockets and armor in this bunker.\\nUse roofed shelters against '
             'their guns and rockets.'},
 {'classname': 'trigger_always', 'target': 'range_help', 'delay': '1'},
 {'classname': 'info_player_intermission', 'origin': '1200 -816 448', 'angles': '14 130 0'}]

def box(lo, hi, texture, contents=0, flags=0, value=0):
    x,y,z = lo
    X,Y,Z = hi
    planes = [((x,y,z),(x,Y,Z),(x,y,Z)), ((X,y,z),(X,Y,Z),(X,Y,z)),
              ((x,y,z),(X,y,Z),(X,y,z)), ((x,Y,z),(X,Y,Z),(x,Y,Z)),
              ((x,y,z),(X,Y,z),(x,Y,z)), ((x,y,Z),(X,Y,Z),(X,y,Z))]
    faces = []
    for plane in planes:
        points = " ".join("( " + " ".join(f"{v:g}" for v in p) + " )" for p in plane)
        faces.append(f"{points} {texture} 0 0 0 1 1 {contents} {flags} {value}\n")
    return "{\n" + "".join(faces) + "}\n"


def entity(keys, brushes=""):
    return "{\n" + "".join(f'"{key}" "{value}"\n' for key,value in keys.items()) + brushes + "}\n"


def generate():
    path = ROOT / f"maps/source/{NAME}.map"
    text = "// Original Plastic Platoon helicopter test range; directly editable.\n"
    text += entity(ENTITIES[0], "".join(box(*b) for b in BRUSHES))
    text += "".join(entity(e) for e in ENTITIES[1:])
    path.write_text(text)
    print(f"Wrote {path} ({len(BRUSHES)} brushes; {len(ENTITIES)-1} entities)")


def verify(path):
    from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MINS,
                                 PLAYER_MAXS, enabled, parse_entities, vec)
    bsp = BSP(path)
    source_path = ROOT / f"maps/source/{NAME}.map"
    source = parse_entities(source_path.read_text())
    errors, placements, routes, rotor_checks, bay_cover = [], [], [], [], []
    def require(test, message):
        if not test:
            errors.append(message)
    def logic(entities):
        return Counter(tuple(sorted((k,v) for k,v in e["keys"].items() if k != "model"))
                       for e in entities if e["keys"]["classname"] != "light")
    require(logic(source) == logic(bsp.entities), "Source/BSP gameplay entity mismatch")
    starts, helicopters = [], []
    for e in bsp.entities:
        keys, classname = e["keys"], e["keys"]["classname"]
        if classname == "monster_plastic_helicopter":
            helicopters.append(e)
            mins,maxs,mask = (-72,-56,-32),(72,56,48),MONSTER_MASK
        elif classname in ("info_player_start", "info_player_coop"):
            starts.append(e)
            mins,maxs,mask = PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK
        elif classname.startswith(("weapon_", "ammo_", "item_")):
            mins,maxs,mask = (-15,)*3,(15,)*3,PLAYER_MASK
        else:
            continue
        origin = vec(keys["origin"])
        hit = bsp.collision(origin,mins,maxs,mask)
        require(not hit,f"{classname} at {origin} intersects {hit}")
        placements.append(dict(classname=classname,origin=origin,collision=hit))
    # Sample complete rotor sweep and clearance around each initial gunship.
    for e in helicopters:
        origin = vec(e["keys"]["origin"])
        blockers = []
        for angle in range(0,360,5):
            a = math.radians(angle)
            for radius in (0,48,92):
                point = (origin[0]+radius*math.cos(a),origin[1]+radius*math.sin(a),origin[2]+48)
                hit = bsp.collision(point,(-3,)*3,(3,)*3,MONSTER_MASK)
                if hit:
                    blockers.append(dict(point=point,collision=hit))
        require(not blockers,f"Helicopter at {origin} has obstructed main rotor: {blockers[:3]}")
        rotor_checks.append(dict(origin=origin,samples=216,blockers=blockers))
        # All guns and rocket pods aim through opaque bunker cover toward starts.
        for start in starts:
            eye = vec(start["keys"]["origin"])
            eye = (eye[0],eye[1],eye[2]+22)
            yaw = math.atan2(eye[1]-origin[1],eye[0]-origin[0])
            for x,y,z in ((64,-24,-10),(64,24,-10),(30,-46,-2),(30,46,-2)):
                muzzle = (origin[0]+x*math.cos(yaw)-y*math.sin(yaw),
                          origin[1]+x*math.sin(yaw)+y*math.cos(yaw),origin[2]+z)
                hit = bsp.segment_hits(muzzle,eye)
                require(bool(hit),f"Unprotected start {eye} from helicopter at {origin}")
                bay_cover.append(dict(helicopter=origin,muzzle=muzzle,eye=eye,blocked=bool(hit)))
    paths = {
        "west_flank": [(0,-1488,24),(-352,-1488,24),(-352,-1280,24),(-1184,-1280,24),
                       (-1184,-256,24),(-1328,-256,24),(-1328,1472,24),(-400,1472,24)],
        "east_flank": [(0,-1488,24),(352,-1488,24),(352,-1280,24),(1184,-1280,24),
                       (1184,544,24),(1328,544,24),(1328,1472,24),(400,1472,24)],
        "central_approach": [(-1184,-1280,24),(-1184,-944,24),(-448,-944,24),
                             (-448,-608,24),(0,-608,24),(0,512,24),(320,512,24),(320,1216,24)]}
    for name,points in paths.items():
        samples,blockers = 0,[]
        for a,b in zip(points,points[1:]):
            steps = max(1,math.ceil(math.dist(a,b)/8))
            for i in range(steps+1):
                p = tuple(a[j]+(b[j]-a[j])*i/steps for j in range(3))
                hit = bsp.collision(p,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK)
                support = bsp.collision((p[0],p[1],p[2]-2),(-4,-4,-24),(4,4,32),PLAYER_MASK)
                if (hit or not support) and len(blockers)<6:
                    blockers.append(dict(point=p,blocker=hit or "no floor support"))
                samples += 1
        require(not blockers,f"Blocked player route {name}: {blockers}")
        routes.append(dict(name=name,samples=samples,blockers=blockers))
    counts = [sum(e["keys"]["classname"] == "monster_plastic_helicopter" and enabled(e,skill)
                  for e in source) for skill in range(3)]
    require(counts == [3,3,3],f"Need three helicopters on every difficulty: {counts}")
    require(len(starts) == 4,"Need one single player and three co-op starts")
    names = {e["keys"]["targetname"] for e in source if "targetname" in e["keys"]}
    for e in source:
        for key in ("target","deathtarget"):
            if key in e["keys"]:
                require(e["keys"][key] in names,f"Unresolved {key}: {e['keys']}")
    require(bool(bsp.lumps["visibility"]) and bool(bsp.lumps["lighting"]),"BSP lacks VIS or RAD")
    report = dict(passed=not errors,errors=errors,placements=placements,routes=routes,
                  rotor_checks=rotor_checks,supply_bay_cover=bay_cover,monsters_per_skill=counts,
                  map_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                  bsp_sha256=hashlib.sha256(bsp.raw).hexdigest())
    output = ROOT / f"build/maps/{NAME}/verification.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(passed=not errors,errors=errors,placements=len(placements),
                         route_samples=sum(r["samples"] for r in routes),rotor_samples=216*len(helicopters),
                         shielded_start_sightlines=len(bay_cover)),indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify",action="store_true",help="verify compiled BSP without rewriting MAP")
    p.add_argument("--bsp",type=Path,default=ROOT / f"baseq2/maps/{NAME}.bsp")
    args = p.parse_args()
    if args.verify:
        raise SystemExit(verify(args.bsp))
    generate()
