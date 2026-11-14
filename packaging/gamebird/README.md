# Game Bird test installation

These files adapt Plastic Platoon to the current Game Bird native-package
format used alongside Drop Grid. `game.json` launches `launch.sh`; copy
`gamebird.cfg` into the package's `baseq2/` directory. The default launch starts
`pp_sandstorm`. No global SDL, input, boot, or root-filesystem changes are
needed.

## Installed Pi

The original test installation on 2026-11-01 used engine commit
`0b9598188a3c9f7a6d00fedf23605664f20b16a9`:

- Device: Pi Zero 2 W, 32-bit Raspbian 13, kernel `6.12.47+rpt-rpi-v7`.
- Source/build: `/data/build-sources/plastic-platoon-0b95981/`.
- Package: `/home/gamebird/gamebird-shell/data/nest/games/plastic-platoon/`.
- Library: `/home/gamebird/gamebird-shell/apps/nest-plastic-platoon.gbgame`.
- Saves/settings: `/home/gamebird/gamebird-shell/data/nest/saves/plastic-platoon/`.
- Launcher log: `/home/gamebird/gamebird-shell/data/nest/logs/plastic-platoon.log`.

The package, library record, and saves are on Game Bird's persistent `/data`
partition. The root filesystem is a RAM overlay and must not hold the build or
game assets. The library title is **Plastic Platoon**, in **GAMEBIRD**.

The 2026-11-11 update builds the current source natively in
`/data/build-sources/plastic-platoon-gamebird-20261111/`. The installed package
now contains the standalone asset archive and all mission packs, including
Sandstorm. The previous package is retained beside it as
`.plastic-platoon.backup-20261111`; existing saves/settings were preserved.
The hardware control check passed Sandstorm New Game, movement, ADS pitch and
inversion, turning, crouch persistence through pause, jump recovery, weapon
selection, and Select quick grenade. Its report, frame CSVs and screenshots are
in that build directory's `smoke-20261111T184437Z/controls/` directory.

The first check exposed an existing device swap-service fault:
`rpi-resize-swap-file.service` tried copying the 425 MB `/var/swap` into the RAM
overlay and triggered the OOM killer. It was temporarily masked with
`sudo systemctl mask --runtime --now rpi-resize-swap-file.service`.
Reboot clears this workaround; `sudo systemctl unmask --runtime
rpi-resize-swap-file.service` also removes it. The device has since rebooted
with working zram swap and the service unmasked; the second update required
no swap workaround. Persistent swap settings were not changed.

The second November 11 update enables the compact HUD, swaps the physical
north/east ADS and modifier actions, adds modifier + up for F1 help/objectives,
and removes sprite-generation success messages. The full handheld control
check passed 24 checks over 716 frames. A final visual check verified the HUD
and wrapped objective text at 240x240; its output directory is recorded in
`latest-smoke-r2-final-path.txt` in the native build directory. Each update
retains the previous package beside the installed one; the shell is restored
after checks and the existing save directory is unchanged.

## Build and deploy

Build natively on the Pi to match its 32-bit userspace and installed SDL/Mesa:

```sh
env -u DEBUG -u ASAN -u UBSAN \
  TMPDIR=/data/build-sources/plastic-platoon-gamebird-20261111/tmp \
  make -j2 WITH_SDL3=no WITH_OPENAL=no VERBOSE=1 \
    config client game ref_gl1 ref_gles1
```

Create the temporary directory first. This builds `quake2`, `baseq2/game.so`,
GL1/GLES1 renderers. Build the assets on the development host with `make all`
and copy its generated `release/baseq2/` archives and tuning data. The Pi already
has the compiler, SDL2, OpenGL/GLES, and cURL development packages. OpenAL is
optional and was disabled because its development headers are absent; audio
uses the engine's SDL backend.

Copy `quake2`, `ref_gl1.so`, and `ref_gles1.so` to the package root. Copy
`game.so`, `plastic-platoon.pk3`, its manifest, every `operation-*.pk3`,
`gamebird.cfg`, and tuning data to `baseq2/`. Stock Quake II PAKs are not needed.
Do not copy an x86 game module, old `config.cfg`, or another
installation's saves. Keep `launch.sh` executable.

Create a library record matching the installed Drop Grid format, with
`format_version: 1`, `managed_by: "gamebird-nest"`, `id: "plastic-platoon"`,
`title: "Plastic Platoon"`, and absolute `package_dir`, `save_dir`, and
`log_path` values. The library daemon discovers it automatically. The
`.gbgame` record belongs in `apps/`; the script and executable stay inside
the package, so the game appears only once.

