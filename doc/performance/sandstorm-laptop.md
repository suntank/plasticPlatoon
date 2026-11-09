# Sandstorm laptop performance repair — November 8, 2026

The reported slowdown outdoors and in the central sandbox had two contributing
causes: CPU rendering through the desktop's X11 connection, and a map compiled
with fast visibility. The model and texture inventory was already optimized.

## Graphics startup

The existing live game's log identified GL1 at 1920×1080 with Mesa llvmpipe.
The laptop is an Intel i7-8550U with UHD Graphics 620. An isolated SDL/OpenGL
probe found that X11 reported “screen 0 does not appear to be DRI3 capable” and
selected llvmpipe, while native Wayland selected
`Mesa Intel(R) UHD Graphics 620 (KBL GT2)`.

SDL2 startup now prefers native Wayland on Linux when `WAYLAND_DISPLAY` is set.
Explicit `SDL_VIDEODRIVER` environment settings or hints retain their priority.
If native video initialization fails, normal SDL discovery is retried. Older
SDL headers/runtimes retain their prior behavior. SDL3 is unchanged.
No resolution, texture, population, effect, lighting or gameplay settings were
reduced. Restart the game to load the rebuilt `release/quake2` and renderer.

GL1 also computes large MD2 meshes' repeated normal-based vertex colors once
per normal index per draw. The regression fixture checks exact colors and
interpolated positions against the prior production formula, including shell,
alpha, minimum-light and static-pose cases. Small meshes retain the prior path.
Its isolated CPU-preparation improvement is modest; the graphics driver change
accounts for the large observed gain.

## Map visibility

The current edited source is `baseq2/maps/pp_sandstorm.map`, not the older
`maps/source` snapshot. The installed BSP's visibility lump was byte-identical
to an independent fast-VIS build of that source. It exposed an average of
428/513 clusters (83.4%); the drop-zone cluster exposed 500/513.

`tools/performance/rebuild_visibility.py` rebuilds full visibility and checks
that the source still reproduces the existing geometry and entities. It copies
only the new visibility lump into the original lit BSP, preserving every other
lump, including collision, face lightmap metadata, and baked lighting. See
`maps/README-sandstorm.md` for the command and package precedence requirements.

## Asset audit

Seventy placed soldiers use 1,784-triangle bodies plus 1,399–1,616-triangle
weapons. Four ants use 1,240 triangles each. A helicopter including its rotors
uses 1,376 triangles. Actor world skins are generally 256²; the blaster shares a
512² first-person skin. The map references 22 materials, none larger than 512².
The active project archive contains the already-optimized assets. No further
mesh simplification or texture reduction was justified by this inspection.

## Measurement and validation

Local raw captures, original config/log, recordings, before/fixed binaries and
build logs are retained under `build/sandstorm-performance/`; original map and
full-VIS compiler evidence are under `build/sandstorm-performance-map/`.
These build directories are ignored by Git. The compact summary is in `sandstorm-laptop-results.json`.

The controlled comparison replays the same outdoor and courtyard recordings
at 1920×1080, GL1, VSync off, no MSAA/anisotropy/shadows, unchanged texture
quality. Each capture has 60 complete frames with 10 warmup frames discarded;
two trials per configuration are descriptive measurements, not long-session
frame-rate guarantees. Compilation is suspended or complete during timed runs.
The user's original game remains running throughout; desktop scheduling and
its background load remain sources of variation. Sound is disabled in captures.

A demo recorded with old visibility retains its original server entity
snapshots. It can measure the improved client world culling, but understates
additional server-side entity visibility savings during a fresh live map load.
The fixes do not establish a complete mission playthrough or sustained combat
performance guarantee.

Focused checks:

```sh
sh tests/renderers/run_sdl2_video_driver_tests.sh
sh tests/renderers/run_gl1_alias_color_tests.sh
python3 tests/performance/test_rebuild_visibility.py
python3 tests/performance/test_map_tools.py
make -j2 client ref_gl1
```

## Results

Median complete-frame milliseconds in two trials (lower is better):

| Scene | Original X11 / CPU rendering | Original engine with native GPU | Fixed startup, renderer and full VIS |
| --- | --- | --- | --- |
| Outdoor drop zone | 112.677 / 108.075 | 11.509 / 11.279 | 10.856 / 9.590 |
| Central courtyard | 88.487 / 79.345 | 7.771 / 7.580 | 7.822 / 7.500 |

The GPU connection is responsible for most of the speedup. Full VIS reduces
drawn world triangles from 16,932 to 10,960 outdoors (35.3%), and from 10,578
to 6,259 in the courtyard (40.8%). Recorded model submissions are identical,
as expected from replaying the same server snapshots. The courtyard's timing
change after the GPU fix is within trial variation; lower triangle counts
should not be confused with an equal percentage FPS gain.

Average visible clusters across the whole map fell from 428.035/513 to
252.101/513 (83.44% to 49.14%). Full-VIS map SHA256:
`24617a1995cbcd8e7b286914e874e79365415de1b9ce6e2ac4c2b32b4be6cb9c`.
All six installed loose/archive map copies match, and all non-VIS BSP lumps
are unchanged. Fixed screenshots of both outdoor scenes were inspected.

The rebuilt normal game selects Wayland/Intel without a manual environment
variable. GL1 and GLES1 builds, 74 production MD2 loader/cache checks, renderer
lifecycle checks, focused rendering/display tests, map-tool tests and Sandstorm
mission-entity/save-load tests passed. A fresh two-player 1080p map load also
completed 180 frames on the Intel GPU (median complete frame 15.750 ms after
60 warmup frames); this is a startup smoke check, not sustained combat evidence.

### Test isolation correction

A startup smoke check exposed an existing runner bug: portable mode writes
settings beside the executable even when `--data` points elsewhere. That one
check wrote `release/baseq2/config.cfg`. The known prior portable settings
(GL3, fullscreen, native resolution and VSync) were restored; other overridden
archived graphics values were restored from the saved active playing profile.
The exact prior portable config was not backed up, so exact restoration of
those other portable-only preferences cannot be claimed. Controls and unrelated
values were retained; the active game's home-directory config was not changed.

The benchmark runner now rejects an executable outside its isolated data
folder before creating files, including executable symlinks that resolve
outside it. New tests verify both playing configurations and directories stay
unchanged on rejection. Final measured runs use copied binaries and data in
the same isolated runtime. The unsuccessful smoke summary is excluded above.
