# Authored Mortar Cannon

The Mortar Cannon uses a deep wide tube, round baseplate and two-leg bipod
with the established army-man plastic palette and molded mitten hands. The
pickup is deployed at 55 degrees on its flat plate and extended legs. The
first-person and player-held versions carry the plate low with the legs
hanging below the tube, preserving the recognizable mortar equipment.

Hands and forearms stay in the first-person model and atlas, keeping one
weapon draw per camera. First-person and pickup versions each use one static
pose; the held model follows all 198 original player attachment poses with
maximum rigid-fit RMS error about 0.0464 model units. There is no separate enemy
mortar attachment model.

Aiming raises the actual model onto the camera's center ray through the shared
0.18-second transition. Each local split-screen player has independent aiming
state. `mortar_model_ads.h` supplies sight and muzzle offsets from the authored
geometry, replacing the previous Mortar Cannon image overlay. Selectable
player colors are regenerated from the new atlases, and the player muzzle
table follows the reviewed front rim through every pose. Mortar ammunition,
projectiles and gameplay tuning retain their existing behavior.

## Asset budgets

| Version | Previous triangles | Current triangles | Reduction | Frames |
| --- | ---: | ---: | ---: | ---: |
| First person, including hands and arms | 1,400 | 740 | 47.1% | 1 |
| Deployed pickup | 900 | 328 | 63.6% | 1 |
| Player held, carried plate and legs | 1,632 | 312 | 80.9% | 198 |

`tools/assets/mortar-manifest.json` records exact counts, hashes, bounds,
sight/muzzle anchors and all-pose validation. Geometry counts describe asset
work; Raspberry Pi performance requires a controlled target-device comparison.

## Rebuild and verify

Reauthoring requires NumPy and Pillow. Normal Make and CMake builds verify
checked assets using only the Python standard library before packaging.

```sh
python3 tools/assets/build_mortar.py
python3 tools/assets/build_player_muzzle_points.py
python3 tools/assets/build_color_variants.py
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

python3 tools/assets/build_mortar.py --verify
python3 tools/assets/verify_mortar_runtime.py
OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_mortar.py
sh tests/input/run_mortar_model_ads_tests.sh
sh tests/renderers/run_view_weapon_clip_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

If muzzle topology changes, inspect the front rim and update the mortar
selector in `build_player_muzzle_points.py` before regenerating the player
attachment table.

Legacy decimation inventories exclude the mortar models and atlases; previous
records remain under `superseded_*` for comparison. A complete rebuild invokes
the dedicated generator. This weapon was never part of the separate ten-pickup
conversion inventory, which remains unchanged. The optional Pi overlay now
contains only four body models: all twenty-six legacy gun entries are omitted
and the authored guns come from the main package.

## Runtime visual review

The capture tool supports `--weapon 'Mortar Cannon'`. Compile the existing
review fixture as described in [the pump shotgun notes](shotgun-simple-shapes.md),
then use a fresh output directory:

```sh
python3 tools/performance/capture_m16.py \
  --label mortar-review --weapon 'Mortar Cannon' --ads --renderer gl1 \
  --package baseq2/plastic-platoon.pk3 \
  --map-file build/shotgun-review-map/pp_m16_review.bsp \
  --output build/mortar-qa-review --file-controls
```

Repeat with `--renderer gl3` and a fresh directory for GL3. Add
`--four --mixed-weapons` to alternate pistol and mortar players and assert
independent aiming. The current control regression switches to the authored
Rifle and verifies its model ADS. Hand-grenade image-overlay behavior remains
covered by the production C regressions. Host visual checks establish
appearance and behavior; target-device frame rates require measurement.

Final captures use the mortar's 22-unit ADS eye relief, which leaves space for
the existing 12-unit backward kick without moving the camera into the deep
tube. The shared 0.18-second aiming transition and mortar recoil/ballistics are
unchanged. The asset regression checks the production transform across aiming
and recoil, including the previous alignment's failure case.

| Capture | Directory | Views |
| --- | --- | ---: |
| GL1 single player | `build/mortar-qa-gl1-verified` | 8 |
| GL3 single player | `build/mortar-qa-gl3-verified` | 8 |
| Software single-player smoke | `build/mortar-qa-soft-verified` | 8 |
| GL1 four-player mixed weapons | `build/mortar-qa-four-verified` | 5 |
| GL1 complete deployed-pickup preview | `build/mortar-qa-gl1-pickup-full` | 4 |

All five manifests report completion and return code zero. The captures use package SHA256
`6619512227484c9419affa4903d380ac851bbda185c5495870224cc8df9beef2`
and revised executable SHA256
`0c9fb60c5131df6fa382303d0c7fa153046b32e46f53e64887d248f798b7a37f`.
The OpenGL singles ran sequentially and captured observed hip/ADS recoil of
0.970831/0.970817 in GL1 and 0.846140/0.867108 in GL3. Their actual firing
images keep the camera outside the model; the passing shell can briefly cross
the sights, retaining the existing projectile behavior. Software covers the
actual rendered hip, ADS, firing, release, held and pickup paths with its dark
palette and faceting.

Inspection confirms a clear real-model sight picture, a visible carried plate
in front of the torso and hanging bipod legs. The lower, oblique pickup camera
shows the complete deployed baseplate, elevated tube and leg support. The mixed
four-player pass equips pistol/mortar pairs and waits for actual models and
independent aim endpoints `[1, 0, 1, 0]`, followed by `[0, 1, 0, 1]`, before
recording both firing arrangements. The single-player control regression also
confirms the authored Rifle still aims correctly.