The launcher selects SDL KMSDRM and identifies the SPI panel by hardware path
rather than assuming a DRM card number. It follows Game Bird's TV-mode marker
when HDMI is selected. Handheld output was tested; HDMI was not connected.
The launcher routes Yamagi's config directory into `GAMEBIRD_SAVE_DIR` without
changing the user's home directory. Normal Game Bird launches release the
shell's exclusive controller grab before executing the game.

## Handheld controls

| Control | Action |
| --- | --- |
| D-pad up/down | Forward/back; look up/down while aiming |
| D-pad left/right | Turn |
| L/R | Strafe left/right |
| SDL A | Fire |
| SDL B | Jump |
| Physical north (SDL X / west) | Hold to aim down sights |
| Physical east (SDL Y / north) | Hold for weapon/crouch/help controls |
| Modifier + D-pad left/right | Previous/next weapon |
| Modifier + D-pad down | Toggle crouch |
| Modifier + D-pad up | Toggle help/objectives (F1) |
| Select | Quick grenade |
| Start | Game menu; use Quit to return to Game Bird |

Jump also ends crouching. **Options → gamepad → invert pitch** reverses
D-pad up/down while aiming. The modifier takes priority over aiming and
suppresses D-pad movement/looking while selecting weapons or toggling crouch.
The native game uses SDL button names, which differ from physical positions
on this handheld. The profile swaps ADS/modifier to match those positions.

`scr_gamebird_hud 1` selects the compact handheld HUD: grenades in the upper
right and health, armor, and ammo in three evenly spaced bottom columns.

## Aiming and weapon update

ADS look speed defaults to half normal speed for mouse, sticks, gyro and
digital controls (`cl_ads_sensitivity 0.5`). The handheld profile enables
`cl_gamebird_autolevel 1`: releasing ADS linearly returns pitch to level over
`cl_gamebird_autolevel_time 0.25` seconds. New pitch input, re-aiming, a menu,
death or a level transition cancels that return.

`cl_aimassist 1` enables controller assistance against visible, living hostile
monsters in single-player/co-op. ADS smoothly attracts the view; hip fire
leaves the camera steady and moves the reticle to match the assisted shot.
Both modes target the same chest/body center. Assistance requires visibility
of that body point and does not switch to an exposed head above cover.
Mouse/keyboard input disables the controller signal. Friendlies, players,
dead enemies and occluded targets are excluded. `cl_aimassist_strength 8`
and `cl_aimassist_speed 30` control ADS attraction; the speed cap remains
below full handheld ADS turn speed so the player can pull away. Server
settings are `sv_aimassist`, `sv_aimassist_range`, `sv_aimassist_ads_cone`,
`sv_aimassist_hip_cone` and `sv_aimassist_hip_speed`.

Ants and spiders now immediately use their existing explosive gib effects on
every death. The unlimited-ammo pistol hides its ammo display; finite-ammo
weapons keep their normal counts and empty-ammo warning.

This update passed 20 hardware checks over 346 frames, including a measured
ADS/hip turn ratio of 0.500001, monotonic return from -24 degrees to level,
actual ADS target convergence, a stationary hip camera with shot-aligned
reticle offsets, pistol hiding and finite rifle ammo. Output is in
`/data/build-sources/plastic-platoon-gamebird-20261111/smoke-r3-20261111T200001Z/controls/`.
The prior package is `.plastic-platoon.backup-20261111-r3`. Existing save
layouts, saves and settings are preserved; the shell is restored after testing.

The color and soldier-height update was built natively with optimized ARM
client/game and GL1/GLES1 renderers on November 11. The installed archive includes
all 374 color variants and six taller soldier/weapon models. The handheld check
verified Sandstorm at 240x240, blue and pink weapon changes, ADS, and red taller
soldiers using the Broadcom GL1 renderer. Enemy plastic uses the same fully
saturated red as its held weapons, preserving brightness, shadows and details.
Ten generated player-body atlases now share their weapon pigment and brightness
recipe in both normal and pistol poses, split-screen, and the player preview.
Canonical skins, icons, and existing weapon textures remain unchanged.
Cycling weapon overlays retained at most eight colored ADS images. The latest
321-frame check and all twenty color/pose views exited cleanly; persistent
save/settings hashes were unchanged and the Game Bird shell was restored.
Output is in
`/data/build-sources/plastic-platoon-gamebird-20261111/smoke-player-colors-20261111T213728Z/`.
The previous installed package is retained beside the game as
`.plastic-platoon.backup-colors-20261111T213728Z`.

