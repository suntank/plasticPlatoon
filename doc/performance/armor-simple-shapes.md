# Authored armor pickups

Curved shells, cuffs and boot surfaces now use the selective shading described
in [the health/armor normal audit](pickup-normal-smoothing.md).

Four original armor pickups use the established army-man plastic palette:
a hollow wrist guard for the shard, paired armored boots for jacket armor,
a hollow helmet for combat armor and a front/back plate carrier for body armor.
Boot cuffs remain open, the helmet has an interior and chin strap, and the
vest has shoulder/side bridges and three front pouches. Tier markings and
material details share one 256 by 256 RGB atlas per item. Every model uses one
static pose and preserves its source frame identity and pickup origin.

Existing item classes, rotation flags, armor gains, protection fractions,
capacities, upgrade/salvage rules and shard behavior retain their gameplay
values. This covers the four custom armor assets present in the project.
Inherited power-screen/shield definitions have no custom model files or
placements in the current maps.

## Asset budgets

| Existing class / new shape | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| Shard / wrist guard | 800 | 76 | 90.5% |
| Jacket / boots | 799 | 248 | 69.0% |
| Combat / helmet | 1,000 | 168 | 83.2% |
| Body / plate carrier | 1,000 | 212 | 78.8% |

The four models total 704 triangles instead of 3,599, an 80.4% reduction.
`armor-manifest.json` records exact outputs, original sources, topology checks,
bounds and atlas hashes. The existing shard `lod1.md2` is byte-identical to
the close wrist guard. Geometry counts describe asset work; Raspberry Pi
frame rates require a controlled device comparison.

## Ownership and source preservation

The armor owner supplies four close models, four exclusive atlases and the
shard LOD sibling. No other model or mission archive shares these skins, so
no archive mutation is needed. Old model/atlas records remain in the
`superseded_*` inventories.

All original decimated pickup pairs now have dedicated owners. `pickups.json`
and its manifest contain zero active conversion entries. Their checked source
archive remains available for source frames, historical comparison and the
corrected rocket/health compatibility atlases still used by mission packages.
The empty legacy inventory cannot restore any authored pickup on a full rebuild.

Every configured distant pickup now comes from its authored ammo, health or
armor owner and has the same bytes as its close model. `--refresh-authored`
adopts only owner-verified outputs. Both original archives remain hash-pinned,
and no active QEM recipe remains. LOD verification/metadata refresh use only
the standard library; combined LOD generation uses NumPy/Pillow without
requiring PyMeshLab.

## Rebuild and verify

```sh
python3 tools/assets/build_armor.py
python3 -S tools/assets/build_pickup_lods.py --refresh-authored
python3 -S tools/assets/verify_armor_runtime.py
python3 -S tools/assets/build_pickup_lods.py --verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_armor.py --verify
python3 tests/assets/test_armor.py
python3 tests/assets/test_pickup_lods.py
python3 tests/assets/test_md2_assets.py
sh tests/armor/run_tests.sh
sh tests/renderers/run_pickup_lod_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

Normal Make/CMake builds verify the checked armor owner before LOD verification
and packaging. Full source builds generate armor before the shared LOD metadata
refresh. Other authored assets and mission-overlay owners retain their current
pipelines.

Native high/low-angle views assess real cuffs, interiors, straps and connected
vest panels alongside ordinary front/side silhouettes. Production armor tests
check upgrade/salvage behavior and unchanged capacities. Host captures establish
appearance and behavior; they do not establish target-device frame rates.

## Native gallery and pickup evidence

The isolated gallery records front, opposite, side, high and underside views
at 1280 by 720, accounting for each pickup's normal rotation. The close upward
helmet view shows its inner crown and chin strap; high views show open wrist
and boot cuffs. The vest's side view shows the connected lower walls and upper
arm gap. Shield markings distinguish the shard and tiers I, II and III.

```sh
python3 tools/performance/capture_armor.py --prepare-only \
  --q2tool /path/to/q2tool --output build/armor-review-map
python3 tools/performance/capture_armor.py --renderer gl3 \
  --map-dir build/armor-review-map/maps --output build/armor-qa-gl3-final
```

Repeat with `--renderer gl1` and `--renderer soft` in fresh output directories.
`--targets` selects individual classes; `--gallery-only` limits a preliminary
review to pictures and empty-inventory pickups. Full runs start every target
and boundary scenario with a full map reset, avoiding inherited coop inventory
or collected-item state. Existing give-item commands prepare starting armor;
real player touches and read-only inventory snapshots determine the results.

| Renderer | Final directory | Images | Native behavior scenarios |
| --- | --- | ---: | ---: |
| GL1 | `build/armor-qa-gl1-final` | 20 | 15 |
| GL3 | `build/armor-qa-gl3-final` | 20 | 15 |
| Software | `build/armor-qa-soft-final` | 20 | 15 |

All three reports pass and complete with return code zero on final package
SHA256 `5710196d1d13205dd2f2edfa0fccb7a00f5b2cea598aa19db619fb7759a479b7`.
Inspection confirms distinct silhouettes, readable badges, visible interiors
and connected vest panels. Software retains its darker palette and faceting
with the same openings and tier markings.

Each renderer verifies the same native results:

| Scenario | Result |
| --- | --- |
| Empty pickups | Shard gives 2 jacket; boots 25 jacket; helmet 50 combat; vest 100 body |
| Better-tier upgrade | Jacket 25 becomes combat 62; combat 50 becomes body 137; old tier is cleared |
| Weaker-tier salvage | Body 100 plus jacket becomes body 109; plus combat becomes body 137 |
| Capacity clamping | Jacket 27 becomes 50; combat 52 becomes 100; body 109 becomes 200 |
| Full-capacity refusal | Jacket 50, combat 100 and body 200 stay unchanged; the matching pickup remains visible |
| Shard special case | Body 200 becomes 202, retaining the existing uncapped shard behavior |

Shard LOD reports are under `build/armor-shard-lod-gl1-final`,
`build/armor-shard-lod-gl3-final` and `build/armor-shard-lod-soft-final`.
They captured the earlier package SHA256
`ccd8bf9b45dde99cf9b119748fdacd216d4dcf94a855c565f277e38b09097081`.
`build/armor-shard-lod-final-attestation.json` verifies that the final package
changes only the vest model, which is absent from these shard fixtures: shard close/LOD models, atlas and every
tested executable/game/renderer binary remain byte-identical. This preserves
the scope of that shard evidence without claiming a new capture of the final
vest. GL1 and GL3 pass all six numeric checks with 76/76 triangles and zero
far delta, including restart, reload, disabling LOD and missing-sibling
fallback. Software passes visual/camera smoke coverage; it exposes no triangle
counters and makes no numeric reduction claim.
