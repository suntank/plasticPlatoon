# Four-player experiments on PC and the Game Bird Pi

## Run on this PC

From the project directory, close any running game and run:

```sh
./tools/performance/bench-pc
```

Choose a level, or select it directly:

```sh
./tools/performance/bench-pc --map pp_sandbox2 --quality normal
./tools/performance/bench-pc --map pp_sandstorm --quality both

# Test a local compiled BSP without changing release/ or normal saves
./tools/performance/bench-pc --map pp_sandbox2 --map-file baseq2/maps/pp_sandbox2.bsp

# Export safe test positions, then adjust the JSON as the layout changes
./tools/performance/bench-pc --map pp_sandbox2 --quality normal --export-scene /tmp/sandbox-scene.json
./tools/performance/bench-pc --map pp_sandbox2 --scene /tmp/sandbox-scene.json

# Fixed names make revision comparisons easier (each output must be new)
./tools/performance/bench-pc --map pp_sandbox2 --quality normal --output build/pc-bench-results/before
./tools/performance/bench-pc --map pp_sandbox2 --quality normal \
  --map-file /path/to/edited/pp_sandbox2.bsp --output build/pc-bench-results/after \
  --compare build/pc-bench-results/before/report.json
```

PC mode defaults to the existing `release/` runtime, GL1, four local players and
a **960×960 window** (four480×480 views). Use `--size 1280x720` for a different
window or `--size 240x240` for the Pi's viewport dimensions. Dimensions must be
even. Raw results and reports go under `build/pc-bench-results/<UTC timestamp>/`.
The runtime and `~/.yq2` are fingerprinted before/after; test configuration, saves,
logs and screenshots are private to each result directory. `release/` is copied,
never launched in portable/write-in-place mode. No desktop service or system
mixer is changed. Sound mixing stays enabled through SDL's dummy audio output.

PC FPS measures the PC, not the Pi. Reports record target and framebuffer;
`--compare` rejects PC/Pi, different resolution, and headless/native comparisons
before launching. Temperature/throttle readings from Pi-specific sensors are
unavailable on PC and must not be interpreted as zero. Keep the same machine,
resolution, graphics driver and test settings when comparing edits.

`--headless` runs through Xvfb with software rendering for validation without a
desktop window. Its reports explicitly identify software validation; those
timings do not measure the desktop GPU. Normal PC mode uses the current desktop
display. Close the game before launching, and leave controls alone during tests.

The launcher also auto-detects this PC when called directly as
`tools/performance/pi_bench/pp-bench`. This version supports the existing Linux
x86-64 engine/GL1 build. Its separate `input_driver-pc.so` is compiled against the
matching project headers, with explicit engine/renderer/driver compatibility
pins. After rebuilding engine or renderer code, revalidate the helper before
updating those pins. Level/asset edits do not require rebuilding the helper.

## Launch Pi tests from this PC

```sh
./tools/performance/bench-pi
./tools/performance/bench-pi --map pp_sandbox2 --quality normal
```

This is an SSH launcher for the existing tool at `gamebird@192.168.1.185`.
Authentication uses SSH normally; no password is stored. File arguments here
refer to **paths on the Pi**. For local edited BSP files, use PC mode or copy the
file to the Pi first. Pi reports remain on the Pi; this launcher does not replace
the installed tool or alter its mute behavior.

## Run directly on the Pi

Close the game first, then run this **in a terminal on the Pi** (SSH is fine):

```sh
/data/pp-bench/pp-bench
```

Choose a level from the numbered list. The tool starts four real local clients,
runs normal and low quality, prints a table, then restores the shell. Allow a few
minutes, especially for Endline's train sequence. The Pi stays muted; software
sound mixing remains enabled. No physical controllers are required. Leave the
controls alone during a run. Ctrl+C stops the test and restores the shell;
cleanup may take several seconds.

```sh
# Same fixed, firing/turning and DM death/respawn scenes as the earlier tests
/data/pp-bench/pp-bench --map pp_sandbox2 --quality normal
/data/pp-bench/pp-bench --map pp_sandstorm --quality both
/data/pp-bench/pp-bench --map pp_endline --quality low

# Temple is a test-only addon, kept outside the installed game
/data/pp-bench/pp-bench --map pp_temple --addon /data/pp-bench/addons/operation-temple.pk3

# See available compiled maps (include --addon when appropriate)
/data/pp-bench/pp-bench --list

# Test an edited BSP WITHOUT replacing the installed level
/data/pp-bench/pp-bench --map pp_sandbox2 --map-file /path/to/pp_sandbox2.bsp

# Fresh baseline and a subsequent level revision, with explicit output locations
/data/pp-bench/pp-bench --map pp_sandbox2 --quality normal --output /data/pp-bench/results/before
/data/pp-bench/pp-bench --map pp_sandbox2 --quality normal \
  --map-file /path/to/edited/pp_sandbox2.bsp --output /data/pp-bench/results/after \
  --compare /data/pp-bench/results/before/report.json
```

Every output directory is new; existing results are never overwritten. Default
results live under `/data/pp-bench/results/<UTC timestamp>/`. Each contains:

