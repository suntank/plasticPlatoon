# Renderer lifecycle validation

## Established results

The updated GL1 and GL3 clients completed a live split-screen lifecycle smoke on
2026-10-31, repeated after fixing the secondary map-transition handshake described
below. Each renderer completed five captures of 120 complete display frames,
with two camera submissions per frame. Across the two processes this is **1,200
complete display frames and 2,400 camera views**, with ten actual screenshots.

Every captured display was **240×240**, and every individual viewport was
**240×120**. The startup logs independently report a 240×240 drawable. Both
processes exited normally after the scripted checks.
The server status printed at every phase independently confirms that both local
clients are spawned after map replacement and renderer restarts.

| Stage | Action | GL1 | GL3 |
| --- | --- | --- | --- |
| Initial | Start the real two-player local-client session | 120 frames, 240 views | 120 frames, 240 views |
| Map reload | `gamemap pp_lifecycle_reload` | 120 frames, 240 views | 120 frames, 240 views |
| Renderer restart | `vid_restart` | 120 frames, 240 views | 120 frames, 240 views |
| World fallback | Disable the renderer's static-world toggle | 120 frames, 240 views | 120 frames, 240 views |
| Restored | Re-enable static world resources, then `vid_restart` | 120 frames, 240 views | 120 frames, 240 views |

`pp_lifecycle_reload.bsp` is a byte-identical copy of the compiled diagnostic
fixture under a different filename. The different world name forces the old
world's resources to be freed and the new registration path to run. This checks
resource replacement without changing world geometry, materials, or pickup
placements. It is not a test of the supplied sandbox.

The exact renderer was loaded three times per process: initial startup and two
renderer restarts. No fallback to a different renderer, reported invalid GL
operation, or process crash occurred in these checks. All captured views had
working renderer counters after the transitions.

## Host and settings

These are functional software-rendering checks on Linux x86-64 under Xvfb:

- `GL_VENDOR`: Mesa.
- `GL_RENDERER`: llvmpipe, LLVM 20.1.2, 256 bits.
- GL1 context: OpenGL 4.5 Compatibility Profile, Mesa 25.2.8.
- GL3 context: OpenGL 4.5 Core Profile, Mesa 25.2.8.
- `LIBGL_ALWAYS_SOFTWARE=1`, `LP_NUM_THREADS=2`.
- VSync disabled, `vid_maxfps=60`, `cl_maxfps=60`, `cl_async=1`.
- `r_shadows=1`, `r_viscache=1`, dynamic lights and particles enabled.
- Fullbright disabled, ordinary world/entity rendering and culling enabled.
- `gl_finish=0`; no synchronous GPU wait was added for these checks.

Other validation/build work was running on the host. These captures must **not**
be used as before/after timing results or as evidence of Pi performance. The
240×240 drawable is a window in Xvfb, not a Game Bird SPI display measurement.

The runtime uses the actual project `plastic-platoon.pk3` above the stock PAK.
It does not rely on loose model files winning filesystem lookup. The game,
renderer, executable, map, and project archive hashes are recorded in each
`run.json`.

The executed client SHA256 was:

```text
09c43d7c21bcca8fe6242aefdef55342b06e3bd02969f73021ff6d93213a932b
```

The project archive SHA256 was:

```text
0a6b8f8133497ce1e5bfccbc1d2804c18adf47d3b0b03b3be99636a507ed4313
```

## Evidence that the selected paths ran

The visible geometry counts remained the same in every phase: 650 world
triangles and 258,200 model triangles per complete display frame. The model
count includes projected shadows in this deliberately dense pickup fixture.

Switching to the legacy world path increased the instrumented vertex payload,
and restoring persistent geometry restored the earlier payload:

| Complete-display median payload | Persistent | Legacy world fallback | Persistent after restart |
| --- | ---: | ---: | ---: |
| GL1 client-array vertex payload | 2,666,464 bytes | 2,699,560 bytes | 2,666,464 bytes |
| GL3 dynamic vertex-buffer uploads | 8,657,656 bytes | 8,709,664 bytes | 8,657,656 bytes |

The many projected pickup shadows remain dynamic and account for much of this
workload. The GL1 figures describe submitted client arrays, not measured driver
DMA traffic. These payload counts establish that the intended fallback and
restored paths were exercised; they are not frame-rate gains.

The registration counters also demonstrate world rebuilds and renderer reloads:

| Cumulative static vertex upload counter | Initial | Different-name map reload | After `vid_restart` |
| --- | ---: | ---: | ---: |
| GL1 | 368,216 bytes | 386,920 bytes | 368,216 bytes |
| GL3 | 378,904 bytes | 408,296 bytes | 378,904 bytes |

The map transition adds the new world's immutable vertex data while retaining
reusable model resources. Reloading the renderer rebuilds its resources and
starts a new renderer-local registration counter. The static index total was
101,436 bytes after each renderer initialization.

