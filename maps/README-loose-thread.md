# Operation Loose Thread

Load `map pp_loose_thread` from the console, or run `./release/play-portable.sh +map pp_loose_thread`. For local co-op, set up the squad first and then load the map. The map and its surface materials ship together in `baseq2/operation-loose-thread.pk3`.

Cross a wooden sewing box and release the brass case latch. The button tin opens with one pistol lookout. The cotton reels introduce the field shotgun, a mixed patrol, then the double barrel before the next tray. In the needle book, a stack of cards offers a way onto the first guard’s perch. A rifle and bullets wait beyond the next divider, ahead of the first automatic rifleman. The pin cushion screens the last resupply stop from the latch. Defeating the three latch guards releases the clasp. Gather every living squad member on the brass plate to complete the mission and continue to Garden Ghost.

The main route can be walked from end to end. Optional jumps across three bobbins in the cotton tray and three needle cards in the next tray lead to armor. A missed jump drops the player onto the main route. Check behind the thimble, around the ends of the partitions, and on the buttons for supplies. Weapons stay for teammates in co-op. Health and ammunition are shared.

## Editing and visibility

Edit `maps/source/pp_loose_thread.map` directly in a Quake II map editor. The wooden dividers meet the floor and lid. Staggered openings and low connecting passages make full VIS split the four compartments into local clusters. Buttons, pins, reels and other small props are detail brushes. The lighting is baked. The final clasp is the only moving piece of scenery.

| Compiled-map measure | Loose Thread | Published Garden Infiltration |
| --- | ---: | ---: |
| Source brushes | 173 | 543 |
| BSP faces | 2,733 | 8,175 |
| VIS clusters | 51 | 147 |
| Mean visible clusters | 10.4 | 45.9 |
| Peak visible clusters | 19 | 80 |
| Peak unique world faces in a cluster’s potentially visible set | 992 | 4,988 |

Face counts are measured before camera-frustum culling. The ground-level playtest route covers approximately 14,700 map units. A normal-skill solo run reached the latch with cheats off. After reloading the pre-fight save, the player cleared all three defenders with the double barrel and extracted with 74 health. A separate desktop test exercised both three-jump armor routes. Four local players spawned separately, activated the final ambush, and completed extraction when the fourth living player entered the plate. The co-op check used assisted placement and combat equipment.

## Raspberry Pi Zero 2 W combat test

Four local players fired and turned in separate compartments on the native 240×240 display. The fourth player activated the latch ambush. Each difficulty ran for 90 seconds at normal graphics quality with live AI, dynamic lights, software sound mixing and the Garden benchmark’s extra health and shotgun ammunition. The figures cover the entire display.

| Difficulty | Average FPS | P95 frame time | P99 frame time |
| --- | ---: | ---: | ---: |
| Normal | 35.54 | 33.28 ms | 36.97 ms |
| Hard | 35.92 | 33.13 ms | 36.69 ms |

Both combat captures passed the resource checks with zero process major faults and zero current throttle bits. The benchmark restored the Pi shell. The tested BSP SHA-256 is `3228d745514ba8f72a79316a34318cb7ecea7c1a671cd7002e4af30d2a576ff4`. The private Pi test directory `/data/build-sources/loose-thread-test-NFJDCt2O` contains the exact scene, assets, metadata and raw swap timestamps. [Garden combat measurements](../doc/performance/pi-profile-20261116.md)

## Rebuild

With Python, Pillow, NumPy and q2tools-220 installed, run the following commands from the repository root. The first command is needed only when repainting the procedural materials. The build reads the checked-in MAP, runs BSP, full VIS and RAD, and packages the compiled map and its texture dependencies.

```sh
.venv/bin/python tools/maps/generate_loose_thread_materials.py
.venv/bin/python tools/maps/build_loose_thread.py
cp baseq2/operation-loose-thread.pk3 release/baseq2/
```

Use `--tool /path/to/q2tool` to select a different compiler location.