Any controller can now leave split-screen setup using Select or the menu's
cancel button. If marked Ready, the first press clears Ready and the second
returns to settings. This also works when the only controller is assigned to
player two and player one has the keyboard. Controller release state is cleared
at the lobby boundary so the next confirm press works immediately. One- and
two-controller SDL regression checks passed with the handheld profile.

USB/Bluetooth analog-controller input remains available. These bindings also
apply to secondary split-screen players, with separate aiming, modifier,
crouch, and weapon controls for each player.

## Handheld menu pass (2026-11-12)

The 240x240 interface uses a native pixel layout with high contrast cards, a
lime selection rail, and setting values stacked below their labels. Long menus
scroll by complete rows and keep the selected control visible. Save lists show
numbered slots and mission names, with explicit left/right page hints. Controller
bindings use short button names such as A, B, L, R, Select, and D-pad; the pause
menu includes Resume mission. System messages wrap within their own screen.
GL1/GLES1 solid panels flush earlier queued glyphs so HUD and console text
cannot bleed through pause menus or the scoreboard.

Squad setup keeps every player's Ready indicator visible while its detail card
follows the last player to use an input. Pause and scoreboard text fit each
player's viewport, including the handheld's 240x120 split-screen views.

Run the reusable host capture test from the repository root:

```sh
python3 tests/menus/smoke_menus.py --size 240x240
```

The test exercises 23 registered menu entry points and 45 states, including
scrolling, save lists, bindings, display settings, controller setup, and modal
messages. It retains screenshots and a report in an isolated runtime. Host
captures verify layout and navigation; physical legibility needs review on the
handheld display. The native build workspace for this pass is
`/data/build-sources/plastic-platoon-menus-20261112T160800Z/`.

The verified native client and GL1/GLES1 renderers were installed on November 12.
All 23 menu entry points were captured at 240x240 using Broadcom/KMSDRM, and a
separate live Sandstorm check verified pause and the Resume action. Host checks
also covered four-player pause panels, exit-hold progress, and the shared
scoreboard. The previous package is retained as
`.plastic-platoon.backup-menu-20261112T160800Z-r5`; all 27 existing save/settings
files were unchanged and `gbshell.service` was restored. The build directory's
`deployment-menu-final.json` records the installed hashes and audit results.

The existing swap-service copy-up fault recurred during device checks and
triggered the OOM killer. The documented `rpi-resize-swap-file.service` runtime
mask was applied for those checks. The persistent repair below supersedes that
temporary workaround.

## Persistent swap repair (2026-11-12)

The Pi now uses 256 MiB of compressed zram swap at priority 100, with a separate
1 GiB disk fallback at priority 10 in `/data/system/swap/swapfile`. The fallback
file is preallocated on persistent ext4, mode 0600, in a mode 0700 directory.
Its native `data-system-swap-swapfile.swap` unit requires the `/data` mount and
checks that it is a mountpoint; it never allocates a replacement in the RAM
overlay if storage is unavailable.

The protected root contains `/etc/rpi/swap.conf.d/80-gamebird-overlay-swap.conf`
with `Mechanism=zram` and `Zram.FixedSizeMiB=256`, plus the enabled fallback swap
unit. These were installed through `overlayroot-chroot`. The stock hybrid
zram/writeback mechanism was removed from the boot dependency chain, so
`rpi-resize-swap-file.service` no longer runs or touches `/var/swap`. No service
mask is required. Boot firmware, networking, and the existing fstab were not
changed.

The initial software reboot stalled at the splash screen; a full power cycle
returned to Game Bird normally. Both swap tiers then started automatically from
the persisted configuration. A bounded 512 MiB anonymous allocation filled with
random bytes passed, checking 16 retained memory samples, with zero OOM kills.
Peak swap usage was 256 MiB of zram and about 281 MiB of disk fallback. The RAM
overlay stayed at 4.6 MiB used, and the shell remained active.

Backups, installer/verifier scripts, boot IDs, hashes, and verification results
are retained in `/data/system/maintenance/swap-fix-20261112T172047Z/`.

## Original device verification (2026-11-01)

- Actual engine output: SDL `KMSDRM`, `Broadcom`, `VC4 V3D 2.1`, OpenGL 2.1
  Mesa `25.0.7-2+rpt3`, actual 240×240 framebuffer.
- Native ARM executable/module linkage passed; no packages were installed into
  the temporary root overlay.
