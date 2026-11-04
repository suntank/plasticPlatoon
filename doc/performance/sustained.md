# Sustained effects and sandbox diagnostics

Two sustained captures each retained **18,000 complete display frames after 120 warmup frames**. Both used two local players, a 240×240 total framebuffer, GL1 on the software-rendered development host, and an explicit 30 FPS display cap. Their retained durations are 604.730355 seconds for the effects fixture and 601.934127 seconds for the sandbox diagnostic.

The effects capture records one shared preparation per display frame with two views, and the sandbox capture records a substantial increase in active monster flags through the source map's wave system. These are useful sustained functional and workload observations. **They are not an equivalent-state before/after performance comparison, a final-commit validation, or evidence that a Pi Zero 2 W sustains 30 FPS.**

## Evidence retained and unavailable

The two original aggregate summaries are copied byte-for-byte into the repository:

- [Effects fixture summary](results/sustained/pp-effects-soak-summary.json).
- [Sandbox wave diagnostic summary](results/sustained/sandbox-wave-diagnostic-summary.json).
- [Provenance, summary hashes and exact historical commands](results/sustained/provenance.json).

The original runtime directories were under `/tmp` and became unavailable after the execution environment recycled. Their raw frame/view CSVs, console output, settings files, run metadata, generated command configurations and requested screenshots are no longer available. The `capture` paths in the retained JSON are historical paths, not links to recoverable raw data. Launcher commands below were recovered from the run owner's retained task history, not from surviving `*-run.json` files.

Consequently, the summaries support their recorded distributions, extrema, means and first/last observations. They cannot support a reconstructed time series, a last-minute plateau, a memory-growth slope, a particular player's health/input state, exact times of wave messages, or a claim that no warnings occurred. No missing raw artifact or screenshot has been recreated or represented as the original.

The captures used an intermediate optimized engine containing the geometry, asset and shared-effect changes plus the capture-exclusive guard. They preceded the final secondary-client changing/reconnect snapshot-generation fix and the profiler's renderer-reload serial-identity fix. Those later changes target transitions rather than ordinary steady rendering, but these captures are still not proof about the final commit. See [shared-effect regressions](shared-effects.md) and [lifecycle validation](lifecycle-validation.md) for separate correctness evidence.

## Conditions and scenario differences

The run history records `LP_NUM_THREADS=2`, `LIBGL_ALWAYS_SOFTWARE=1`, Xvfb and the `nobody` account used to retain the engine's root-execution guard. This was the x86-64 Mesa llvmpipe development environment described in [the main report](README.md), not a physical GPU or Pi. Original per-capture startup strings and binary hashes cannot be independently rechecked because the run metadata was lost. The run owner confirms that the sandbox used the same optimized project PK3 as the quiet benchmark.

Both commands disabled asynchronous GPU profiling with `r_perf_gpu 0`. All timing columns below are CPU-side wall-clock intervals, including any rendering-driver waits. The 240×240 width, height and two-view count are confirmed by minimum and maximum values in both retained summaries. Per-view dimensions and camera histories cannot be re-audited without the view CSVs. The Game Bird display-transfer path was not exercised.

Other map compilation, Mesa and renderer-lifecycle functional work ran concurrently. These captures were intended to expose sustained behavior, not establish uncontended frame-time differences. Their timing distributions must remain separate from the serial, equivalent-content quiet-scene measurements in the main report.

### Effects fixture

`pp_perf_effects` is the generated two-room scene with 92 pickup placements, full VIS and baked lighting. Its native `target_blaster` and `target_explosion` entities are driven by normal timers. It exercises projectiles, trails, impacts, explosion particles, smoke, sprites and dynamic lighting through the real server and local-client paths. The fixture has no monster wave system and is not a replacement for the sandbox. Its generator and compilation procedure are documented in [benchmarks.md](benchmarks.md).

### Supplied-source sandbox

The sandbox capture used the exact supplied source, SHA-256 `09dd444a8523b669d31c26940dd630f2ce42e7799ee6745a0622ccf5284bd550`, compiled into the separate diagnostic BSP with SHA-256 `9fab23b549fc863d42c05ca07f106a1f7d524d2c63e7f0f544120472a27457c9`. That BSP used **fast VIS and no baked lighting**. It was not replaced during the capture when full VIS and diagnostic RAD subsequently completed.

All 13 custom texture paths were unavailable: 12 `sandbox/*` textures and `common/caulk`. Three linked soldier weapon models were also missing: `models/monsters/soldier/weapon_blaster.md2`, `weapon_shotgun.md2` and `weapon_machinegun.md2`. The available demo PAK supplied the stock soldier body, skins and sounds. Missing texture metadata, lighting and weapon attachments change appearance and rendering cost. This capture therefore does not represent the intended complete sandbox content.

