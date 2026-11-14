# Temple

The **multiplayer Temple arena from the Nintendo 64 GoldenEye 007**, rebuilt
as an editable Plastic Platoon level. This is Temple, not the Egyptian
single-player mission. Load `map pp_temple` to explore with the current rules,
or `exec temple_dm.cfg` for deathmatch with a 20-frag / 10-minute limit.
For local play, select Temple in the split-screen match settings. The map
appears automatically after restarting the game with its archive installed.
The launch config enables **spawn farthest** (`dmflags 512`) so four players
joining together use distinct original starts. Direct map loading keeps the
current match rules; enable spawn farthest in those rules for four-player play.

## Layout and scale

The reference preserves all 25 original background room sections, 1,014 surface
triangles, 204 navigation tiles and 37 inter-room portals. The central floor
opening, lower chamber, sloped connecting passages, tall halls, wall recesses,
exterior openings and six vertical sliding doors follow the original coordinates.
The five deathmatch starts and eight weapon sites use the original setup pads.
An exploration start and three co-op starts allow loading outside deathmatch;
there are no enemies or mission objectives.

One uniform conversion applies to every axis: N64 `(x,y,z)` becomes Quake II
`(x,-z,y) * 92/165`. GoldenEye's nominal standing eye is 175 runtime units;
Temple's background coordinates use a 33/70 level scale. This maps the original
82.5-unit background eye height to Quake II's 46-unit standing eye height.
Coplanar triangles are joined only when their union is convex. Brush thickness
extends behind the measured surfaces, preserving the playable room dimensions.
A distant sky shell seals the original background's open sky and backdrop edges.

The geometry targets the original layout at the same apparent player scale.
Gameplay remains Plastic Platoon: its wider collision hull, jumping, movement,
weapons, ammunition, pickup models and door activation differ from GoldenEye.
The eight original weapon slots are mapped, in increasing strength, to two
shotguns, a double-barrel, two machine guns, an M60, a grenade launcher and a
rocket launcher. Original ammunition sites, including shared sites, and the
body-armor site are retained. Doors open on approach and close after 25 seconds.

## Materials and reference provenance

The level reuses `sandkeep/sand_wall`, `sandkeep/sand`, `sandkeep/wood`,
`endline/concrete`, and the existing Sandkeep sky. Lighting is baked for this
engine; it does not reproduce the N64's vertex lighting exactly. No GoldenEye
texture pixels, sounds, characters, weapons, ROM or executable code are included.

Temple's design is by Duncan Botwood / Rare. Its measured geometry and setup
coordinates come from the public
[n64decomp/007 reference records](https://github.com/n64decomp/007/tree/c4356466796c697dfd298010b9bed261f9ed8c6a/assets/obseg),
pinned to commit `c4356466796c697dfd298010b9bed261f9ed8c6a`.
The exact input URLs and SHA-256 hashes are recorded in
`tools/maps/temple_layout.json`. The
[GoldenEye Depot Temple plan](https://goldeneyedepot.com/levels/temple)
provides an independent visual cross-check. This recreation's level geometry
is derived from GoldenEye; it is not newly authored Plastic Platoon geometry.
GoldenEye and Temple's original design remain the work of their respective owners.

## Editable source and rebuild

The editable master is `maps/source/pp_temple.map`. The installed editor copy
is `baseq2/maps/pp_temple.map`; the game uses `maps/pp_temple.bsp` inside
`operation-temple.pk3`. The package is installed into both `baseq2` and
`release/baseq2`. Restart the game after replacing it; named PK3s override loose
BSPs. Regenerating the map overwrites manual editor changes.

```sh
python3 tools/maps/generate_temple.py
python3 tools/maps/build_temple.py --threads 4
python3 tools/maps/package_temple.py
```

The build prepares private, color-correct compiler textures, runs BSP, full VIS
and RAD, and verifies the exact resulting source/BSP hashes before packaging.
`tools/maps/verify_temple.py` checks the compiled collision against independent
reference floors, surface planes, player starts and room connections. Reports
are written to `build/maps/pp_temple`.

For repeatable real-engine views:

```sh
python3 tools/maps/capture_sandkeep.py --map-name pp_temple \
  --map baseq2/maps/pp_temple.bsp --materials baseq2 \
  --views tools/maps/temple_views.json --output-root build/temple-qa \
  --label temple-gl3 --renderer gl3
python3 tools/assets/smoke_standalone.py --map pp_temple \
  --renderer gl3 --renderer gl1 --frames 30 --output-dir build/temple-smoke
python3 tools/maps/check_temple_runtime.py --players 2 4 --label temple-check
```

The runtime check uses disposable game directories and real local clients to
check alive multiplayer starts, rendered views, all six approach-trigger doors,
and missing assets. It uses teleportation to isolate door behavior; it is not
a manual match or a combat playthrough. Use a fresh label for each run.

To refresh the measured reference, download the three pinned C records listed
in the JSON's `sources` into `build/temple-reference` as `temple-bg.c`,
`temple-stan.c`, and `temple-setup.c`, then run
`python3 tools/maps/import_temple_reference.py`. The importer decodes geometry,
navigation and setup coordinates while discarding texture data and display lists.
