# Four-player Pi test after the authored model replacements

The current game was built natively, deployed and tested on the Game Bird Pi
Zero 2 W. Model geometry is substantially lower, but measured four-player FPS
is largely unchanged. The busy Sandbox, Sandstorm and Endline scenes still
miss steady 30 FPS. Temple meets that frame-time target in the sampled scenes.

These are complete-display FPS measurements on the native 240×240 panel,
four 120×120 views, hardware GL1 (`Broadcom / VC4 V3D 2.1`, Mesa 25.0.7),
with the existing rifle-based four-player test plans. Sound mixing stays on;
physical PCM output stays muted. GPU profiling is off. The display loop is
uncapped by the benchmark; quality settings are retained per capture.

## Firing and turning

| Map | Quality | Previous FPS | Current FPS | Change | Current P95 frame | Model triangles, previous → current |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Sandbox | normal | 18.23 | 18.49 | +1.4% | 95.3 ms | 51,857 → 20,085 |
| Sandbox | low | 21.16 | 21.30 | +0.7% | 77.9 ms | 54,168 → 20,697 |
| Sandstorm † | normal | 17.36 | 18.37 | +5.8% | 62.3 ms | 76,597 → 47,778 |
| Sandstorm † | low | 24.82 | 23.67 | -4.6% | 48.7 ms | 71,396 → 49,738 |
| Endline † | normal | 10.80 | 10.72 | -0.8% | 100.6 ms | 72,192 → 39,347 |
| Endline † | low | 14.09 | 13.83 | -1.9% | 77.8 ms | 70,248 → 41,542 |
| Temple | normal | 36.82 | 36.82 | +0.0% | 31.1 ms | 10,571 → 5,346 |
| Temple | low | 35.93 | 36.33 | +1.1% | 28.4 ms | 10,585 → 5,341 |

† Protected co-op comparisons use the tool's existing `--god` option on both
versions to keep four stationary players alive. It adds matching shell passes,
so these rows are separate from ordinary gameplay. Default Sandstorm also
passed on the current build: 19.20 FPS normal and 25.72 FPS low in its firing
scene. Three original default runs lost players (baseline Sandstorm, baseline
Endline and current Endline); those captures remain explicitly invalid.

P95 is the time within which 95% of frames complete. Steady 30 FPS needs
33.3 ms; steady 20 FPS needs 50 ms. The short death/respawn phases are functional
checks and are not used as gameplay-performance scores.

## Fixed spawn views

| Map | Quality | Previous FPS | Current FPS | Current P95 frame |
| --- | --- | ---: | ---: | ---: |
| Sandbox | normal | 12.43 | 12.64 | 85.6 ms |
| Sandbox | low | 12.73 | 13.02 | 85.7 ms |
| Sandstorm | normal | 19.29 | 19.83 | 56.0 ms |
| Sandstorm | low | 19.75 | 20.08 | 54.4 ms |
| Endline | normal | 28.24 | 28.67 | 39.3 ms |
| Endline | low | 28.80 | 29.02 | 38.5 ms |
| Temple | normal | 35.67 | 36.05 | 32.8 ms |
| Temple | low | 35.99 | 36.44 | 28.0 ms |

In the dense Sandbox view, model triangles fell from 151,214 to 57,856
(61.7% lower), with world triangles unchanged at 36,673. Draw calls stayed at
787 per complete frame. Mean CPU model work fell from 8.02 to 6.12 ms, while
renderer submission still occupied about 66.9 ms. These counters suggest that
the remaining rendering work deserves profiling; triangle count alone does
not explain the frame time. The timings are nested CPU intervals, not GPU
execution measurements, and must not be added together.

## Comparison limits and checks

The baseline is the complete previously installed game, including its optional
Pi actor overlay. The update contains the new authored models and intervening
client/game changes. All four compiled BSPs are byte-identical across versions.
This measures the installed-version change rather than isolating polygons as
the only changed variable. Live AI and effects vary; differences of a few
percent are not evidence of a consistent speedup.

Normal Sandbox was repeated after its first baseline capture paged. The
baseline repeat had no sampled major faults or swap; the new repeat later
showed 484 sampled major faults during action and up to about 9 MiB of swapped
pages across its phases. Both repeats are retained with that caveat. The first
clean current run returned 18.51 FPS versus 18.49 on the repeat, reinforcing
the overall near-flat result without selecting a best FPS result. The paired
protected co-op runs completed without sampled action-phase major faults or
swap. No current throttling was observed; final `get_throttled` is `0x0`.

All selected pairs passed the original input, four-view, viewport, weapon,
living-player, renderer-counter and camera qualifications. Both deathmatch
maps passed four-player death and respawn checks. Both protected Endline
versions passed the actual train-carry and bridge-position assertions in both
qualities. Current sessions identify native KMSDRM/VC4 rendering. Sampled
Sandbox and Endline screenshots were visually inspected.

## Deployment and evidence

The native optimized build uses SDL2, `-O2`, GL1/GLES1 and SDL sound, with
OpenAL disabled. The source and full native build log are retained under
`/data/build-sources/plastic-platoon-lowpoly-20261114/`. The installed package
is `/home/gamebird/gamebird-shell/data/nest/games/plastic-platoon`; its complete
prior version remains alongside it as `.plastic-platoon.backup-lowpoly-20261114`.
The obsolete `pi-actor-models.pkz` is kept in that backup and removed from the
new package so it cannot restore superseded models. The core archive is
`3985852fe1beb22fd922f588d834a9b0278363fb8fbe31a0df92538527c9036a`.

The final verification confirms unchanged real saves/settings, unchanged game
files during the tests, an exact unchanged backup, no game left running and
the Game Bird shell restored. `/data/pp-bench` and the canonical Pi helper
compatibility pins now match the validated engine/renderer/controller.

| Native component | SHA-256 |
| --- | --- |
| engine | `4ce95bf6c626878ca85c6cd87505e8fb3ec58ddcd237eca45b1d9564326a5e15` |
| renderer | `29a59891ef22c559de72eb7191498379d7fc018f4ad0ab2f0eb472d2f51b892f` |
| driver | `10a723267cc505d885584fe4343446f4ed003eb20681249463135cd6157a5e76` |

[Full combined results and capture ledger](../../build/pi-lowpoly-20261114/results.md),
[numeric results](../../build/pi-lowpoly-20261114/results.json), and
[final device verification](../../build/pi-lowpoly-20261114/device-results/final-device-state.json)
are retained locally. Every run keeps its raw frame/view CSVs, effective
settings, telemetry, logs and screenshots, including invalid attempts. The
compressed evidence bundle has SHA-256
`202453bb7f0398f4096703665bafa64c74bf9f9afc931786747a3ab99789f895`.
