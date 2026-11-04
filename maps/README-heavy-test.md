# Heavy Gunner Test Range

Open the game console and run `exec heavy_test.cfg`, or use `map pp_heavy_test`
in an existing single-player session. The range uses the current game module's
`monster_soldier_heavy` enemy and the existing Sandkeep materials.
The ready-to-use `operation-heavy-test.pk3` contains this range's map, config,
only its required materials, and the existing M60 shot/end sounds. The updated
game module and client are required. Restart a running engine after installing
the archive so it discovers the new files.

The protected south bay supplies an M60 (`weapon_chaingun`), six boxes of bullets,
a shotgun, armor and health. Three heavy gunners face south: the first in the
central lane, the second beyond the west divider, and the last in the northeast
corner. They appear on every difficulty. Full-height cover, lower barricades,
and open side lanes let you test deployment, sustained fire, pursuit and flanking.
Two more ammunition/health caches sit on the flanks. Defeating all three displays
“RANGE CLEAR” and leaves the map running for inspection. Run `map pp_heavy_test`
to reset. Three extra co-op starts are also provided.

The distinct `monster_soldier_heavy` has 180 health, 250 mass, and a slow walk
and chase of about 33 units per second. It crouches to deploy for about 0.2
seconds, fires 1.5-second M60 bursts at 10 rounds per second and 6 damage per
round, then rises with a one-second cooldown. Firing requires solid ground,
stopped movement, a target in front, and a clear muzzle. Its slow turn allows
flanking; hits of at least 15 damage can interrupt a burst, with a two-second
pain debounce.

The source is directly editable and can be regenerated with Python 3, without
third-party packages:

```sh
python3 tools/maps/generate_heavy_test.py
./compile_map.sh --source maps/source/pp_heavy_test.map \
  --basedir build/sandkeep-assets \
  --tool /home/austin-morgan/Documents/q2tools/Linux64/q2tool \
  --profile release --threads 4 --output-dir baseq2/maps
python3 tools/maps/generate_heavy_test.py --verify
python3 tools/maps/package_heavy_test.py --install-user
```

The compile asset directory must contain the existing `textures/sandkeep/*.wal`
files and an authentic `pics/colormap.pcx`. The generated source does not change
those materials. Release compilation runs BSP, full VIS and RAD and rejects leaks
or missing textures. The output is `baseq2/maps/pp_heavy_test.bsp`; the build
manifest and compiler logs are under `build/maps/pp_heavy_test`.
The verification command checks source/BSP entity agreement, spawn and pickup
hulls, five walking routes with floor support, all three difficulty settings,
target wiring, and compiled visibility/lightmaps. Its report is
`build/maps/pp_heavy_test/verification.json`. It reuses the existing Sandkeep BSP
reader and checks compiled geometry independently of this map's brush writer.

Packaging checks the exact source/BSP hashes against the passing verification,
uses fixed archive timestamps, and installs identical archives into `baseq2` and
`release/baseq2`. Add `--install-user` to install into `~/.yq2/baseq2` as well.
The source WAVs live in `baseq2/sound/weapons/m60{1,2,3,4,5,end}.wav`. To import
those existing sounds the first time, use
`python3 tools/maps/package_heavy_test.py --sound-source ~/.yq2/baseq2/sound/weapons`.
No original game PAK data is included in this archive.
