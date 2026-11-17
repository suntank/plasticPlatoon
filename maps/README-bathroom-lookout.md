# Operation Sink Duty

Load the graybox with `map pp_bathroom_lookout` or run `./release/play-portable.sh +map pp_bathroom_lookout` from the repo root. For local co-op, set up the squad before issuing the map command.

The faucet and red flag mark the destination from the tile floor. The ABC staircase takes twenty 16-unit steps up the lookout's firing lane. Behind the pump bottle, a towel leads to two short jumps across the bottle caps and soap dish. Both approaches open onto the sink rim. Step off its front edge onto the hanging towel to return to the mat. Rally on the marked pad by the red flag to finish.

## Desktop playtest

- Completed each approach from a fresh solo start on normal skill in the desktop game, using scripted movement, aiming and pistol fire with cheats off. The ABC run needed no jumps and finished with 56 health. On the bottle run the lookout held position through both jumps. The player flanked it from behind the soap and finished with 102 health including the small pickup.
- Ran the towel shortcut back down, deliberately jumped wide of the second bottle, walked around the foot of the towel, climbed back up and finished. The packaged map awarded one goal, showed intermission, then loaded Operation Garden Ghost after a keypress.
- Spawned four local co-op players at separate spots on the tile. In a separate placement-assisted trigger check, three players on the pad waited for the fourth. Intermission started when the fourth entered. Route and combat playthroughs were solo. Testing used a desktop PC only.

## Editing and rebuilding

Edit `maps/source/pp_bathroom_lookout.map` directly in TrenchBroom's Quake 2 format. From the repo root, prepare the same private compiler textures used for the garden build and run full BSP, VIS and RAD.

```sh
PYTHONPATH=tools/maps python3 -c 'from pathlib import Path as P; from build_endline import prepare_assets; prepare_assets(P("maps/source/pp_bathroom_lookout.map"), P("build/bathroom-qa/compile-assets"))'
./compile_map.sh --map pp_bathroom_lookout --profile release \
  --tool ~/q2tools-220/build/q2tool --basedir build/bathroom-qa/compile-assets \
  --rad-subdiv 128 --rad-ambient 32 --output-dir baseq2/maps
(cd baseq2 && zip -q -X operation-sink-duty.pk3 maps/pp_bathroom_lookout.bsp)
cp baseq2/operation-sink-duty.pk3 release/baseq2/
```

The operation pack carries the BSP. Its materials come from the existing Plastic Platoon packages.
