# Giant Ant Test Range

Open the game console and run `exec ant_test.cfg`, or use `map pp_ant_test`
in an existing single-player or co-op session. The range requires the rebuilt
game module with `monster_ant`, and the standalone Plastic Platoon asset pack. Restart after installing the test-range PK3.

Three ants occupy the center and rear lanes on every difficulty. The supply
bay provides weapons, armor and ammunition, and three extra co-op starts are
included. The ants pursue and bite at close range; use the cover and side
lanes to maneuver. Defeating all three displays “ANT RANGE CLEAR” and leaves
the map running. Use `map pp_ant_test` to reset.

The `operation-ant-test.pk3` contains the compiled map, editable source,
launch config, used Sandkeep materials, ant model and skin, and the M60
sounds used by the supplied weapon. It contains no original game PAK data.

Regenerate, compile and package the range with:

```sh
python3 tools/maps/generate_ant_test.py
./compile_map.sh --source maps/source/pp_ant_test.map \
  --basedir baseq2 --tool "$Q2TOOL" \
  --profile release --threads 4 --output-dir baseq2/maps
python3 tools/maps/generate_ant_test.py --verify
python3 tools/maps/package_ant_test.py
```

Set `Q2TOOL` to the installed q2tool executable. The compiler asset directory
must contain the Sandkeep WALs and the project-generated `pics/colormap.pcx`. Release
compilation runs BSP, VIS and RAD and rejects leaks or missing textures. The
verifier reads the compiled BSP and checks source/entity agreement, monster,
player and item placements, supported lanes, all skill settings, target
wiring, visibility and lightmaps. Its report and source/BSP hashes are in
`build/maps/pp_ant_test/verification.json`. These geometry checks do not replace
a live combat playthrough. Packaging requires that exact source and BSP to pass
verification and writes identical archives to `baseq2` and `release/baseq2`.