- Single-player sandbox: 180 complete frames, exit 0, screenshot saved, settings
  and automatic saves written into the persistent save directory.
- Split-screen sandbox: 180 complete frames and 360 views, exactly two
  240×120 viewports, clean return through `gblaunch`.
- Registered-library/control check: 300 complete frames. Injecting and releasing
  the existing controller's D-pad Left changed yaw from 45° to 155.006°.
- `gblaunch --db data/catalog.db --game-id 133 --dry-run` resolves the package
  correctly. Game IDs are local database identifiers, not portable package IDs.

These were short functional checks with the playable 30 FPS cap and VSync
enabled, not uncapped optimization comparisons or sustained-wave benchmarks.
After 60 warmup frames, complete-frame medians were 33.507 ms for single player
and 62.269 ms for split screen; P95 values were 34.791 ms and 71.188 ms. CPU
throttling flags were zero. The two-player camera starts in a different area
and may activate additional gameplay, so this is not an isolated camera-cost
comparison. See `doc/performance/pi-zero2.md` for rigorous measurements.

Raw CSV/settings/screenshots are in the game's persistent `baseq2/perf/` and
`baseq2/scrnshot/` directories. Build and helper logs are in the source/build
directory. The stock-sized single-player HUD clips at 240 pixels wide, and
the supplied content reports existing `common/caulk` texture and ammo-profile
name warnings. These game/content issues were retained for testing rather
than changing the map, wave rules, or gameplay during installation.

For an SSH check, release the shell's controller grab by temporarily stopping
`gbshell.service`, run the registered `gblaunch` command as `gamebird`, and
restart the shell afterward, including on failure. Merely pausing the shell
leaves its exclusive input grab in place. Do not run the engine as root.

For direct diagnostics, set `GAMEBIRD_GAME_DIR` and `GAMEBIRD_SAVE_DIR`, then
run `launch.sh` with extra engine arguments. Explicit arguments replace the
default map command. `PLASTIC_PLATOON_RENDERER=gles1` selects the alternate
built renderer; `PLASTIC_PLATOON_MAP` changes the default map.

## Pickup distance LOD update (2026-11-12)

The five common bullet, shell, grenade, armor-shard and small-health pickups now
have additional distant models. Their close-up models and existing textures are
unchanged. One of each drops from 4,399 to 824 triangles when selected as a LOD.
The renderer chooses independently for each split-screen camera, requiring both
a distance of at least 256 units and a projected diameter of at most 12 pixels.
`r_pickup_lod 1` is the default; `r_pickup_lod 0` supports comparisons.

The native client and GL1/GLES1 renderers were built in
`/data/build-sources/plastic-platoon-pickup-lod-20261112T185707Z/`.
The five models passed native Broadcom/KMSDRM mixed near/far tests, including
exact triangle differences, video restart, map reload, toggle restoration and
missing-file fallback. All original archive payloads and the game module were
verified unchanged before installation. The prior package is retained as
`.plastic-platoon.backup-pickup-lod-20261112T185707Z`.

The build directory contains `deployment-pickup-lod.json` and
`pickup-lod-visual-qa/report.json`. Four-player measurements use fresh isolated
save directories and the same new build with LOD disabled/enabled, with actual
settings, inputs, map hashes and Endline train motion checked for each capture.

All twelve native sessions completed with their input, mode, viewport,
train-motion and death/respawn checks passing. Complete-display combat averages
with LOD disabled/enabled in the same new build were:

| Map | Normal FPS, off → on | Low FPS, off → on |
| --- | ---: | ---: |
| Sandstorm | 14.41 → 14.81 | 20.08 → 20.70 |
| Endline bridge | 7.43 → 7.67 | 9.35 → 9.39 |
| Sandbox2 deathmatch | 22.68 → 23.35 | 24.66 → 25.18 |

The later draw-batching suite adds explicit alive/equipped-weapon checks. Its
deathmatch action results supersede these historical deathmatch figures: the
earlier setup could leave players dead after spawn telefrags, then respawn them
with a blaster during the firing phase.

Geometry savings exceed the small FPS gains: Sandstorm's fixed spawn views
submit about 302,000 versus 197,000 model triangles, with 1,053 draw calls in
both cases. All tested action samples still exceed the 30 FPS P95 frame budget.
These are short live scripted samples, one pair per setting; AI and game-clock
progression can vary, and random deathmatch spawn views are descriptive only.
The local `build/pi-pickup-lod-20261112/comparison.html` report retains the full
fourteen scene/detail pairs, raw captures and verification evidence. Existing
saves were preserved and the Game Bird shell was restored after the suite.

