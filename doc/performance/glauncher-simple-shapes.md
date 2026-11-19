# Authored grenade launcher

The grenade launcher uses original low-poly geometry with a beveled rotary
drum, molded chamber panels, a foregrip and a stock. Its barrel ends in a
closed cup with a dark recessed floor. The first-person model, world pickup
and player-held model share the design and the army-man palette. First person
uses the existing molded mittens and lowers the hip pose to show the drum.
The drum advances by one chamber after every shot. Only the drum moves
within the first-person model, so the hands, sights and muzzle stay aligned
as the existing recoil moves the whole weapon. The pickup has one pose and
the player-held model follows all 198 archived attachment poses.

Aiming pulls the actual sights into the camera's center ray through the shared
0.18-second transition. The wider rear notch and pale front sight insert
improve visibility, including with other player colors. Each local split-screen
player has independent aiming and uses their own firing frames.
`glauncher_model_ads.h` supplies the sight and muzzle offsets and the drum's
frame range. The muzzle table follows the barrel rim through all held poses.

The grenade launcher has no enemy attachment model. The rocket launcher and
its enemy attachment are separate assets. Grenade ammunition and the fired
projectile models retain their existing geometry and behavior.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,400 | 760 | 45.7% | 5 |
| Pickup | 800 | 332 | 58.5% | 1 |
| Player held | 1,742 | 332 | 80.9% | 198 |

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
assert independent aim blends. Single-view runs capture the drum in motion in
both hip and aimed views at received gunframe 10. They also capture the
resting hip and aimed views, the world pickup and the player-held model. The
asset tests check the recessed bore, closed gun and hand geometry, clear
sights, drum motion, all held poses and exact checked outputs.
