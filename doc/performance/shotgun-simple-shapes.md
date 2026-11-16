# Authored pump shotgun

The single-barrel shotgun is an original simple-shape model with a beveled
receiver, shoulder stock, barrel, magazine tube, ribbed sliding fore-end,
trigger guard and aligned sights. The first-person version reuses the M16's
molded mitten style and arm geometry. The support hand and fore-end move
together through the pump cycle; the trigger hand stays on the grip and the
support elbow stays anchored. The moving forearm bends between that elbow and
the pump hand.

The replacement covers the first-person model, world pickup, all 198 player
attachment poses, all 475 enemy attachment poses and the taller enemy variant.
The original attachment models supply rigid pose references. The new fore-end
also cycles through the player standing and crouched attack poses and every
enemy shooting loop; normal movement and idle poses keep it forward. The shotgun keeps
one model and one atlas per representation, including its first-person hands.
Existing selectable player colors and red enemy variants are rebuilt from the
new atlases. The double-barrel shotgun is a separate weapon.

Aiming moves the actual sights into the center of the screen through the
shared model-ADS transition. Hip fire, aiming, firing and release work in
single-player and independently for each split-screen player. The shotgun's
first-person animation retains the firing frame schedule so that the fore-end
and support hand can visibly cycle after a shot. The existing pump sound is
synchronized with that action. The generated `shotgun_model_ads.h` supplies the
sight and muzzle offsets from the authored geometry.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,399 | 752 | 46.2% | 40 |
| Pickup | 799 | 300 | 62.5% | 1 |
| Player held | 1,399 | 300 | 78.6% | 198 |
| Enemy held, including taller variant | 1,399 | 300 | 78.6% | 475 |

`tools/assets/shotgun-manifest.json` records exact counts, hashes, bounds,
sight anchors and animation validation. The previous first-person model had
one static frame with no separate hand geometry or pump animation.

These figures describe geometry cost. They do not establish a Raspberry Pi
frame-rate improvement; that requires a controlled comparison on the device.
The animated viewmodel does not use the single-pose static cache used by the
M16 and pistol.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify the
checked-in authored assets using only the Python standard library, then rebuild
height/color derivatives and package them.

```sh
python3 tools/assets/build_shotgun.py
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_shotgun.py --verify
python3 tools/assets/verify_shotgun_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_shotgun.py
sh tests/input/run_shotgun_model_ads_tests.sh
python3 tests/assets/test_enemy_shotgun_muzzle.py
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the replacement's front barrel rim and
update the shotgun selector in `build_player_muzzle_points.py` before
regenerating the muzzle table.

The enemy shotgun's seven active flash entries in `src/common/shared/flash.c`
also follow the decoded barrel rim at their firing poses. These shared offsets
place both the pellet source and visual flash. Values below are unscaled
forward/right/up units; the shared soldier macros apply the foot-anchored
height transform once. Model Y is negated to obtain right.

| Shotgun flash | Soldier firing pose | MD2 frame | Forward | Right | Up |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | attak103 | 2 | 27.529101 | 4.749997 | 16.419995 |
| 2 | attak205 | 16 | 23.873203 | 4.749883 | 16.419992 |
| 3 | attak303 | 32 | 20.830810 | 4.749783 | 4.250450 |
| 4 | attak403 | 41 | 18.936078 | 4.749795 | 12.866359 |
| 6 | death122 | 293 | 26.390353 | 4.442650 | -5.493738 |
| 7 | death125 | 296 | 26.390353 | 4.442650 | -5.493738 |
| 8 | runs04 | 112 | 22.157626 | 4.749845 | 14.681726 |

Flash 5 has no firing callback and keeps its previous value. Run
`python3 tests/assets/test_enemy_shotgun_muzzle.py` to compare the compiled
shared table with the taller exported MD2 at all seven mapped firing frames.

The legacy decimation configuration and manifests exclude the shotgun's
models and atlases. Previous records remain under `superseded_*` for comparison.
A full legacy rebuild invokes the dedicated shotgun generator after processing
the remaining assets. The optional Pi actor overlay also omits authored shotgun
models, including the taller enemy attachment. Rebuild an existing Pi overlay
before installing it with the new main package.


## Runtime visual review

The runtime capture tool supports `--weapon Shotgun`. It equips real local
players, exercises ordinary firing/aim input, and records the executable,
renderer and package hashes beside each set of screenshots. The test-only
controller can queue a screenshot when the received weapon frame reaches 13;
frames 12 and 13 share the fully retracted pose, allowing normal interpolation
to reach the pump endpoint before the capture. Both the support mitten and
fore-end move in the hip-fire views, while the real sights remain centered
when aiming.

Compile the existing review fixture into a private output directory, then
capture a fresh run (the output directory must not already exist):

```sh
python3 tools/performance/compile_map.py \
  --source maps/fixtures/pp_m16_review.map --tool /path/to/q2tool \
  --profile release --output-dir build/shotgun-review-map
python3 tools/performance/capture_m16.py \
  --label shotgun-review --weapon Shotgun --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/shotgun-qa-review --file-controls
```

`--file-controls` uses the QA controller's console-file channel so offline
captures also work when localhost UDP is unavailable. Omit it to use the
existing local RCON channel. Repeat with `--renderer gl3` and another fresh
output directory for GL3. Add `--four --mixed-weapons` for alternating pistol
and shotgun players; that run asserts independent ADS blends of
`[1,0,1,0]` and then `[0,1,0,1]`, including firing in each arrangement.

Completed host reviews are recorded in `build/shotgun-qa-gl1-file`,
`build/shotgun-qa-gl3-file`, `build/shotgun-qa-four-file`, and the clean final
GL1 run in `build/shotgun-qa-final`. Single-player runs cover hip fire,
fully retracted and returned pump positions, model sights, aimed pump action,
aimed firing, release to hip, player-held and pickup views. The current capture tool also asserts
that the authored Rifle uses its model-ADS path.
The GL1/GL3 and four-player screenshots were visually inspected for sight
alignment, hand contact, pump motion and held/pickup silhouette. These are
appearance and behavior checks on an offscreen host, not Pi timing results.