## Inline brush batching and focused profiling (2026-11-12)

`r_gl1_batch_inline 1` enables registration-time ordering of compatible opaque
inline brush faces in GL1/GLES1. It groups texture, baked lightmap slot and static
VBO within each entity. The geometry, texture/lightmap data and per-view backface
tests are unchanged. Animated, scrolling, warped, transparent and overlapping
coplanar material surfaces preserve their source-order barriers. Translucent
entities, disabled static buffers and allocation failure use the original path.
The optional ordering arrays are freed before the world model memory.

`r_drawprofile 1` adds per-view submission CPU scopes, actual draw calls, buffer
flush causes and the four costliest inline model IDs to performance captures.
These timings include driver waits and profiling overhead; they are attribution
evidence, not GPU timings or uninstrumented performance estimates. HUD rendering
is outside the profiler. Inline IDs are meaningful only in per-view rows, and
frame rows use -1 for IDs. The pickup class covers the five LOD pickup paths.

Profiling-disabled captures retain the original CSV schema and skip all detailed
profile counter reads/output. A capture fixes its schema at `cl_perf_start`;
start a new capture after changing `r_drawprofile` to change the columns.

The focused Pi bridge profile identified Endline's train (`*11`) as 970 draw
calls across the four views, out of about 1,822 total calls. The native static
fixture verified exact pixel equality and unchanged triangles with batching
off/on, including dynamic lighting enabled/disabled, static-buffer fallback,
video restart and map reload. Fixture calls fell from 226 to 7 (inline 221 to 2).
Production-function and real-buffer regressions are in
`tests/renderers/run_gl1_inline_batch_tests.sh`; the profiling fixture runs through
`tests/run_renderer_tests.py`. ASan/UBSan passed; LeakSanitizer was unavailable
under the host sandbox's ptrace environment.

Native sources, build logs, isolated saves and deployment receipts are in
`/data/build-sources/plastic-platoon-draw-batching-20261112T195708Z/`. Local reports
and test tools are in `build/pi-draw-batching-20261112/`. This deployment changes
only the client, GL1/GLES1 libraries and deployment receipt; all game assets and
the game module retain their previous bytes.

The installed candidate passed all twelve four-player sessions (forty captures),
with fourteen valid scene/detail pairs. Tests used the same 240×240 GL1 setup,
four 120×120 views, audio enabled, VSync off and an uncapped renderer. Pickup LOD
remained enabled. Three virtual SDL controllers plus the handheld's physical
controller exercised the real local clients. Equipped scenes explicitly checked
four living clients and `models/weapons/v_machn/tris.md2` before/after capture.
Deathmatch startup and functional respawns used ordinary attack-based respawn,
parking each revived player at the existing fixed position to prevent telefrags.
The deathmatch `spawn` sample is consequently a prepared fixed-position sample.

Complete-display action averages, batching disabled/enabled in the same build:

| Map | Normal FPS, off → on | Low FPS, off → on |
| --- | ---: | ---: |
| Sandstorm roof | 14.64 → 15.07 | 20.05 → 20.19 |
| Endline bridge | 7.55 → 9.11 | 9.43 → 12.74 |
| Sandbox2 deathmatch, four guns turning | 16.20 → 16.75 | 19.69 → 19.66 |

Endline bridge calls fell from 1,824 to 938 (normal) and 1,822 to 968 (low).
Matched Endline spawn views retained identical geometry/model counts, removed
532 calls (about 36%) and gained about 17% FPS in both qualities. Bridge combat
samples include live-AI variation; in particular, low-detail model triangles
were about 15% lower in the enabled sample. Treat the precise combat FPS change
as an observed pair, rather than an isolated estimate of batching's effect.
Sandstorm's small mixed changes are not a broad performance win. Sandbox2 has
no inline brush models: fixed normal views were effectively unchanged
(10.940 → 10.945 FPS), and its small turning differences are normal variation.

All action P95 frame times still exceed the 33.3 ms budget for 30 FPS. Endline's
enabled low-detail P95 is 85.0 ms. The remaining world/render submission and
static-item costs warrant attention before player-mesh reductions. There were
no measured OOM events or throttling; maximum sampled temperature was 63.4°C.
The fourteen-pair report is `build/pi-draw-batching-20261112/comparison.html`,
with its JSON, raw captures, excluded earlier DM audit evidence, deployment
receipt and native `final-state.json` alongside it. Regenerate it with
`tools/performance/analyze_draw_batching.py`. Native source hashes match the
workspace; installed binaries match the tested runtime. All existing saves and
assets remain unchanged, and `gbshell.service` is active after the suite.
The preceding package is retained as
`.plastic-platoon.backup-draw-batching-20261112T195708Z`.

