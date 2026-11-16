# Authored rocket launcher

The rocket launcher uses an original tube with flared ends, a physically
open bore and closed wall surfaces, plus the established army-man plastic
palette, molded mitten hands and forearms. The first-person
model, world pickup, player-held model and normal/tall enemy attachments share
the authored design. Hands and arms stay in the first-person gun model and
atlas, keeping one weapon draw per camera.

The first-person model retains the complete tube and rear flare. GL1, GL3
and software alias rendering use a 0.1-unit near clipping plane only for
`RF_WEAPONMODEL` draws so the close rear tube stays visible through aiming
and recoil. GL world rendering keeps its configured `gl_znear`; software world
aliases retain their 4-unit near plane. GL1 stereo and both hardware renderers'
XY projection retain their existing alignment.

Software bounding-box checks, transformed vertices and triangle clipping all
use that entity's near plane. Weapon depth is an affine mapping of true inverse
distance into a safe integer range, preserving screen-space interpolation and
self-occlusion without changing XY projection. World alias depth is unchanged.

Aiming moves the actual model sights onto the camera's center ray over the
shared 0.18-second transition. Each local split-screen player has independent
aiming state. `rlauncher_model_ads.h` supplies geometry-derived sight and muzzle
offsets. First-person and pickup models each use one static frame. The held
model follows all 198 player attachment poses; the enemy attachment follows
all 475 soldier poses, including the existing taller variant.

The dedicated generator transfers archived enemy attachment motion directly
onto the canonical rocket mesh. `build_heavy_gunner.py --weapon rocket` now
delegates to that generator and returns its reproducible
`rocket-soldier-manifest.json` report. This removes the old wrapper's dependency
on obsolete runtime M16/launcher hash pins and a second round of player-frame
quantization. The M60 wrapper continues using its own authored generator.

Selectable player colors and red enemy skins are rebuilt from the new atlases,
and the player muzzle table tracks the reviewed front rim through every pose.
Rocket ammunition, the fired projectile and weapon tuning retain their
existing behavior and geometry.

The rocket soldier fires from planted `attak303` (MD2 frame 32). Its front
tube rim center is `(23.470810, -4.749782, 4.422446)` before the soldier height
transform. The shared `MZ2_SOLDIER_ROCKET` entry negates model Y to right and
applies the foot-anchored height once, aligning the projectile source and
client flash with the taller attachment. The compiled-table comparison in
`tests/assets/test_enemy_rlauncher_muzzle.py` checks the exported rim at that
exact firing pose.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,399 | 684 | 51.1% | 1 |
| Pickup | 799 | 256 | 68.0% | 1 |
| Player held | 1,427 | 256 | 82.1% | 198 |
| Enemy held, including taller variant | 1,427 | 256 | 82.1% | 475 |

`tools/assets/rlauncher-manifest.json` records exact counts, hashes, bounds,
sight anchors and all-pose validation. Geometry counts describe asset work;
Raspberry Pi performance requires a controlled target-device comparison.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify
checked assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_rlauncher.py
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_rlauncher.py --verify
python3 tools/assets/verify_rlauncher_runtime.py
python3 tools/assets/build_heavy_gunner.py --weapon rocket --verify
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_rlauncher.py
sh tests/input/run_rlauncher_model_ads_tests.sh
python3 tests/assets/test_enemy_rlauncher_muzzle.py
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the front rim and update the rocket-launcher
selector in `build_player_muzzle_points.py` before regenerating the player
attachment table.

The clipping regression compiles the actual GL1/GL3 projection functions and
software alias bounding-box, vertex and triangle paths. It checks configured
world near planes, unchanged XY/stereo projection, retained close weapon faces,
correct long-triangle depth ordering and integer bounds. The same suite passes
with undefined-behavior and floating-to-integer overflow sanitizers enabled.

Legacy decimation inventories exclude the launcher models and atlases; old
records remain under `superseded_*` for comparison. A full rebuild invokes the
dedicated generator and emits its rocket-enemy report. The optional Pi overlay
omits authored rocket-launcher models; rebuild an installed overlay before
combining it with the new main package.

## Runtime visual review

The capture tool supports `--weapon 'Rocket Launcher'`. Compile the existing
review fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md),
then use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label rlauncher-review --weapon 'Rocket Launcher' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/rlauncher-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and rocket-launcher players and
assert independent aim blends. The current control regression switches
to the authored Rifle and checks its model ADS. Host visual checks establish
appearance and behavior; target-device frame rates require measurement.


Final GL captures are recorded in `build/rlauncher-qa-gl1-verified` and
`build/rlauncher-qa-gl3-verified`, with nine views each. They cover hip and
aimed firing, idle sights, release, M1 Flamethrower overlay, player-held,
pickup and the actual rocket-soldier attachment. Both runs completed with
return code zero. Idle and firing images were inspected specifically for a
continuous tube silhouette at the lower corners, including the strongest
observed kicks below. The test-only controller queues these screenshots when
the local recoil state reaches at least 0.65 and records the measured amount
in the view metadata.

| Renderer | Hip firing recoil observed | Aimed firing recoil observed |
| --- | ---: | ---: |
| GL1 | 0.849978 | 0.849720 |
| GL3 | 0.679836 | 0.696906 |

The software smoke is recorded in `build/rlauncher-qa-soft-final` (nine views,
return code zero). It passed the same equipment, aim, release and firing-state
readbacks, and its rendered hip/ADS views show a continuous model without the
cutout strips. Software screenshots read a buffered surface, so the numeric
projection tests establish close-depth behavior at the recoil extreme; the
GL screenshots above provide the direct strong-kick image evidence.

`build/rlauncher-qa-four-verified` contains five completed four-player views.
The runner checks every actual equipped model and waits for independent ADS
endpoints `[1,0,1,0]` and then `[0,1,0,1]`, with firing in both arrangements.
These images were also inspected for clipping. Completed prior-weapon
regressions are in `build/rlauncher-qa-grenade-verified` (seven views),
`build/rlauncher-qa-pump-verified` (eleven views, including frame-13 pump
backstroke at hip and full aim) and `build/rlauncher-qa-m60-verified` (eight
views, including the heavy-soldier attachment). All returned zero, and their
held models, sights and pump action were visually checked.

The ten asset tests verify full flares and an open decoded lumen, watertight
walls, existing mittens, clear sights, all 198/475 poses and exact checked
outputs. Final captures used matching source/release asset packages with
SHA-256 `570f83ed7f239400ec0f6addfd9bc167b6bab1ba9c2678a219b94b90bddc481b`;
renderer and executable hashes are recorded separately in each manifest.
These are appearance and behavior checks on a host, not Pi timing results.
