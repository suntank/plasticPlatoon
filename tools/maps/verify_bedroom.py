#!/usr/bin/env python3
"""Check Nightlight's compiled hulls, walking routes and objective wiring."""
import json
import math
import argparse
import hashlib
from collections import Counter
from pathlib import Path

from verify_sandkeep import (BSP, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK,
                             MONSTER_MASK, parse_entities, enabled, vec)

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bsp",type=Path,default=ROOT / "build/nightlight-release/maps/pp_bedroom.bsp")
    args = parser.parse_args()
    bsp = BSP(args.bsp)
    source = parse_entities((ROOT / "maps/source/pp_bedroom.map").read_text())
    errors, routes, placements = [], [], []

    def require(ok, text):
        if not ok:
            errors.append(text)

    keys = [e["keys"] for e in source]
    def logic(entities):
        return Counter(tuple(sorted((k,v) for k,v in e["keys"].items()
                                    if k != "model" and not k.startswith("_")))
                       for e in entities if e["keys"]["classname"] != "light")
    require(logic(source) == logic(bsp.entities), "Compiled gameplay entities differ from the current source")
    names = {k["targetname"] for k in keys if "targetname" in k}
    for k in keys:
        require(not k.get("target") or k["target"] in names, f"Unresolved target: {k}")
    require(sum(k["classname"] == "info_player_start" for k in keys) == 1, "Need one SP start")
    require(sum(k["classname"] == "info_player_coop" for k in keys) == 3, "Need three additional co-op starts")
    require(sum(k["classname"] == "key_power_cube" for k in keys) == 1, "Need exactly one power cell")
    require(any(k["classname"] == "trigger_key" and k.get("item") == "key_power_cube"
                and k.get("target") == "radio_online" for k in keys), "Radio must require the cell")
    require(any(k["classname"] == "trigger_multiple" and k.get("target") == "radio_key"
                for k in keys), "Radio must permit retrying without a cell")
    exits = [k for k in keys if k.get("target") == "mission_complete"]
    require(len(exits) == 1 and int(exits[0].get("spawnflags",0)) & 4
            and exits[0].get("targetname") == "radio_online", "Extraction must start disabled until radio activation")
    for skill in range(3):
        for e in source:
            k = e["keys"]
            if k.get("target") or k["classname"].startswith(("info_player", "key_")):
                require(enabled(e,skill), f"Required entity excluded on skill {skill}: {k}")
    for e in bsp.entities:
        k = e["keys"]
        c = k["classname"]
        if c.startswith(("info_player_start", "info_player_coop", "monster_")):
            mins,maxs = PLAYER_MINS,PLAYER_MAXS
            mask = MONSTER_MASK if c.startswith("monster_") else PLAYER_MASK
        elif c.startswith(("key_", "weapon_", "ammo_", "item_")):
            mins,maxs,mask = (-15,)*3,(15,)*3,PLAYER_MASK
        else:
            continue
        p = vec(k["origin"])
        hit = bsp.collision(p,mins,maxs,mask)
        require(not hit,f"{c} at {p} intersects {hit}")
        placements.append(dict(classname=c,point=p,blocker=hit))
    document = json.loads((ROOT / "tools/maps/bedroom_routes.json").read_text())
    for route in document["routes"]:
        previous, samples, blockers = None,0,[]
        opened = route.get("opened_doors", [])
        for a,b in zip(route["points"],route["points"][1:]):
            steps = max(1,math.ceil(math.dist(a,b)/8))
            for i in range(steps+1):
                p = tuple(a[j]+(b[j]-a[j])*i/steps for j in range(3))
                hit = bsp.collision(p,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,opened)
                if hit and previous:
                    for rise in range(1,19):
                        raised = (p[0],p[1],p[2]+rise)
                        if raised[2] > previous[2]+18.03125:
                            break
                        if bsp.collision(raised,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,opened):
                            continue
                        # Verify the up-and-over sweep as well as its endpoint.
                        up = (previous[0],previous[1],max(previous[2],raised[2]))
                        sweep = [tuple(previous[j]+(up[j]-previous[j])*t/4 for j in range(3)) for t in range(1,5)]
                        sweep += [tuple(up[j]+(raised[j]-up[j])*t/4 for j in range(3)) for t in range(1,5)]
                        if any(bsp.collision(q,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,opened) for q in sweep):
                            continue
                        p,hit = raised,None
                        break
                support = any(bsp.collision((p[0],p[1],p[2]-dz),(-4,-4,-24),(4,4,32),PLAYER_MASK,opened)
                              for dz in (2,8,16,24))
                if (hit or not support) and len(blockers)<6:
                    blockers.append(dict(point=p,blocker=hit or "unsupported"))
                if not hit:
                    previous = p
                samples += 1
        require(not blockers,f"Route {route['name']}: {blockers}")
        routes.append(dict(name=route["name"],samples=samples,blockers=blockers))
    # Check the actual moving gate blocks standing players before activation.
    require(bool(bsp.collision((2032,764,728),PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK)), "Radio bridge gate is bypassable at its center")
    require(not bsp.collision((2032,764,728),PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,["radio_online"]), "Radio bridge gate does not clear")
    require(bool(bsp.lumps["visibility"]) and bool(bsp.lumps["lighting"]), "Release requires VIS and lightmaps")
    report = dict(passed=not errors,errors=errors,placements=placements,routes=routes,
                  map_sha256=hashlib.sha256((ROOT/"maps/source/pp_bedroom.map").read_bytes()).hexdigest(),
                  bsp_sha256=hashlib.sha256(bsp.raw).hexdigest(),
                  monsters_by_skill={s:sum(e["keys"]["classname"].startswith("monster_") and enabled(e,s)
                                           for e in source) for s in range(3)})
    path = ROOT / "build/maps/pp_bedroom/verification.json"
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(passed=not errors,errors=errors,placements=len(placements),routes=len(routes)),indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