The separate renderer view serial remains strictly increasing across both
restarts, allowing delayed GPU samples to retain unambiguous origins. Both
renderers' captured serial ranges progress from 245–484 initially to 1,101–1,340
after the first restart and 1,821–2,060 after the second. Every reported GPU origin
was no later than its reporting view; the checks do not reinterpret a delayed
sample as the current view's GPU time.

The initial capture deliberately calls `cl_perf_start` a second time with the
already active label halfway through. Both logs report refusal, and the original
capture retains all 120 frames and 240 views. This validates the direct console
command's new exclusive-creation behavior with a running game, beyond the Python
runner's separate collision checks.

## Visual inspection and artifacts

All ten original PNGs were inspected. Both views retain the room walls/floor,
recognizable project pickups, per-instance shadows, first-person weapons, HUD,
and split divider through map replacement, renderer restart, and fallback
changes. Pickup rotation and weapon animation naturally differ between
screenshots taken at different times. GL1 screenshots also contain normal
temporary console notifications; they have not been retouched.

The retained validation evidence is versioned under:

```text
doc/performance/results/lifecycle/gl1-mapfix/
doc/performance/results/lifecycle/gl3-mapfix/
```

Each directory contains startup and sequence configs, console logs, an
authoritative local-server status response showing both spawned local players,
per-phase CSV/settings files, provenance/validation JSON, and these screenshots.
CSV files are gzip-compressed with a fixed timestamp and decompress to the exact
original bytes. Text files replace the temporary runtime roots and the local
test-only rcon token with explicit placeholders. `archive-manifest.json` records
original, decoded, and packaged hashes, sizes, and those redactions. Original PNG
bytes are preserved, including any temporary capture paths visible in console
notifications; all 15 selected lifecycle/transition PNGs decoded successfully.

| PNG filename | Stage |
| --- | --- |
| `screenshots/q2_0000.png` | Initial persistent resources |
| `screenshots/q2_0001.png` | Different-name map reload |
| `screenshots/q2_0002.png` | Renderer restart |
| `screenshots/q2_0003.png` | Legacy world fallback |
| `screenshots/q2_0004.png` | Persistent resources restored and renderer restarted |

The bounded versioned driver is `tools/performance/run_lifecycle.py`. It stages
an isolated temporary runtime and copies binaries/game/map/archive inputs.
Configuration, savegames, captures, screenshots, and caches belong
to that temporary runtime. It does not write to the benchmark runtime being
compared. A localhost-only control command queues the sequence after both
players have reached the spawned state.

Re-run from the repository root on a Linux validation host with Xvfb and Mesa
software rendering. `--source` defaults to the assembled `release` runtime;
`--output-root` defaults to `build/lifecycle`. A source runtime must contain
`quake2`, the selected `ref_gl1.so` or `ref_gl3.so`, `baseq2/game.so`, the user's
`baseq2/pak0.pak`, the generated project `baseq2/plastic-platoon.pk3`, and the
compiled `baseq2/maps/pp_perf_fixture.bsp`. Use the build, asset-packaging, and
fixture-compilation procedure in [benchmarks.md](benchmarks.md). Use a fresh
artifact label for every attempt:

```sh
python3 tools/performance/run_lifecycle.py --source release --renderer gl1 --label gl1-new-check
python3 tools/performance/run_lifecycle.py --source release --renderer gl3 --label gl3-new-check
```

The driver runs as the current ordinary user. In a root-owned automated
validation environment, add `--unprivileged nobody` (or another existing test
account); the client itself refuses root execution. Each new run creates a fresh
local control token, binds only to `127.0.0.1`, and refuses to replace an existing
artifact directory. The copied retained configs contain a redacted token and are
evidence of the tested settings; new runnable configs are generated by the tool.

Revalidate the published compressed evidence without a game, compiler, GPU, or
Xvfb process:

```sh
python3 tools/performance/run_lifecycle.py --renderer gl1 \
  --analyze-only doc/performance/results/lifecycle/gl1-mapfix
python3 tools/performance/run_lifecycle.py --renderer gl3 \
  --analyze-only doc/performance/results/lifecycle/gl3-mapfix
```

Both offline analyses reproduce the original recorded validation JSON exactly.
The versioned drivers retain the tested scene and lifecycle sequence; their
portable account/output/input handling was checked without repeating the live
engine runs after packaging.

## Limits and observations

This validates usable resource cleanup/rebuild paths, not absence of every CPU or
driver allocation leak. GL1 process RSS rose from approximately 180.4 MiB to
192.4 MiB, and GL3 from approximately 163.2 MiB to 177.8 MiB across startup,
map replacement, shader/driver warmup, and two restarts. These short samples do
not distinguish retained driver/allocator caches from leaks. Sustained restart
and wave-session memory checks remain separate device validation work.

The minimal data runtime reports missing optional custom sounds, one unavailable
grenade-ammo model/icon, the existing `Com_sprintf: overflow` message during map
startup, fallback from unavailable `libcurl.so.3` to `libcurl.so.4`, and IPv6
socket setup warnings when explicitly bound to the IPv4 localhost address.
These diagnostics are retained in the logs. They did not prevent the tested
rendering and lifecycle operations; they are not represented as clean full-game
asset coverage.

