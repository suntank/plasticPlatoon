# Pi Zero 2 W validation procedure

Pi performance is **unverified**. No Pi, VC4 GPU, or Game Bird display transport
was connected during implementation. The 30 FPS target is **33.333 ms for the
complete display frame**, including both players and one presentation.

The official board specification is a 1 GHz quad-core Cortex-A53 with 512 MB RAM.
Mesa's VC4 documentation describes desktop OpenGL 2.1 and GLES 2.0 support and
specifically recommends unsigned-short indices. GL1 and GLES1 are the relevant
engine paths; GL3 requests desktop 3.2 and GLES3 requests 3.0.

References:

- <https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/>
- <https://docs.mesa3d.org/drivers/vc4.html>

## Build an optimized fixed-function client

On Raspberry Pi OS, install the development packages available for the installed
release, then build as the ordinary user:

```sh
sudo apt-get install build-essential python3 pkg-config libsdl2-dev libgl-dev libgles-dev \
  libvulkan-dev libopenal-dev libcurl4-openssl-dev zlib1g-dev
make -j2 VERBOSE=1 pi > build-pi.log 2>&1
```

`pi` builds the client, game, GL1 and GLES1 without spending time on the newer
shader backends. The Makefile release path uses `-O2`, `-fno-strict-aliasing`,
`-fwrapv` and the appropriate target architecture. Do not set `DEBUG`, `ASAN`,
`UBSAN` or inherited debug `CFLAGS` for the measured build. Inspect the log to
verify the actual flags. CMake's existing default is Debug; if using CMake,
explicitly select `-DCMAKE_BUILD_TYPE=Release -DSDL3_SUPPORT=OFF` and the intended
renderer options. Make remains the maintained build route.

Use an isolated runtime directory containing `quake2`, its renderer libraries,
`baseq2/game.so`, the complete existing game data, and the generated
`release/baseq2/plastic-platoon.pk3`. Keep the original installation available
for comparisons. The project archive includes the presets. Its separate name
preserves the stock PAKs and gives the project models priority over them. Loose
project files alone are insufficient when a numbered stock PAK contains the
same model path. `make pi` and `make all` generate this archive and its manifest.

## Confirm the real backend and display

Launch from the actual runtime directory:

```sh
./quake2 -portable +set vid_renderer gl1 +set r_mode -1 \
  +set r_customwidth 240 +set r_customheight 240 +exec performance/pi_zero2.cfg \
  +map pp_sandbox_coop1
```

The startup log must identify hardware VC4 rendering. `llvmpipe`, `softpipe` or
the engine's `soft` renderer indicate a software path. Save `GL_VENDOR`,
`GL_RENDERER`, `GL_VERSION`, SDL video driver, the real drawable dimensions and
the complete launch command. `glxinfo -B` is also useful under X11, but the
engine's startup log is authoritative for its actual context.

For an existing GLES1 display setup, choose it before initialization:

```sh
./quake2 -portable +set vid_renderer gles1 +set r_mode -1 \
  +set r_customwidth 240 +set r_customheight 240 +exec performance/pi_zero2.cfg \
  +map pp_sandbox_coop1
```

The preset is renderer-neutral, so it does not override that startup selection.
Verify the startup log rather than assuming the requested backend succeeded.
The initial profile requests 240×240 and disables projected shadows, MSAA and
anisotropic filtering. It preserves dynamic lights,
particles and populations. The separate `pi_zero2_low.cfg` explicitly trades
texture resolution and dynamic lightmap updates for lower workload. Keep results
from that profile in a separate table.

The 240x240 setting requests the Game Bird framebuffer size. Verify the measured
CSV says 240x240 and two 240x120 views, rather than assuming the window system
honored the request. Record any scaling in the frontend or display driver.

## Repeatable captures

Use the supplied runner with the complete local game data. It selects uncapped,
VSync-off measurement settings, which differ deliberately from the playable
30 FPS preset. Replace the paths below with the Pi's isolated runtime directory:

```sh
python3 tools/performance/run_benchmark.py \
  --binary /path/to/runtime/quake2 --data /path/to/runtime \
  --label pi-gl1-single --renderer gl1 --map pp_sandbox_coop1 \
  --players 1 --size 240x240 --frames 1920 --warmup 120 --timeout 300

python3 tools/performance/run_benchmark.py \
  --binary /path/to/runtime/quake2 --data /path/to/runtime \
  --label pi-gl1-same --renderer gl1 --map pp_sandbox_coop1 \
  --players 2 --size 240x240 --frames 1920 --warmup 120 --timeout 300 \
  --pose 0 -1696 160 -880 0 45 --pose 1 -1760 160 -880 0 45

python3 tools/performance/run_benchmark.py \
  --binary /path/to/runtime/quake2 --data /path/to/runtime \
  --label pi-gl1-different --renderer gl1 --map pp_sandbox_coop1 \
  --players 2 --size 240x240 --frames 1920 --warmup 120 --timeout 300 \
  --pose 0 -1696 160 -880 0 45 --pose 1 -3528 -688 -984 0 45

python3 tools/performance/summarize.py /path/to/runtime/baseq2/perf/*-frames.csv \
  --warmup 120 --json pi-summary.json
```

`--pose` is diagnostic: it enables the existing local teleport cheat and supplies
camera placement once the appropriate connection is ready. It does not freeze
simulation or replace networking. The engine's existing teleport command adds
10 units to the requested feet position. The actual resulting camera coordinates,
angles and viewport dimensions are recorded in `*-views.csv`; compare those,
entity counts and gameplay state before treating two captures as equivalent.

For combat and sustained waves, use the reproducibility rules and scenario table
in [benchmarks.md](benchmarks.md). Capture for at least 10 minutes once the short
tests pass. Track entities, living/dead monster flags, particles and RSS as well
as timing distributions. Do not silently cap enemies or alter timer/spawner rules
to make the result fit.

## Distinguish rendering from display transfer

Run the same binary, map, saved state, cameras, settings and resolution first on
HDMI and then through the handheld's actual 240x240 SPI display path. Capture the
frontend/display-copy process separately with that implementation's profiler or
system tracing. The repository does not include the Game Bird transfer frontend,
so `present_ms` measures SDL presentation and cannot claim to include an external
asynchronous SPI copy. Compare external display transfer time, CPU usage and
frame delivery cadence in addition to the engine CSV.

Mesa recommends starting VC4 diagnosis with:

```sh
VC4_DEBUG=perf ./quake2 -portable +set vid_renderer gl1 +exec performance/pi_zero2.cfg \
  +map pp_sandbox_coop1 > vc4-perf.log 2>&1
```

Also record OS/kernel, CPU clock, temperature and throttling state using the
tools available in the installed OS (`uname -a`, `vcgencmd measure_temp`,
`vcgencmd get_throttled`, and process/system memory). Do not change GPU/CMA memory
allocations blindly on a 512 MB board. Measure available memory and actual stalls
first.

Accept the initial 30 FPS target only when the complete-frame median and slow
frames, sustained memory, gameplay correctness and displayed cadence meet the
chosen criterion on the real device. Host software rendering cannot establish it.
