# Authored double-barrel shotgun

The double-barrel shotgun uses original simple-shape twin barrels, receiver,
stock, grip and sights. Its first-person molded mittens and arms follow the
M16's established army-man style. The gun and hands share one model and one
atlas, preserving a single weapon draw per camera. The world pickup and all
198 player-held poses use the same gun silhouette without first-person hands.
This weapon has no enemy attachment model.

The oval stock flows into a beveled receiver. Two barrels in the player's
selected color rise from rounded shoulders above a checkered fore-end. The
support mitten cups the fore-end farther back, and the lower hip pose
exposes both barrels.
When aiming, a brass-colored bead sits between two swept rear sight ears.
The pickup and player-held models use simpler versions of the same contours.

Aiming pulls the real model into a centered sight picture over the shared
0.18-second transition. Each local split-screen player has independent aiming
state. The generated `sshotgun_model_ads.h` binds sight and muzzle offsets to
the authored geometry. First-person and pickup models each have one static
frame; the held model follows all 198 original rigid attachment poses. The
pump shotgun retains its separate cycling fore-end and animation.

Existing selectable player colors are rebuilt from the new atlases. The
player muzzle attachment follows the center of the paired barrel openings
through every pose.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,400 | 896 | 36.0% | 1 |
| Pickup | 800 | 352 | 56.0% | 1 |
| Player held | 1,510 | 352 | 76.7% | 198 |

`tools/assets/sshotgun-manifest.json` records exact counts, hashes, bounds,
sight anchors and all-pose validation.

Geometry counts describe asset work. Any Raspberry Pi frame-rate improvement
requires a separate controlled comparison on the target device.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify
checked-in outputs using only the Python standard library, regenerate color
derivatives and package the runtime assets.

```sh
python3 tools/assets/build_sshotgun.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_sshotgun.py --verify
python3 tools/assets/verify_sshotgun_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_sshotgun.py
sh tests/input/run_sshotgun_model_ads_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the paired front barrel rims and update
the double-barrel selector in `build_player_muzzle_points.py` before
regenerating the attachment table.

The legacy decimation configuration and manifests exclude this weapon's
models and atlases; previous records remain under `superseded_*` for comparison.
A complete legacy rebuild invokes the dedicated generator for these assets.
The optional Pi actor overlay also omits the authored double-barrel models.
Rebuild an existing Pi overlay before installing it with the new main package.

## Runtime visual review

The shared capture tool supports `--weapon 'Double Barrel Shotgun'`. It uses
ordinary gameplay input and records package, executable and renderer hashes
beside its screenshots. Compile the existing review fixture as described in
[the pump shotgun notes](shotgun-simple-shapes.md), then capture a fresh output
directory:

```sh
python3 tools/performance/capture_m16.py \
  --label sshotgun-review --weapon 'Double Barrel Shotgun' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/sshotgun-qa-review --file-controls
```

Repeat with `--renderer gl3` and another fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and double-barrel shotgun players
and assert independent aim blends. `--file-controls` uses the offline QA
console-file channel when local UDP is unavailable. The current control regression
restores the authored Rifle and checks its model ADS.


Completed host captures are recorded in `build/sshotgun-qa-gl1`,
`build/sshotgun-qa-gl3` and `build/sshotgun-qa-four`. Both single-view runs
include hip fire, real sights, aimed firing, release to hip, player-held and
pickup views, plus the Heavy Machinegun overlay used before its replacement. They assert full
model aim at 1, release at 0 and unsupported-weapon model aim at 0. The four
mixed-weapon views assert independent blends of `[1,0,1,0]` and then
`[0,1,0,1]`, with firing in both arrangements. The exported twin barrels,
closed surfaces, existing two-hand style and clear sight channel are also
covered by the nine asset tests.

The separate pump-shotgun regression is recorded in
`build/sshotgun-qa-pump-regression`. It verifies the original shotgun still
reaches received gunframe 13 with a fully retracted fore-end and support
hand, both at hip fire and while aiming, then returns forward. All four
runs completed successfully. The GL1/GL3 hip, sight, held and pickup views,
four-player aiming, and pump backstroke were visually inspected. These host
captures establish appearance and behavior, not target-device frame rates.
