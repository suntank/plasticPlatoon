#!/usr/bin/env python3
"""Generate and independently verify the spider sandbox range.

Geometry uses existing Sandkeep materials without changing their artwork.
Python's standard library is sufficient; verification reads the compiled BSP.
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
SPIDER_MINS = (-32., -32., -24.)
SPIDER_MAXS = (32., 32., 24.)


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

    # Oversized sandbox with an opaque lid: no external skybox is required.
    solid((-1440,-1632,-64),(1440,1632,0),"sand")
    solid((-1440,-1632,512),(1440,1632,544),"wood_end")
    for lo, hi in [((-1440,-1632,0),(-1408,1632,512)),
                   ((1408,-1632,0),(1440,1632,512)),
                   ((-1408,-1632,0),(1408,-1600,512)),
                   ((-1408,1600,0),(1408,1632,512))]:
        solid(lo,hi)
    # Wooden board rails, toy peg posts and warm overhead light strips.
    for x in (-1408,1384):
        solid((x,-1600,176),(x+24,1600,200),"wood_end",True)
        for y in (-1504,-864,-224,416,1056,1536):
            solid((x,y,0),(x+24,y+32,288),"trim",True)
    for y in (-1408,-896,-384,128,640,1152,1472):
        solid((-896,y-12,484),(896,y+12,496),"iron",True)
        solid((-880,y-8,480),(880,y+8,484),"lamp",True)
        for x in (-1056,-352,352,1056):
            entities.append(entity("light",(x,y,376),light=560,_color="1 .94 .80"))

    # A tall, roofless supply bay shields every start and loadout pickup.
    # Two broad side doors open into continuous, full-length flank lanes.
    solid((-544,-1104,0),(544,-1056,208),"plastic_green_smooth")
    solid((-552,-1112,192),(552,-1048,216),"wood_end",True)
    for x in (-544,512):
        for y,Y in ((-1600,-1344),(-1200,-1104)):
            solid((x,y,0),(x+32,Y,208),"plastic_green_smooth")
            solid((x-8,y,192),(x+40,Y,216),"wood_end",True)

    # Tall cover and gaps create broad approaches.
    cover = [((-240,-848,0),(240,-752,160),"plastic_blue_smooth"),
             ((-944,-720,0),(-752,-624,160),"plastic_red"),
             ((752,-560,0),(944,-464,160),"plastic_blue_smooth"),
             ((-960,160,0),(-288,224,192),"wood"),
             ((288,160,0),(960,224,192),"wood"),
             ((-272,544,0),(272,624,160),"plastic_green_smooth"),
             ((-960,944,0),(-784,1040,160),"plastic_blue_smooth"),
             ((784,1168,0),(960,1264,160),"plastic_red"),
             ((-256,1360,0),(256,1424,160),"wood")]
    for lo,hi,texture in cover:
        solid(lo,hi,texture)
        solid((lo[0]-4,lo[1]-4,hi[2]-16),(hi[0]+4,hi[1]+4,hi[2]),"wood_end",True)
    # Low markers frame each spider while leaving space to maneuver.
    for x,y in ((0,-224),(-672,640),(672,1056)):
        for side in (-1,1):
            solid((x+side*176-16,y-48,0),(x+side*176+16,y+48,24),
                  "plastic_green_smooth",True)
        entities.append(entity("monster_spider",(x,y,24),angle=270,
                               deathtarget="spider_down"))
        entities.append(entity("light",(x,y-112,208),light=400,_color=".78 .88 1"))

    for i,(x,y) in enumerate(((0,-1488),(96,-1488),(-96,-1488),(192,-1488))):
        entities.append(entity("info_player_start" if i == 0 else "info_player_coop",
                               (x,y,24),angle=90))
    pickups = [("weapon_rocketlauncher",-192,-1392),
               ("weapon_chaingun",192,-1392),
               ("item_armor_body",0,-1392),
               ("item_health_large",-384,-1392),("item_health_large",384,-1392),
               ("item_health_large",-1184,-64),("ammo_rockets",-1184,48),
               ("ammo_bullets",-1184,160),
               ("item_health_large",1184,544),("ammo_rockets",1184,656),
               ("ammo_bullets",1184,768),
               ("item_health_large",0,1184),("ammo_rockets",112,1184)]
    pickups += [("ammo_rockets",x,y) for x in (-384,-256,-128) for y in (-1264,-1168)]
    pickups += [("ammo_bullets",x,y) for x in (128,256,384) for y in (-1264,-1168)]
    for classname,x,y in pickups:
        entities.append(entity(classname,(x,y,32)))

    # Keep the level running after victory so the spiders can be inspected.
    entities.append(entity("trigger_counter",targetname="spider_down",count=3,
                           spawnflags=1,target="range_complete"))
    entities.append(entity("trigger_relay",targetname="range_complete",target="range_goal",
                           message="SPIDER RANGE CLEAR\\nAll three spiders defeated.\\nConsole: map pp_spider_test to reset."))
    entities.append(entity("target_goal",(0,1504,48),targetname="range_goal"))
    entities.append(entity("target_help",targetname="range_help",spawnflags=1,
                           message="SPIDER TEST\\nThree giant spiders are on the range.\\nThey close in and bite at melee range.\\nCollect weapons and armor in this bay.\\nUse the cover and lanes to maneuver."))
    entities.append(entity("trigger_always",target="range_help",delay=1))
    entities.append(entity("info_player_intermission",(1200,-816,304),angles="14 130 0"))

    header = ('// Spider test range. Original geometry; existing Sandkeep materials.\n'
              '// Generated by tools/maps/generate_spider_test.py; directly editable.\n'
              '{\n"classname" "worldspawn"\n"message" "Spider Test Range"\n"sounds" "0"\n')
    path = ROOT / "maps/source/pp_spider_test.map"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(header + "".join(world) + "}\n" + "".join(entities))
    print(f"Wrote {path} ({len(world)} brushes; {len(entities)} entities)")



def verify(path):
    """Verify the compiled map's placements, target wiring and supported routes."""
    from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MAXS,
                                 PLAYER_MINS, enabled, parse_entities, vec)
    bsp = BSP(path)
    source_path = ROOT / "maps/source/pp_spider_test.map"
    source = parse_entities(source_path.read_text())
    errors, placements, routes = [], [], []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def logic(entities):
        return Counter(tuple(sorted((k, v) for k, v in e["keys"].items() if k != "model"))
                       for e in entities if e["keys"]["classname"] != "light")

    require(logic(source) == logic(bsp.entities), "Source/BSP gameplay entity mismatch")
    starts = []
    for e in bsp.entities:
        k, c = e["keys"], e["keys"]["classname"]
        if c == "monster_spider":
            mins, maxs, mask = SPIDER_MINS, SPIDER_MAXS, MONSTER_MASK
        elif c in ("info_player_start", "info_player_coop"):
            mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
            starts.append(e)
        elif c.startswith(("weapon_", "ammo_", "item_")):
            mins, maxs, mask = (-15.,) * 3, (15.,) * 3, PLAYER_MASK
        else:
            continue
        p = vec(k["origin"])
        hit = bsp.collision(p, mins, maxs, mask)
        require(not hit, f"{c} at {p} collides with {hit}")
        placements.append(dict(classname=c, origin=p, collision=hit))

    # Use the spider hull on its approaches as well as the player's routes.
    intended_routes = {
        "west_flank": [(0,-1488,24),(-352,-1488,24),(-352,-1272,24),
                       (-1184,-1272,24),(-1184,1488,24),(-400,1488,24)],
        "east_flank": [(0,-1488,24),(352,-1488,24),(352,-1272,24),
                       (1184,-1272,24),(1184,1488,24),(400,1488,24)],
        "central_approach": [(-1184,-1272,24),(-1184,-944,24),(-480,-944,24),
                             (-480,-432,24),(0,-432,24),(0,352,24),
                             (-416,352,24),(-416,1216,24),(0,1216,24)],
        "west_spider_lane": [(-672,640,24),(-672,480,24),(-1184,480,24),(-1184,-896,24)],
        "east_spider_lane": [(672,1056,24),(672,896,24),(1184,896,24),(1184,-896,24)],
        "center_spider_advance": [(0,-224,24),(0,-576,24),(-480,-576,24),(-480,-896,24)],
    }
    for name, points in intended_routes.items():
        spider = "spider_" in name
        mins, maxs, mask = (SPIDER_MINS, SPIDER_MAXS, MONSTER_MASK) if spider else (PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        samples, blockers = 0, []
        for a, b in zip(points, points[1:]):
            steps = max(1, math.ceil(math.dist(a, b) / 8))
            for i in range(steps + 1):
                p = tuple(a[j] + (b[j] - a[j]) * i / steps for j in range(3))
                hit = bsp.collision(p, mins, maxs, mask)
                support = bsp.collision((p[0], p[1], p[2] - 2), (-4,-4,-24), (4,4,32), PLAYER_MASK)
                if (hit or not support) and len(blockers) < 6:
                    blockers.append(dict(point=p, blocker=hit or "no floor support"))
                samples += 1
        require(not blockers, f"Route {name}: {blockers}")
        routes.append(dict(name=name, hull="spider" if spider else "player", samples=samples, blockers=blockers))

    counts = [sum(e["keys"]["classname"] == "monster_spider" and enabled(e, skill)
                  for e in source) for skill in range(3)]
    require(counts == [3, 3, 3], f"Need three spiders on every difficulty: {counts}")
    require(len(starts) == 4, f"Need single-player and three co-op starts: {len(starts)}")
    names = {e["keys"]["targetname"] for e in source if "targetname" in e["keys"]}
    for e in source:
        for key in ("target", "deathtarget"):
            if key in e["keys"]:
                require(e["keys"][key] in names, f"Unresolved {key}: {e['keys']}")
    require(bool(bsp.lumps["visibility"]) and bool(bsp.lumps["lighting"]), "BSP lacks VIS or RAD")
    report = dict(passed=not errors, errors=errors, placements=placements, routes=routes,
                  monsters_per_skill=counts,
                  map_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                  bsp_sha256=hashlib.sha256(bsp.raw).hexdigest())
    output = ROOT / "build/maps/pp_spider_test/verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(passed=not errors, errors=errors, placements=len(placements),
                          route_samples=sum(r["samples"] for r in routes)), indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify compiled BSP without regenerating")
    parser.add_argument("--bsp", type=Path, default=ROOT / "baseq2/maps/pp_spider_test.bsp")
    args = parser.parse_args()
    if args.verify:
        raise SystemExit(verify(args.bsp))
    generate()
