# Authored M60

The M60 uses original simple geometry with a side feed box, long barrel and
gas tube and paired folded bipod legs. Its established
army-man plastic palette and molded mitten hands match the other replacements. The first-person model, world pickup,
player-held model and normal/tall enemy attachments share the same design.
The first-person hands and arms remain in the gun's model and atlas, keeping
one weapon draw per camera.

The top carrying handle has been removed from every version, including both
enemy attachments. The existing sights, feed cover, hands and gun placement
are retained. This removes 32 triangles from each model.
The updated GL3 capture in `build/m60-no-handle-qa-gl3/manifest.json`
completed eight views with a clean exit, including hip, ADS, firing, pickup,
player-held and enemy-held models. First-person and ADS screenshots were
visually checked. The ten M60 asset tests, ADS alignment, enemy muzzle,
four player muzzle checks, heavy-gunner verification and normal build passed.

Aiming moves the actual sights onto the camera's center ray through the shared
0.18-second transition. Each local split-screen player owns its aiming state.
The generated `m60_model_ads.h` supplies geometry-derived sight and muzzle
offsets. First-person and pickup models each use one static pose; procedural
recoil, raising and aiming do not require duplicate frames. The player-held
model follows all 198 original attachment poses, and the enemy model follows
all 475 soldier poses with the existing taller variant.

The dedicated M60 generator transfers archived enemy attachment motion
directly onto the new canonical world mesh and validates the exported faces
in every pose. `build_heavy_gunner.py` delegates its M60 path to that generator;
it no longer depends on the previous M60 or M16 runtime hash pins. Its
`heavy-gunner-manifest.json` report remains reproducible alongside the new
M60 manifest. The rocket path also delegates to its own authored generator.

Selectable player colors and red enemy skins are regenerated from the new
atlases. The third-person muzzle table follows the reviewed barrel rim in
every held pose.

The heavy gunner fires from the planted `attak303` pose (MD2 frame 32).
Its reviewed flash-hider cap center is `(25.120810, -4.747138, 3.594972)`
before the soldier height transform. The shared `MZ2_SOLDIER_HEAVY` table
negates model Y to right and applies that height transform once, aligning
both the pellet source and client flash with the taller enemy barrel.
`tests/assets/test_enemy_m60_muzzle.py` compares the compiled table with
the exported tall MD2 at this exact firing frame.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,399 | 784 | 44.0% | 1 |
| Pickup | 799 | 348 | 56.4% | 1 |
| Player held | 1,545 | 348 | 77.5% | 198 |
| Enemy held, including taller variant | 1,545 | 348 | 77.5% | 475 |

`tools/assets/m60-manifest.json` records exact counts, hashes, bounds, sight
anchors and all-pose validation.

Geometry reductions describe asset work. Raspberry Pi frame-rate improvement
requires a separate controlled comparison on the target device.

## Rebuild and verify

Reauthoring needs NumPy and Pillow. Normal Make and CMake builds verify checked
assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_m60.py
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_m60.py --verify
python3 tools/assets/verify_m60_runtime.py
python3 tools/assets/build_heavy_gunner.py --verify
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_m60.py
sh tests/input/run_m60_model_ads_tests.sh
python3 tests/assets/test_enemy_m60_muzzle.py
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the front barrel rim and update the M60
selector in `build_player_muzzle_points.py` before regenerating the muzzle
attachment table.

Legacy decimation inventories exclude the M60 models and atlases. Their old
records remain under `superseded_*` for comparison. A complete rebuild invokes
the M60 generator and emits its enemy-retarget report. The optional Pi overlay
omits authored M60 models; rebuild an installed overlay before combining it
with the new main package.

## Runtime visual review

The capture tool supports `--weapon 'Heavy Machinegun'` for M60 hip, model ADS,
firing, release, pickup and player-held views. Compile the existing review
fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md),
then use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label m60-review --weapon 'Heavy Machinegun' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/m60-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and M60 players and assert
independent aim blends. The current control regression switches to the authored Rifle and checks
its model ADS. Host appearance checks do not establish
target-device frame rates.

Completed host captures are recorded in `build/m60-qa-gl1-final`,
`build/m60-qa-gl3` and `build/m60-qa-four`. Each single-view run contains eight
views: hip fire, actual model sights, aimed firing, release to hip, Grenade
Launcher overlay, player-held, world pickup and a close heavy-enemy attachment.
The four-player run contains five views and checks independent pistol/M60 ADS
blends of `[1,0,1,0]` and then `[0,1,0,1]`, with firing in both arrangements.
The GL1/GL3 and four-player images were inspected for sight alignment, clear
hands, feed-box silhouette, held fit and the red enemy attachment. The
final GL1 capture waits for the received weapon selection before photographing
the held model; unique state labels record that readback.

Prior weapon regressions are recorded in `build/m60-qa-pump-regression`
(eleven views, including frame-13 pump backstroke at hip and while aiming)
and `build/m60-qa-sshotgun-regression` (seven double-barrel views). All five
capture manifests completed with return code zero and their assertions passed.
The ten M60 asset tests, model-ADS C suites, effects checks, compiled heavy
muzzle check, six soldier-height tests, twelve color tests and four player
muzzle tests also passed. Those M60 checks used matching source and release
packs with SHA-256
`9ec9198f6f45c8d7360fadbc962a90dbcd12d66f66aa7587ba509b8a7106023e`.
These host checks establish appearance and behavior; device performance still
requires measurement on the Raspberry Pi.
