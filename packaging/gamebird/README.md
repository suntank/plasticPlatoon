# Game Bird test installation

These files adapt Plastic Platoon to the current Game Bird native-package
format used alongside Drop Grid. `game.json` launches `launch.sh`; copy
`gamebird.cfg` into the package's `baseq2/` directory. The default launch starts
`pp_sandbox_coop1`. No global SDL, input, boot, or root-filesystem changes are
needed.

## Installed Pi

The test installation on 2026-11-01 uses engine commit
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

## Build and deploy

Build natively on the Pi to match its 32-bit userspace and installed SDL/Mesa:

```sh
env -u DEBUG -u ASAN -u UBSAN \
  TMPDIR=/data/build-sources/plastic-platoon-0b95981/tmp \
  make -j2 WITH_SDL3=no WITH_OPENAL=no VERBOSE=1 pi
```

Create the temporary directory first. This builds `quake2`, `baseq2/game.so`,
GL1/GLES1 renderers, and the optimized project asset archive. The Pi already
has the compiler, SDL2, OpenGL/GLES, and cURL development packages. OpenAL is
optional and was disabled because its development headers are absent; audio
uses the engine's SDL backend.

Copy `quake2`, `ref_gl1.so`, and `ref_gles1.so` to the package root. Copy
`game.so`, `plastic-platoon.pk3`, and its manifest to `baseq2/`, together with
the existing game PAKs, custom maps, textures, sounds, skyboxes, pictures, and
tuning data. Do not copy an x86 game module, old `config.cfg`, or another
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
| D-pad up/down | Forward/back |
| D-pad left/right | Turn |
| L/R | Strafe left/right |
| A | Fire |
| B | Jump |
| X | Aim down sights |
| Y | Next weapon |
| Select | Quick grenade |
| Start | Game menu; use Quit to return to Game Bird |

USB/Bluetooth analog-controller input remains available. These bindings apply
to ordinary single-player input; secondary split-screen players retain the
engine's existing controller scheme.

## Device verification

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
