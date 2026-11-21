# Attic — The Rooms Remember

The squad climbs into an attic with a floor hatch, a steamer trunk, and exposed rafters. From there, overlapping pieces of a building take over. Ceiling grids drift out of alignment. Plaster columns interrupt the long views, walls end halfway through a span, and rows of lights continue into dead ends. Carpet climbs a carton ramp to a bridge while a second passage runs underneath. A floating landing carries one familiar chair and another hangs upside down. Farther in, a break in the ceiling exposes the old rafters again.

Open the map with `map pp_attic`. The editable map is [pp_attic.map](source/pp_attic.map), and the portable build uses [operation-attic.pk3](../baseq2/operation-attic.pk3).

## Mission

- **Find the M1 Flamethrower.** Brass strips mark major thresholds in both directions. The route leads from the pillar field through the storage stacks, across the upper bridge, past the rafters, and down to the counter hall. The last folded passage leads to the cool-lit supply trunk. The waiting hall, lower passage, and side lobbies offer detours, scattered spiders, and supplies.
- **Survive the chase.** A scrape sounds ahead near the upper landing. The Melted Soldier joins the chase at the concourse. Ordinary hits briefly stagger it. Direct flame and burning napalm can kill it. Its footfalls and breathing drop out for just over two seconds after it loses sight of you. They return sooner if it spots you again.
- **Return to the hatch.** Picking up the flamethrower enables extraction. The Melted Soldier can be alive when you leave. In co-op, the shutter closes after all living players reach the hatch.

## Editing and rebuilding

The [Attic builder](../tools/maps/build_attic.py) defines the hand-positioned spaces, interrupted floors, fixtures, and furniture reused from the earlier attic. It compiles the MAP with full VIS and RAD and refreshes the mission pack. The builder needs Pillow, NumPy, and a local q2tools-220 executable. Regenerate the MAP only when you want to replace the editable source with the layout in the builder.

```sh
python tools/maps/build_attic.py --tool /path/to/q2tool
make -j4 game
cp baseq2/operation-attic.pk3 release/baseq2/
./release/play-portable.sh +map pp_attic
```

The hand-positioned `info_melted_path` points follow walkable lines, including both ends of the ramps. A point's `target` names its parent toward the hatch and `count` is its depth in that route tree. Keep the lines between connected nodes clear for the Melted Soldier's 32-unit-wide, 85-unit-tall hull. Place waypoints at different elevations on their respective floors so the Soldier follows a ramp instead of trying to walk through the deck.
