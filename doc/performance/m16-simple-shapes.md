# M16 simple-shape experiment

## What changed

The M16 has been rebuilt from original polygonal prisms, open profile rings,
and six/eight-sided tubes. The new mesh does not reuse decimated topology.
The stock, receiver, curved magazine, pistol grip, open carry handle, front
sight and muzzle retain the previous rifle's overall proportions.

The first-person version includes two forearms and two molded mitten hands.
Rounded palms, fused finger masses and distinct wrapping thumbs follow the
army-man reference. Painted grooves suggest fingers without separate digits.
The right hand encloses the grip; the support hand cups the handguard.
The hands use
the rifle's existing MD2 entity and the same 256 by 256 diffuse atlas, so they
do not introduce another model submission or material pass. The rifle itself
uses 372 triangles; the hands, forearms, thumbs and cuffs add 428.
Rear caps close the handguard and flash hider so neither exposes the background
from the player's viewpoint or behind a held/pickup rifle.

M16 ADS now moves the actual model into a centered sight picture over 0.18
seconds. The model remains visible instead of being replaced with an image.
Its rear sight is 9.5 model units from the eye at full aim. Idle bob fades
out as the sights align. Existing recoil, raising and ADS input/sensitivity
behavior remain in use. Each split-screen player owns a separate aim blend.
The pistol now shares this model-ADS path with its own offsets; the remaining
weapons continue using their existing image overlays.

## Measured asset budgets

Baseline is the shipped repository at
`7b30465800c9aa479d4e231010772e49a4358559`, not the much larger original
imported meshes. The complete output hashes, bounds, frame counts and pose
transfer measurements are in `tools/assets/m16-manifest.json`.

| Representation | Before triangles | After triangles | Reduction | Position vertices, before / after | Render vertices, before / after |
| --- | ---: | ---: | ---: | ---: | ---: |
| First person, now including hands | 1,400 | 800 | 42.9% | 696 / 744 | 1,480 / 1,097 |
| Pickup | 800 | 256 | 68.0% | 396 / 304 | 974 / 448 |
| Player held | 1,398 | 256 | 81.7% | 695 / 304 | 1,584 / 448 |
| Enemy held | 1,444 | 256 | 82.3% | 718 / 304 | 1,607 / 448 |

The player fallback `weapon.md2` matches `w_machinegun.md2`. The taller enemy
variant uses the same 256-triangle topology with the existing foot-anchored
1.2 scale. Position vertices matter for CPU animation work; render vertices
also include normal/UV boundaries. Triangle reductions alone do not measure
whole-frame performance.

The first-person MD2 remains a single static pose. The split-screen M16 path
now explicitly uses frame zero and copies the final weapon origin into its
old origin, making it eligible for the existing static geometry cache.
Procedural recoil, raising and aiming do not require duplicate MD2 frames.

## Animation, color and effect integration

All 198 player poses and all 475 enemy poses retain their original frame
names. The new rigid rifle follows rotations/translations fitted from every
archived weapon pose. The old mesh supplies pose references only. Every new
exported pose is checked for collapsed or inverted triangles after MD2 byte
quantization. The source animation archive is hash-pinned and does not require
Git history or a user's local installation.

The atlas uses the soldier's established brightness range, including the
existing player colors and red enemy material. Its painted finger details,
handguard grooves and magazine ribs remain texture details. Updating the
M16's original atlas and then rebuilding color variants preserves the existing
global recoloring rules.

The third-person muzzle-point table was regenerated from the replacement's
reviewed front rim through every player frame. M16 first-person muzzle offsets
also follow the ADS translation. The split effect scope is decoded from its
one-based identifier before looking up the player's aim blend.

## Rebuild and verify

Normal engine builds package the checked assets and use a standard-library
verification gate. Reauthoring the mesh additionally needs NumPy and Pillow.
The exporter resolves tied normal directions by table order and rounds report
diagnostics to twelve significant digits to avoid CPU-dependent floating-point
noise in regenerated assets and manifests.

```sh
python3 tools/assets/build_m16.py
python3 tools/assets/build_soldier_height.py
python3 tools/assets/build_color_variants.py
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
make -j4 all
```

If the world mesh's muzzle topology changes, inspect its front rim and update
the M16 selectors in `build_player_muzzle_points.py`, then regenerate that
header before compiling the client:

```sh
python3 tools/assets/build_player_muzzle_points.py
```

