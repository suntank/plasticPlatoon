#!/usr/bin/env python3
"""Generate the small, directly editable rocket soldier test range.

Uses existing Sandkeep materials; does not regenerate or change their artwork.
No third-party Python packages or other map generators are required.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DETAIL = 0x08000000


def box(lo, hi, texture="wood", *, detail=False):
    x, y, z = lo
    X, Y, Z = hi
    assert x < X and y < Y and z < Z
    planes = [((x,y,z),(x,Y,Z),(x,y,Z)),
              ((X,y,z),(X,Y,Z),(X,Y,z)),
              ((x,y,z),(X,y,Z),(X,y,z)),
              ((x,Y,z),(X,Y,Z),(x,Y,Z)),
              ((x,y,z),(X,Y,z),(x,Y,z)),
              ((x,y,Z),(X,Y,Z),(X,y,Z))]
    faces = []
    for plane in planes:
        points = " ".join("( " + " ".join(f"{v:g}" for v in p) + " )" for p in plane)
        faces.append(f"{points} sandkeep/{texture} 0 0 0 1 1 {DETAIL if detail else 0} 0 0\n")
    return "{\n" + "".join(faces) + "}\n"


def entity(classname, origin=None, **keys):
    props = {"classname": classname}
    if origin is not None:
        props["origin"] = " ".join(f"{v:g}" for v in origin)
    props.update({key: str(value) for key, value in keys.items()})
    return "{\n" + "".join(f'"{key}" "{value}"\n' for key, value in props.items()) + "}\n"


def generate():
    world, entities = [], []
    def solid(lo, hi, texture="wood", detail=False):
        world.append(box(lo, hi, texture, detail=detail))

    # A sealed, brightly lit toy sandbox. An opaque lid avoids sky dependencies.
    solid((-992,-1184,-64),(992,1184,0),"sand")
    solid((-992,-1184,448),(992,1184,480),"wood_end")
    for lo, hi in [((-992,-1184,0),(-960,1184,448)),
                   ((960,-1184,0),(992,1184,448)),
                   ((-960,-1184,0),(960,-1152,448)),
                   ((-960,1152,0),(960,1184,448))]:
        solid(lo, hi)
    # Board rails, toy posts and overhead light bars establish scale.
    for x in (-960,936):
        solid((x,-1152,144),(x+24,1152,168),"wood_end",True)
        for y in (-1056,-512,32,576,1088):
            solid((x,y,0),(x+24,y+24,240),"trim",True)
    for y in (-992,-480,64,576,1024):
        solid((-512,y-12,420),(512,y+12,432),"iron",True)
        solid((-496,y-8,416),(496,y+8,420),"lamp",True)
        for x in (-560,0,560):
            entities.append(entity("light",(x,y,336),light=480,_color="1 .94 .79"))

    # Protected loadout bay; both side exits lead to broad, continuous flanks.
    solid((-448,-816,0),(448,-784,128),"plastic_green_smooth")
    solid((-464,-824,120),(464,-776,144),"wood_end",True)
    for x in (-448,416):
        for y,Y in ((-1152,-1008),(-864,-816)):
            solid((x,y,0),(x+32,Y,112),"plastic_green_smooth")
        solid((x,-1008,96),(x+32,-864,112),"wood_end")
    # Several independent pieces of cover allow peeking, withdrawal and flanks.
    for lo,hi,texture in [((-624,-560,0),(-368,-496,80),"plastic_blue_smooth"),
                          ((240,-464,0),(496,-400,80),"plastic_red"),
                          ((-720,176,0),(-192,224,144),"wood"),
                          ((192,176,0),(720,224,144),"wood"),
                          ((-624,352,0),(-400,416,80),"plastic_blue_smooth"),
                          ((336,512,0),(592,576,80),"plastic_red"),
                          ((-144,672,0),(144,736,96),"plastic_green_smooth")]:
        solid(lo,hi,texture)
        solid((lo[0]-4,lo[1]-4,hi[2]-8),(hi[0]+4,hi[1]+4,hi[2]),"wood_end",True)
    # Low side markers leave every rocket's southern firing sector unobstructed.
    for x,y in ((0,-96),(-480,560),(480,864)):
        for side in (-1,1):
            solid((x+side*112-16,y-64,0),(x+side*112+16,y+48,40),"plastic_green_smooth",True)
        entities.append(entity("monster_soldier_rocket",(x,y,24),angle=270,
                               spawnflags=1,deathtarget="rocket_down"))
        entities.append(entity("light",(x,y-96,128),light=320,_color=".80 .90 1"))
    entities.append(entity("light",(0,-992,128),light=320,_color=".80 .90 1"))

    starts = [(0,-1088),(96,-1088),(-96,-1088),(192,-1088)]
    for i,(x,y) in enumerate(starts):
        entities.append(entity("info_player_start" if i == 0 else "info_player_coop",
                               (x,y,24),angle=90))
    pickups = [("weapon_rocketlauncher",0,-992),
               ("weapon_shotgun",-224,-992),("ammo_shells",-224,-912),
               ("item_armor_jacket",224,-992),("item_health_large",224,-912),
               ("item_health_large",-800,-80),("item_health_large",800,400),
               ("ammo_rockets",-800,16),("ammo_rockets",800,496)]
    pickups += [("ammo_rockets",x,y) for x in (-112,0,112) for y in (-912,-960)]
    for classname,x,y in pickups:
        entities.append(entity(classname,(x,y,32)))

    # Count kills without ending the map, so corpses and positions can be checked.
    entities.append(entity("trigger_counter",targetname="rocket_down",count=3,
                           spawnflags=1,target="range_complete"))
    entities.append(entity("trigger_relay",targetname="range_complete",target="range_goal",
                           message="RANGE CLEAR\\nAll three rocket soldiers defeated.\\nConsole: map pp_rocket_test to reset."))
    entities.append(entity("target_goal",(0,1056,48),targetname="range_goal"))
    entities.append(entity("target_help",targetname="range_help",spawnflags=1,
                           message="ROCKET SOLDIER TEST\\nThree rocket soldiers must squat before firing.\\nUse tall cover and either side lane to flank.\\nThe starting bay has a rocket launcher, armor, ammunition and health."))
    entities.append(entity("trigger_always",target="range_help",delay=1))
    entities.append(entity("info_player_intermission",(784,-640,240),angles="14 118 0"))

    header = ('// Rocket soldier test range. Original geometry; existing Sandkeep materials.\n'
              '// Generated by tools/maps/generate_rocket_test.py; directly editable.\n'
              '{\n"classname" "worldspawn"\n"message" "Rocket Soldier Test Range"\n"sounds" "0"\n')
    path = ROOT / "maps/source/pp_rocket_test.map"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(header + "".join(world) + "}\n" + "".join(entities))
    print(f"Wrote {path} ({len(world)} brushes; {len(entities)} entities)")


def verify(path):
    """Check the actual compiled hulls, routes and gameplay entity agreement."""
    from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MAXS,
                                 PLAYER_MINS, enabled, parse_entities, vec)
    bsp = BSP(path)
    source = parse_entities((ROOT / "maps/source/pp_rocket_test.map").read_text())
    errors, placements, routes = [], [], []
    def require(condition, message):
        if not condition:
            errors.append(message)
    def logic(entities):
        return Counter(tuple(sorted((k,v) for k,v in e["keys"].items() if k != "model"))
                       for e in entities if e["keys"]["classname"] != "light")
    require(logic(source) == logic(bsp.entities), "Source/BSP gameplay entity mismatch")
    for e in bsp.entities:
        k = e["keys"]
        c = k["classname"]
        if c.startswith(("info_player_start", "info_player_coop", "monster_")):
            mins, maxs = PLAYER_MINS, PLAYER_MAXS
            mask = MONSTER_MASK if c.startswith("monster_") else PLAYER_MASK
        elif c.startswith(("weapon_", "ammo_", "item_")):
            mins, maxs, mask = (-15,)*3, (15,)*3, PLAYER_MASK
        else:
            continue
        p = vec(k["origin"])
        hit = bsp.collision(p, mins, maxs, mask)
        require(not hit, f"{c} at {p} collides with {hit}")
        placements.append(dict(classname=c, origin=p, collision=hit))
    intended_routes = {
        "west_flank": [(0,-1088,24),(-256,-1088,24),(-256,-944,24),
                       (-800,-944,24),(-800,1008,24),(0,1008,24)],
        "east_flank": [(0,-1088,24),(256,-1088,24),(256,-944,24),
                       (800,-944,24),(800,1008,24),(0,1008,24)],
        "central_approach": [(-800,-944,24),(-800,-672,24),(0,-672,24),
                             (0,-96,24),(0,512,24),(224,512,24),(224,864,24),(0,864,24)],
        "west_gunner": [(-800,656,24),(-480,656,24),(-480,560,24)],
        "east_gunner": [(800,960,24),(480,960,24),(480,864,24)],
    }
    for name, points in intended_routes.items():
        samples, blockers = 0, []
        for a,b in zip(points, points[1:]):
            steps = max(1, math.ceil(math.dist(a,b)/8))
            for i in range(steps+1):
                p = tuple(a[j]+(b[j]-a[j])*i/steps for j in range(3))
                hit = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
                support = bsp.collision((p[0],p[1],p[2]-2),(-4,-4,-24),(4,4,32),PLAYER_MASK)
                if (hit or not support) and len(blockers) < 6:
                    blockers.append(dict(point=p, blocker=hit or "no floor support"))
                samples += 1
        require(not blockers, f"Route {name}: {blockers}")
        routes.append(dict(name=name, samples=samples, blockers=blockers))
    counts = [sum(e["keys"]["classname"] == "monster_soldier_rocket" and enabled(e,skill)
                  for e in source) for skill in range(3)]
    require(counts == [3,3,3], f"Need three rocket soldiers on every difficulty: {counts}")
    names = {e["keys"]["targetname"] for e in source if "targetname" in e["keys"]}
    for e in source:
        for key in ("target", "deathtarget"):
            if key in e["keys"]:
                require(e["keys"][key] in names, f"Unresolved {key}: {e['keys']}")
    require(bool(bsp.lumps["visibility"]) and bool(bsp.lumps["lighting"]), "BSP lacks VIS or RAD")
    report = dict(passed=not errors, errors=errors, placements=placements,
                  routes=routes, monsters_per_skill=counts,
                  map_sha256=hashlib.sha256((ROOT / "maps/source/pp_rocket_test.map").read_bytes()).hexdigest(),
                  bsp_sha256=hashlib.sha256(bsp.raw).hexdigest())
    output = ROOT / "build/maps/pp_rocket_test/verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(passed=not errors, errors=errors, placements=len(placements),
                         route_samples=sum(r["samples"] for r in routes)),indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify the compiled BSP without regenerating")
    parser.add_argument("--bsp", type=Path, default=ROOT / "baseq2/maps/pp_rocket_test.bsp")
    args = parser.parse_args()
    if args.verify:
        raise SystemExit(verify(args.bsp))
    generate()
