#!/usr/bin/env python3
"""Independently verify End of the Line's entities and compiled collision.

This does not import the level generator. Route points are standing player
origins. A route may name ``opened_doors`` and ``train_at`` (a mapping from
func_train targetname to a path_corner targetname) to describe the real mission
state being tested. The optional drop_segments list identifies ledge drops by
their zero-based segment indices. Static validation does not replace live play.
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


def samples(start, end, spacing=8):
    count = max(1, math.ceil(math.dist(start, end) / spacing))
    return [tuple(a + (b - a) * i / count for a, b in zip(start, end)) for i in range(count + 1)]


def train_side(y):
    # The locomotive faces west at both stops.
    if y == 0:
        return "center"
    return "left" if y < 0 else "right"


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

    def one(classname, targetname=None):
        matches = [e for e in source if e["keys"]["classname"] == classname and
                   (targetname is None or e["keys"].get("targetname") == targetname)]
        require(len(matches) == 1, f"Need one {classname} {targetname or ''}".rstrip())
        return matches[0] if len(matches) == 1 else {"keys": {}, "brushes": []}

    extraction = one("trigger_platoon_extract")
    boarding = extraction["keys"]
    require(not int(boarding.get("spawnflags", 0)) & 4 and
            boarding.get("target") == "endline_train_armed",
            "The boarding volume must check every living player before exposing the switch")
    switch = one("func_button", "endline_depart_switch")
    require(int(switch["keys"].get("health", 0)) > 0 and
            switch["keys"].get("target") == "endline_depart_shot",
            "Departure must come from shooting the exposed switch")
    cover = one("func_explosive", "endline_depart_cover")
    button_bounds, cover_bounds = entity_bounds(switch), entity_bounds(cover)
    require(button_bounds and cover_bounds and
            all(cover_bounds[i] <= button_bounds[i] <= button_bounds[i + 3] <= cover_bounds[i + 3]
                for i in range(3)),
            "An explosive cover must enclose the shootable switch")
    require(not any(k.get("target") == "endline_depart_switch" for k in keys),
            "The switch cannot be activated remotely")
    require({k.get("targetname") for k in keys if k.get("target") == "endline_depart_cover"} ==
            {"endline_train_armed"}, "Only boarding may destroy the switch cover")
    require({k.get("targetname") for k in keys if k.get("target") == "endline_train"} ==
            {"endline_depart_shot", "endline_bridge_cleared", "endline_ambush_cleared"},
            "Only the departure shot and the cleared ambushes may move the train")
    require({k.get("classname") for k in keys if k.get("target") == "endline_depart_shot"} ==
            {"func_button"}, "The departure shot cannot be bypassed")
    one("target_platoon_intermission", "endline_complete")

    train = one("func_train", "endline_train")
    train_keys = train["keys"]
    require(int(train_keys.get("spawnflags", 0)) & 3 == 2 and
            train_keys.get("target") == "endline_siding",
            "The train must begin stationary at the station and support triggered stops")
    corners = {k.get("targetname"): k for k in keys if k["classname"] == "path_corner"}
    siding = corners.get("endline_siding", {})
    bridge_stop = corners.get("endline_bridge_stop", {})
    gate_stop = corners.get("endline_gate_stop", {})
    exit_corner = corners.get("endline_exit", {})
    outside_corner = corners.get("endline_outside", {})
    require(siding.get("target") == "endline_bridge_stop" and
            bridge_stop.get("target") == "endline_gate_stop" and
            bridge_stop.get("pathtarget") == "endline_bridge_arrived" and
            float(bridge_stop.get("wait", 0)) == -1 and siding and gate_stop and
            vec(gate_stop["origin"])[0] < vec(bridge_stop["origin"])[0] < vec(siding["origin"])[0],
            "The train must stop for the bridge ambush between the station and the garage")
    bridge_triggers = []
    for name, target in (("endline_bridge_arrived", "endline_bridge_attack"),
                         ("endline_bridge_cleared", "endline_train")):
        trigger = one("trigger_once", name)
        k = trigger["keys"]
        require(int(k.get("spawnflags", 0)) & 7 == 4 and k.get("target") == target and
                entity_bounds(trigger),
                f"Bridge trigger {name} must wait to be enabled, then use a rider to activate {target}")
        bridge_triggers.append(trigger)
    require({k.get("targetname") for k in keys if k.get("pathtarget") == "endline_bridge_arrived"} ==
            {"endline_bridge_stop"} and not any(k.get("target") == "endline_bridge_arrived" for k in keys),
            "Only arrival at the bridge may enable its attack trigger")
    require(all(k["classname"] == "trigger_counter" and k.get("targetname") == "endline_bridge_down"
                for k in keys if k.get("target") == "endline_bridge_cleared"),
            "Only the bridge death counter may enable the clear trigger")
    require(gate_stop.get("target") == "endline_exit" and
            gate_stop.get("pathtarget") == "endline_gate_arrived" and
            float(gate_stop.get("wait", 0)) == -1,
            "The garage stop must await the kill counter instead of a timer")
    require(exit_corner.get("target") == "endline_outside" and
            exit_corner.get("pathtarget") == "endline_complete" and
            not float(exit_corner.get("wait", 0)) and
            float(outside_corner.get("wait", 0)) == -1,
            "The train must continue outside after moving players to intermission")
    jumps = [e for e in source if e["keys"]["classname"] == "trigger_monsterjump"]
    jumps_by_stop = {}
    for stop, objective in (("endline_gate_stop", "ambush_jump"), ("endline_bridge_stop", "bridge_jump")):
        stop_jumps = [e for e in jumps if e["keys"].get("_endline_objective") == objective]
        require(Counter(e["keys"].get("_endline_side") for e in stop_jumps) == {"left": 1, "right": 1},
                f"{stop} needs one jump across each armored rim")
        jumps_by_side = {e["keys"].get("_endline_side"): e for e in stop_jumps}
        jumps_by_stop[stop] = jumps_by_side
        for side, yaw in (("left", 90), ("right", 270)):
            jump = jumps_by_side.get(side)
            bounds = entity_bounds(jump) if jump else None
            jump_keys = jump["keys"] if jump else {}
            require(bounds and all(train_side(bounds[i]) == side for i in (1, 4)) and
                    float(jump_keys.get("angle", 0)) % 360 == yaw and
                    float(jump_keys.get("speed", 0)) > 0 and float(jump_keys.get("height", 0)) > 0,
                    f"The {side} jump at {stop} must launch soldiers inward over the armored rim")
    require(len(jumps) == 4, "The two ambushes require four boarding jumps in total")

    ship = one("misc_platoon_dropship", "endline_insertion_flight")["keys"]
    fall = one("trigger_hurt")
    fall_bounds = entity_bounds(fall)
    require(fall["keys"].get("_endline_hazard") == "window_fall" and
            int(fall["keys"].get("spawnflags", 0)) & 8 and int(fall["keys"].get("dmg", 0)) >= 1000,
            "The window exterior needs a lethal fall trigger")
    if ship and fall_bounds:
        start = vec(ship["origin"])
        lift = corners.get(ship.get("target"), {})
        outside = corners.get(lift.get("target"), {})
        away = corners.get(outside.get("target"), {})
        removal = one("trigger_relay", away.get("pathtarget"))["keys"]
        require(lift and outside and away and
                vec(lift["origin"])[2] > start[2] and
                start[1] > fall_bounds[4] > vec(outside["origin"])[1] and
                removal.get("killtarget") == ship.get("targetname"),
                "The dropship must lift from the sill, fly outside, and disappear")
        require(all(fall_bounds[0] < x < fall_bounds[3] and y > fall_bounds[4] and z - 24 > fall_bounds[5]
                    for x, y, z in starts), "Every start must be safe on the sill above the exterior hazard")
    require(any(k["classname"] == "trigger_once" and k.get("target") == "endline_intro" for k in keys) and
            any(k.get("targetname") == "endline_intro" and k.get("target") == "endline_insertion_flight" and
                float(k.get("delay", 0)) > 0 for k in keys),
            "The window insertion must trigger a delayed dropship departure")

    gate_name = "endline_garage_door"
    stages = ("first", "second", "third")
    ambush_waves = tuple("endline_ambush_" + stage for stage in stages)
    hatch_names = tuple("endline_ambush_hatch_" + stage for stage in stages)
    stage_sides = (("left",), ("right",), ("left", "right"))
    gate_doors = [e for e in named[gate_name] if e["keys"]["classname"] == "func_door"]
    ambush_hatches = [e for name in hatch_names for e in named[name] if e["keys"]["classname"] == "func_door"]
    require(sum(len(e["brushes"]) for e in gate_doors) == 10 and
            {e["keys"].get("team") for e in gate_doors} == {gate_name},
            "The ten garage door segments must open together")
    hatch_sides = Counter()
    for hatch in ambush_hatches:
        bounds = entity_bounds(hatch)
        if require(bounds and bounds[1] * bounds[4] > 0,
                   "Each garage ambush hatch must lie on one side of the train"):
            hatch_sides[hatch["keys"]["targetname"], train_side(bounds[1])] += 1
    require(hatch_sides == Counter((name, side) for name, sides in zip(hatch_names, stage_sides) for side in sides),
            "Garage hatches must open on the left, then the right, then both sides")
    require(all(float(e["keys"].get("wait", 0)) == -1 and
                not int(e["keys"].get("spawnflags", 0)) & 33 for e in gate_doors + ambush_hatches),
            "The garage and ambush doors must start closed and stay open once activated")
    arrival_relays = [e["keys"] for e in named["endline_gate_arrived"] if e["keys"]["classname"] == "trigger_relay"]
    activation_order = [gate_name] + [name for stage in zip(ambush_waves, hatch_names) for name in stage]
    arrival_delays = []
    for target in activation_order:
        relays = [k for k in arrival_relays if k.get("target") == target]
        if require(len(relays) == 1, f"Garage arrival needs one relay to {target}"):
            arrival_delays.append(float(relays[0].get("delay", 0)))
    if len(arrival_delays) == len(activation_order):
        require(arrival_delays[0] == 0 and all(a < b for a, b in zip(arrival_delays, arrival_delays[1:])) and
                arrival_delays[-1] <= 10,
                "The garage must open immediately, followed by a staged ambush during the hold")
    bridge_waves = ("endline_bridge_wave_first", "endline_bridge_wave_second")
    bridge_hatches = ("endline_bridge_hatch_first", "endline_bridge_hatch_second")
    bridge_attack = [e["keys"] for e in named["endline_bridge_attack"] if e["keys"]["classname"] == "trigger_relay"]
    for wave, hatch, side, spawn_at in zip(bridge_waves, bridge_hatches, ("right", "left"), (.5, 4.5)):
        door = one("func_door", hatch)
        bounds = entity_bounds(door)
        require(bounds and all(train_side(bounds[i]) == side for i in (1, 4)) and
                float(door["keys"].get("wait", 0)) == -1 and
                not int(door["keys"].get("spawnflags", 0)) & 33,
                f"Bridge hatch {hatch} must be closed on the {side} until release and then stay open")
        for target, delay in ((wave, spawn_at), (hatch, spawn_at + .5)):
            require([float(k.get("delay", 0)) for k in bridge_attack if k.get("target") == target] == [delay],
                    f"Bridge attack must activate {target} once at {delay:g}s")
    require({k.get("targetname") for k in keys if k.get("target") == "endline_bridge_attack"} ==
            {"endline_bridge_arrived"}, "Only the rider trigger at the bridge may release its waves")
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
        armed_chain = chain("endline_train_armed", skill)
        require(any(k["classname"] == "func_explosive" and k.get("targetname") == "endline_depart_cover"
                    for k in armed_chain) and all(k["classname"] != "func_train" for k in armed_chain),
                f"Skill {skill}: boarding must uncover the switch and leave the train stopped")
        departure_chain = chain("endline_depart_shot", skill)
        require(any(k["classname"] == "func_train" for k in departure_chain) and
                any(k["classname"] == "target_platoon_intermission" for k in departure_chain),
                f"Skill {skill}: the departure shot cannot complete the escape")
        reinforcement_chain = chain("endline_divert", skill)
        wave = [k for k in monsters if k.get("targetname") == "endline_wave"]
        require(len(wave) == (6, 9, 12)[skill],
                f"Skill {skill}: reinforcement count is {len(wave)}")
        require(all(int(k.get("spawnflags", 0)) & 2 and k in reinforcement_chain for k in wave),
                f"Skill {skill}: each approach reinforcement must be activated from a sealed bay")
        ambush = [k for k in monsters if k.get("targetname") in ambush_waves]
        wave_counts = [sum(k.get("targetname") == name for k in ambush) for name in ambush_waves]
        require(wave_counts == [3 + skill] * len(ambush_waves),
                f"Skill {skill}: garage wave populations differ from their authored difficulty: {wave_counts}")
        wave_sides = [Counter(train_side(vec(k["origin"])[1]) for k in ambush if k.get("targetname") == name)
                      for name in ambush_waves]
        third_left, third_right = ((1, 2), (2, 2), (2, 3))[skill]
        require(wave_sides == [{"left": 3 + skill}, {"right": 3 + skill},
                               {"left": third_left, "right": third_right}],
                f"Skill {skill}: garage waves must attack left, right, then both sides: {wave_sides}")
        require(all(int(k.get("spawnflags", 0)) & 2 and k.get("_endline_reserve") == "finale" and
                    k.get("combattarget") and k.get("deathtarget") == "endline_ambush_down" for k in ambush),
                f"Skill {skill}: every garage attacker must spawn on cue, board, and report its death")
        garage_counters = [k for k in live if k["classname"] == "trigger_counter" and
                           k.get("targetname") == "endline_ambush_down"]
        require(len(garage_counters) == 1 and int(garage_counters[0].get("count", 0)) == len(ambush) and
                garage_counters[0].get("target") == "endline_ambush_cleared" and
                not int(garage_counters[0].get("spawnflags", 0)) & 1,
                f"Skill {skill}: the visible garage counter must count every ambusher before releasing the train")
        bridge_ambush = [k for k in monsters if k.get("targetname") in bridge_waves]
        bridge_sides = [Counter(train_side(vec(k["origin"])[1])
                                for k in bridge_ambush if k.get("targetname") == name)
                        for name in bridge_waves]
        require(bridge_sides == [{"right": 3 + skill}, {"left": 3 + skill}],
                f"Skill {skill}: the bridge attack needs {3 + skill} attackers per wave, right then left: {bridge_sides}")
        require(all(int(k.get("spawnflags", 0)) & 2 and k.get("_endline_reserve") == "bridge" and
                    k.get("combattarget") and k.get("deathtarget") == "endline_bridge_down" for k in bridge_ambush),
                f"Skill {skill}: every bridge attacker must spawn on cue, board, and report its death")
        bridge_counters = [k for k in live if k["classname"] == "trigger_counter" and
                           k.get("targetname") == "endline_bridge_down"]
        require(len(bridge_counters) == 1 and int(bridge_counters[0].get("count", 0)) == len(bridge_ambush) and
                bridge_counters[0].get("target") == "endline_bridge_cleared" and
                not int(bridge_counters[0].get("spawnflags", 0)) & 1,
                f"Skill {skill}: the visible bridge counter must count every ambusher before releasing the train")
        difficulties.append({"skill": skill, "enemies": len(monsters), "counters": counters,
                             "garage_waves": wave_counts, "garage_wave_sides": wave_sides,
                             "bridge_wave_sides": bridge_sides})
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

    def train_origin(model, corner):
        position = vec(corner["origin"])
        return tuple(position[i] - (bsp.models[model][i] - 1) for i in range(3))

    # The game sends each component of a moving entity's origin as a signed
    # 16-bit integer in eighths of a unit. Linear motion stays in range if
    # all of the path corners do, including the outdoor stop.
    train_origins = {}
    for entity, model, _ in initial_models:
        k = entity["keys"]
        if k["classname"] != "func_train":
            continue
        corner_name = k.get("target")
        while corner_name and corner_name not in train_origins:
            corner = corners.get(corner_name)
            if not require(corner is not None, f"Train path missing corner {corner_name}"):
                break
            origin = train_origin(model, corner)
            require(all(-4096 <= coord <= 4095.875 for coord in origin),
                    f"Train origin wraps on the network at {corner_name}: {origin}")
            train_origins[corner_name] = origin
            corner_name = corner.get("target")
    report["train_network_origins"] = train_origins

    def set_train_positions(overrides=None):
        bsp.bmodels = []
        for entity, model, offset in initial_models:
            k = entity["keys"]
            if k["classname"] == "func_train":
                corner_name = (overrides or {}).get(k.get("targetname"), k.get("target"))
                corner = names.get(corner_name)
                if require(corner and corner["classname"] == "path_corner",
                           f"Train {k.get('targetname')} has no path corner {corner_name}"):
                    offset = train_origin(model, corner)
            bsp.bmodels.append((entity, model, offset))

    train_label = "func_train endline_train"
    train_model = next((model for e, model, _ in initial_models if e["keys"].get("targetname") == "endline_train"), None)
    camera = one("info_player_intermission")["keys"]
    if train_model is not None and "endline_outside" in train_origins and camera:
        offset = train_origins["endline_outside"]
        bounds = tuple(value + offset[i % 3] for i, value in enumerate(bsp.models[train_model][:6]))
        cam_x, cam_y, _ = vec(camera["origin"])
        yaw = vec(camera["angles"])[1] if "angles" in camera else float(camera.get("angle", 0))
        angles = [math.degrees(math.atan2(y - cam_y, x - cam_x))
                  for x in (bounds[0], bounds[3]) for y in (bounds[1], bounds[4])]
        camera_clearance = min(abs((angle - yaw + 180) % 360 - 180) for angle in angles)
        require(camera_clearance >= 55, "The parked train must leave the intermission camera's view")
        report["train_outside"] = {"bounds": bounds, "camera_clearance_degrees": camera_clearance}

    authored_train = next((e for e in source if e["keys"]["classname"] == "func_train"), None)
    if authored_train:
        pivot = vec(authored_train["keys"].get("origin", "0 0 0"))
        rubber = [entity_bounds({"brushes": [brush]}) for brush in authored_train["brushes"]
                  if brush and all(face["texture"] == "endline/rubber" for face in brush)]
        treads = [bounds for bounds in rubber if abs(bounds[2] - 256) < .1]
        require(len(treads) == 12, "The three cars require twelve wheel treads")
        for corner_name, origin in train_origins.items():
            set_train_positions({"endline_train": corner_name})
            for bounds in treads:
                x = (bounds[0] + bounds[3]) / 2 + origin[0] - pivot[0]
                y = (bounds[1] + bounds[4]) / 2 + origin[1] - pivot[1]
                z = bounds[2] + origin[2] - pivot[2]
                point = (0, 0, 0)
                rail = bsp.collision((x, y, z - .25), point, point, SOLID)
                tire = bsp.collision((x, y, z + .25), point, point, SOLID)
                require((rail or "").startswith("world") and "func_train endline_train" in (tire or ""),
                        f"Wheel does not meet the running rail at {corner_name}: {(x, y, z)}")
        report["wheel_contact_probes"] = len(treads) * len(train_origins)

    set_train_positions()
    garage_models = [(e, model, offset) for e, model, offset in bsp.bmodels
                     if e["keys"].get("targetname") == gate_name]
    garage_probes = []
    if garage_models and gate_stop and exit_corner:
        stop = vec(gate_stop["origin"])
        exit_x = vec(exit_corner["origin"])[0]
        west = max(bsp.models[model][0] + offset[0] for _, model, offset in garage_models)
        east = min(bsp.models[model][3] + offset[0] for _, model, offset in garage_models)
        require(exit_x < west < east < stop[0], "The exit track must pass through the garage door after the hold")
        point = ((west + east) / 2, stop[1] + 144, stop[2] + 80)
        closed = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        opened = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, [gate_name])
        require(gate_name in (closed or "") and not opened,
                f"Garage door must block the track when closed and clear it when open: {closed}, {opened}")
        require(report.get("train_outside", {}).get("bounds", (0,) * 6)[3] < west,
                "Every car must coast beyond the garage doorway")
        garage_probes.append({"door": gate_name, "point": point, "closed": closed, "opened": opened})
    bridge_probes = []
    for e, model, offset in bsp.bmodels:
        name = e["keys"].get("targetname")
        if name not in (*hatch_names, *bridge_hatches):
            continue
        bounds = bsp.models[model]
        point = [(bounds[i] + bounds[i + 3]) / 2 + offset[i] for i in range(3)]
        point[2] = bounds[2] + offset[2] + 24
        closed = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        opened = bsp.collision(point, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, [name])
        require(name in (closed or "") and not opened,
                f"Ambush hatch {name} must block closed and clear open: {closed}, {opened}")
        probes = bridge_probes if name in bridge_hatches else garage_probes
        probes.append({"door": name, "point": point, "closed": closed, "opened": opened})
    report["garage_doors"] = garage_probes
    report["bridge_doors"] = bridge_probes

    if bridge_stop:
        # The single-use triggers fire from an occupied part of the parked car.
        # Expand trigger bounds by the player hull to test overlap as the game does.
        nose_x, _, _ = vec(bridge_stop["origin"])
        set_train_positions({"endline_train": "endline_bridge_stop"})
        car_samples = [(nose_x + x, y, 329) for x in range(720, 1121, 16)
                       for y in range(-104, 105, 16)]
        clear_samples = [p for p in car_samples
                         if not bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)]
        require(clear_samples, "The train must be inhabitable at the bridge stop")
        for trigger in bridge_triggers:
            bounds = entity_bounds(trigger)
            if bounds:
                misses = [p for p in clear_samples
                          if not all(p[i] + PLAYER_MAXS[i] > bounds[i] and
                                     p[i] + PLAYER_MINS[i] < bounds[i + 3] for i in range(3))]
                require(not misses,
                        f"Bridge trigger {trigger['keys']['targetname']} misses the parked car at {misses[:4]}")
        set_train_positions()

    if ship:
        flight = [vec(ship["origin"])]
        next_name = ship.get("target")
        seen = set()
        while next_name in corners and next_name not in seen:
            seen.add(next_name)
            corner = corners[next_name]
            flight.append(vec(corner["origin"]))
            next_name = corner.get("target")
        flight_hits = []
        for a, b in zip(flight, flight[1:]):
            for x, y, z in samples(a, b, 16):
                # The visible green helicopter sits 36 units above its origin.
                blocker = bsp.collision((x, y, z + 36), (-114, -114, 0), (114, 114, 60), SOLID)
                if blocker and len(flight_hits) < 4:
                    flight_hits.append(((x, y, z), blocker))
        require(not flight_hits, f"The dropship clips the window or scenery during departure: {flight_hits}")
        report["window_flight"] = {"path": flight, "blockers": flight_hits, "fall_bounds": fall_bounds}

    if train_model is not None and "endline_siding" in train_origins:
        # At the station, players can walk off the gantry's lip and land below the rim.
        boarding_path = [(1632, -154, 488), (1632, -102, 488), (1632, -102, 329)]
        blockers = [(p, hit) for a, b in zip(boarding_path, boarding_path[1:]) for p in samples(a, b)
                    if (hit := bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK))]
        landing = boarding_path[-1]
        support = bsp.collision((landing[0], landing[1], landing[2] - 2), PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        require(not blockers and train_label in (support or ""),
                f"The station gantry must allow a clear drop into the armored car: {blockers[:4]}")
        # The rim has firing slots, but their gaps must not fit a crouched player.
        rim = [(x, y) for x in range(1505, 1938, 16) for y in (-128, 130)]
        rim.extend((x, y) for x in (1495, 1941) for y in range(-106, 110, 16))
        holes = [(x, y, z) for x, y in rim for z in (329, 348, 368, 392, 416, 442)
                 if train_label not in (bsp.collision((x, y, z), PLAYER_MINS, (16, 16, 4), PLAYER_MASK) or "")]
        require(not holes, f"The armored car must hold crouching or jumping riders: {holes[:6]}")
        offset = tuple(a - b for a, b in zip(train_origins["endline_siding"], pivot))
        interior = []
        for brush in authored_train["brushes"]:
            bounds = entity_bounds({"brushes": [brush]})
            x, y, z, X, Y, Z = (v + offset[i % 3] for i, v in enumerate(bounds))
            if x < 1937 and X > 1506 and y < 108 and Y > -107:
                interior.append(Z)
        max_cover = max([cover_bounds[5]] + interior) if cover_bounds else max(interior, default=449)
        # A 270-unit jump under default 800 gravity rises about 46 units.
        require(max_cover + 47 < 449, "A rider can jump over the rim from an interior surface")
        if button_bounds:
            x = (button_bounds[0] + button_bounds[3]) / 2
            z = (button_bounds[2] + button_bounds[5]) / 2
            ray_start, ray_end = (x, -32, z), (x, (button_bounds[1] + button_bounds[4]) / 2, z)
            cover_model = next((model for e, model, _ in initial_models
                                if e["keys"].get("targetname") == "endline_depart_cover"), None)
            if cover_model is not None:
                bsp.secret_models["endline_depart_cover"] = cover_model
            closed = bsp.segment_hits(ray_start, ray_end)
            opened = bsp.segment_hits(ray_start, ray_end, destroyed=("endline_depart_cover",)) if cover_model else []
            require(closed and "func_explosive endline_depart_cover" in closed[0]["entity"] and
                    opened and "func_button endline_depart_switch" in opened[0]["entity"],
                    "The car's departure switch must be shielded before boarding and shootable after")
        report["armored_car"] = {"drop": boarding_path, "rim_samples": len(rim) * 6,
                                 "holes": holes, "highest_cover": max_cover}

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
        if c in ("info_player_start", "info_player_coop"):
            require(bsp.collision((p[0], p[1], p[2] - 2), mins, maxs, mask),
                    f"Sill spawn {p} has no support")
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
    garage_routes = []
    bridge_routes = []
    boarding_waves = {
        **{wave: ("endline_gate_stop", hatch, garage_routes) for wave, hatch in zip(ambush_waves, hatch_names)},
        **{wave: ("endline_bridge_stop", hatch, bridge_routes)
           for wave, hatch in zip(bridge_waves, bridge_hatches)},
    }

    def jump_landing(start, deck_z, opened, jump):
        """Sample Quake's 10 Hz monster flight, including the swept hull."""
        speed = float(jump["keys"]["speed"])
        height = float(jump["keys"]["height"])
        yaw = math.radians(float(jump["keys"].get("angle", 0)))
        vx, vy = math.cos(yaw) * speed, math.sin(yaw) * speed
        x, y, z = start
        for frame in range(1, 16):
            t = frame * .1
            end = (start[0] + vx * t, start[1] + vy * t, start[2] + height * t - 40 * t * (frame + 1))
            for p in samples((x, y, z), end, 3)[1:]:
                hit = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, opened)
                if hit:
                    if end[2] < z and p[2] >= deck_z - 5 and -106 < p[1] < 108 and train_label in hit:
                        return p, None
                    return None, {"point": p, "blocker": hit}
            x, y, z = end
        return None, {"point": (x, y, z), "blocker": "never landed in the armored car"}

    for e in source:
        k = e["keys"]
        targetname = k.get("targetname")
        if targetname not in ("endline_wave", *boarding_waves) or not k["classname"].startswith("monster_"):
            continue
        bay = k.get("_endline_reserve")
        p = vec(k["origin"])
        boarding_wave = boarding_waves.get(targetname)
        if boarding_wave:
            stop, hatch, boarding_routes = boarding_wave
            side = train_side(p[1])
            jump = jumps_by_stop[stop].get(side)
            jump_bounds = entity_bounds(jump) if jump else None
            set_train_positions({"endline_train": stop})
            opened = [hatch]
        else:
            set_train_positions()
            opened = ["endline_reserve_doors"]
            if require(bay in bay_bounds, f"Unprotected reinforcement: {p}"):
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
        ground_path = path
        has_takeoff = boarding_wave and require(jump_bounds and len(path) >= 3,
                                                f"Ambusher {p} needs a guided route to the {side} jump")
        if has_takeoff:
            launch_y = jump_bounds[1] - PLAYER_MAXS[1] if side == "left" else jump_bounds[4] - PLAYER_MINS[1]
            takeoff = (path[-1][0], launch_y, path[-2][2])
            require(jump_bounds[0] < takeoff[0] < jump_bounds[3],
                    f"Ambusher {p} cannot reach the takeoff trigger")
            require(bsp.collision((takeoff[0], takeoff[1], takeoff[2] - 2),
                                  PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, opened),
                    f"Ambusher {p} has no ground at the {side} takeoff")
            ground_path = path[:-1] + [takeoff]
        for a, b in zip(ground_path, ground_path[1:]):
            for q in samples(a, b):
                hit = bsp.collision(q, PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, opened)
                if hit and len(failures) < 4:
                    failures.append({"point": q, "blocker": hit})
        result = {"origin": p, "bay": bay, "path": path, "failures": failures}
        if has_takeoff:
            x, y, z = path[-1]
            support = bsp.collision((x, y, z - 2), PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, opened)
            require(not bsp.collision((x, y, z), PLAYER_MINS, PLAYER_MAXS, MONSTER_MASK, opened) and
                    train_label in (support or ""),
                    f"Ambush waypoint {path[-1]} must reach the train deck: {support}")
            landing, blocker = jump_landing(takeoff, z, opened, jump)
            if blocker:
                failures.append(blocker)
            result.update(side=side, takeoff=takeoff, landing=landing)
            boarding_routes.append(result)
        elif not boarding_wave:
            exits.append(result)
        require(not failures, f"Reinforcement {p} cannot enter the fight: {failures}")
    report["reserve_bays"] = bays
    report["reserve_doors"] = door_results
    report["reinforcement_exits"] = exits
    report["garage_boarding_routes"] = garage_routes
    report["bridge_boarding_routes"] = bridge_routes

    document = json.loads(args.routes.read_text())
    if isinstance(document, list):
        document = {"routes": document}
    require(bool(document.get("routes")), "No walking routes supplied")
    secret_routes = {r.get("secret") for r in document.get("routes", []) if r.get("secret")}
    secret_names = {k.get("targetname") for k in keys if k["classname"] == "target_secret"}
    require(secret_names == secret_routes, "Every secret needs an explicit route entry")
    routes, choices = [], defaultdict(set)
    for route in document.get("routes", []):
        if route.get("secret") in secret_names and route.get("unavailable"):
            warnings.append(f"Route {route['name']} unavailable: {route['unavailable']}")
            routes.append({"name": route["name"], "unavailable": route["unavailable"]})
            continue
        points = route["points"]
        require(len(points) >= 2, f"Route {route['name']} needs at least two points")
        set_train_positions(route.get("train_at"))
        opened, previous, failures, samples_checked = route.get("opened_doors", []), None, [], 0
        if route.get("objective") and route.get("approach"):
            choices[route["objective"]].add(route["approach"])
        drops = set(route.get("drop_segments", ()))
        require(all(isinstance(i, int) and 0 <= i < len(points) - 1 for i in drops),
                f"Route {route['name']} has an invalid drop segment")
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if index in drops:
                require(0 < a[2] - b[2] <= 160, f"Route {route['name']} has an unsafe drop from {a} to {b}")
                edge = (b[0], b[1], a[2])
                air = samples(a, edge) + samples(edge, b)[1:]
                blockers = [(p, hit) for p in air
                            if (hit := bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened))]
                supported = all(bsp.collision((p[0], p[1], p[2] - 2), PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, opened)
                                for p in (a, b))
                if blockers or not supported:
                    failures.append({"drop": [a, b], "blockers": blockers[:3], "supported": supported})
                samples_checked += len(air)
                previous = tuple(b)
                continue
            for p in samples(a, b):
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
                samples_checked += 1
        require(not failures, f"Route {route['name']}: {failures}")
        routes.append({"name": route["name"], "samples": samples_checked, "failures": failures})
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
    print(json.dumps({k: report[k] for k in ("passed", "errors", "warnings", "difficulty")}, indent=2))
    raise SystemExit(not report["passed"])


if __name__ == "__main__":
    main()
