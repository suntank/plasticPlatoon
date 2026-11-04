# Operation Nightlight

An original Plastic Platoon bedroom mission for single-player or 2–4 player
co-op. Launch with `exec bedroom_solo.cfg` or `exec bedroom_coop.cfg`.
These configs enable `r_farsee 1` and restart video for the large room's draw
distance. Joining co-op clients must also set `r_farsee 1` and run `vid_restart`
once. For local split-screen, start the normal split-screen co-op session, then
set that draw distance, restart video and enter `map pp_bedroom`.

## Mission

The platoon's radio has gone dark. Recover a power cell from the dresser,
carry it up the red book staircase, and touch the cell slot on the desk radio.
The radio unlocks the ruler bridge and activates extraction. Cross the bridge,
descend the blue books, and rally on the H on top of the toy chest.

- **Start:** a cardboard shoebox command post at the foot of the bed, with four
  spaced spawn points, weapons and ammunition. The under-bed lane provides a
  covered approach into the room.
- **Objective:** climb the green books to recover the dresser's power cell,
  then climb the red books and restore the desk radio. A sign at each station
  and the objective help screen explain the next step.
- **Finish:** a lit extraction pad on the oversized toy chest. Reaching the
  pad before restoring the radio cannot complete the level.

The room measures 4,608 by 3,840 units with a 2,048-unit ceiling; a standing
soldier is only 56 units tall. A raised bed, quilt, pillow, giant bedside lamp,
window with curtains, door, dresser drawers, radio and alphabet blocks establish
scale. Furniture heights range from 400 to 1,008 units. Broad book stairways
have 16-unit risers, so the required route needs no precision jumps or co-op
boosts. Floor cover, under-bed supplies and a toy tunnel give the squad room
to spread out.

Easy/normal/hard have 16/19/22 placed enemies. All objectives and supplies are
available on every difficulty. The power cell uses Quake II's native co-op key
handling; the radio and bridge remain activated for returning players. Weapons,
health and ammo follow the engine's normal SP/co-op pickup rules. This is one
self-contained mission: extraction opens the standard intermission, and
continuing starts a fresh run of `pp_bedroom`.

## Source and build

The editable source is `maps/source/pp_bedroom.map`. Its generator is
`tools/maps/generate_bedroom.py` (Python 3 and Pillow). Regeneration overwrites
the source, route JSON and this mission's textures. It reuses the existing
Sandkeep brush writer but does not change Sandkeep's files or require its art.
WAL textures provide legacy compatibility and PNGs provide full-color artwork.

```sh
python3 tools/maps/generate_bedroom.py
# Stage textures/bedroom and an authentic loose pics/colormap.pcx in the basedir.
./compile_map.sh --source maps/source/pp_bedroom.map \
  --basedir build/bedroom-assets \
  --tool /home/austin-morgan/Documents/q2tools/Linux64/q2tool \
  --profile release --threads 4 --build-dir build/bedroom-builds \
  --output-dir build/nightlight-release/maps
python3 tools/maps/verify_bedroom.py
python3 tools/maps/package_bedroom.py
```

The package contains this mission's source, BSP, configs and original materials;
no licensed game data. The installer places `operation-nightlight.pk3` in the
project's baseq2, release/baseq2 and the current user's ~/.yq2/baseq2. Restart a
running engine so it discovers the new archive.

## Verification

`verify_bedroom.py` checks the compiled standing-player and pickup hulls, six
walking routes, stair clearance and floor support, difficulty availability,
source/BSP entity agreement, key wiring, the disabled extraction trigger, and
closed/open bridge collision. Reports live in `build/maps/pp_bedroom`.

For real-engine screenshots in an isolated runtime:

```sh
python3 tools/maps/capture_sandkeep.py --map-name pp_bedroom --farsee \
  --map build/nightlight-release/maps/pp_bedroom.bsp --materials baseq2 \
  --assets /home/austin-morgan/.yq2/baseq2 --label bedroom-final \
  --output-root build/bedroom-qa --views tools/maps/bedroom_views.json
```

Camera captures and static route checks are not a complete human playthrough
or a four-client network test. Difficulty and co-op resource balance can be
tuned after playtesting.
