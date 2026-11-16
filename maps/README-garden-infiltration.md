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

The shipped `operation-garden-infiltration.pk3` and loose BSP contain the latest
manually saved mission published on November 16, 2026. Its matching editable
and runtime MAPs, design metadata, translation receipt and full BSP/VIS/RAD
build receipt are inside the archive. Exact source/BSP/package hashes are
recorded in `maps/garden-infiltration-status.json`.

The preceding map revision averaged 33.78 FPS on normal and 32.50 FPS on hard
in native four-player Pi combat tests with players in separate regions.
The user accepted the average FPS result and requested this subsequent map
publication without rerunning tests. Those measurements apply to the prior
map hash; this publication has not repeated gameplay, stress or mission audits.
See `doc/performance/pi-profile-20261116.md` for measurement identities and limits.

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

The November 16 publication records live in `build/garden-publish-20261116`;
the preceding profiling records live in `build/garden-combat-opt-20261116`.
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
The November 16 publication was assembled directly from the full compiled
output with matching source and asset dependencies, without rerunning those
audits at the user's request; its build receipt records that distinction.
Detached extra `worldspawn` brush containers are treated as compiler-only
`func_group` geometry in the private compile copy, without changing their
brushes or the editable source.
