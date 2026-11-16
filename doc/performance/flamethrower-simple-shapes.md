# Authored M1 Flamethrower

The M1 Flamethrower uses original low-poly geometry, the established army-man
plastic palette and molded mitten hands. The first-person model, world pickup
and player-held model share the authored design. The gun, hands and forearms
share a first-person model and atlas, keeping one weapon draw per camera.

The player-held version includes paired fuel tanks, retaining bands, a
central pressure bottle and a flexible hose attached to the soldier's back.
The repaired original supplies independent gun and backpack motion through all
198 player poses; the backpack follows the torso instead of inheriting the
wand's aim. Both fitted components have maximum RMS error below 0.088 model
units. An authored hose with eight six-sided rings bends between the separately
moving endpoints, with its pack controls following the backpack and its gun
controls following the wand.

The gun, backpack and hose remain one held MD2 and atlas. The static pickup
shows the complete assembly; the static first-person version includes hands
and a hose entering from below the screen. There is no separate enemy
flamethrower attachment model.

Aiming moves the actual model into the camera's center ray through the shared
0.18-second transition. Each local split-screen player has independent aiming
state. `flamethrower_model_ads.h` provides geometry-derived sight and muzzle
offsets, replacing the previous image-overlay aiming. Selectable player colors
are regenerated from the new atlases, and the held muzzle table follows the
reviewed nozzle through every pose. Flame fuel, projectiles and weapon tuning
retain their existing behavior.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands, arms and hose | 1,799 | 804 | 55.3% | 1 |
| Pickup, including tanks and hose | 1,199 | 648 | 46.0% | 1 |
| Player held, including tanks and hose | 2,493 | 648 | 74.0% | 198 |

`tools/assets/flamethrower-manifest.json` records exact counts, hashes, bounds,
sight/muzzle anchors and all-pose validation. Geometry reductions describe
asset work; Raspberry Pi performance requires a controlled target-device
comparison.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify
checked assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_flamethrower.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_flamethrower.py --verify
python3 tools/assets/verify_flamethrower_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_flamethrower.py
sh tests/input/run_flamethrower_model_ads_tests.sh
sh tests/renderers/run_view_weapon_clip_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If nozzle topology changes, inspect the front rim and update the flamethrower
selector in `build_player_muzzle_points.py` before regenerating the player
attachment table.

Legacy decimation inventories exclude the flamethrower models and atlases.
Old records, including the archived held model's hash-pinned triangle/ST-table
repair, remain under `superseded_*` for comparison. Obsolete triangle targets
are retained under `superseded_targets` in `platoon.json`. A complete rebuild
invokes the dedicated generator. This weapon was never part of the separate
ten-pickup conversion inventory, which remains unchanged. The optional Pi
overlay omits both the authored first-person and player-held flamethrower so
it cannot restore the previous gun or backpack.

## Runtime visual review

The capture tool supports `--weapon 'M1 Flamethrower'`. Compile the existing
review fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md),
then use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label flamethrower-review --weapon 'M1 Flamethrower' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/flamethrower-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and flamethrower players and
assert independent aiming. The current control regression switches to the authored Rifle and checks
its model ADS. Rear and side views are required to assess the
backpack attachment, along with the ordinary hip, ADS, firing, release,
pickup and held views. Host visual checks establish appearance and behavior;
target-device frame rates require measurement.

Completed visual captures are recorded in these directories:

| Capture | Directory | Views |
| --- | --- | ---: |
| GL1 single player | `build/flamethrower-qa-gl1-final` | 12 |
| GL3 single player | `build/flamethrower-qa-gl3-final` | 12 |
| Software single-player smoke | `build/flamethrower-qa-soft-final` | 12 |
| GL1 four-player mixed weapons | `build/flamethrower-qa-four-final` | 5 |

All four manifests report completion and return code zero, using package SHA256
`9eda0e40a5b8e75aec939e9d8fbd77ef399d9f7e276e226c079b05b1132b725a`.
The single-player passes cover hip, actual-model ADS, firing, release, the
Mortar Cannon overlay regression, pickup, and held views from both sides and
behind the soldier. The added `held-fire`, `held-crouch-side` and
`held-crouch-rear` views use live player input. The capture shim records the
actual body frame and crouch flag, and the runner waits for those states before
capturing. Standing firing arrived at frame 46 in all three renderers; crouched
side/rear frames were 142/149 in GL1, 140/148 in GL3 and 141/149 in software,
with the ducked flag set in every crouched view.

Visual inspection confirms the tank assembly stays seated against the back in
the standing firing and crouched poses, and the hose follows the wand without
detaching. GL1 and GL3 show flames leaving the modeled nozzle. Software images
retain the renderer's dark palette and faceting, with the sights, tank silhouette
and hose intact. The mixed four-player pass equips pistol/flamethrower pairs
and verifies independent model-aim endpoints of `[1, 0, 1, 0]`, followed by
`[0, 1, 0, 1]`, before recording both firing arrangements.