- `report.txt`: the terminal table, saved for later.
- `report.html`: the table and scene screenshots, viewable after copying to a PC.
- `report.json`: numeric metrics, settings and content fingerprints for comparisons.
- `metadata.json`, `plan.json`, logs, raw frame/view CSVs, screenshots and two-second
  resource samples under the quality folders.

The table reports complete-display FPS, P95 frame time, percentage of frames over
33.3 ms, average draw calls and world/model triangles across all four views.
Resource notes include RSS, swapped pages, sampled major faults, temperature,
current throttle/undervoltage and camera drift. P95 below 33.3 ms is a useful
30 FPS target; a high average alone does not mean steady frame delivery. Short
functional death/respawn captures are checks, not gameplay-performance claims.
JSON retains full metric summaries, CPU stage means, sampled CPU clock ranges
and actual effective settings. The engine’s zero-duration opening frame is
retained in raw CSV and excluded from timed FPS, matching the earlier analyzer.

The Pi home/root filesystem is a small RAM-backed overlay. Keep the tool, edited
BSPs and result directories on `/data`, which survives reboot. A free-space check
rejects output locations that cannot fit a private runtime plus a margin.
Output directories must be under `/data`; RAM-backed home/root and `/tmp`
locations are rejected to avoid distorting memory and performance measurements.

The tool copies the current installed runtime into a private directory and uses
private saves/configuration. It fingerprints the actual assets afresh each run,
so edited maps are supported. It checks installed files and real saves again on
exit. A supplied BSP/addon is copied only into the private runtime. Raw results
are always retained; the large runtime copy is removed after success to conserve
space. Use `--keep-runtime` to retain it. Failed runs retain their runtime and logs.

## Protection and comparison with the previous tests

By default, both modes use `dmflags=384`: no friendly fire (256) plus
model teams (128); all four test soldiers share a model. This game’s
`OnSameTeam` check requires the team flag in co-op as well as deathmatch. This keeps teammate bullets from killing the test players **without god
mode's extra shell rendering**. Enemy damage, environmental hazards, self-damage
and teammate knockback still happen. Unexpected player deaths invalidate a
required-alive capture; they are not silently accepted or automatically retried.

Use `--god` explicitly when you need the older invulnerable stress workload.
God mode adds visible shell passes, so results must be labelled and compared with
the same protection setting. The new default should not be treated as a pure
map improvement over older god-mode measurements. Functional death/respawn tests
still deliberately kill players even when protection is enabled.

## Other maps and moved test positions

The four original maps have recorded scene presets. A changed map can make the
old roof/train/camera coordinates invalid. Check the screenshots and camera
warnings. Use `--preset spawn` for a generic spawn-area and rotating firing test:

```sh
/data/pp-bench/pp-bench --map my_level --mode coop --preset spawn
/data/pp-bench/pp-bench --map my_arena --mode dm --preset spawn
```

Generic deathmatch uses the first four DM spawn points; they must be safe and
distinct. Generic tests cover those views, not the whole mission. Co-op enemies
can kill stationary players. Mode `auto` uses the known map mode or infers it
from spawn entities; use `--mode` to override it.

Export a plan to adjust the four positions, yaw angles, phase durations or
commands. `cl_bench_pose SLOT X Y Z PITCH YAW` is the position format. Export
does not launch the game and never overwrites an existing file.

```sh
/data/pp-bench/pp-bench --map pp_sandbox2 --quality normal --export-scene /data/pp-bench/sandbox-scene.json
# Edit the cl_bench_pose commands and prepare_deathmatch.poses in that JSON.
/data/pp-bench/pp-bench --map pp_sandbox2 --scene /data/pp-bench/sandbox-scene.json
```

Keep the same plan, quality, protection and test duration when comparing edits.
Inspect actual draw/triangle counts as well as FPS: live AI and effects vary.
Repeat meaningful comparisons a few times; changes of a percent or two can be
noise. `--compare` prints deltas, not proof of identical workloads. It keeps every
capture and warning. `--seconds 5 --warmup 2` is useful for tool smoke tests only;
use the defaults for real comparisons.

Pi mode targets four players at 240×240 with the current GL1 build. Its
input helper is deliberately checked against the current engine/renderer hashes
because it accesses private structure layouts. Map and asset experiments work;
after rebuilding the engine or renderer, rebuild and validate the input helper
before updating the compatibility pins. Detailed profiling and GPU monitoring
remain off during these FPS tests. No engine, level or renderer source is changed
by this tool.

The helper source is `input_driver.c`, reused from the earlier validated harness.
On the Pi, compile it against the exact native engine source/header tree with SDL2 flags
(PC builds use the same flags with output `input_driver-pc.so` instead):

```sh
cc -std=c11 -D_DEFAULT_SOURCE -DYQ2ARCH='"test"' -DYQ2OSTYPE='"test"' \
  -Wall -Wextra -Werror -O2 -shared -fPIC -I/path/to/matching/source \
  $(sdl2-config --cflags) input_driver.c -ldl $(sdl2-config --libs) -o input_driver.so
```

The driver remains a tool asset outside the installed game; it is preloaded only
into the isolated test session. Vendored `lib/` helpers retain the earlier input,
camera, per-view counter and preservation checks. The worker is adapted to fresh
user experiments rather than immutable historical package snapshots.
