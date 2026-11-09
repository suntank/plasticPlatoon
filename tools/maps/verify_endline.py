#!/usr/bin/env python3
"""Independently verify End of the Line's entities and compiled collision.

This does not import the level generator. Route points are standing player
origins. A route may name ``opened_doors`` and ``train_at`` (a mapping from
func_train targetname to a path_corner targetname) to describe the real mission
state being tested. Static validation does not replace an in-game playthrough.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path

from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MAXS,
                            PLAYER_MINS, SOLID, enabled, entity_bounds,
                            parse_entities, vec)

ROOT = Path(__file__).resolve().parents[2]
DIFFICULTY_FLAGS = 256 | 512 | 1024
MATERIAL_FAMILIES = {"endline", "sandbox", "bedroom", "sandkeep", "common"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(args):
    source = parse_entities(args.map.read_text())
    keys = [e["keys"] for e in source]
    errors, warnings = [], []
    report = {"map_sha256": sha(args.map)}

    def require(ok, message):
        if not ok:
            errors.append(message)
        return ok

    named = defaultdict(list)
    for entity in source:
        k = entity["keys"]
        if k.get("targetname"):
            named[k["targetname"]].append(entity)
        for field in ("origin", "angles"):
            if field in k:
                vec(k[field])

    def chain(name, skill):
        pending, seen, found = deque([name]), set(), []
        while pending:
            next_name = pending.popleft()
            if next_name in seen:
                continue
            seen.add(next_name)
            for e in named.get(next_name, ()):
                if not enabled(e, skill):
                    continue
                found.append(e["keys"])
                for field in ("target", "deathtarget", "pathtarget"):
                    if e["keys"].get(field) and e["keys"]["classname"] != "target_spawner":
                        pending.append(e["keys"][field])
        return found

    for k in keys:
        for field in ("target", "deathtarget", "killtarget", "pathtarget", "combattarget"):
            if k.get(field) and not (field == "target" and k["classname"] == "target_spawner"):
                require(k[field] in named,
                        f"Unresolved {field}={k[field]} on {k['classname']} {k.get('origin', '')}")
        # Skill-specific kill counters are allowed, but objective controls,
        # navigation, supplies and extraction must exist on every difficulty.
        if not k["classname"].startswith("monster_") and k["classname"] != "trigger_counter":
            require(not int(k.get("spawnflags", 0)) & DIFFICULTY_FLAGS,
                    f"Non-encounter entity is difficulty filtered: {k['classname']} {k.get('targetname', '')}")

    for classname, count in (("info_player_start", 1), ("info_player_coop", 3)):
        require(sum(k["classname"] == classname for k in keys) == count,
                f"Need exactly {count} {classname} entities")
    starts = [vec(k["origin"]) for k in keys if k["classname"] in
              ("info_player_start", "info_player_coop")]
    for i, a in enumerate(starts):
        for b in starts[i + 1:]:
            require(math.dist(a, b) >= 40, f"Overlapping player starts: {a}, {b}")
    weapons = [k for k in keys if k["classname"] == "weapon_supershotgun"]
    require(bool(weapons), "Missing double-barrel shotgun introduction")
    for weapon in weapons:
        p = vec(weapon["origin"])
        require(any(k["classname"] == "ammo_shells" and math.dist(p, vec(k["origin"])) <= 192
                    for k in keys), f"Double-barrel introduction at {p} has no nearby shells")
    require(sum(k["classname"] == "target_secret" for k in keys) == 3,
            "The brief requires three discoverable secrets")

    materials = sorted({t for e in source for t in e["textures"]})
    for material in materials:
        require(material.split("/", 1)[0] in MATERIAL_FAMILIES,
                f"Material is outside original Plastic Platoon families: {material}")
        require((ROOT / "baseq2/textures" / (material + ".wal")).is_file(),
                f"Missing compiler material: {material}.wal")
    require(any(m.startswith("endline/") for m in materials), "No original railway materials used")
    require(any(m.startswith(("sandbox/", "bedroom/", "sandkeep/")) for m in materials),
            "No existing Plastic Platoon materials reused")
    report["materials"] = materials

    extraction = [k for k in keys if k["classname"] == "trigger_platoon_extract"]
    require(len(extraction) == 1, "Need one all-living-player extraction volume")
    for k in extraction:
        require(bool(int(k.get("spawnflags", 0)) & 4) and bool(k.get("targetname")),
                "Extraction must start disabled until the siding is secure")
        require(bool(k.get("target")), "Extraction must activate departure")
    require(any(k["classname"] == "func_train" for k in keys), "Missing physical train")
    require(any(k["classname"] == "func_button" for k in keys), "Missing railway switch/control")
    endings = [k for k in keys if k["classname"] in ("target_platoon_intermission", "target_changelevel")]
    require(bool(endings), "Missing mission completion")
    trains = [k for k in keys if k["classname"] == "func_train" and k.get("targetname") == "endline_train"]
    require(len(trains) == 1, "One persistent endline_train must perform the preview, arrival and escape")
    for train in trains:
        require(int(train.get("spawnflags", 0)) & 2,
                "The train needs TOGGLE to stop at its hold and boarding path corners")
        require(train.get("target") == "endline_intro_start", "The train must begin at the introduction path")
    corners = {k.get("targetname"): k for k in keys if k["classname"] == "path_corner"}
    for corner in corners.values():
        if corner.get("targetname", "").startswith("endline_") and float(corner.get("wait", 0)) < 0:
            require(bool(corner.get("target")) or corner.get("pathtarget") == "endline_complete",
                    f"Stopped railway corner {corner.get('targetname')} has no continuation")
    board_counter = [k for k in keys if k["classname"] == "trigger_counter" and
                     k.get("targetname") == "endline_board_condition"]
    require(len(board_counter) == 1 and int(board_counter[0].get("count", 2)) == 2,
            "Boarding must require both train arrival and a secured siding")
    permission = [k for k in keys if k["classname"] == "trigger_counter" and
                  k.get("targetname") == "endline_depart_permission"]
    require(len(permission) == 1 and int(permission[0].get("count", 2)) == 2 and
            permission[0].get("target") == "endline_extract",
            "Extraction requires both a ready train and a manual departure request")
    permission_sources = {k.get("targetname") for k in keys if k.get("target") == "endline_depart_permission"}
    require(permission_sources == {"endline_board_ready", "depart_arm"},
            "Only ready-state and manual-control relays may satisfy departure permission")
    require(not any(k.get("target") == "endline_extract" and
                    k.get("targetname") != "endline_depart_permission" for k in keys),
            "Extraction has a path that bypasses the ready-state permission counter")
    intro_delays = [k for k in keys if k["classname"] == "trigger_relay" and
                    k.get("targetname") == "endline_intro_done" and k.get("target") == "endline_dispatch"]
    require(len(intro_delays) == 1 and float(intro_delays[0].get("delay", 0)) >= .2,
            "Intro completion must wait for func_train to stop before dispatch can resume it")
    spawn_delays = [float(k.get("delay", 0)) for k in keys if k["classname"] == "trigger_relay" and
                    k.get("targetname") == "endline_divert" and k.get("target") == "endline_wave"]
    door_delays = [float(k.get("delay", 0)) for k in keys if k["classname"] == "trigger_relay" and
                   k.get("targetname") == "endline_divert" and k.get("target") == "endline_reserve_doors"]
    require(spawn_delays and door_delays and min(door_delays) >= max(spawn_delays) + .2,
            "Deployment doors must stay closed until reinforcement spawning has completed")

    difficulties = []
    for skill in range(3):
        live = [e["keys"] for e in source if enabled(e, skill)]
        monsters = [k for k in live if k["classname"].startswith("monster_")]
        counters = []
        for counter in (k for k in live if k["classname"] == "trigger_counter"):
            name = counter.get("targetname")
            sources = [k for k in live if k.get("deathtarget") == name or
                       (k.get("target") == name and k["classname"] != "target_spawner")]
            deaths = [k for k in sources if k["classname"].startswith("monster_") and
                      k.get("deathtarget") == name]
            count = int(counter.get("count", 2))
            require(count > 0 and len(sources) >= count,
                    f"Skill {skill}: counter {name} requires {count} events but has {len(sources)} sources")
            if deaths:
                require(len(deaths) == len(sources) == count,
                        f"Skill {skill}: kill counter {name} has {len(deaths)} enemies but count {count}")
            counters.append({"name": name, "count": count, "sources": len(sources)})
        for k in extraction:
            end_chain = chain(k.get("target"), skill)
            require(any(v["classname"] in ("target_platoon_intermission", "target_changelevel") for v in end_chain),
                    f"Skill {skill}: extraction cannot reach mission completion")
            require(any(v["classname"] == "func_train" for v in end_chain),
                    f"Skill {skill}: extraction does not start the train")
        switch_chain = chain("endline_divert", skill)
        require(any(k["classname"] == "func_train" for k in switch_chain),
                f"Skill {skill}: the railway switch cannot summon the train")
        wave = [k for k in monsters if k.get("targetname") == "endline_wave"]
        require(len(wave) == (6, 9, 12)[skill],
                f"Skill {skill}: counterattack needs {(6, 9, 12)[skill]} enemies, found {len(wave)}")
        require(all(int(k.get("spawnflags", 0)) & 2 and
                    k.get("deathtarget") == "endline_wave_down" for k in wave),
                f"Skill {skill}: each counterattack defender must trigger-spawn and report its death")
        require(all(k in switch_chain for k in wave),
                f"Skill {skill}: switch does not activate every counterattack defender")
        for condition in ("endline_arrived", "endline_secured"):
            condition_chain = chain(condition, skill)
            require(any(k.get("targetname") == "endline_board_condition" for k in condition_chain),
                    f"Skill {skill}: {condition} does not satisfy the boarding gate")
        difficulties.append({"skill": skill, "enemies": len(monsters), "counters": counters})
    counts = [d["enemies"] for d in difficulties]
    require(counts[0] < counts[1] < counts[2],
            f"Enemy populations must increase from easy to normal to hard: {counts}")
    report["difficulty"] = difficulties
    report["supplies"] = dict(sorted(Counter(k["classname"] for k in keys if
                                      k["classname"].startswith(("weapon_", "ammo_", "item_"))).items()))

    if args.static_only:
        report.update(passed=not errors, errors=errors, warnings=warnings,
                      limitations=["Source-only checks; compiled collision, VIS and lighting were not tested."])
        return report

    bsp = BSP(args.bsp)
    report["bsp_sha256"] = sha(args.bsp)

    def normalized(entities):
        return Counter(tuple(sorted((k, v) for k, v in e["keys"].items()
                                    if k != "model" and not k.startswith("_")))
                       for e in entities if e["keys"]["classname"] != "light")

    require(normalized(source) == normalized(bsp.entities), "Compiled entities differ from the MAP source")
    require(bool(bsp.lumps["visibility"]) and bool(bsp.lumps["lighting"]),
            "Release BSP requires visibility and baked lighting")

    # Train models are translated by func_train_find on the first server tick.
    # CM_LoadSubmodels expands model bounds by one unit before assigning mins.
    names = {k["targetname"]: k for k in keys if k.get("targetname")}
    initial_models = list(bsp.bmodels)

    def set_train_positions(overrides=None):
        bsp.bmodels = []
        for entity, model, offset in initial_models:
            k = entity["keys"]
            if k["classname"] == "func_train":
                corner_name = (overrides or {}).get(k.get("targetname"), k.get("target"))
                corner = names.get(corner_name)
                if require(corner and corner["classname"] == "path_corner",
                           f"Train {k.get('targetname')} has no path corner {corner_name}"):
                    p = vec(corner["origin"])
                    offset = tuple(p[i] - (bsp.models[model][i] - 1) for i in range(3))
            bsp.bmodels.append((entity, model, offset))

    set_train_positions()
    placements, actors = [], []
    for e in source:
        k, c = e["keys"], e["keys"]["classname"]
        if c in ("info_player_start", "info_player_coop") or c.startswith("monster_"):
            mins, maxs = PLAYER_MINS, PLAYER_MAXS
            mask = MONSTER_MASK if c.startswith("monster_") else PLAYER_MASK
            if c in ("monster_tank", "monster_plastic_tank"):
                mins, maxs = (-32, -32, -16), (32, 32, 72)
            elif c == "monster_ant":
                mins, maxs = (-24, -24, -24), (24, 24, 16)
            actors.append((e, mins, maxs))
        elif c.startswith(("weapon_", "ammo_", "item_", "key_")):
            mins, maxs, mask = (-15,) * 3, (15,) * 3, SOLID
        else:
            continue
        p = vec(k["origin"])
        hit = bsp.collision(p, mins, maxs, mask)
        require(not hit, f"{c} at {p} intersects {hit}")
        placements.append({"classname": c, "origin": p, "blocker": hit})
    for i, (e, mins, maxs) in enumerate(actors):
        p = vec(e["keys"]["origin"])
        for other, omin, omax in actors[i + 1:]:
            if not any(enabled(e, s) and enabled(other, s) for s in range(3)):
                continue
            q = vec(other["keys"]["origin"])
            overlap = all(p[j] + mins[j] < q[j] + omax[j] and
                          q[j] + omin[j] < p[j] + maxs[j] for j in range(3))
            require(not overlap, f"Overlapping actor spawns: {e['keys']['classname']} {p}, {other['keys']['classname']} {q}")
    report["placements"] = placements

    # Independently sample all six faces of each staging room's closed shell.
    # The 16-unit lattice is finer than a crouched player's narrowest dimension,
    # and includes walls, floor and roof, so the named door alone is not enough
    # to mask a second entrance or an open roof that permits a spawn telefrag.
    bay_bounds = {"upper": (-1472, -640, 240, -896, -352, 432),
                  "lower": (-800, 864, 0, -128, 1136, 208),
                  "yard": (2112, -1712, 0, 2592, -1120, 208)}
    bays = []
    for bay, bounds in bay_bounds.items():
        probes, leaks = 0, []
        for axis in range(3):
            other_axes = [j for j in range(3) if j != axis]
            positions = ((bounds[axis] - 8, bounds[axis + 3] + 8) if axis == 2 else
                         (bounds[axis] + 12, bounds[axis + 3] - 12))
            for position in positions:
                for a in range(bounds[other_axes[0]] + 12, bounds[other_axes[0] + 3] - 11, 16):
                    for b in range(bounds[other_axes[1]] + 12, bounds[other_axes[1] + 3] - 11, 16):
                        p = [0., 0., 0.]
                        p[axis], p[other_axes[0]], p[other_axes[1]] = position, a, b
                        probes += 1
                        if not bsp.collision(p, (0, 0, 0), (0, 0, 0), SOLID) and len(leaks) < 6:
                            leaks.append(p)
        require(not leaks, f"Reserve bay {bay} is accessible before deployment: {leaks}")
        bays.append({"name": bay, "shell_samples": probes, "leaks": leaks})
    doors = [(e, m, o) for e, m, o in bsp.bmodels if e["keys"].get("targetname") == "endline_reserve_doors"]
    require(len(doors) == 4, "Both reserve bays and both station-store exits require sealed deployment doors")
    door_results = []
    for e, model, offset in doors:
        bounds = bsp.models[model]
        p = [(bounds[i] + bounds[i + 3]) / 2 + offset[i] for i in range(3)]
        p[2] = bounds[2] + offset[2] + 24
        closed = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        opened = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, ["endline_reserve_doors"])
        require(closed and not opened, f"Reserve door {e['keys'].get('_endline_reserve_door')} must block closed and clear open: {closed}, {opened}")
        door_results.append({"point": p, "closed": closed, "opened": opened})
    exits = []
    for e in source:
        k = e["keys"]
        if k.get("targetname") != "endline_wave" or not k["classname"].startswith("monster_"):
            continue
        bay = k.get("_endline_reserve")
        require(bay in bay_bounds, f"Unprotected reinforcement: {k.get('origin')}")
        p = vec(k["origin"])
        if bay in bay_bounds:
            bounds = bay_bounds[bay]
            require(all(bounds[i] < p[i] < bounds[i + 3] for i in range(3)),
                    f"Reinforcement {p} lies outside its sealed {bay} deployment room")
        path, next_name, seen = [p], k.get("combattarget"), set()
        while next_name and next_name not in seen:
            seen.add(next_name)
            goal = names.get(next_name)
            require(goal and goal["classname"] == "point_combat", f"Reinforcement {p} lacks a combat exit waypoint")
            if not goal:
                break
            path.append(vec(goal["origin"]))
            next_name = goal.get("target")
        failures = []
        require(len(path) >= 2, f"Reinforcement {p} has no guided exit from its deployment room")
        for a, b in zip(path, path[1:]):
            steps = max(1, math.ceil(math.dist(a, b) / 8))
            for i in range(steps + 1):
                q = tuple(a[j] + (b[j] - a[j]) * i / steps for j in range(3))
                hit = bsp.collision(q, PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, ["endline_reserve_doors"])
                if hit and len(failures) < 4:
                    failures.append({"point": q, "blocker": hit})
        require(not failures, f"Reinforcement {p} cannot leave its opened bay: {failures}")
        exits.append({"origin": p, "bay": bay, "path": path, "failures": failures})
    report["reserve_bays"] = bays
    report["reserve_doors"] = door_results
    report["reinforcement_exits"] = exits

    document = json.loads(args.routes.read_text())
    if isinstance(document, list):
        document = {"routes": document}
    require(bool(document.get("routes")), "No walking routes supplied")
    secret_routes = {r.get("secret") for r in document.get("routes", []) if r.get("secret")}
    secret_names = {k.get("targetname") for k in keys if k["classname"] == "target_secret"}
    require(secret_names == secret_routes, "Every secret needs a compiled walking route to its reward")
    routes, choices = [], defaultdict(set)
    for route in document.get("routes", []):
        points = route["points"]
        require(len(points) >= 2, f"Route {route['name']} needs at least two points")
        set_train_positions(route.get("train_at"))
        opened, previous, failures, samples = route.get("opened_doors", []), None, [], 0
        if route.get("objective") and route.get("approach"):
            choices[route["objective"]].add(route["approach"])
        for a, b in zip(points, points[1:]):
            steps = max(1, math.ceil(math.dist(a, b) / 8))
            for i in range(steps + 1):
                p = tuple(a[j] + (b[j] - a[j]) * i / steps for j in range(3))
                hit = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened)
                if hit and previous:
                    for rise in range(1, 19):
                        raised = (p[0], p[1], p[2] + rise)
                        if raised[2] > previous[2] + 18.03125:
                            break
                        if bsp.collision(raised, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened):
                            continue
                        up = (previous[0], previous[1], max(previous[2], raised[2]))
                        sweep = [tuple(previous[j] + (up[j] - previous[j]) * t / 4 for j in range(3))
                                 for t in range(1, 5)]
                        sweep += [tuple(up[j] + (raised[j] - up[j]) * t / 4 for j in range(3))
                                  for t in range(1, 5)]
                        if any(bsp.collision(q, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened) for q in sweep):
                            continue
                        p, hit = raised, None
                        break
                # PM_StepSlideMove traces the complete player hull downward;
                # a narrow center-foot probe incorrectly rejects stair edges
                # where the actual standing hull already overlaps the tread.
                support = any(bsp.collision((p[0], p[1], p[2] - dz),
                                            PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened)
                              for dz in (2, 8, 16, 24))
                if (hit or not support) and len(failures) < 8:
                    failures.append({"point": p, "blocker": hit or "unsupported"})
                if not hit:
                    previous = p
                samples += 1
        require(not failures, f"Route {route['name']}: {failures}")
        routes.append({"name": route["name"], "samples": samples, "failures": failures})
    for objective in document.get("required_route_choices", ("signal", "boarding")):
        require(len(choices[objective]) >= 2,
                f"Objective {objective} needs two independently checked approaches")
    report["routes"] = routes
    report["route_choices"] = {k: sorted(v) for k, v in choices.items()}
    report.update(passed=not errors, errors=errors, warnings=warnings,
                  limitations=["Static BSP validation does not prove AI behavior, pacing, moving-train riding, or mission completion in a live game."])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=ROOT / "maps/source/pp_endline.map")
    parser.add_argument("--bsp", type=Path, default=ROOT / "baseq2/maps/pp_endline.bsp")
    parser.add_argument("--routes", type=Path, default=ROOT / "tools/maps/endline_routes.json")
    parser.add_argument("--output", type=Path, default=ROOT / "build/maps/pp_endline/verification.json")
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    report = verify(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "errors", "difficulty")}, indent=2))
    raise SystemExit(not report["passed"])


if __name__ == "__main__":
    main()
