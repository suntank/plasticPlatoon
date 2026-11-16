# Authored ammo pickups

The seven ammo pickups follow the weapon replacement style and existing pickup
paths, in this order: shotgun shells, bullets, hand grenades, grenade-launcher
rounds, rockets, flamethrower fuel and sniper rounds. Shells and bullets use
green labeled boxes; the other items use simple recognizable geometry.
All models are static, with one atlas per item. Gameplay classes, quantities
and weapon ammunition rules retain their existing behavior.

The dedicated generator owns all seven close models and the existing
`lod1.md2` siblings for shells, bullets and grenades. Those siblings use the
same authored recipe as the close versions, so distant views cannot restore
the former trays or grenade geometry. Their low close-up budgets make a
second different shape unnecessary. The existing distance/projection rules
continue selecting each camera's LOD independently.

## Atlas and source ownership

Most new atlases retain the existing `skin.png` paths. The rocket pickup uses
`models/items/ammo/rockets/medium/skin_ammo.png` because the old `skin.png` is
originally served the fired rocket and remains compatibility media in the
tank/helicopter missions. That legacy atlas remains byte-identical; the authored
flying rocket now uses `models/objects/rocket/skin.png`. A full legacy rebuild explicitly
reads its corrected source from the pinned pickup archive rather than restoring
the different older atlas in the complete original snapshot. Projectile meshes
and mission packages stay outside the ammo generator's ownership; their
separate replacement and narrow mission sync are described in
[the projectile notes](projectiles-simple-shapes.md).

The old ammo model and atlas records remain under `superseded_*` in the
conversion manifests. Ammo triangle targets moved to `superseded_targets` in
`platoon.json`; all original pickup pairs now have dedicated owners, leaving
only other legacy assets in the active full-conversion inventory. The projectile rocket atlas
is the intentional shared-source exception. A full rebuild invokes the ammo
generator after converting the remaining assets.

## Asset budgets

`tools/assets/ammo-manifest.json` records exact counts, hashes, model bounds,
atlas dimensions and LOD siblings. Each atlas is a deterministic 256 by 256
RGB image; stencil glyphs defined in the generator draw cream labels without
relying on installed fonts. Shell and bullet labels cover both broad faces and the lid.

| Item | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| Shotgun shells | 1,000 | 116 | 88.4% |
| Bullets | 999 | 116 | 88.4% |
| Hand grenades | 800 | 148 | 81.5% |
| Grenade-launcher rounds | 999 | 76 | 92.4% |
| Rockets | 500 | 128 | 74.4% |
| Flamethrower fuel | 899 | 180 | 80.0% |
| Sniper rounds | 900 | 200 | 77.8% |

The seven close-up models total 964 triangles, down from 6,097 (84.2% fewer).
Shell, bullet and grenade LODs are byte-identical to their close-up models.

Geometry reductions describe asset work. Raspberry Pi performance requires a
controlled comparison on the target device.

## Rebuild and verify

Reauthoring uses the same NumPy/Pillow asset environment as the authored
weapons. Normal Make and CMake builds verify checked outputs using only the
Python standard library before packaging.

```sh
python3 tools/assets/build_ammo.py
python3 -S tools/assets/build_pickup_lods.py --refresh-authored
python3 -S tools/assets/build_pickup_lods.py --verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_ammo.py --verify
python3 tools/assets/verify_ammo_runtime.py
python3 tests/assets/test_ammo.py
python3 tests/assets/test_md2_assets.py
python3 tests/assets/test_pickup_lods.py
sh tests/renderers/run_pickup_lod_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

The ownership tests check that a legacy rebuild excludes authored ammo and
preserves the corrected rocket projectile atlas, including its mission copies.
The LOD generator verifies ammo siblings alongside the separately authored
health injector and armor guard. `--refresh-authored` adopts only hash pins
from independently verified owners before refreshing metadata. A full asset rebuild performs this step automatically. Host model and runtime captures establish
appearance and behavior; they do not establish target-device frame rates.

## Runtime visual review

The seven-item gallery uses one isolated pickup per compiled map. It records
front, opposite, end and downward lid views at 1280 by 720, then touches the
item through normal player movement. Read-only inventory snapshots verify the
amount gained and the item disappearing. The private QA controller also
records the actual rendered camera angles before each image; its opt-in camera
helper expires the benchmark teleport freeze when using noclip.

```sh
python3 tools/performance/capture_ammo.py --prepare-only \
  --q2tool /path/to/q2tool --output build/ammo-review-map
python3 tools/performance/capture_ammo.py --renderer gl1 \
  --map-dir build/ammo-review-map/maps --output build/ammo-qa-gl1-final
```

Use fresh output directories and `--renderer gl3` or `--renderer soft` for the
other renderers. `--targets ammo_shells ammo_bullets` limits the gallery to the
two labeled boxes. All gallery commands use file-driven QA controls and default
to the current `release` build.

Final galleries are under `build/ammo-qa-gl1-final`,
`build/ammo-qa-gl3-final` and `build/ammo-qa-soft-final`. All three reports show
28 views, seven successful pickups, completion, and return code zero, using
package SHA256
`96d4f8a4290df77a99e798e3e836d4c44f871662fec0a697997879c4df574a96`.
Inspection confirms upright, readable SHELLS and BULLETS text on both broad
faces and lids. The handles stay clear of the lid words. The grenade lever and
ring, short launcher round, finned rocket, paired fuel tanks and four-round
sniper clip retain distinct silhouettes. Software keeps its dark palette and
faceting, with the close box labels still readable.

| Pickup | Inventory gain in each renderer |
| --- | ---: |
| Shells | 10 |
| Bullets | 50 |
| Grenades | 2 |
| GL Ammo | 5 |
| Rockets | 5 |
| Napalm | 50 |
| Sniper Rounds | 10 |

The existing mixed near/far LOD tool now accepts file controls, selected targets
and software rendering:

```sh
python3 tools/performance/capture_pickup_lod.py --renderer gl1 \
  --file-controls --output build/ammo-lod-gl1-final
python3 tools/performance/capture_pickup_lod.py --renderer soft \
  --targets ammo_shells ammo_bullets ammo_grenades \
  --file-controls --output build/ammo-lod-soft-final
```

Repeat the first command with `--renderer gl3` and a fresh directory. GL1 and
GL3 expose triangle counters for numeric comparison. Software reports only
visual smoke coverage because its model-triangle counter is unavailable; it
retains off/on, renderer restart, map reload and missing-sibling images without
claiming a numeric triangle reduction.

Final distance reports pass in `build/ammo-lod-gl1-final` and
`build/ammo-lod-gl3-final` for all five existing LOD fixtures, and in
`build/ammo-lod-soft-final` for the three ammo fixtures as visual smoke. The
OpenGL counters show the expected zero ammo triangle delta because each new
ammo sibling is identical to its close model. The untouched armor shard and
stimpack retain their exact far-view reductions of 600 and 620 triangles,
respectively. Near views stay unchanged; renderer restart, map reload,
disabling LOD and missing-sibling fallback all pass. Inspection of the mixed
near/far images confirms the authored ammo silhouette persists at distance.
