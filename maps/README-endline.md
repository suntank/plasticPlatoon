# Operation End of the Line

Raid the toy railway beneath a garage workbench, divert its ammunition train,
defend the siding, and escape across the bridge you passed beneath on arrival.
This is an original Plastic Platoon single-player and 2–4 player co-op mission.

## Play

| Console command | Mode |
| --- | --- |
| `exec endline_easy.cfg` | Easy, solo |
| `exec endline_solo.cfg` | Normal, solo |
| `exec endline_hard.cfg` | Hard, solo |
| `exec endline_coop.cfg` | Normal, network co-op |

For local split-screen, set up the squad in the multiplayer menu, choose the
difficulty, and enter `map pp_endline`. Direct map loading preserves the current
rules and skill. The launch configs set the long draw distance for the garage.

The mission archive is `baseq2/operation-endline.pk3`, also installed in
`release/baseq2`. The editable master is `maps/source/pp_endline.map`; its
editor-friendly installed copy is `baseq2/maps/pp_endline.map`. Work on a copy if
editing by hand: regeneration replaces both copies.

## Objectives and route choices

Every difficulty has exactly the same objectives, controls, routes, equipment
and three secrets. Difficulty changes enemy spawning, including the number of
counterattack enemies that must be defeated.

1. **Capture the signal cabin.** Leave the tipped shipping box, collect the
   double-barrel shotgun beside the bridge or on the foam-stair landing, and
   choose the elevated maintenance walk or the cardboard freight passages
   beneath the railway. The blue-brick staircase reconnects these approaches
   before the cabin. The cabin has independent north and south entrances.
2. **Divert the train and secure the siding.** Touch the cabin's switch. The
   signal changes from red to green, the train whistles, and the toolbox service
   shortcut opens. Defeat reinforcements from the upper walk, lower passages
   and the far storage area. The arriving locomotive and cars interrupt the
   yard's long firing lane. Both the train's arrival and the cleared
   counterattack are required to unlock the departure control. Reinforcements
   spawn inside closed rooms before the shutters open, so a co-op player cannot
   be killed by an enemy spawning on their position.
3. **Board and depart together.** Resupply on the loading platform. Reach it
   from the cabin walkway, broad southern loading steps, or eastern steps.
   Touch the exposed departure control beside the rear flatcar, then gather
   every living player on that car. Departure never requires a timed jump.
   Remain aboard for the short bridge ride and mission completion.

The signal and departure controls activate by **touching** them. The departure
request persists while waiting for teammates. Dead players do not block the
all-aboard check; living players left on the platform do.

## Encounters and supplies

| Difficulty | Total enemies | Counterattack |
| --- | ---: | ---: |
| Easy | 20 | 6 |
| Normal | 31 | 9 |
| Hard | 40 | 12 |

Easy emphasizes pistol scouts and small close-range pairs. Normal adds rifle
crossfire on the approaches and extra yard defenders. Hard adds heavy gunners
and another reinforcement group. Enemy spawn exclusions use the engine's
standard easy/normal/hard flags; the three matching death counters all unlock
the same boarding objective.

The shipping box supplies the regular shotgun, machinegun, jacket armor,
health, shells and bullets. The **double-barrel shotgun** has a ground-level
alcove with two shell boxes, a dedicated sign, a pickup explanation and nearby
shotgun defenders. An additional copy and shells on the foam-stair landing
ensure the upper approach also introduces it. Both approaches have ammunition and health;
the cabin and platform provide recovery before and after the counterattack.
Co-op weapons remain available to teammates; ammunition and health are shared
finite supplies. The captured train's crates are physical cover.

Three optional secrets reward searching the freight-car floor, the torn label
behind insertion, and the spool/ruler climb above the cabin. They contain armor,
a medic cache, and grenades/ammunition respectively. No secret is required.

The intended exploration/combat length is around 15–20 minutes. That is a
design target, not a measured human playthrough time; combat balance and pacing
should be tuned from playtesting, especially with four players.

## Original assets and authoring

No Quake II game assets or PAK files are used. The level reuses the project's
wood, toy block, plastic, foam and ammunition-crate materials. New concrete,
cardboard, painted train/toolbox metal, rail, sleeper, rubber, signal, sign and
button artwork is generated deterministically with Pillow and the original
Plastic Platoon palette. The whistle and wheel loop are original synthesis.
The underlying GPL engine's entity class names do not imply stock game media.

Generators and provenance:

- `tools/maps/generate_endline.py`: brush geometry and mission entity graph.
- `tools/maps/generate_endline_materials.py`, `endline-materials.json`: editable
  procedural texture source and output hashes.
- `tools/maps/generate_endline_audio.py`, `endline-audio.json`: synthesized audio.
- `ASSET-LICENSE.md`: GPL-2.0-or-later asset terms and existing asset provenance.

One compound `func_train` performs the preview, siding arrival and escape. Its
offstage return loop uses an engine-supported train teleport behind storage
boxes; no player ride uses that teleport. Its negative waits require explicit
dispatch and departure events. A two-input dispatch counter handles players
who reach the switch before the preview finishes. A separate two-input counter
requires train arrival and the defeated counterattack. A final permission
counter requires both that completed objective and a manual departure request,
so climbing around the control cover cannot bypass combat. Native entities preserve
this state in saved games; no new gameplay code is required.

## Rebuild and verify

```sh
python3 tools/maps/generate_endline_materials.py
python3 tools/maps/generate_endline_audio.py
python3 tools/maps/generate_endline.py
python3 tools/maps/build_endline.py --quick --tool /path/to/q2tool --threads 4
python3 tools/maps/verify_endline.py
python3 tools/maps/check_endline_runtime.py --label easy-solo --skill 0 --players 1
python3 tools/maps/check_endline_runtime.py --label normal-coop --skill 1 --players 2
python3 tools/maps/check_endline_runtime.py --label hard-coop --skill 2 --players 2
python3 tools/maps/package_endline.py
```

The delivered preview uses 256-unit lighting patches; full VIS was already
available and is retained. `--quick` produces subsequent test builds with fast
VIS and 256-unit lighting patches. Omit `--quick` for full VIS and finer 128-unit
lighting, or pass `--rad-subdiv 64` for a more detailed lighting build later.
The build helper makes temporary opaque RGBA
copies of RGB textures to avoid an uninitialized-color bug in this local
q2tools-220 compiler's PNG reader. It preserves every RGB pixel and leaves all
source/runtime artwork untouched. The verifier checks compiled collision,
standing player routes, placements, target wiring, skill counters, shared
objectives, original material availability, visibility and lighting. Route
probes explicitly position the train at the siding for boarding checks.

The runtime harness creates a disposable original-assets-only game directory,
uses Xvfb by default, and exercises actual buttons, death counters, squad
assembly, player carriage and completion. It uses cheats to isolate progression
from combat. One-player checks use one connected player in a co-op server to
retain local test control, including native save/load. These checks and
screenshots do not replace a human single-player or co-op combat playthrough.
Reports and screenshots live under `build/endline-qa/`; the
compiler/validation/package evidence lives under `build/maps/pp_endline/`.
