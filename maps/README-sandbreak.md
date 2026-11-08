# Operation Sandbreak

Operation Sandbreak is an original cooperative assault for one to four players.
Green plastic soldiers cross an oversized wooden sandbox, breach a sandcastle,
destroy a tan tank and helicopter, and reach a green extraction beacon. The
mission includes all five implemented enemy soldier variants and every usable
player weapon in the current game.

## Play

The compiled level package is `baseq2/operation-sandbreak.pk3`, also installed
in `release/baseq2`. It requires the current Plastic Platoon engine and game
module and the project's standalone `plastic-platoon.pk3` asset pack.
No original Quake II game data is required.

Launch from the repository:

```sh
./release/quake2 +exec sandbreak_coop.cfg
```

After updating, restart the game and start a fresh mission. The tank gate fix
requires the rebuilt game module, not only the map package. Older saves can
retain the former aiming timer in the map-event delay field. Build the fixed
module with `make -j4 DEBUG= game` before launching if rebuilding from source.

From the game console, use `exec sandbreak_coop.cfg`. This starts a new mission
on normal difficulty with four co-op slots. Other players can join the host
through the game's network menu or `connect HOST_ADDRESS`. All participants
need the level package and compatible Plastic Platoon game assets.

For another difficulty, set `skill 0` for easy or `skill 2` for hard before
`map pp_sandbreak` in an already configured co-op session. The launch config
explicitly selects normal difficulty. Optional soldiers increase resistance on
normal and hard; required vehicle objectives remain available on every skill.

## Assault sequence

1. **Landing and castle controls.** Rearm in the protected insertion hut, leave
   through either side, and work around blocks and thread spools. Sand ramps
   lead to the two tower upper floors. Touch both red control buttons, in either
   order, to open the assault gate. The controls stay pressed; simultaneous
   activation is unnecessary. The exposed connecting bridge offers a strong
   weapon and lets teammates cross between towers.
2. **Tank courtyard.** Collect the rocket launcher beyond the gate. Broad flank
   lanes and tall toy blocks let one player draw the turret while others move.
   The roofed side shelters contain supplies. Destroy the tank to open the
   airfield. The blue water basin on the west side contains the optional mortar
   cache and has a stair route at both ends.
3. **Airfield.** Advance between tall blocks and roofed shelters while fighting
   the helicopter and its infantry support. Use the sheltered ammunition before
   committing to an exposed firing position. Destroying the helicopter opens
   the final gate.
4. **Extraction.** Reach the green beacon beyond the north gate. Entering it
   awards the mission goal and starts the completion intermission, followed by
   a small debrief room. The red button in that room starts another assault.

An extraction reached by one player completes the shared mission; it is not an
all-players occupancy puzzle. Infantry kills are useful for safety but are not
additional hidden progression requirements.

Closed gates are red and numbered 01, 02 and 03. Green frames mark the route
through an opened gate, and the taller green beacon marks extraction. Raised
alphabet letters distinguish toy-block cover, tower battlements reinforce the
castle silhouette, and medical crosses identify roofed resupply shelters.
Arrows mark the tower approaches and the side entrance to the mortar basin.

## Cooperative rules

There are four separated insertion starts. The map uses the game's existing
respawn behavior: players return to insertion, not to moving checkpoints.
Opened gates remain open, and the flank lanes give returning players a clear
route back to the group. This also keeps the mission playable with one player
or an uneven team.

Ordinary weapon pickups remain available for each co-op player. Ammunition,
health and armor are shared consumables, so supply stations provide multiple
separate ammunition portions. Picking up the same weapon again is not an
unlimited resupply method. The pistol remains an ammunition-free fallback.
Each supply station now has two large health pickups. Four jackets at insertion
and extra courtyard armor give the team more opportunities to share protection.

## Weapon roles and locations

| Weapon | Placement | Intended use |
| --- | --- | --- |
| Pistol | Starting equipment | Finish weakened infantry and conserve supplies |
| Shotgun | Insertion hut | Close fights around cover and tower entrances |
| Rifle | Insertion hut | Reliable moving fire across the landing lanes |
| Hand grenades | Rear of insertion hut | Attack enemies behind blocks and corners |
| Double Barrel Shotgun | East tower upper floor | Clear close tower and courtyard threats |
| Sniper Rifle | West tower upper floor | Cover a teammate advancing below; rearm on the ground floor |
| M1 Flamethrower | Exposed bridge between towers | Trade exposure for strong close-range clearing |
| Grenade Launcher | Castle approach to first gate; later airfield pickup | Lob rounds into defended positions |
| Rocket Launcher | Beyond first gate; airfield shelter | Defeat the tank and helicopter from useful firing angles |
| Heavy Machinegun or M60 | Beyond first gate; airfield shelter | Sustained infantry and vehicle damage during safe firing windows |
| Mortar Cannon | Optional west courtyard water basin | Spend its three pickup rounds on dense resistance or armor |

