# Authored sniper rifle

The sniper rifle uses original low-poly geometry with the established
army-man plastic palette and molded mitten hands. Its rounded stock, beveled
receiver, tapered fore-end and flared scope appear in first person, in the
world pickup and in all player-held poses. The first-person scope has twelve
sides and a hollow optical channel with four reticle posts around a clear
center. The muzzle brake has a recessed cup. Hands and forearms share the
first-person gun's model and atlas, keeping one weapon draw per camera.

Aiming moves the actual modeled scope onto the camera's center ray through
the shared 0.18-second transition. Each local split-screen player owns its
aiming state. The generated `sniper_model_ads.h` provides geometry-derived
scope and muzzle offsets. This replaces the sniper's previous image overlay.
The first-person and pickup models each use one static pose; the player-held
model follows all 198 original rigid attachment poses. There is no enemy
sniper attachment model.

Selectable player colors tint the entire held rifle, including the barrel,
scope housing, reticle and muzzle recess. The player muzzle table follows the
reviewed barrel rim through every held pose.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 2,000 | 996 | 50.2% | 1 |
| Pickup | 1,200 | 520 | 56.7% | 1 |
| Player held | 2,664 | 520 | 80.5% | 198 |

`tools/assets/sniper-manifest.json` records exact counts, hashes, bounds,
scope/muzzle anchors and all-pose validation. Geometry reductions describe
asset work; Raspberry Pi performance requires a controlled target-device
comparison.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify
checked assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_sniper.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_sniper.py --verify
python3 tools/assets/verify_sniper_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_sniper.py
sh tests/input/run_sniper_model_ads_tests.sh
sh tests/renderers/run_view_weapon_clip_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the front rim and update the sniper selector
in `build_player_muzzle_points.py` before regenerating the attachment table.

Legacy decimation inventories exclude the sniper models and atlases. Their
old records remain under `superseded_*`; obsolete triangle targets are retained
under `superseded_targets` in `platoon.json`. A complete rebuild invokes the
sniper generator. This pickup was never part of the separate ten-pickup
conversion inventory, which remains unchanged. The optional Pi overlay omits
the authored first-person sniper; its held model also comes from the main
package because the old Pi recipe never covered it.

## Runtime visual review

The capture tool supports `--weapon 'Sniper Rifle'`. Compile the existing review
fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md), then
use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label sniper-review --weapon 'Sniper Rifle' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/sniper-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and sniper players and assert
independent aiming. The current control regression uses the authored Rifle and checks model ADS.
Host visual checks establish appearance and behavior; target-device frame
rates require measurement.


## Original model ADS rollout

Single-view evidence for the initial scope implementation was recorded in `build/sniper-qa-gl3-final`,
`build/sniper-qa-gl1-final` and `build/sniper-qa-soft-final` (eight views each).
All completed with return code zero. The GL3 run includes a downrange soldier:
the target remains visible through the shortened optical channel and the
physical reticle is centered and readable. The refined hip placement, idle
scope, firing, release, held and pickup silhouettes were visually inspected.
Received weapon states confirm `v_rail` was restored before each held capture;
the M1 Flamethrower used its separate image-overlay ADS path in those runs.

GL firing screenshots are triggered at an observed recoil of at least 0.65.
The final GL1 run recorded 0.966664 for both hip and aimed firing; GL3 recorded
0.827600 hip and 0.851188 aimed. Both preserve a continuous scope silhouette
without near-plane cutouts during the kick. Software provides real rendered
smoke coverage and the same equipment/aim/release readbacks. Its buffered
screenshot surface can lag the brief recoil pose; the renderer projection
suite supplies close-depth numeric coverage, while GL images provide direct
strong-kick evidence.

`build/sniper-qa-four-final` contains five completed mixed pistol/sniper views.
Every slot's actual model is checked and the runner waits for independent ADS
endpoints `[1,0,1,0]` and then `[0,1,0,1]`, with firing in both arrangements.
The scope apertures and reticles remain visible independently in both layouts.
All final captures used asset package SHA-256
`35f10531ab211d5918d20eff89959fde5031922a6df6f99216e78156e9431c96`;
executable and renderer hashes are pinned separately in each manifest.
The eleven sniper asset tests also passed, including the decoded center and
lower-channel rays, reticle gap, closed walls, existing hands, all 198 poses,
recessed muzzle and exact outputs. These host checks establish appearance and
behavior, not Raspberry Pi frame rates.
