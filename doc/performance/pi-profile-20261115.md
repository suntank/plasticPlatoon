# Pi four-player CPU profiling and visibility optimization

The slow fixed Sandbox scene is limited primarily by CPU-side rendering.
The largest identified engine hotspot is world BSP traversal and frustum
checks. Hierarchical culling is now installed in the Pi GL1 renderer, reducing
repeated checks while preserving the submitted geometry. Repeated off/on
comparisons improved the dense scene by **about 6%**; heavy scenes still miss
steady 30 FPS.

## Measurements and diagnosis

All native runs use the Game Bird Pi Zero 2 W, the real KMSDRM/VC4 display,
four 120×120 views in a 240×240 framebuffer, normal quality, ordinary geometry
and sound mixing. Physical audio remains muted. Normal FPS claims use detailed
profiling off. No engine, game module or asset changes enter these comparisons.

The initial diagnostic measured profiler-off frames around 79–80 ms and
profiler-on frames around 105 ms. Detailed timers and expanded CSV output are
therefore attribution tools, not performance scores. Its world scope was
about 37 ms (16.4 ms visibility traversal, 15.4 ms texture-chain submission);
model groups together occupied roughly 23 ms. The old `model_ms` counter only
covered about 6 ms of vertex preparation, excluding lighting and most draw
submission. Removing models diagnostically left expensive world work; the
`r_drawworld 0` attempt was forced back to 1 by the multiplayer cheat guard and
is excluded as an ineffective ablation.

A separate bounded SIGPROF sample, with detailed timers off, recorded 1,992
PC samples over 20.05 wall seconds and 20.96 process CPU seconds. This confirms
about one busy CPU core. There were no invalid PCs or bin-storage overflows.
Exact ELF mappings and explicit symbol-size ranges resolve the samples:

| Location | Share of recorded CPU samples |
| --- | ---: |
| GL1 renderer module | 49.4% |
| Mesa driver module | 23.7% |
| World recursive traversal | 11.2% |
| Box/plane classification | 6.3% |
| Box-culling wrapper | 1.6% |
| Alias vertex preparation | 7.5% |
| Static light-point traversal | 2.0% |
| Game module | 0.4% |

Module totals and contained function rows overlap and must not be added.
The three world traversal/culling routines together account for about 19%
of samples. Mesa's private symbols are stripped, so no internal driver
function is guessed. CPU samples do not measure GPU elapsed time or blocked
GPU work; system CPU is represented at userspace return sites, not kernel
stacks. This identifies an actionable engine cost without claiming all
remaining rendering costs are solved.

## Off/on comparison

The same native candidate binary uses `r_gl1_hierarchical_cull 0` for the legacy
algorithm and `1` for the optimization. Each phase records and asserts its
actual switch value. The dense test is ABAB; each performance phase lasts
20 seconds, with the same original resource and input/camera gates.

| Scene | Off FPS | On FPS | Change | Off P95 | On P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sandbox dense 1 | 12.70 | 13.42 | +5.7% | 84.8 ms | 81.4 ms |
| Sandbox dense 2 | 12.67 | 13.46 | +6.2% | 85.7 ms | 80.7 ms |
| Sandbox turning/firing | 18.30 | 18.85 | +3.0% | 96.6 ms | 90.3 ms |
| Endline train (live AI) | 10.92 | 11.14 | +2.0% | 100.1 ms | 96.9 ms |
| Temple fixed | 36.40 | 36.52 | +0.3% | 28.0 ms | 28.0 ms |

Dense Sandbox averages 12.68 → 13.44 FPS (+6.0%). All four dense captures
submit exactly 787 draws, 36,673 world triangles and 57,856 model triangles per
complete display frame. The moving-view pair shows about 3%; its averaged
world/visible-model workload differs slightly with turning phase alignment.
The Endline pair retains normal live AI and protective god-mode shell passes;
its roughly 2% difference is descriptive, not a strong isolated speedup claim.
Temple is essentially unchanged. No scored performance phase had sampled major
faults, swapped game pages or current throttling. The short Temple death and
respawn phases are functional checks, not FPS scores.

## Implementation and correctness

`R_RecursiveWorldNode` now inherits a four-plane mask. Once a parent box lies
fully inside a plane, its contained descendants avoid repeating that test.
Masks start fresh for every camera; PVS, area gates, front/back ordering,
texture animation, sky and alpha chains still run normally.

Compiled BSP child boxes can spill beyond parent bounds. Registration-scoped
metadata records which child edges are contained; unsafe edges restore all
four tests. The four maps have 69, 8, 22 and 2 unsafe edges respectively. The
cache is one byte per BSP node (6,239 bytes for Sandbox), invalidates on world
or registration changes, and frees with world cleanup. Allocation failure
uses the original algorithm; `r_cull 0` remains fully respected. The old
algorithm remains available with `r_gl1_hierarchical_cull 0`.

Host and native ARM regressions compare exact accepted leaf sets and
opaque/alpha/sky chain ordering across 384 frusta on each of four real BSPs,
plus PVS/areas, non-contained and invalid bounds, disabled culling, reload/free
and allocation fallback. Existing inline/world batching tests and GL1/GLES1
compilation passed. Native input, fresh renderer counters, four-view state,
train carry/bridge position and Temple death/respawn checks passed. Sandbox
off/on screenshots were inspected.

The new train test's camera selector initially read the metadata phase instead
of the frozen plan phase. That produced false warnings. The selector was
corrected and the original saved views were re-audited, with unchanged
tolerances, hard-input results and every CSV byte. Original metadata/reports
remain under `ab-endline/original-camera-audit/`; the correction receipt is
retained alongside them. No timing capture was rerun to obtain a better score.

## Installation and limitations

Only `ref_gl1.so` and its deployment inventory changed in the installed game.
Engine, game module, all assets/maps, settings and saves are byte-identical.
The old renderer/inventory are in
`/data/build-sources/plastic-platoon-profile-20261115/installed-backup/`; the
standard `/data/pp-bench` launcher and canonical Pi compatibility pins are
updated. The Game Bird shell is restored, no test game remains running, and
final throttling status is `0x0`.

Native source, patch, build logs and evidence remain under
`/data/build-sources/plastic-platoon-profile-20261115/`. The candidate is built
from the exact previous Pi source plus this renderer-only patch; unrelated
workstation renderer edits were not mixed into the measurement. Installed GL1
SHA-256 is `7527296ddbec121894dc54a7517314e4f5a3ca96e8b0d3eb3066df26d6f76fcb`.

Both old and candidate GLES1 smoke checks failed at `eglCreateContext` with
`EGL_BAD_ALLOC`, before world rendering. This separate alternate-backend issue
is retained in the logs; the installed GLES1 library is unchanged.

[Numeric results](../../build/pi-profile-20261115/results.json),
[CPU attribution](../../build/pi-profile-20261115/device-results/cpu-resolved.json),
[deployment verification](../../build/pi-profile-20261115/device-results/final-device-state.json),
and all raw CSVs, logs, screenshots and original camera-audit history are
retained locally under `build/pi-profile-20261115/device-results/`. Evidence
archive SHA-256: `d5624723df3e536cad90260f72fd706e92f40956a08d469c617813dd662a90d9`.
For CPU re-resolution after deployment, use the backed-up original renderer
(`--binary ref_gl1.so=.../installed-backup/ref_gl1.so`), not the new installed
renderer; the existing resolved report records the original ELF hash.