## Scoped world array state (2026-11-13)

`r_gl1_world_arrays 1` enables scoped vertex-array state reuse in GL1/GLES1;
`r_gl1_world_arrays 0` selects the previous setup path for comparisons. During
opaque world and opaque inline brush passes, consecutive compatible draws reuse
the resident world VBO's vertex and two texture-coordinate array definitions.
Material/lightmap selection, index data, draw order and lighting stay unchanged.

Each pass flushes its final packet and restores the previous array/buffer state
before sky, translucent surfaces, aliases, another entity transform or camera.
Scratch vertices and special packets interrupt reuse and keep their existing
submission path. Buffer reset keeps its original discard behavior. Model free,
renderer shutdown and view boundaries also close reuse before resources change.
The feature adds no GPU buffers or textures and preserves the model, entity and
renderer buffer structure layouts.

## Static pickup color reuse (2026-11-13)

`r_gl1_alias_colors 1` enables a bounded prepared-color cache in GL1/GLES1;
`r_gl1_alias_colors 0` selects the previous path for comparisons. One-frame
models reuse their client-array vertex colors only when the model, normal-light
rotation, final lighting RGB, transparency and minimum-light state match exactly.
World light sampling, animated light styles, dynamic lights, glow and infrared
lighting still run for each view. Models, textures, triangles and draw order stay
the same. Animated or moving poses and shadow rendering use the previous path.

The cache uses a 512 KiB CPU arena and 128 bounded entries, without per-draw heap
allocation or additional GPU buffers. It resets when models are freed, a map is
registered, or the minimum-light table is rebuilt. Cached colors are submitted
directly as the existing client array; every buffer flush/reset clears that
temporary pointer. No model, entity or renderer buffer structure layout changes.

## World and lightmap profiling/batching (2026-11-12)

This update preserves all level sources, installed archives, BSPs and their
visibility/area/portal data. No production level was rebuilt. A separate synthetic
fixture under `build/pi-world-lightmaps-20261112/visual-fixture/` is used only in
disposable QA runtimes. Content audits hash every installed archive and all
nineteen lumps of every packed/loose BSP against the native baseline.

`r_gl1_batch_world 1` groups compatible already-visible world faces by lightmap
and static VBO within their existing color-texture chains. Registration assigns
groups and protects coplanar depth ties. Rendering traverses only current visible
faces and touched groups, without frame-time sorting or allocation. Per-view
visibility, geometry, lightmap generation, alpha/sky order, animated/flowing/warped
surface barriers and legacy fallbacks remain unchanged. The cache is freed before
world memory. Its persistent bookkeeping is bounded at about 251 KiB for the
largest current map on the 32-bit Pi; registration scratch storage is freed.

The extended `r_drawprofile 1` columns separate world marking, brush lighting,
lightmap scans/builds/uploads, texture chains, blending, sky and alpha. Build and
upload times are nested inside regeneration time. All are CPU wall scopes and may
include driver waiting; they are not isolated GPU timings. Physical atlas counts
are per-view identifiers (frame rows contain -1). Main comparison captures keep
profiling disabled and retain the original small CSV schema.

The initial native profiles measured about 25 ms/671 world texture-chain draws
in Sandstorm and Endline spawn views, and 36 ms/977 draws during Endline boarding.
Most flushes switched lightmap textures. Normal combat also spends substantial
time regenerating lightmaps: about 20 ms in Sandstorm and 31 ms at Endline bridge,
including roughly 8/15 ms of builds and 10/12 ms of uploads respectively.

An additional native test enabled the existing three-copy lightmap buffer path.
Its upload-time differences were small while upload bytes increased 15–27%, so
the main comparison explicitly retains `gl1_lightmapcopies 0` at renderer startup.
Pickup LOD and inline brush batching remain enabled in all comparison cases.

Four-camera native visual checks use nine lightmap atlases and distinct persistent
slot-scoped lights. Batching reduced fixture world draws 168 to 72 with all 10,708
triangles unchanged. Off/on pixels match exactly with dynamic lighting on/off,
static-buffer fallback, and within initial/restarted/reloaded contexts. A tiny
cross-context variation also reproduces in the previous renderer: the initial
strict attempt and predecessor control changed 11 pixels/23 channels; the final
candidate control changed 7 pixels/11 channels, all at most 2/255. The controlled
QA records that raw variation and requires
the signed changes to match with batching disabled/enabled; no pixel tolerance
is applied to off/on comparisons. Initial strict QA evidence is retained.

