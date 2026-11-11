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
