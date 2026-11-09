# Mission 01: Operation Sandstorm

Infiltrate Sandcastle One, destroy the radio, fight through the rooftop defenses,
and assemble the living squad at the extraction helicopter. This version includes
four giant ants. Start it with `exec sandstorm_solo.cfg` or
`exec sandstorm_coop.cfg`; for local split-screen, start co-op first and then
enter `map pp_sandstorm`.

The latest edited map is `baseq2/maps/pp_sandstorm.map`. It includes the user's
November 8 geometry and encounter changes; `maps/source/pp_sandstorm.map` is an
older snapshot and must not replace it. The sandbox WALs are built from the
existing sandbox artwork using `python3 tools/maps/build_sandstorm_wals.py`;
Pillow is required.

The game module must include the Sandstorm helicopter, extraction and cinematic
entities and the giant ant. `sh tests/sandstorm/run_tests.sh` checks the mission
entities and save/load. Map source, BSP and route verification must pass before
`tools/maps/package_sandstorm.py` installs the mission. That older packaging tool
currently selects `maps/source/pp_sandstorm.map`; do not use its defaults to
install the newer edited level.

The preview package is `release/baseq2/operation-sandstorm-preview.pk3`. The
moved map had lost the helicopter's departure path; two original path corners
were restored. The untouched moved file is backed up locally under
`build/maps/pp_sandstorm/backups/user-moved/pp_sandstorm.map` (build files are
not tracked). The adrenaline
pickup temporarily uses the existing large-health model, and the explosion
sound uses the existing grenade explosion. These are fallback assets.

The old route verifier was written for the earlier geometry and reports blocked
routes in the edited map; these require investigation before treating the level
as fully verified. A successful initial render is not a playthrough.

## Visibility and performance

The November 8 installed map used fast VIS: its visibility lump exactly matched
an independent `q2tool -vis -fast` build. It exposed an average of 428 of 513
clusters (83.4%), including 500 clusters from the drop zone. This makes the
renderer and server consider much more hidden geometry and more hidden entities.
The full-VIS rebuild reduces the average to 252 clusters (49.1%), 41.1% fewer,
without changing geometry, lighting or gameplay entities. Use full VIS for
playing/release builds; reserve fast VIS for quick editor previews.

To rebuild full visibility while retaining the exact existing lighting, geometry,
collision and mission entities:

```sh
python3 tools/performance/rebuild_visibility.py \
  --source baseq2/maps/pp_sandstorm.map \
  --bsp baseq2/maps/pp_sandstorm.bsp \
  --tool /home/austin/q2tools/build/q2tool \
  --basedir baseq2 --threads 2 \
  --output build/visibility/pp_sandstorm.bsp
```

Substitute the compiler path on another machine. The tool compiles BSP and full
VIS, checks that every geometry/entity lump still matches the original, then
writes a separate candidate BSP and `.visibility.json` report. It preserves all
original lumps except visibility, including baked lighting and face lightmap
metadata. If the source geometry changed, it refuses the transfer; use
`compile_map.sh --source baseq2/maps/pp_sandstorm.map --tool /path/to/q2tool`
for a complete BSP, full VIS and lighting rebuild instead.

Installation must update both loose `maps/pp_sandstorm.bsp` and its matching
entry in `operation-sandstorm-preview.pk3` in each playing directory (`baseq2`
and `release/baseq2`). The package takes precedence over loose content. Preserve
all other package entries and keep a backup of the previous BSP/package.