Neither command supplied a pose override or an input route. The supplied source's primary start overlaps Area 3's trigger, while the first cooperative start is inside Area 1's trigger. Normal player movement processing checks these triggers even without requested movement. This source-derived activation route explains why an ordinary two-player launch can start both Areas 1 and 3 without teleporting players or changing gameplay rules. The lost console prevents an independent replay of the exact activation/message timeline from this run.

**A fresh single-player sandbox launch and a fresh two-player launch do not necessarily have equivalent gameplay state.** The additional cooperative start can activate an additional wave group. A controlled cost-of-second-camera comparison must match activated areas, snapshots or a compatible save state as well as quality settings and camera placement.

The source's timed shutoff chains do not cancel already queued `DelayedUse` deliveries. The Area 3 delivery tail can extend to roughly 475 seconds after initial activation, making a ten-minute capture more useful than stopping at the first 300-second timer interval. This is an inference from the actual map and game code, documented in [the terrain and wave audit](terrain-review.md); the retained summary alone does not prove a complete playthrough, Area 2 activation or successful wave completion.

## Recorded display cadence and CPU work

`elapsed_seconds` is the sum of retained `frame_ms` intervals after warmup. It is not the launcher's process wall time or a direct measure of simulated server time. Each `frame_ms` is completion-to-completion for the complete display frame, including both views, one presentation and frame limiting.

| Capture | Timed frames | Retained interval seconds | Median ms | P95 ms | P99 ms | Maximum ms | Intervals >33.333 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Effects fixture | 18,000 | 604.730355 | 33.363 | 39.614 | 45.509 | 133.652 | 50.550% |
| Sandbox diagnostic | 18,000 | 601.934127 | 33.323 | 37.788 | 42.763 | 374.976 | 49.706% |

The explicit 30 FPS cap makes a median near 33.333 ms expected. Small frame-pacing variation around that threshold can put roughly half the intervals above it; this percentage is not a count of missed hardware VSync deadlines. P95, P99 and maximum intervals also show slow frames. Neither capture establishes stable 30 FPS, and the two rows do not measure an engine or asset speedup.

| Median CPU-side interval, ms | Effects fixture | Sandbox diagnostic |
|---|---:|---:|
| Shared listen-server frame work | 0.033 | 0.053 |
| Client update | 0.056 | 0.137 |
| Client scene preparation | 0.322 | 0.125 |
| Sum of both renderer calls | 18.078 | 11.504 |
| Presentation | 3.162 | 5.110 |
| Screen-render/presentation interval | 22.018 | 18.153 |

These intervals nest and have different boundaries; do not add their medians. Simulation and snapshot-send medians are zero because not every display interval contains a server tick. Their P95 values are, respectively, 0.044/0.020 ms in the effects fixture and 0.278/0.055 ms in the sandbox diagnostic. CPU rendering submission is not a GPU-execution measurement. Concurrency and software-renderer scheduling prevent attribution of individual slow frames without the lost raw rows.

## Entity, particle and resident-memory observations

First/last values refer to the retained post-warmup window. Ranges are the summary's observed minimum and maximum; they do not describe when a value occurred.

| Recorded quantity | Effects: first → last | Effects: range | Sandbox: first → last | Sandbox: range |
|---|---:|---:|---:|---:|
| All in-use server edicts | 133 → 133 | 133–135 | 369 → 509 | 369–516 |
| `monsters` flag count | 0 → 0 | 0–0 | 37 → 179 | 37–179 |
| `dead_monsters` flag count | 10 → 10 | 10–12 | 0 → 3 | 0–7 |
| Active particles | 1,994 → 2,511 | 1,945–2,970 | 0 → 0 | 0–1,752 |
| Process RSS, KiB | 157,312 → 157,784 | 156,652–158,136 | 186,556 → 187,460 | 186,432–187,460 |

The RSS endpoint differences are **+472 KiB** for the effects fixture and **+904 KiB** for the sandbox diagnostic. Expressed in MiB, the effects endpoints are 153.625 and 154.086; the sandbox endpoints are 182.184 and 183.066. The profiler samples process resident memory every 60 display frames and repeats the latest sample between observations. RSS is not decoded texture memory, VRAM, total system usage or available memory on a Pi. These modest endpoint differences and recorded ranges do not prove a flat late-session trend or absence of a leak; the lost raw samples prevent a defensible slope calculation.

The sandbox's net increase of 140 in-use edicts and 142 monster flags is consistent with additional waves being spawned. It is not an exact count of births, deaths or living enemies: entities can be freed or reclassified during the window. The source's default edict storage is a preallocated array, so a larger active count need not increase RSS proportionally. The observation does not establish safe headroom for longer sessions, all three areas, different combat behavior or Pi memory limits.

