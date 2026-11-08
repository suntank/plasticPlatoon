#!/usr/bin/env python3
"""Verify Sandbreak's compiled collision, roster and co-op objective wiring.

Reads the MAP and IBSP38 independently of the generator. Route waypoints are
player origins and use {"routes": [{"name": ..., "points": [[x,y,z], ...],
"opened_doors": [...], "allow_water": false}]}. Water routes still require
clearance; only their underwater samples may omit floor support. This is a
static geometry/logic check, not a human combat or multiplayer playthrough.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path

from verify_sandkeep import (BSP, EPSILON, MONSTER_MASK, PLAYER_MASK,
                            PLAYER_MAXS, PLAYER_MINS, enabled, flags, label,
                            parse_entities, vec)

ROOT = Path(__file__).resolve().parents[2]
NAME = "pp_sandbreak"
SOLDIERS = ("monster_soldier_light", "monster_soldier", "monster_soldier_ss",
            "monster_soldier_heavy", "monster_soldier_rocket")
VEHICLES = ("monster_plastic_tank", "monster_plastic_helicopter")
WEAPONS = ("weapon_shotgun", "weapon_supershotgun", "weapon_machinegun",
           "weapon_chaingun", "ammo_grenades", "weapon_grenadelauncher",
           "weapon_rocketlauncher", "weapon_hyperblaster", "weapon_railgun",
           "weapon_bfg")
AMMO = ("ammo_shells", "ammo_bullets", "ammo_grenades", "ammo_gl_rounds",
        "ammo_rockets", "ammo_cells", "ammo_slugs")
GATES = ("assault_gate", "air_gate", "extraction_gate")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(source_path, bsp_path, routes_path, output):
    errors = []
    report = {"passed": False, "errors": errors,
              "scope": "Static compiled geometry and entity logic; no combat playthrough"}

    def require(condition, message):
        if not condition:
            errors.append(message)
        return bool(condition)

    try:
        source = parse_entities(source_path.read_text())
        bsp = BSP(bsp_path)
        report.update(map_sha256=sha(source_path), bsp_sha256=sha(bsp_path),
                      routes_sha256=sha(routes_path), verifier_sha256=sha(__file__))
        by_name = defaultdict(list)
        for e in source:
            if e["keys"].get("targetname"):
                by_name[e["keys"]["targetname"]].append(e)

        def reachable(start, key="target", skill=None):
            pending = deque(by_name.get(start["keys"].get(key), ()))
            seen, found = set(), []
            while pending:
                e = pending.popleft()
                if e["index"] in seen or (skill is not None and not enabled(e, skill)):
                    continue
                seen.add(e["index"])
                found.append(e)
                pending.extend(by_name.get(e["keys"].get("target"), ()))
            return found

        def logic(entities):
            return Counter(tuple(sorted((k, v) for k, v in e["keys"].items()
                                        if k != "model" and not k.startswith("_")))
                           for e in entities if e["keys"].get("classname") not in
                           ("worldspawn", "light", "info_null", "func_group"))

        require(logic(source) == logic(bsp.entities), "Compiled gameplay entities differ from MAP")
        require(bool(bsp.lumps["visibility"]), "BSP has no full visibility data")
        require(bool(bsp.lumps["lighting"]), "BSP has no baked lighting")
        report["bsp"] = {"bytes": len(bsp.raw), "vis_bytes": len(bsp.lumps["visibility"]),
                         "lighting_bytes": len(bsp.lumps["lighting"]),
                         "world_brushes": len(bsp.model_brushes[0])}

        for e in source:
            k = e["keys"]
            for key in ("target", "deathtarget", "killtarget", "pathtarget", "combattarget"):
                if k.get(key) and not (key == "target" and k.get("classname") == "target_spawner"):
                    require(k[key] in by_name, f"{label(e)} unresolved {key}={k[key]}")
            require(not flags(e) & 4096, f"{label(e)} has a co-op exclusion flag")

        starts = [e for e in source if e["keys"].get("classname") in
                  ("info_player_start", "info_player_coop")]
        require(sum(e["keys"]["classname"] == "info_player_start" for e in starts) == 1,
                "Need exactly one main start")
        require(sum(e["keys"]["classname"] == "info_player_coop" for e in starts) >= 3,
                "Need at least three co-op starts")
        for e in starts:
            require(not e["keys"].get("targetname"), f"{label(e)} must be unnamed for direct launch")

        counts = []
        for skill in range(3):
            count = Counter(e["keys"].get("classname") for e in source if enabled(e, skill))
            counts.append(dict(sorted(count.items())))
            for classname in (*SOLDIERS, *WEAPONS, *AMMO):
                require(count[classname] > 0, f"Missing {classname} on skill {skill}")
            for classname in VEHICLES:
                require(count[classname] == 1, f"Need one {classname} on skill {skill}, got {count[classname]}")
            require(count["info_player_start"] == 1 and count["info_player_coop"] >= 3,
                    f"Player starts missing on skill {skill}")
        require(not any(e["keys"].get("classname") in ("weapon_blaster", "ammo_mortar_rounds")
                        for e in source), "Pistol is default and mortar rounds have no pickup model")
        report["entities_per_skill"] = counts
        report["weapons"] = {"default": "Pistol", "placed": list(WEAPONS), "total": 11}

        doors = {}
        for name in GATES:
            matches = [e for e in by_name[name] if e["keys"].get("classname") == "func_door"]
            if require(len(matches) == 1, f"Need exactly one func_door named {name}"):
                doors[name] = matches[0]
                require(float(matches[0]["keys"].get("wait", "3")) < 0,
                        f"{name} must stay open for respawning teammates")
                require(not flags(matches[0]) & 1, f"{name} must start closed")
                for skill in range(3):
                    require(enabled(matches[0], skill), f"{name} absent on skill {skill}")

        counters = [e for e in source if e["keys"].get("classname") == "trigger_counter"
                    and doors.get("assault_gate") in reachable(e)]
        if require(len(counters) == 1, "Need one counter controlling the assault gate"):
            counter = counters[0]
            require(int(counter["keys"].get("count", "2")) == 2, "Assault counter must require two inputs")
            buttons = [e for e in source if e["keys"].get("classname") == "func_button"
                       and counter in reachable(e)]
            require(len(buttons) == 2, "Assault counter needs exactly two independent buttons")
            for button in buttons:
                require(float(button["keys"].get("wait", "3")) < 0,
                        f"{label(button)} must be one-shot so one button cannot satisfy both inputs")
                require(not button["keys"].get("targetname") or float(button["keys"].get("health", "0")) > 0,
                        f"{label(button)} has neither touch nor shoot activation")
                for skill in range(3):
                    require(enabled(button, skill) and counter in reachable(button, skill=skill),
                            f"{label(button)} counter chain fails on skill {skill}")
            for skill in range(3):
                require(enabled(counter, skill) and doors.get("assault_gate") in reachable(counter, skill=skill),
                        f"Assault counter gate chain fails on skill {skill}")

        for classname, deathname, doorname in zip(VEHICLES, ("armor_down", "air_down"),
                                                  ("air_gate", "extraction_gate")):
            for e in source:
                if e["keys"].get("classname") != classname:
                    continue
                require(e["keys"].get("deathtarget") == deathname,
                        f"{classname} must fire deathtarget {deathname}")
                for skill in range(3):
                    require(doors.get(doorname) in reachable(e, "deathtarget", skill),
                            f"{classname} cannot open {doorname} on skill {skill}")

        exits = [e for e in source if e["keys"].get("classname") == "target_changelevel"]
        require(len(exits) == 1, "Need exactly one level-completion destination")
        for e in exits:
            require(e["keys"].get("map") == "pp_sandbreak_end", "Completion must enter pp_sandbreak_end")
        triggers = [e for e in source if e["keys"].get("classname") == "trigger_once"
                    and e["keys"].get("target") == "mission_complete"]
        require(len(triggers) == 1, "Need one physical mission_complete trigger")
        for trigger in triggers:
            for skill in range(3):
                chain = reachable(trigger, skill=skill)
                require(enabled(trigger, skill) and any(e["keys"].get("classname") == "target_goal" for e in chain)
                        and all(e in chain for e in exits), f"Final objective chain fails on skill {skill}")
        report["objective_gates"] = sorted(doors)

        placements, actors, rotors = [], [], []
        for e in bsp.entities:
            k, classname = e["keys"], e["keys"].get("classname", "")
            if classname in SOLDIERS:
                mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK
            elif classname == VEHICLES[0]:
                mins, maxs, mask = (-56, -42, -24), (56, 42, 48), MONSTER_MASK
            elif classname == VEHICLES[1]:
                mins, maxs, mask = (-72, -56, -32), (72, 56, 48), MONSTER_MASK
            elif classname in ("info_player_start", "info_player_coop"):
                mins, maxs, mask = PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
            elif classname.startswith(("weapon_", "item_", "ammo_")):
                mins, maxs, mask = (-15,) * 3, (15,) * 3, PLAYER_MASK
            else:
                continue
            p = vec(k["origin"])
            hit = bsp.collision(p, mins, maxs, mask)
            require(not hit, f"{label(e)} starts inside {hit}")
            placements.append({"entity": label(e), "origin": p, "blocker": hit})
            if classname.startswith("monster_") or classname.startswith("info_player_"):
                actors.append((e, p, mins, maxs))
            if classname == VEHICLES[1]:
                blocked = []
                for angle in range(0, 360, 5):
                    a = math.radians(angle)
                    for radius in (0, 48, 92):
                        point = (p[0] + radius * math.cos(a), p[1] + radius * math.sin(a), p[2] + 48)
                        hit = bsp.collision(point, (-3,) * 3, (3,) * 3, MONSTER_MASK)
                        if hit and len(blocked) < 8:
                            blocked.append({"origin": point, "blocker": hit})
                require(not blocked, f"Helicopter rotor is obstructed: {blocked[:2]}")
                rotors.append({"origin": p, "radius": 92, "samples": 216, "blockers": blocked})
        for i, (e, p, mins, maxs) in enumerate(actors):
            for other, q, qmin, qmax in actors[i + 1:]:
                overlapping = all(p[j] + mins[j] < q[j] + qmax[j] - EPSILON
                                  and q[j] + qmin[j] < p[j] + maxs[j] - EPSILON for j in range(3))
                require(not overlapping, f"Actor hulls overlap: {label(e)} / {label(other)}")
        report["placements"], report["rotor_checks"] = placements, rotors

        # A continuous closed collision sheet prevents walking, swimming and
        # explosive-jump shortcuts around the three staged objective gates.
        barrier_results = []
        for name, y in zip(GATES, (-960, 960, 2720)):
            holes, samples = [], 0
            for x in range(-1184, 1185, 32):
                for z in range(24, 993, 32):
                    samples += 1
                    p = (x, y, z)
                    if not bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK) and len(holes) < 8:
                        holes.append(p)
            require(not holes, f"Closed {name} has a player-sized bypass: {holes}")
            open_blockers = []
            for x in (-112, 0, 112):
                hit = bsp.collision((x, y, 24), PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, (name,))
                if hit:
                    open_blockers.append({"origin": (x, y, 24), "blocker": hit})
            require(not open_blockers, f"Opened {name} blocks its aperture: {open_blockers}")
            barrier_results.append({"gate": name, "closed_samples": samples, "holes": holes,
                                    "opened_aperture_blockers": open_blockers})
        report["gate_barriers"] = barrier_results

        sightlines = []
        for enemy, p, _, _ in actors:
            if not enemy["keys"]["classname"].startswith("monster_"):
                continue
            muzzle = (p[0], p[1], p[2] + 25)
            for start in starts:
                q = vec(start["keys"]["origin"])
                eye = (q[0], q[1], q[2] + 22)
                blocked = bool(bsp.segment_hits(muzzle, eye))
                require(blocked, f"Initial enemy {label(enemy)} can see protected start {q}")
                sightlines.append({"enemy": label(enemy), "start": q, "blocked": blocked})
        report["protected_start_sightlines"] = sightlines

        route_doc = json.loads(routes_path.read_text())
        routes = route_doc["routes"] if isinstance(route_doc, dict) else route_doc
        routes = list(routes)
        # Independent probes supplement the designer's main route waypoints.
        routes.append({"name": "independent_east_tower_ramp", "points":
                       [(680, -2240, 24), (680, -2200, 24), (680, -1680, 172),
                        (680, -1640, 152), (680, -1450, 152)]})
        # Approach the south stairs from their east side: the shelter's north
        # wall deliberately blocks a straight approach from y=-464.
        water_path = [(-720, -416, 24), (-784, -416, 24), (-832, -416, 40), (-896, -416, 40)]
        for y, z in ((-384, 56), (-352, 72), (-320, 88),
                     (-288, 72), (-256, 56), (-224, 40), (-192, 24), (0, 24),
                     (192, 24), (224, 40), (256, 56), (288, 72), (320, 88),
                     (352, 72), (384, 56), (416, 40), (448, 24), (464, 24)):
            water_path.append((-896, y, z))
        routes.extend(({"name": "independent_water_south_to_north", "points": water_path,
                        "allow_water": True},
                       {"name": "independent_water_north_to_south", "points": list(reversed(water_path)),
                        "allow_water": True}))
        for y in (-600, 1240, 2040):
            for side, x0, x1 in (("west", -1160, -600), ("east", 600, 1160)):
                routes.append({"name": f"independent_{side}_shelter_{y}",
                               "points": [(x0, y, 24), (x1, y, 24)]})
        require(bool(routes), "Need independently sampled player routes")
        route_results = []
        for route in routes:
            points, opened = route["points"], set(route.get("opened_doors", ()))
            if route.get("hull") == "tank":
                route_mins, route_maxs, route_mask = (-56, -42, -24), (56, 42, 48), MONSTER_MASK
            else:
                route_mins, route_maxs, route_mask = PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
            require(opened <= set(doors), f"Route {route['name']} names unknown open doors")
            require(len(points) >= 2 and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in points),
                    f"Route {route['name']} requires at least two finite 3D points")
            samples, blockers, unsupported, adjustments, water_samples = 0, [], [], 0, 0
            previous = None
            for start, end in zip(points, points[1:]):
                steps = max(1, math.ceil(math.dist(start, end) / 8))
                for i in range(steps + 1):
                    p = tuple(start[j] + (end[j] - start[j]) * i / steps for j in range(3))
                    samples += 1
                    hit = bsp.collision(p, route_mins, route_maxs, route_mask, opened)
                    if hit and previous is not None:
                        for rise in range(1, 19):
                            raised = (p[0], p[1], p[2] + rise)
                            if raised[2] > previous[2] + 18 + EPSILON:
                                break
                            if bsp.collision(raised, route_mins, route_maxs, route_mask, opened):
                                continue
                            up = (previous[0], previous[1], max(previous[2], raised[2]))
                            trajectory = [tuple(previous[j] + (up[j] - previous[j]) * t / 4 for j in range(3))
                                          for t in range(1, 5)]
                            trajectory += [tuple(up[j] + (raised[j] - up[j]) * t / 4 for j in range(3))
                                           for t in range(1, 5)]
                            if any(bsp.collision(v, route_mins, route_maxs, route_mask, opened)
                                   for v in trajectory):
                                continue
                            p, hit = raised, None
                            adjustments += 1
                            break
                    if hit:
                        if len(blockers) < 8:
                            blockers.append({"origin": p, "blocker": hit})
                        continue
                    previous = p
                    in_water = bool(bsp.point_contents((p[0], p[1], p[2] - 23)) & 32)
                    water_samples += int(in_water)
                    support = any(bsp.collision((p[0], p[1], p[2] - dz), (-4, -4, -24),
                                                (4, 4, 32), route_mask, opened) for dz in (2, 8, 16, 24))
                    if not support and not (route.get("allow_water", False) and in_water) and len(unsupported) < 8:
                        unsupported.append(p)
            require(not blockers, f"Route {route['name']} blocked: {blockers[:2]}")
            require(not unsupported, f"Route {route['name']} lacks floor support: {unsupported[:2]}")
            route_results.append({"name": route["name"], "samples": samples, "opened_doors": sorted(opened),
                                  "blockers": blockers, "unsupported": unsupported,
                                  "step_adjustments": adjustments, "water_samples": water_samples,
                                  "clear": not blockers and not unsupported})
        report["routes"] = route_results
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        errors.append(f"Verification could not complete: {exc}")
    report["passed"] = not errors
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "errors": errors,
                      "placements": len(report.get("placements", [])),
                      "route_samples": sum(r["samples"] for r in report.get("routes", [])),
                      "report": str(output)}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / f"maps/source/{NAME}.map")
    parser.add_argument("--bsp", type=Path, default=ROOT / f"baseq2/maps/{NAME}.bsp")
    parser.add_argument("--routes", type=Path, default=ROOT / f"build/maps/{NAME}/routes.json")
    parser.add_argument("--output", type=Path, default=ROOT / f"build/maps/{NAME}/verification.json")
    args = parser.parse_args()
    raise SystemExit(verify(args.source, args.bsp, args.routes, args.output))
