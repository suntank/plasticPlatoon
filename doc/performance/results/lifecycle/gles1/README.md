# GLES1 functional evidence

These captures exercise the actual engine using SDL offscreen and an isolated
Mesa 25.2.8 **softpipe CPU driver** with GLES1 enabled. They establish rendering,
resource-lifetime and diagnostic correctness for the recorded scenarios. Their
timings are not Pi measurements or comparative performance results.

The [validation report and driver recipe](../../../gles1-host-validation.md)
explain the installed driver's missing GLES1 support, the temporary replacement
used only for these processes, and the limits of the results.

## Captures

| Capture | Purpose | Retained evidence |
| --- | --- | --- |
| `gles1-functional-240` | Initial 180-frame two-player smoke, with 30 warm-up frames | [Frames](perf/gles1-functional-240-frames.csv.gz), [views](perf/gles1-functional-240-views.csv.gz), [settings](perf/gles1-functional-240-settings.txt), [console](perf/gles1-functional-240-console.log), [configuration](perf/gles1-functional-240.cfg), [original run metadata](perf/gles1-functional-240-run.json) |
| `gles1-lifecycle-clone-240` | Static-world toggle, renderer restart, differently named byte-identical BSP, return; 348 frames and 696 views | [Frames](perf/gles1-lifecycle-clone-240-frames.csv.gz), [views](perf/gles1-lifecycle-clone-240-views.csv.gz), [settings](perf/gles1-lifecycle-clone-240-settings.txt), [console](perf/gles1-lifecycle-clone-240-console.log), [configuration](perf/gles1-lifecycle-clone-240.cfg), [command events](perf/gles1-lifecycle-clone-240-events.json) |
| `gles1-lifecycle-fixed-240` | Fixed secondary map handshake: fixture → `demo1` → fixture, plus toggle/restart; 346 frames and 692 views | [Frames](perf/gles1-lifecycle-fixed-240-frames.csv.gz), [views](perf/gles1-lifecycle-fixed-240-views.csv.gz), [settings](perf/gles1-lifecycle-fixed-240-settings.txt), [console](perf/gles1-lifecycle-fixed-240-console.log), [configuration](perf/gles1-lifecycle-fixed-240.cfg), [command events](perf/gles1-lifecycle-fixed-240-events.json) |

All three use a 240×240 framebuffer with two 240×120 viewports. The initial
smoke includes connection warm-up; both lifecycle captures recorded two views
in every complete frame. The final capture's renderer serials increase exactly
from 1 through 692 across the renderer restart and both map changes.

The [result manifest](run.json) preserves the tested client, renderer, project
asset-package, fixture BSP and Mesa source hashes. The initial and cloned-map
runs precede the final client handshake fix; its separate client hash is recorded
under `different_map_regression_fixed`.

## Screenshots

- [Initial two-player smoke](screenshots/initial.png).
- [Persistent world buffers](screenshots/persistent.png).
- [Legacy world fallback](screenshots/fallback.png).
- [After renderer restart](screenshots/restarted.png).
- [After cloned-map reload and return](screenshots/reloaded.png).
- [After the fixed different-map transition and return](screenshots/different-map-return.png).

These are lossless PNG conversions of the engine's screenshots, without
cropping or visual changes. Rotation and simulation continued between captures;
they are functional inspections, not pixel-aligned image comparisons.

## Context probes and build configuration

The two small programs isolate context creation from game code:

- [SDL GLES1 context probe](probes/pp-sdl-gles-context.c).
- [Direct EGL context probe](probes/pp-egl-gles-context.c), using Mesa's surfaceless platform.
- [Mesa configure log](mesa-configure.log), with temporary paths redacted.

For example, from the repository root with SDL2/EGL development packages:

```sh
cc -O2 -Wall -Wextra \
  doc/performance/results/lifecycle/gles1/probes/pp-sdl-gles-context.c \
  -lSDL2 -o /tmp/pp-sdl-gles-context
cc -O2 -Wall -Wextra \
  doc/performance/results/lifecycle/gles1/probes/pp-egl-gles-context.c \
  -lEGL -o /tmp/pp-egl-gles-context
```

Use the process-local driver environment in the validation report when
comparing the installed driver with the isolated GLES1-enabled build. The
engine's default context attributes were not changed.

## Replaying the lifecycle commands

The temporary GLES supervisor is not included. The retained configuration and
event records document the commands it sent after observing capture progress.
The versioned GL1/GL3 lifecycle driver is scoped to its separately tested Xvfb
path; it does not claim to run this GLES offscreen setup.

In a fresh isolated runtime, copy the selected capture configuration and the
following transition files to `baseq2/perf/`:

- [Transition to `demo1`](perf/gles1-to-demo.cfg).
- [Return to the pickup fixture](perf/gles1-to-fixture.cfg).
- [Transition to the cloned fixture](perf/gles1-to-clone.cfg), if replaying the cloned-map case.

The three transition files contain only their recorded `gamemap` commands.
They were reconstructed from the validation command sequence because the
temporary originals were not retained. For the cloned-map case, copy the
compiled fixture BSP to `baseq2/maps/pp_gles_reload.bsp` before launching.

Launch with the GLES environment, renderer and 240×240 startup arguments from
the validation report, using the selected lifecycle configuration instead of
the smoke configuration. It starts capture without an automatic frame limit.
After allowing each phase to render, issue the recorded sequence through the
console or a locally configured Rcon connection:

```text
screenshot
set gl1_static_world 0
screenshot
set gl1_static_world 1
vid_restart
screenshot
exec perf/gles1-to-demo.cfg
exec perf/gles1-to-fixture.cfg
screenshot
cl_perf_stop
quit
```

Wait for both players to render in each phase before proceeding. Use
`gles1-to-clone.cfg` in place of `gles1-to-demo.cfg` for the cloned-map case.
The events JSON records the observed frame counts at the original command
requests; those counts are not a promise of identical replay timing. Use fresh
capture labels/output locations so prior evidence is not overwritten.

## Archive integrity

[archive-manifest.json](archive-manifest.json) lists source and packaged SHA256
hashes, sizes and transformations. CSVs are compressed with gzip level 9 and
mtime 0; their decompressed bytes match the retained source CSVs exactly.
Text logs/configuration/JSON redact temporary runtime/build/repository paths
and the local validation password. Historical commands use placeholders such
as `<runtime>` and are provenance records, not directly executable commands.

No executables, driver libraries, dependencies, demo PAKs or BSP binaries are
included. The three reconstructed transition configurations are explicitly
marked in the manifest. This README and the manifest are archive documentation,
not additional recorded engine output.
