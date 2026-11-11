# Operation End of the Line

Land on a garage windowsill, fight through the freight lanes beneath the toy
railway, and escape aboard the ammunition train.
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
rules and skill. Current OpenGL renderers extend the view to the garage's far
wall automatically. The launch configs also set the long draw distance for
older builds. Restart the game after installing a rebuilt archive and start a
fresh run, since existing saves reference the previous brush geometry.

The mission archive is `baseq2/operation-endline.pk3`, also installed in
`release/baseq2`. The editable master is `maps/source/pp_endline.map`; its
editor-friendly installed copy is `baseq2/maps/pp_endline.map`. Compile the
editable master directly to keep the TrenchBroom layout and garage finale.

## Objectives

1. **Enter through the window.** The green dropship leaves through the opening
   behind the squad. Descend into the garage and follow the freight route.
   Falling out the window is lethal.
2. **Fight to the far station.** Cardboard barricades and ABC blocks turn the
   floor into a winding route with several crossings under the track. Follow
   the floor lanes to the ramp at the far end of the garage. The train is
   already waiting at the siding.
3. **Board and shoot the switch.** Resupply at the station and drop from the
   gantry into the armored rear car. Its high walls keep the squad aboard.
   When every living player is inside, the switch cover blows open. Shoot the
   exposed switch to depart.
4. **Defend the bridge.** The train stops between two raised catwalks. The
   first wave boards on the right and the second on the left, facing the
   locomotive. Clear both waves to get moving again.
5. **Clear the garage ambush.** The train stops while the door opens. With the
   locomotive ahead, the first wave boards on the left, the second on the right,
   and the third from both sides. Use the staggered cases as cover. The train
   departs when the last attacker dies.
   Watch it clear the garage and leave the intermission camera's view.

| Difficulty | Station reinforcements | Bridge ambush | Garage ambush |
| --- | ---: | ---: | ---: |
| Easy | 6 | 6 | 9 |
| Normal | 9 | 8 | 12 |
| Hard | 12 | 10 | 15 |

The freight route provides weapons, ammunition and health. There are
additional supplies at the station and inside the armored car. Co-op weapons
remain available to teammates, while ammunition and health are shared.
The optional inspector cache above the cabin lacks an approach in this layout.

## Original assets and authoring

No Quake II game assets or PAK files are used. The level reuses the project's
wood, toy block, plastic, foam and ammunition-crate materials. New concrete,
cardboard, painted train/toolbox metal, rail, sleeper, rubber, signal, sign and
button artwork is generated deterministically with Pillow and the original
Plastic Platoon palette. The whistle and wheel loop are original synthesis.
The underlying GPL engine's entity class names do not imply stock game media.

Generators and provenance:

- `tools/maps/generate_endline.py`: original generated layout before the
  TrenchBroom edits.
- `tools/maps/generate_endline_materials.py`, `endline-materials.json`: editable
  procedural texture source and output hashes.
- `tools/maps/generate_endline_audio.py`, `endline-audio.json`: synthesized audio.
- `ASSET-LICENSE.md`: GPL-2.0-or-later asset terms and existing asset provenance.

The compound `func_train` starts at the siding. The all-aboard volume
detonates the covered switch, and the shootable button starts the train.
At the bridge and garage, sealed bays release soldiers onto elevated platforms.
Monster jump triggers launch them over the armored rim. Each stop has its own
skill-specific death counter. The intermission moves players to the camera
before the train continues west, keeping the moving train origin and the
player views within the engine's coordinate range.

## Rebuild and verify

```sh
python3 tools/maps/generate_endline_materials.py
python3 tools/maps/generate_endline_audio.py
python3 tools/maps/build_endline.py --quick --tool /path/to/q2tool --threads 4
python3 tools/maps/verify_endline.py
python3 tools/maps/check_endline_runtime.py --label easy-solo --skill 0 --players 1
python3 tools/maps/check_endline_runtime.py --label normal-coop --skill 1 --players 2
python3 tools/maps/check_endline_runtime.py --label hard-coop --skill 2 --players 2
python3 tools/maps/package_endline.py
```

The delivered preview uses fast VIS and 256-unit lighting patches. Omit
`--quick` for full VIS and finer 128-unit lighting, or pass `--rad-subdiv 64`
for more detailed lighting. The bake uses low ambient fill to keep the car
interior and window landing legible.
The build helper makes temporary opaque RGBA
copies of RGB textures to avoid an uninitialized-color bug in this local
q2tools-220 compiler's PNG reader. It preserves every RGB pixel and leaves all
source/runtime artwork untouched. The BSP stage uses the compiler's large
bounds option for the scenery beyond the garage door. The verifier checks
compiled collision, player routes, placements, wheel contact, train coordinates,
target wiring, skill counters, original material availability, visibility and
lighting. Route probes position the train at the siding for boarding checks.

The runtime harness creates a disposable original-assets-only game directory,
uses Xvfb by default, and exercises actual buttons, death counters, squad
assembly, player carriage and completion. It uses cheats to isolate progression
from combat. One-player checks use one connected player in a co-op server to
retain local test control, including native save/load. These checks and
screenshots do not replace a human single-player or co-op combat playthrough.
Reports and screenshots live under `build/endline-qa/`; the
compiler/validation/package evidence lives under `build/maps/pp_endline/`.
