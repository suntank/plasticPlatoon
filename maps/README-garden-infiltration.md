# Operation Garden Ghost

`pp_garden_infiltration` is a mission version of `pp_garden`.
The original Garden source and BSP are retained as a separate map. The mission
source includes later manual terrain, cover and encounter edits; its original
four player starts remain intact. The generator's initial additive version
preserved all original brushes and entities, but regenerating would discard the
later manual edits.

The friendly helicopter has just dropped off the squad and departs after five
seconds. Follow the winding gardens, use the earth banks and bunkers to break
sight lines, and avoid waking every ambush guard at once. Reach the closed
sandbox perimeter and assemble every living squad member at the gate. Completion
leaves the squad outside; the sandbox interior belongs to a later mission.

The field shotgun cache is approximately halfway along the walking route.
Its weapon remains for co-op teammates. All enemies are pistol or shotgun
soldiers, with shotgun soldiers guarding the narrow passes and final bunker.
Supplies are limited to hand grenades, the shotgun, shells, small/regular health,
armor shards and 25-point jacket armor. Ammunition and health are shared.

The shipped `operation-garden-infiltration.pk3` and loose BSP retain the earlier
verified playable mission. Its complete matching editable and runtime MAPs,
design metadata and translation receipt are inside that archive. The newer
`maps/source/pp_garden_infiltration.map` is work in progress: a full release
compile succeeded, but seven soldier starts and three supplies intersected
solids or void, and the recorded walking route failed on 13 segments. This
candidate is not shipped. Exact source/BSP/package hashes and failed placements
are recorded in `maps/garden-infiltration-status.json`. Previous Pi performance
measurements apply to the shipped BSP, not the newer manual edits.

Load `map pp_garden_infiltration` after local squad setup, or use
`exec garden_infiltration_solo.cfg` / `exec garden_infiltration_coop.cfg`.

The editable mission is `maps/source/pp_garden_infiltration.map`, with route and
verification metadata in `maps/source/pp_garden_infiltration.design.json`. Its generator
reads the base Garden without writing it. Regenerating the variant overwrites
manual changes to the variant, so preserve those before running it.

The mission uses existing original project textures, models and audio; the
three new labels use the project's procedural lettering and palette. Grass
clumps use sparse opaque brushes. Earth banks are world geometry to improve
occlusion and avoid a separate renderer model for each prop. Static baked
lighting keeps covered sentries readable without adding dynamic lamps.

Build and verification records live in `build/maps/pp_garden_infiltration`.
The separate archive is `operation-garden-infiltration.pk3`; it never replaces
the base Garden map or its package. Performance evidence records the native
Pi framebuffer, exact map hash, capture positions, quality and protection mode.

The base artwork lies partly beyond the engine's +/-4096 player-coordinate
range. The build creates a private copy translated by (-3200,-2000,0), with
texture shifts compensated. This rigid translation changes no shape, distance
or route. The editable authoring source and original Garden remain unchanged;
the archive also contains the translated runtime MAP for direct inspection.

Rebuild the manually edited mission with
`python3 tools/maps/build_garden_infiltration.py --edited-source`, then package
with `python3 tools/maps/package_garden_infiltration.py`. The build performs
full BSP, full VIS, baked lighting, and independent mission/route/collision
verification. The edited-source audit reports original-preservation drift;
the default audit still requires the generator's strict additive contract.
Failed audits retain the previous playable BSP and cannot be packaged.
Detached extra `worldspawn` brush containers are treated as compiler-only
`func_group` geometry in the private compile copy, without changing their
brushes or the editable source.