## Different-content map regression discovered and fixed

The initial resource-replacement check used identical geometry under a different
name. A separate `demo1` investigation reproduced loss of subsequent render/capture
progress and rcon replies with both direct `map demo1` and a queued
`gamemap demo1`. The queued case also reproduces with **the baseline GL1 engine
and the original, pre-optimization project asset archive**. It therefore
predates both the persistent-buffer changes and optimized assets.

The decisive baseline run used a fresh UDP source port for each localhost rcon
request, preventing delayed replies from an earlier screenshot or command from
being mistaken for a status response. The frame CSV stayed at 8,192 bytes across
two post-transition observation windows, and the status request timed out. The
game had logged `Player entered the game` in `demo1`. The exact baseline engine
SHA256 was `008416d4a7d894079f13c59177f0b6a79528a10f572013c563c8b7668d2b7ef9`,
and the original project archive SHA256 was
`f78b6b48cc1306e97d128808fca84e336310b4de38182dd4a55a938c2bfacc00`.

Launching the game as a child of GDB allowed a main-thread stack sample without
changing the host's debugger-attachment restrictions. The sample was inside
Mesa's `libgallium`, called by the baseline path
`R_ApplyGLBuffer -> R_SetBufferIndices -> R_DrawGLPoly -> R_DrawAlphaSurfaces ->
RI_RenderFrame -> SS_RenderViews`. One stack sample does not distinguish an
endlessly repeated alpha draw from an unusually expensive driver operation.

Source inspection then identified a pre-existing split-screen correctness bug:
the secondary client's stufftext handler ignored the server's `changing` and
`reconnect` commands. It retained a valid old-map snapshot and never requested
the new map's serverdata. Meanwhile, the rendering helper accepted that snapshot
without checking its server generation. Old entity model indices could therefore
be interpreted against the primary's newly registered model table. An identical
map under a new name hid this invalid mixing of generations.

The implemented fix handles the secondary transition handshake on its existing
connection, clears its complete snapshot/delta/entity/presentation history, and
waits for an active, valid snapshot matching the primary's server generation.
A waiting viewport is filled black. Physical held inputs and local profile
choices are preserved. Production-function tests check this handshake, history
reset, rejection of a recycled old delta tick, and all presentation gates in
normal and ASan/UBSan builds.

The live regression now passes:

| Renderer and content | Transition | Fixed-client result |
| --- | --- | --- |
| GL1, original pre-optimization assets | Queued `gamemap demo1` | Both clients spawned on `demo1`; responsive status; continuous rendering; 593 captured displays / 1,186 views across the run |
| GL3, optimized project assets | Direct rcon `map demo1` | Both clients spawned on `demo1`; responsive status; continuous rendering; 673 captured displays / 1,280 views across the run |

The GL3 capture includes loading displays where the secondary correctly waits
instead of drawing old-generation entities. After the transition, both recorded
240×120 views contain the new map with 13 submitted entities each. Both post-map
screenshots were inspected and show correct separate camera positions in the
new room. Capture files continued growing across two separated post-transition
checks. These are functional success results, not comparative timing results.

The updated five-phase lifecycle runs reported above were then repeated with
explicit spawned-client checks at **every** phase. This verifies that secondary
reconnection succeeds in addition to rebuilding renderer resources.

The isolated probe, exact configs, logs, CSV, provenance, and full debugger
backtrace are retained in
`doc/performance/results/lifecycle/queued-map-gl1-baseline-original-confirm/`;
its bounded versioned driver is `tools/performance/rcon_transition_probe.py`.
Only the final confirmed baseline probe is included in the published evidence;
earlier inconclusive attempts are not used for the conclusion above.

The fixed different-content checks are retained under
`doc/performance/results/lifecycle/queued-map-gl1-fixed-original/` and
`doc/performance/results/lifecycle/direct-map-gl3-fixed/`. Reproduce the original-assets queued
case with a fresh output label:

```sh
python3 tools/performance/rcon_transition_probe.py \
  --engine release --data-source /path/to/original-assets/runtime \
  --renderer gl1 --queued --label queued-gl1-new-check
```

The probe defaults both runtime paths to `release`, writes new evidence beneath
`build/lifecycle`, and requires the target `demo1` map in the installed data.
Use `--target-map` for a different installed map, or omit `--queued` for a direct
map command. `--debug` launches the test game as GDB's own child and captures a
stack when a stall is detected; it does not attach to another user's process.
Root validation hosts require the same `--unprivileged` option as above. The
recorded baseline stall can end with a partially buffered final CSV row; that
evidence is retained exactly and is not used for a timing distribution.

A separate check completed a real GLES1
fixture→`demo1`→fixture round trip with a renderer restart under Mesa softpipe;
see [gles1-host-validation.md](gles1-host-validation.md) and
`doc/performance/results/lifecycle/gles1/run.json`. The GL1/GL3 Xvfb drivers above
do not replace that separate GLES/offscreen environment procedure. This remains a
host GLES capability/lifecycle check, not Pi acceleration or display-transfer
validation.