`monsters` counts `SVF_MONSTER` entities without `SVF_DEADMONSTER`; `dead_monsters` counts all entities bearing the latter flag. Some projectiles and gibs use that flag, and death animations can remain in the former category temporarily. The effects fixture's 10–12 dead-monster flags therefore must not be described as monster corpses. `projectiles_by_effect` ranged from 10–12 in the effects fixture and was zero throughout the sandbox summary. That effect-flag heuristic can include puddles and omit projectile types, so zero is not proof that every possible projectile was absent. This sandbox observation is also not a controlled sustained-combat trial.

## Shared preparation and persistent-resource evidence

Both summaries have a two-view minimum and maximum and a `shared_preparations` minimum and maximum of **one**. That is direct sustained evidence that the shared preparation phase ran once per complete display frame during these two-view captures.

In the effects fixture, shared entity-effect evaluations and reuse counts both ranged from 10–12 with mean 11.0001 per display frame. Their aggregate distributions support that eligible work was reused for the additional view; without raw rows they cannot establish event-by-event correspondence. Mean particle creation was 74.935 and mean particle-update work was 2,695.127 per display frame, with 2,970 maximum active particles observed. The focused regression suite, rather than this aggregate report, establishes occurrence identity, instantaneous-particle correctness, viewport-order behavior and unequal-input handling.

After warmup, both summaries record zero topology builds and zero PVS rebuilds, with two PVS hits per display frame. All recorded static and dynamic vertex/index buffer-upload counters are also zero. That does **not** mean zero geometry submission: GL1 client-array payload counters remain nonzero, with median submitted client vertex bytes of 763,040 in the effects fixture and 784,264 in the sandbox. These are submitted payload estimates, not measured driver DMA or GPU memory traffic.

The effects fixture records 193,528 lightmap-update bytes per display frame throughout the summarized window. This identifies sustained dynamic-lightmap traffic worth profiling on Pi hardware even after static topology and geometry preparation are improved. The sandbox's lightmap-update median is zero and maximum is 299,096 bytes; no timing or trend for those updates can be recovered from extrema alone. Counter scope is documented in [renderer.md](renderer.md).

## Exact historical commands and reproduction

The following commands preserve the original launch arguments and output destinations. The `/tmp` runtimes no longer exist, so these are historical records rather than commands that can be rerun unchanged in the current environment. Rebuild isolated runtimes using [benchmarks.md](benchmarks.md), copy the required game data and intended BSP, and use new capture labels and summary filenames. New captures should retain the raw CSVs, settings, console, run metadata, hashes and screenshots before an environment reset.

```sh
LP_NUM_THREADS=2 LIBGL_ALWAYS_SOFTWARE=1 python3 tools/performance/run_benchmark.py \
  --binary /tmp/plastic-platoon-perf-dk4rz7xp/optimized/quake2 \
  --data /tmp/plastic-platoon-perf-dk4rz7xp/optimized \
  --label pp-effects-soak --renderer gl1 --map pp_perf_effects \
  --players 2 --size 240x240 --frames 18120 --warmup 120 --timeout 720 \
  --xvfb --unprivileged nobody --set vid_maxfps 30 --set r_perf_gpu 0 \
  --screenshot > ../pp-effects-soak-summary.json

LP_NUM_THREADS=2 LIBGL_ALWAYS_SOFTWARE=1 python3 tools/performance/run_benchmark.py \
  --binary /tmp/plastic-platoon-wave-validation/quake2 \
  --data /tmp/plastic-platoon-wave-validation \
  --label sandbox-wave-diagnostic --renderer gl1 --map pp_sandbox_coop1 \
  --players 2 --size 240x240 --frames 18120 --warmup 120 --timeout 900 \
  --xvfb --unprivileged nobody --set vid_maxfps 30 --set r_perf_gpu 0 \
  --set port 27912 --screenshot > ../sandbox-wave-diagnostic-summary.json
```

The 18,120-frame limits include 120 warmup frames, leaving the recorded 18,000-frame windows. Neither command sets a pose or changes map wave rules. Both use the runner's documented quality defaults; the unavailable per-capture settings files prevent an independent audit of every effective runtime setting. The recorded commands also request screenshots, but those screenshots are unavailable and are not used as evidence here.

For the next intended-content sustained check, restore the missing textures and soldier attachments, compile the unchanged sandbox with full VIS and baked lighting, match the activated areas between revisions, and retain the complete output bundle. Run the normal combat and wave route on the actual accelerated Pi backend with the separate device procedure in [pi-zero2.md](pi-zero2.md). The current software-host summaries establish workload and functional observations only; Pi FPS, sustained device memory, thermals and Game Bird display transfer remain unverified.