The previous decimation records remain under `superseded_*` in the legacy
manifests for comparison. Active decimation inventories exclude the M16, and
`platoon.json` declares the procedural generator's ownership. A full legacy
conversion cannot silently restore the old rifle over the new one.
The optional Pi actor overlay also omits its five legacy M16 entries. Rebuild
that overlay before installing it with the new main package so an old PKZ
cannot take precedence over the authored models.

Relevant checks:

```sh
python3 tests/assets/test_m16.py
python3 tests/assets/test_authored_hands.py
bash tests/input/run_m16_model_ads_tests.sh
python3 tests/assets/test_player_muzzle_points.py
python3 tests/assets/test_color_variants.py
python3 tests/assets/test_md2_assets.py
python3 tests/assets/test_md2_animation.py
python3 tools/assets/verify_m16_runtime.py
python3 tools/assets/build_m16.py --verify
python3 tools/assets/build_platoon.py verify
python3 tools/assets/md2_assets.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

The optional old decimator determinism test is skipped when PyMeshLab is not
installed. The new primitive model generator does not use that dependency.

## Visual review

`tools/assets/render_m16.py` imports the exported MD2 triangles, UVs and normal
indices into Blender. Its saved project includes the actual exported models,
packed textures, three camera scenes, and separate editable source scenes with
named primitive parts. These are studio renders of the real geometry.

`tools/performance/capture_m16.py` captures actual GL1/GL3 first-person, ADS,
pickup, held and four-player views in an isolated runtime. Its opt-in QA
controller equips and positions real local players. It asserts independent
ADS blends, release-to-hip behavior, and preservation of the Shotgun's image
overlay path. Capture manifests pin the package, executable and renderer.

## Performance interpretation

The checked host comparison is recorded in
`doc/performance/m16-simple-shapes-host.json`. It uses the same current
executable and renderer for both asset packages, four local players at fixed
camera positions, GL1, normal baked lighting, and a 1280 by 720 offscreen
Mesa llvmpipe display. The two 480-frame runs were sequential, with 120 warm-up
frames discarded from each. ADS and firing were exercised after timing.
These historical timings precede the rear-cap repair, which adds twelve
first-person and ten world-model triangles. A later hand repair adds twenty
first-person triangles to close the shared arm, cuff and thumb ends, and a
solid right-wrist connection adds another twenty triangles. The subsequent
molded-mitten redesign adds 264 triangles for the fuller palms, fused finger
masses and wrapping thumbs. These historical timings were not rerun for the
redesigned hands; the asset table above is current.

| Complete four-view display frame | Old assets | New assets | Change |
| --- | ---: | ---: | ---: |
| Model triangles | 21,420 | 11,996 | 44.0% fewer |
| Client vertex submission bytes | 285,200 | 183,296 | 35.7% fewer |
| Draw calls | 34 | 34 | Unchanged |
| World triangles | 1,051 | 1,051 | Unchanged |
| Median CPU-side screen work | 4.128 ms | 3.008 ms | 27.1% lower in this sample |
| Median complete display interval | 8.481 ms | 8.447 ms | Both near the 120 FPS cap |

The M16 contribution in that scene is four first-person draws and five visible
player attachments, totaling 12,590 versus 3,166 rifle triangles. Its one-time
first-person static position buffer is 17,760 versus 10,332 bytes; all four
viewports share that buffer, and per-frame static uploads remain zero.

The pose-cache result also matters: interpolated vertices increased from 1,580
to 2,350 and cache hits fell from eight to six per frame. That pattern is
consistent with two distinct idle pose keys instead of one. Actor pose timing
was not synchronized, so this capture does not establish a reduction in CPU
pose work. A single sequential software-renderer pair and a capped display
interval also do not establish a meaningful whole-game FPS gain.

The asset counts establish substantially less M16 geometry and submission
work. Host software-renderer captures are useful for checking workload and
regressions, but do not establish a Raspberry Pi Zero 2 W frame-rate gain.
The target-device comparison must use the same map, four player positions,
visible enemies, resolution, internal scale, renderer and quality settings.
Measure whole-frame median and high-percentile time with the old and new
assets, ideally alternating several runs after warm-up.

For the target of 30 FPS, the whole display frame must fit within 33.3 ms.
World visibility, actors, effects and pixel fill remain part of that budget.
This experiment should be judged as one weapon replacement, not as proof that
all four-player scenes now meet that target.
