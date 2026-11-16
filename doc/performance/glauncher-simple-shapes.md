# Authored grenade launcher

The grenade launcher uses original simple geometry with a rotary drum,
foregrip and stock, plus the established army-man plastic palette and molded
mitten hands. Its barrel ends in a closed cup with a dark recessed floor.
The first-person model, world pickup and player-held model share the authored
design. The gun, hands
and arms use one model and one atlas per camera. The player-held version
omits first-person hands and follows all 198 original rigid attachment poses.
The first-person and pickup versions each use one static frame.

Aiming pulls the actual sights into the camera's center ray through the shared
0.18-second transition. Each local split-screen player has independent aiming
state. `glauncher_model_ads.h` supplies sight and muzzle offsets from the
geometry. The muzzle table follows the reviewed barrel rim through all held
poses, and selectable player colors are rebuilt from the new atlases.

The grenade launcher has no enemy attachment model. The rocket launcher and
its enemy attachment are separate assets. Grenade ammunition and the fired
projectile models retain their existing geometry and behavior.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,400 | 712 | 49.1% | 1 |
| Pickup | 800 | 284 | 64.5% | 1 |
| Player held | 1,742 | 284 | 83.7% | 198 |

`tools/assets/glauncher-manifest.json` records exact counts, hashes, bounds,
sight anchors and all-pose validation. Geometry counts describe asset work;
Raspberry Pi performance requires a separate controlled comparison on the
target device.

## Rebuild and verify

Reauthoring needs NumPy and Pillow. Normal Make and CMake builds verify checked
assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_glauncher.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_glauncher.py --verify
python3 tools/assets/verify_glauncher_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_glauncher.py
sh tests/input/run_glauncher_model_ads_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the front barrel rim and update the
grenade-launcher selector in `build_player_muzzle_points.py` before
regenerating the muzzle attachment table.

Legacy decimation inventories exclude the launcher models and atlases; old
records remain under `superseded_*` for comparison. A complete rebuild invokes
the dedicated generator. The optional Pi overlay omits authored grenade-launcher
models; rebuild an installed overlay before using it with the new main package.

## Runtime visual review

The capture tool supports `--weapon 'Grenade Launcher'`. Compile the existing
review fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md),
then use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label glauncher-review --weapon 'Grenade Launcher' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/glauncher-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and grenade-launcher players and
assert independent aim blends. The current control regression switches
to the authored Rifle and checks its model ADS. Host visual checks establish
appearance and behavior; target-device frame rates require measurement.


The completed Grenade Launcher reviews are recorded in
`build/glauncher-qa-gl1`, `build/glauncher-qa-gl3` and
`build/glauncher-qa-four-final`. Each single-view run contains seven views:
hip fire, real model sights, aimed firing, release, Rocket Launcher overlay,
player-held and world pickup. Received weapon states confirm the selected
launcher is restored before the held view. The images were inspected for the
wide barrel and drum silhouette, existing mitten contact and clear sight ray.

The final four-player run contains five views and confirms independent pistol
and grenade-launcher aim blends of `[1,0,1,0]` and then `[0,1,0,1]`, with
firing in both arrangements. The QA tool polls each slot's actual model and
completed aim transition using unique state labels; this keeps endpoint
checks reliable when grenade effects slow the offscreen renderer. All three
launcher runs completed successfully with return code zero.


Regression captures are recorded in `build/glauncher-qa-m60-regression`
(eight views, including the heavy-enemy attachment) and
`build/glauncher-qa-pump-regression` (eleven views, including received frame 13
at hip and full aim). Both completed successfully; the M60 held fit and pump
backstroke were also visually inspected. The ten grenade-launcher asset tests
validate the decoded recessed bore, broad drum, closed gun/hand solids,
clear sights, all 198 poses and exact checked outputs. These checks used
matching source/release packages with SHA-256
`96c5478f1a74f5ea6c76b86ea0f3e9807e8a1f5e713dc4cd54cfd86416907a86`.