World/copy-history regression coverage is in
`tests/renderers/run_gl1_world_batch_tests.sh`; strict builds and ASan/UBSan passed
(LeakSanitizer remains unavailable under the host ptrace environment). Native
sources and receipts are in
`/data/build-sources/plastic-platoon-world-lightmaps-20261112T205839Z/`.
The reproducible analyzer is `tools/performance/analyze_world_lightmaps.py`;
local evidence is in `build/pi-world-lightmaps-20261112/`.

All twelve native sessions completed (forty captures, fourteen scene/detail
pairs), with the corrected four-player weapon/input, mode, train and respawn
checks passing. Observed full-display action FPS, world batching off/on:

| Map | Normal FPS, off → on | Low FPS, off → on |
| --- | ---: | ---: |
| Sandstorm roof | 14.92 → 15.09 | 20.66 → 21.03 |
| Endline bridge | 9.12 → 9.51 | 12.45 → 12.81 |
| Sandbox2, four guns turning | 16.67 → 16.80 | 19.58 → 19.88 |

These modest 0.8–4.2% action differences are one live pair per setting, with AI
and model-count variation. They are not isolated estimates of the optimization's
effect. Quiet Endline spawn views gain about 4.2% with matched geometry; normal
Sandstorm spawn is effectively flat (10.287 → 10.272 FPS) despite 1,053 → 884
total draws. All action P95 frame times remain over the 33.3 ms target for 30 FPS;
even low Sandstorm's P95 is 53.38 ms. No throttling or OOM events were observed.

A separate same-context diagnostic alternates world batching 0/1/0/1 with fixed
spawn cameras, Blasters, god/notarget, dynamic lightmaps disabled and unchanged
geometry. It then repeats 0/1 with entities hidden. World-chain calls fall
671 → 502, but the chain wall scope only falls about 25.90 → 22.39 ms: roughly
3.5 ms saved, not the whole pass. Full-entity diagnostic display time changes
118.37 → 114.99 ms; world-only saves about 4.08 ms. These profiler-on timings
include substantial measurement overhead and are not gameplay FPS estimates.
The remaining traversal, geometry/model and normal-combat lightmap work explain
why fewer calls do not produce a proportional full-frame gain; GPU time is not
isolated. A read-only exact-overlap audit found insufficient recoverable state
runs in the sampled single-camera host Sandstorm/Endline views to justify a
further SAT change; those counts are not Pi FPS predictions.

`build/pi-world-lightmaps-20261112/comparison.html` and its JSON contain all
fourteen valid pairs, component profiles, copy-buffer diagnostic, separately
audited six-capture toggle probe, context controls and immutable content evidence.
The analyzer's `--toggle-probe` option includes that diagnostic without weakening
the baseline-only profile validation. `results/native/final-state.json` verifies
the installed binaries match the tested runtime and native target source hashes
match the workspace. Assets, maps, visibility data and existing saves are
unchanged; the shell is active and no test engine remains running. The preceding
package is retained on the Pi as
`.plastic-platoon.backup-world-lightmaps-20261112T205839Z`.

## Optional Pi actor model profile

Build the reviewed model-only overlay on the development host:

```sh
.venv/bin/python tools/assets/build_pi_actor_models.py
.venv/bin/python tools/assets/build_pi_actor_models.py --verify
```

Copy `build/assets/pi-actor-models.pkz` explicitly to the Pi package's `baseq2/`.
Canonical high-detail assets and the normal desktop build remain the inputs;
the optional overlay contains only thirty MD2 replacements and its manifest.
PKZ precedence is deliberate: this engine does not sort the PK3 enumeration,
so a filename prefix alone cannot guarantee which duplicate MD2 wins.

| Model | Original triangles | Pi triangles |
| --- | ---: | ---: |
| Player body | 1766 | 1012 |
| Pistol player body | 1768 | 994 |
| Soldier body, normal/taller | 1784 each | 1028 each |
| Player Machinegun | 1398 | 928 |
| Soldier Machinegun, normal/taller | 1444 each | 954 each |

Seventeen carried guns are reduced. Four sources with nonmanifold UV topology
(player Railgun/Shotgun and both enemy Shotguns) retain their exact original
models. Body checks preserve the 117 original UV charts, closed oriented mesh
topology, all frame names/lattices, surviving packed vertex/normal bytes and
protected grip/sole/helmet vertices. Numerical squared-area extrema across
source-valid animation transitions screen for new triangle collapses; this is
not a formal interval or arbitrary self-intersection proof. Carried guns retain
all original poses and pass their sampled source-valid transition checks.

