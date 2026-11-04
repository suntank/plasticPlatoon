# Rocket Soldier Test Range

Restart the rebuilt game and run `exec rocket_test.cfg` in the console, or
`map pp_rocket_test` in an existing single-player session.

`monster_soldier_rocket` uses the existing enemy body with the actual player
rocket launcher fitted to all 475 animation frames. It shares the heavy
gunner's 180 health, slow walk, squat, collision recovery and pain reactions.
It plants itself for about 0.7 seconds, fires one 60-damage rocket at 450 units
per second, then rises and waits 2.5 seconds before another deployment.
Rockets have an 80-unit splash radius. It refuses shots within 224 units,
backs away when crowded, and checks the launcher and target for obstructions.
Heavy hits can interrupt its windup. It never fires while walking or dying.

The range contains three rocket soldiers, tall cover, broad flank lanes, a
protected supply bay with a rocket launcher and ammunition, and flank health
caches. Defeating all three displays RANGE CLEAR. Co-op starts are provided.
The existing M60 test range is also available as `map pp_heavy_test`.

The deterministic `operation-rocket-test.pk3` includes the BSP, editable MAP,
config, this guide, and only the materials used in this map. The launcher model
ships in `plastic-platoon.pk3`. Original Quake II data supplies rocket audio.

Rebuild the source, BSP and package:

```sh
python3 tools/maps/generate_rocket_test.py
./compile_map.sh --source maps/source/pp_rocket_test.map \
  --basedir build/sandkeep-assets \
  --tool /home/austin-morgan/Documents/q2tools/Linux64/q2tool \
  --profile release --threads 4 --output-dir baseq2/maps
python3 tools/maps/generate_rocket_test.py --verify
python3 tools/maps/package_rocket_test.py --install-user
```

The verifier checks compiled placements, supported walking routes, difficulty
flags, completion wiring, source/BSP agreement and VIS/lightmaps. Packaging
requires a passing verification of the exact source and BSP. The archive is
installed into project/release baseq2 and optionally `~/.yq2/baseq2`.

Rebuild or verify the launcher attachment with the asset conversion environment:

```sh
python tools/assets/build_heavy_gunner.py --weapon rocket --review
python tools/assets/build_heavy_gunner.py --weapon rocket --verify
```