Grenade Launcher ammunition is `ammo_gl_rounds`, separate from throwable
grenades. Napalm fuels the flamethrower; Sniper Rounds fuel the sniper rifle.
Mortar ammunition comes with its weapon pickup, so no invisible mortar-ammo
entities are placed in the level.

## Applying the reference design

The reference document, *Sandbox 2 Level Design — Compact*, guides both the
layout and the visual language:

- **Connected loops inside a linear mission.** Each assault space has west and
  east flanks with crossovers. The objectives give a northward direction while
  the local routes offer choices for escape, regrouping and attacks from the
  side.
- **Readable cover.** Colored plastic blocks and wooden spools have hard edges
  and contrast with sand ramps and rounded tower footprints. Tall cover breaks
  tank fire; actual roofs protect against elevated helicopter fire.
- **Multiple exits.** The insertion hut and supply shelters have two open ends.
  Towers have ground passages and upper openings; the mortar basin has a route
  at either end. Objective gates are deliberate shared bottlenecks between
  larger combat loops.
- **Risk for stronger rewards.** The sniper rifle requires climbing a tower;
  its resupply is below. The flamethrower sits on an exposed bridge. The mortar
  requires a slowed, optional water detour. None of these pickups is a mandatory
  key to progressing.
- **Items and landmarks guide movement.** Supplies sit along shelter loops;
  the two towers identify the initial objective; green trim marks gates; a green
  illuminated pad identifies the final goal. Help text updates after each major
  milestone.
- **Simple interiors.** Straight ramps and compact shelter spaces make combat
  routes readable. The toy-scale wooden enclosure, sandcastle forms, plastic
  pieces and thread spools maintain the sandbox theme.

## Rebuild and verify

The editable map sources are `maps/source/pp_sandbreak.map` and
`maps/source/pp_sandbreak_end.map`. Their reproducible authoring source is
`tools/maps/generate_sandbreak.py`; regeneration replaces manual MAP edits.
`COMPILE_BASEQ2` must contain the existing Sandkeep textures and an authentic
`pics/colormap.pcx`; `Q2TOOL` points to the installed compiler.

```sh
python3 tools/maps/generate_sandbreak.py
./compile_map.sh --source maps/source/pp_sandbreak.map \
  --basedir "$COMPILE_BASEQ2" --tool "$Q2TOOL" \
  --profile preview --vis --threads 4 --output-dir baseq2/maps
"$Q2TOOL" -rad -subdiv 256 -threads 4 -basedir "$COMPILE_BASEQ2" \
  baseq2/maps/pp_sandbreak.bsp
./compile_map.sh --source maps/source/pp_sandbreak_end.map \
  --basedir "$COMPILE_BASEQ2" --tool "$Q2TOOL" \
  --profile release --threads 4 --output-dir baseq2/maps
python3 tools/maps/verify_sandbreak.py
python3 tools/maps/package_sandbreak.py
```

The independent verifier reads the compiled BSP to check entity agreement,
placements, roster and weapon coverage, objective connections, player routes,
and visibility and lighting data. Packaging requires a passing report matching
the exact assault source and BSP, and independently checks the debrief map.
Reports and package hashes are written under `build/maps/pp_sandbreak`.

`python3 tools/maps/capture_sandbreak.py --label sandbreak-review` captures
six real-engine views in a private runtime. Its default SDL dummy display and
software renderer work without opening a desktop window. These views assess
layout and readability; they are not hardware performance measurements.

For windowless OpenGL 3 previews, select an available EGL device explicitly:

```sh
python3 tools/maps/capture_sandbreak.py --label sandbreak-gl3-review \
  --display-backend offscreen --renderer gl3 --egl-device 1
```

Device 1 is the software EGL device on the development host; device numbering
can differ elsewhere. The software renderer's existing soldier skin fallback
can print warnings during previews; OpenGL 3 previews avoid that fallback.
The capture tool records the selected backend and hashes of the tested files.

The vehicle objective regression suites exercise combat, lethal damage, actual
relay and door activation, intentional map delays and saving/loading:

```sh
tests/heavy_tank/run_tests.sh
tests/helicopter/run_tests.sh
python3 tools/maps/test_sandbreak_runtime.py --label sandbreak-progression
```

The runtime check lets the tank attack before killing it with weapon damage,
checks immediate gate passage with normal movement, then tests helicopter
death and extraction into the debrief room. It uses cheats for setup and lethal
telefrag damage for the helicopter; it is not a combat-balance playthrough.

## Tuning

The first tuning pass should use both two- and four-player groups. Watch for
ammunition hoarding, the return time after death, visibility of the red tower
controls, safe movement between helicopter shelters, and how often the team
chooses the water detour. Adjust supply counts and optional infantry before
changing the required objective chain. Static checks and screenshots do not
establish completion time, combat balance, or a full multiplayer playthrough.

The package contains original level geometry, existing project Sandkeep
materials, and the existing sandbox blue sky. It does not redistribute original Quake II PAK data or the compiler's
colormap.
