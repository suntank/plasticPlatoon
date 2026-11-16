# Authored flying projectiles

The actual flying rocket, armed hand grenade and shared grenade-launcher/mortar
round use the same original low-poly shapes and palette as their ammunition
pickups. The rocket points along local +X with its exhaust at the existing
entity origin. The spinning grenade and launcher round stay centered on that
origin. The armed hand grenade uses its body and fuse after releasing the
pickup's pin and lever.

All three retain their existing model paths. Spawn functions, collision
bounds, speeds, spin, fuse timing, damage, effects, trails and sounds keep
their established behavior. Mortar shots share the launcher-round model.
The first-person hand-grenade model and ammunition pickups remain separate.
Each flying model uses one static frame and one atlas.

## Asset budgets

| Flying model | Previous triangles | Current triangles | Reduction |
| --- | ---: | ---: | ---: |
| Rocket | 500 | 128 | 74.4% |
| Armed hand grenade | 800 | 88 | 89.0% |
| Grenade-launcher/mortar round | 999 | 76 | 92.4% |

Together they use 292 triangles instead of 2,299, an 87.3% reduction.
`tools/assets/projectiles-manifest.json` records exact files, source geometry,
origins, bounds and all-face validation. These counts measure geometry work;
Raspberry Pi frame rates require a controlled device comparison.

The flying rocket uses the new `models/objects/rocket/skin.png` atlas.
The grenade models retain their own `objects/grenade/skin.png` and
`objects/grenade2/skin.png` paths with authored ammo-style art. The old shared
rocket-ammo atlas remains byte-identical compatibility media, and the new
rocket pickup continues using its isolated `skin_ammo.png`.

## Mission overlay consistency

Tank and helicopter operations embed their own rocket model, which can shadow
the main package. `build_projectile_overlays.py` replaces only that MD2 and adds
its dedicated atlas in those two archives. The old shared atlas and every
other member retain their exact contents. The mission packagers discover the
new atlas from the model and explicitly retain the compatibility atlas on
future builds.

`projectile-overlays.json` pins a SHA-256 fingerprint of sorted member names,
lengths and content hashes for all unmanaged members: 32 in the tank operation
and 29 in the helicopter operation. Both archives are preflighted before any
write. Each archive is replaced atomically, preserving existing member metadata
and the archive comment. Repeated syncs leave already-correct archives intact.
The resulting archive and managed-file hashes are recorded in
`projectile-overlays-manifest.json`.

The sync refuses an unrelated member edit, addition or deletion instead of
overwriting it. An intentional mission change therefore needs its checked
fingerprint updated as part of that change. The helper writes only project
archives; ordinary release staging copies them into the portable package.
It does not alter installed user archives.

## Rebuild and verify

Reauthoring uses NumPy/Pillow. Normal Make/CMake gates and mission sync use
only the Python standard library. A full asset rebuild generates the
projectiles, synchronizes mission copies and verifies the outputs before
packaging.

```sh
python3 tools/assets/build_projectiles.py
python3 tools/assets/build_projectile_overlays.py
python3 -S tools/assets/verify_projectiles_runtime.py
python3 -S tools/assets/build_projectile_overlays.py --verify
make -j4 all
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3

OPENBLAS_NUM_THREADS=1 python3 tests/assets/test_projectiles.py
python3 tests/assets/test_projectile_overlays.py
python3 tests/assets/test_ammo.py
python3 tests/assets/test_md2_assets.py
sh tests/projectiles/run_tests.sh
sh tests/performance/run_effects_tests.sh
python3 tools/assets/build_platoon.py verify
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
```

The asset suite checks closed geometry, retained origins, flight orientation,
armed-grenade details and exact mission copies. Compiled production spawn tests
exercise player and enemy launch paths and confirm unchanged movement, fuse,
collision and effect values. They also pass with undefined-behavior and
floating-to-integer overflow sanitizers enabled. Mission-sync fixture tests
cover idempotence, unrelated content/metadata preservation, stale source
rejection, safe preflight failure and repair of an old managed rocket.

## Live-fire visual review

The projectile capture tool fires the real Rocket Launcher, Grenades, Grenade
Launcher and Mortar Cannon in an isolated high-ceiling lane. It never spawns a
projectile directly. Read-only game-layout probes record the live entity's
position, angles, velocity, angular velocity, movement type, effect flags and
fuse deadline.

```sh
python3 tools/performance/capture_projectiles.py --prepare-only \
  --q2tool /path/to/q2tool --output build/projectile-review-map-lit
python3 tools/performance/capture_projectiles.py --renderer gl3 \
  --map-file build/projectile-review-map-lit/maps/pp_projectile_review.bsp \
  --output build/projectiles-qa-gl3-verified
```

Use fresh output directories with `--renderer gl1` and `--renderer soft` for
the other renderers. Add `--split` for the two-local-player observer pass, or
`--cases rocket hand launcher mortar` to select launch paths. The tool uses
private file controls and copied binaries; mission operation archives are
also loaded so embedded models participate in the normal asset search.

Flight sampling uses a quarter-speed world clock. Single-view close and
oblique pictures pause the natively fired projectile at a measured gate,
reposition only the inspection camera, and assert that its position and
angles stayed fixed during inspection. A second sample resumes the same
entity's native motion. Its velocity, gravity, spin and fuse are never
rewritten. Impact/fuse-expiry pictures run at normal speed and verify the
projectile disappears. The split pass keeps the world unpaused at quarter
speed, with a real second local player positioned as a noclip observer.

| Final capture | Directory | Images |
| --- | --- | ---: |
| GL3 four launch paths | `build/projectiles-qa-gl3-verified` | 16 |
| GL1 four launch paths | `build/projectiles-qa-gl1-verified` | 16 |
| Software four launch paths | `build/projectiles-qa-soft-verified` | 16 |
| GL1 two-player live observer | `build/projectiles-qa-split-final` | 4 |

All four reports complete successfully with return code zero and package
SHA256 `302a168dc00eebb3211c18ac8c88dd7481a304826ea07a388f1233769c28fd6d`.
Inspection confirms the rocket nose follows its direction of travel, its fins
and exhaust stay at the trail end, and the body has the intended original
scale. The armed grenade has its body and fuse without the released pin or
lever. Launcher and mortar shots show the same compact round with distinct
native arcs. Both local views see the same moving projectile and trail.

The rocket samples retain velocity `[650, 0, 0]` and unchanged orientation.
The hand-grenade samples change from 90 to 180 degrees on all three axes;
launcher and mortar samples change from 120 to 180 degrees. All three retain
native angular velocity `[300, 300, 300]`. The mortar's first measured sample
is still rising at 330 units per second vertically. All twelve normal-speed
impact/fuse captures show the native burst and model removal. Software retains
its dark palette and blocky particles while rendering the authored bodies
and effects. These host images establish appearance and behavior, not
Raspberry Pi frame rates.
