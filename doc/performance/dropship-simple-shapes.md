# Authored friendly green dropship

The player's green transport has an original low-poly body and main rotor.
The wide troop cabin has framed cockpit glazing, star-marked cargo doors and
step sponsons. The shrouded tail fan, molded skids and swept main rotor tips
read from side and overhead views. Both meshes use one 256 by 256 RGB atlas.

Both models use a single static frame. The existing client attachment still
places and spins the separate rotor around the original axle and body socket.
The model preserves the existing mission origin and large clearance envelope.
Route speeds, waits, visibility, insertion/extraction triggers and non-solid
behavior keep their existing values.

## Asset budgets

| Part | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| Body | 2,580 | 680 | 73.6% |
| Main rotor | 411 | 80 | 80.5% |
| Combined | 2,991 | 760 | 74.6% |

`dropship-manifest.json` records every output hash, decoded geometry count,
quantization check, material group, bound and attachment anchor. Geometry
counts measure asset work; device frame rates require a controlled comparison.

## Ownership and existing missions

The friendly entity uses dedicated files:

```text
models/vehicles/platoon_dropship/body.md2
models/vehicles/platoon_dropship/main_rotor.md2
models/vehicles/platoon_dropship/green.png
```

The old `models/monsters/boss2/` body, rotor and shared skin also serve the
legacy enemy. They remain unchanged and retain their existing ownership.
The new owner adds three files, with no legacy model or texture retirement.
The optional Pi actor overlay covers four other actor bodies and cannot
restore the former friendly transport. The mission archives contain four
friendly movers, with two in Sandstorm and one each in Endline and Garden
Infiltration.

`build_dropship_overlays.py` synchronizes the three dedicated files in
`operation-endline.pk3`, `operation-garden-infiltration.pk3` and
`operation-sandstorm-preview.pk3`. It verifies 91 immutable Endline members,
46 Garden Infiltration members and 55 Sandstorm members. The separate
health archive gate verifies Sandstorm's booster model and atlas.

Each shared-archive gate excludes only the fixed, registered paths of the
other owner and verifies its own exact canonical payload plus all immutable
members. Both gates together verify the five authored payload files. A shared
receipt deliberately excludes a volatile whole-ZIP hash, allowing either
owner to update its assets without invalidating the other's proof. The Endline
and Garden Infiltration receipts also record each complete archive hash. Arbitrary exemption paths,
unregistered peer paths and exemptions in the wrong archive are rejected.

All archive plans are validated before the first write. Each changed archive
is installed with a same-directory atomic replacement; there is no claimed
transaction across multiple archives. Existing member metadata and archive
comments are retained. No map generator, compiler or mission packager runs
during sync. In particular, older Sandstorm packager defaults must not be
used to replace the newer edited map. Future mission packaging collects the
dedicated body, rotor and their skin dependency explicitly.

## Rebuild and verify

```sh
python3 tools/assets/build_dropship.py
python3 -S tools/assets/verify_dropship_runtime.py
python3 -S tools/assets/build_health_overlays.py
python3 -S tools/assets/build_dropship_overlays.py
python3 -S tools/assets/build_health_overlays.py --verify
python3 -S tools/assets/build_dropship_overlays.py --verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_dropship.py --verify
python3 -S tests/assets/test_dropship_overlays.py
python3 -S tests/assets/test_health_overlays.py
python3 -S tests/assets/test_projectile_overlays.py
python3 tests/assets/test_md2_assets.py
python3 tools/assets/build_platoon.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

Normal Make/CMake builds verify the dedicated owner, synchronize its mission
copies and verify both Sandstorm owners before packaging. A full asset build
generates the dedicated model pair and atlas before archive synchronization.
The old converter cannot claim these registered paths. Archive fixtures cover
edited-map refusal, source verification, preflight across both missions,
exact idempotence, metadata preservation, managed-file repair and independent
peer updates in either order. Existing health/projectile overlay fixtures
remain part of the focused checks.

## Native visual review

The isolated route fixture and private file controls can be reproduced with:

```sh
python3 tools/performance/capture_dropship.py \
  --renderer gl3 --output build/dropship-review --missions
# Use --renderer gl1 or --renderer soft for the same native gallery/routes.
# Reuse the generated fixture with --fixture <existing pp_dropship_qa.bsp>.
# --missions-only limits a follow-up to the existing mission scenes.

OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_dropship.py
sh tests/sandstorm/run_tests.sh
```

The capture tool compiles only its private route fixture. It copies the existing
Sandstorm and Endline BSPs and their mission archives without rebuilding them.
Its opt-in game-layout helper reads ship state and invokes only the existing
friendly ship's `use` callback. Mission objective and combat gates are bypassed
for scene setup; this is not a complete mission playthrough. Each report keeps
the exact engine, game, renderer, core archive, mission archive and BSP hashes,
plus native ship state, actual rendered attachment transforms and camera state.

The revised transport was captured in the GL3 gallery, on the Sandstorm and
Endline routes and during Garden Infiltration's departure. Local reports are
in `build/dropship-final` and `build/dropship-final-garden`. The GL1 gallery
is in `build/dropship-final-gl1`. Clearance checks sample all three maps
with the decoded MD2 positions and the full rotor sweep.

### Original transport rollout

Final GL1 and software reports are
`build/dropship-qa-gl1-final/report.json` and
`build/dropship-qa-soft-final/report.json`; both completed successfully with eight
images and three native checks. The eight gallery/route views in
`build/dropship-qa-gl3-verified/report.json` cover the same work in GL3. Front,
side, rear, high and underside views show the fuller cabin, canopy, doors,
tail, pods, skids and rotor. The rotor advances while parked, and the native
inbound and outbound routes reach their exact endpoints and parked states.
The software renderer has its expected darker palette; its silhouettes and
attachments remain intact. These are host visual checks, not Pi benchmarks.

Selected existing-mission images were inspected separately. The clear
Sandstorm insertion side view is
`build/dropship-qa-missions-verified2/screenshots/pp_sandstorm-insertion.png`.
That directory also contains clear extraction-flight and Endline
insertion/flight views. Those photographs pause the world at observed native
route positions and use a private observer camera chosen against the existing
BSP. The unpaused parked extraction view is
`build/dropship-qa-gl3-verified/screenshots/pp_sandstorm-extraction-parked.png`.
These show the authored craft at the original insertion locations, over the
Sandstorm pad and leaving the Endline opening. The earlier occluded insertion
frame and a buffered paused parked-extraction frame are excluded from visual
evidence; automated state success alone does not establish a useful image.

All final captures used core archive SHA256
`96b6f194c85a8160bef32cb3b68380670ea3ae7bf681fd9149b2ddf3f4cca6fa`
and game module SHA256
`00dea278df171b793919b8287108c298a816823c2d4a7502b6a0894f96e938d1`,
including the saved-game media rebind. Nine asset checks cover closed decoded
geometry, original envelope, socket alignment through all rotor phases and
unchanged enemy assets. The production saved-game regression covers all five
route states and proves only the two friendly model indices change on load.

`build/dropship-route-clearance.json` records 406 read-only samples against the
current compiled mission BSPs, using the decoded body, all rotor phases,
native segment orientation and hover allowance. Insertion and approach routes
have no scenery contacts. The final Sandstorm outro retains the same 42 legacy
contacts after crossing the outer sky boundary, with no new interior blocker.
