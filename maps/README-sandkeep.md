# Operation Sandkeep

An original Plastic Platoon single-player/co-op assault on a sandcastle inside a
wooden sandbox. Load `map pp_sandkeep`, or `exec sandkeep_solo.cfg`. For local
split-screen, create the normal co-op session before loading the map.

Secure the armory and radio controls in either order to open the keep, collect
the staging bunker's rocket launcher, destroy the helicopter, and reach the
landing pad outside the rear sandbox wall. Both gates stay open for returning co-op players.
The map has 23/28/31 enemies on easy/medium/hard, including the helicopter, and
65 loose rockets. Pickups are shared between co-op players.

## Polish pass

- The squad starts on backyard soil and enters through a splintered opening in
  the sandbox wall. The old insertion room and sign are gone. After the gunship
  fight, the rear gate leads through another broken board to an outdoor landing
  pad, with lawn banks, fence pickets, spilled sand and low rally lights.
- Sloping, irregular sandbanks and angled breastworks replace flat drums and
  rectangular cover. Uneven alphabet-block stacks, an oversized spade and wood
  spools establish the toy scale. Two hollow tipped buckets replace repeated
  arena bunkers while preserving covered resupply and the central retreat lane.
- Two fully enclosed supply secrets sit behind shootable, cracked sand walls.
  Their rewards and discovery triggers are inside; breaking a wall alone does
  not award the secret. Covers have 40 health and harmless debris.
- Tapered octagonal towers have coping, a continuous parapet, and battlements
  supported by the actual tower perimeter. Curtain walls have buttresses and
  framed, chamfered entrances. Stair stringers leave the radio approach clear.
- One-shot controls have guarded push pads, a metallic click, readable labels,
  and idle/activated animation. Their lights and mounting brackets are physical
  geometry. Both independent controls are still required to open the keep.
- Wooden rising gates carry their own iron straps, center stile and rivets.
  Their trim moves with them; fixed frames leave room for the raised gates.
- Directional graphics, switches, gate panels and helipad fit whole texture
  tiles. Classic Quake texture shifts use integral UV placement to survive
  compiler rounding. Secret covers share the surrounding wall's UV grid.
- Ceiling fixtures and console work lights improve interior readability.

## Editable source and build

`maps/source/pp_sandkeep.map` is the editable MAP. The matching generator is
`tools/maps/generate_sandkeep.py`; running it overwrites the MAP and the route
JSON. Preserve manual editor changes before regenerating.

Materials live in `baseq2/textures/sandkeep`, the sky in `baseq2/env`. To regenerate
them, run `python3 tools/maps/generate_sandkeep_materials.py` with NumPy and Pillow
installed. The material generator uses the repository's existing PCX palette.

Compile against a directory containing the Sandkeep WALs and an authentic loose
`pics/colormap.pcx` from the installed game data. Do not distribute that support
palette with the level. The staged compile assets used locally are
`build/sandkeep-assets`.

```sh
python3 tools/maps/generate_sandkeep.py
./compile_map.sh --source maps/source/pp_sandkeep.map \
  --basedir build/sandkeep-assets \
  --tool /home/austin-morgan/Documents/q2tools/Linux64/q2tool \
  --profile release --threads 4 --output-dir build/sandkeep-candidate/maps
python3 tools/maps/verify_sandkeep.py \
  --bsp build/sandkeep-candidate/maps/pp_sandkeep.bsp \
  --routes build/maps/pp_sandkeep/route_waypoints.json \
  --bsp-log build/maps/pp_sandkeep/bsp.log
python3 tools/maps/package_sandkeep.py \
  --bsp build/sandkeep-candidate/maps/pp_sandkeep.bsp
```

The packager requires a passing verification report for the exact MAP/BSP hashes,
backs up replaced files under `build/maps/pp_sandkeep/backups`, and updates both
the loose files and `release/baseq2/operation-sandkeep.pk3`. Rebuilding the PK3 is
essential: the engine loads its map ahead of a loose BSP. Restart an already
running game after installing a new package.

## Repeatable visual checks

```sh
python3 tools/maps/capture_sandkeep.py --label architecture \
  --map build/sandkeep-candidate/maps/pp_sandkeep.bsp --materials baseq2 \
  --assets /home/austin-morgan/.yq2/baseq2
python3 tools/maps/capture_sandkeep.py --label interactions \
  --map build/sandkeep-candidate/maps/pp_sandkeep.bsp --materials baseq2 \
  --assets /home/austin-morgan/.yq2/baseq2 \
  --views tools/maps/sandkeep_interactions.json
```

The harness launches the actual engine using Xvfb and Mesa in a temporary runtime.
It preserves game settings/saves, tests the supplied BSP rather than a stale PK3,
and writes named PNGs, a contact sheet, settings, logs and asset hashes into
`build/sandkeep-qa/<label>`. Labels must identify a fresh output directory.
`--renderer gl1` also checks the legacy renderer. The interaction sequence shoots
secret covers and walks into the controls; review its images/logs for successful
state changes. Camera poses use cheat teleportation and are not a playthrough.

The independent verifier checks entity chains on all three difficulties, 94
spawn/pickup hull placements, nine walking routes, closed/open secret visibility
and access, whole-tile graphics, and exposed coplanar faces across brush models.
It also checks exterior starts and extraction, open sky over the outdoor areas,
standing clearance through both board openings, and access to both bucket caches.
These checks cover specific failure modes; screenshot review remains necessary.
The optional art overlay supplies the user's complete toy-soldier models and
pickups to the isolated runtime. It imports no maps, settings or saves and does
not alter those game assets or the engine.