Nine static first-person guns lose 350 certified back-facing triangles in total.
All source vertices, normals, frames, skins and ST bytes remain exact, as does
the order of surviving GL triangles. The 29-unit visibility envelope covers
ordinary default recoil/bob/lowering and handedness/FOV changes with zero
`gun_x/y/z` and `r_cull 1`. Developer offsets or disabled culling are outside this
optional asset profile. The animated Grenade and uncertified Pistol remain
unchanged.

The frozen actor models passed 1,284 host joint body/gun view comparisons and
68 native Pi comparisons, with separate selected visual review. First-person
cleanup passed 612 bit-exact RGBA/depth/coverage comparisons on each of host GL1
and native Pi GL1. Visual fixtures are separate from gameplay timing.

During the late-night tests, physical ALSA PCM output is kept at 0% and muted,
including after the shell is restored. Main performance runs keep SDL sound
mixing enabled. Diagnostic capture fixtures disable engine sound explicitly;
their timings are never used as gameplay FPS.

The original actor comparison completed sixteen sessions and sixty captures,
with source, four-player, camera, weapon and functional checks passing. All
twenty low-detail performance windows were resource-gated with no own-process
major faults. Observed low-detail full-display results are:

| Four-player scene | Original FPS | Pi model FPS | P95 frame time, original → Pi |
| --- | ---: | ---: | ---: |
| Sandstorm roof, four guns | 21.98 | 24.07 | 51.39 → 47.94 ms |
| Endline bridge, four guns | 12.77 | 12.91 | 84.59 → 84.61 ms |
| Sandbox2, turning/firing | 20.03 | 20.19 | 90.54 → 85.18 ms |
| Temple, turning/firing | 35.83 | 35.90 | 29.29 → 29.31 ms |

Sandbox2's fixed view remains about 11 FPS. These are one live pair per scene,
with changing AI/projectile work; they are not isolated causal estimates or
full-mission guarantees. Invulnerability adds a visible player-shell pass.
Temple is the strongest tested four-player arena. Sandstorm improves in the
low-detail combat scene, while Endline and item-heavy Sandbox still have large
remaining costs.

Normal-detail interpretation is limited. Several original optimized runs
paged while the Python harness expanded all replacement MD2s during live
validation. A separate eight-session normal followup moved streaming payload
checks before launch, retained compact live loaded-header/default/path checks,
and measured both parent and game memory. Idle audit peaks became balanced
at about 19 MiB instead of 19/36 MiB. All model CPU/GPU caches independently
shrink or stay equal, but normal Sandstorm baseline paging still occurred;
the audit transient is a plausible contributor, not the sole proven cause.
The Endline followup also fails its absolute camera gate after a roughly
five-unit player offset, with different live NPC counts. Those normal results
are inconclusive, and no limits were relaxed to accept them.

All ninety scored captures plus two interrupted camera-invalid captures are
retained in `build/pi-actor-models-20261113/comparison.html` and its JSON.
The original sixteen-session integrity report remains unchanged as
`comparison-initial.json`; the combined report explicitly flags the auxiliary
normal followup's two underlying validation issues. The camera-invalid first
Sandstorm attempt is visible and unscored. No result is selected by FPS.

The evidence favors keeping this body detail level and profiling repeated
pickup lighting and model submissions next. In the separate model census,
world pickups dominate Sandbox's alias work. Endline also retains substantial
world/dynamic-lighting and visibility costs. Further body or first-person
triangle cuts alone are unlikely to close those gaps.

The reviewed overlay was installed on November 13 as
`baseq2/pi-actor-models.pkz`, SHA256
`90167389d2bb852111f73e99ad54bbcda7d234498bc1d9f5dcbf8e56a3883af9`.
Only that new archive and `deployment-assets.json` change in the installed
package. The preceding complete package is retained beside it as
`.plastic-platoon.backup-actors-20261113T090100Z`. The original sixteen-session
source/control integrity report authorizes the exact payload; the combined
report retains all auxiliary performance qualifications. Existing real save
files remain byte-identical. The shell is restored and PCM remains 0%/off.
Native receipts and independent verification are under
`/data/build-sources/plastic-platoon-actors-20261113T053941Z/`; local receipts
are in `build/pi-actor-models-20261113/native-results/deployment/`.
