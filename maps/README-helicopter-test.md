# Plastic Helicopter Test Range

Build the current client, game module and assets, then launch the range:

```sh
make -j4 DEBUG= client game ref_gl1 ref_gl3 assets
./release/quake2 +exec helicopter_test.cfg
```

In an existing single-player session, use `exec helicopter_test.cfg` or
`map pp_helicopter_test`. The updated game module/client, Plastic Platoon asset
pack and original Quake II game data are required. The `assets` target installs
the range package into `release/baseq2` alongside the main model pack.

Three tan molded helicopter gunships hover above a large toy sandbox. Their
main and tail rotors turn independently. They strafe and retreat from nearby
targets, fire short paired machinegun bursts, and launch paired green rockets
when they have enough range. Destroying a helicopter sends it tumbling toward
the ground before a series of explosions removes it.

The southern supply bunker has a roof against plunging fire, a rocket launcher,
M60 (`weapon_chaingun`), heavy armor, health, six boxes of rockets and six boxes
of bullets. Exit either side into the broad flank lanes. Tall toy barricades
break firing lines, and two small roofed shelters provide additional cover.
All three helicopters appear on every difficulty. Defeating them displays
“AIR RANGE CLEAR” and leaves the map running. Use `map pp_helicopter_test` to
reset. Three additional co-op starts are provided.

The ready-to-use `operation-helicopter-test.pk3` includes the compiled map,
editable source, config, used Sandkeep materials, helicopter models/skin,
existing rocket model/skin and M60 audio. Baked neutral sunlight and ambient sky light keep the tan plastic readable
without removing shadows. The sky uses the stock `unit1_` skybox
from the user's original game data. No original PAK data is redistributed.

Rebuild the editable source and compile with an installed q2tool executable:

```sh
python3 tools/maps/generate_helicopter_test.py
./compile_map.sh --source maps/source/pp_helicopter_test.map \
  --basedir "$COMPILE_BASEQ2" --tool "$Q2TOOL" \
  --profile preview --vis --threads 4 --output-dir baseq2/maps
"$Q2TOOL" -rad -subdiv 256 -threads 4 -basedir "$COMPILE_BASEQ2" \
  baseq2/maps/pp_helicopter_test.bsp
python3 tools/maps/generate_helicopter_test.py --verify
python3 tools/maps/package_helicopter_test.py
```

`COMPILE_BASEQ2` must contain the existing Sandkeep WALs and an authentic
`pics/colormap.pcx`; `Q2TOOL` is the installed compiler executable. The first
command compiles BSP and full VIS and rejects leaks or missing textures. The
explicit RAD step bakes four light bounces, the source-defined neutral sunlight
(70 direct, 24 ambient), and interior/shelter lamps. The 256-unit radiosity
patches keep the large sky practical to bake while preserving the usual
16-unit lightmap resolution. These are the shipped range's lighting options.
Generation overwrites edits to the MAP source; edit the generator's `BRUSHES`
and `ENTITIES` definitions to preserve layout changes across rebuilds.

Independent verification reads the compiled BSP. It checks source/entity
agreement, helicopter and pickup placement, supported player routes, complete
main-rotor clearance, all initial gun/rocket firing lines into every protected
player start, all skill settings, target wiring, visibility and lighting.
The report is `build/maps/pp_helicopter_test/verification.json`. These static
geometry checks complement the gameplay tests and do not claim a human combat
playthrough. Packaging requires verification for the exact source and BSP.

Run the production gameplay regression suite with:

```sh
tests/helicopter/run_tests.sh
```

It checks target acquisition, flight and patrol, rotor transforms/visibility,
tail-rotor interpolation, actual bullets and rockets, firing safety and
cooldowns, crash gravity/impact/timeout, attachment cleanup and saving/loading
during both attacks and both stages of the crash.
