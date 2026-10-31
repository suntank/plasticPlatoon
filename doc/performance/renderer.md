# Renderer preparation and upload changes

These changes preserve the existing world visibility traversal, per-view area
tests and frustum culling, material/lightmap selection, transparent ordering,
entity transforms, and instance lighting. They operate in GL1/GLES1 as well as
GL3/GLES3. They do not change the simulation or collision models.

## Persistent world resources

GL1/GLES1 uploads non-sky, non-warping, non-scrolling brush vertices and both UV
sets once when the world is registered. Geometry is partitioned into buffers of
at most 65,535 vertices so every index remains an unsigned short. Each surface
has immutable, precomputed triangle indices. Existing visible surface/material
chains select which indices enter a draw packet. Consequently, invisible faces
do not become visible merely because they share a buffer. Draw packets retain
the existing texture, lightmap, blending, alpha and transform boundaries.

Visible index lists are copied into the existing batch buffer. Their contents
depend on visibility and are still submitted per view; vertex positions and UVs
are neither rebuilt nor uploaded per view. This is intentionally not one
always-visible world draw. Scrolling and warped GL1 surfaces retain their
existing dynamic path, and the old client-array path remains available when
buffer objects are unsupported or allocation fails.

GL3/GLES3 uses a separate immutable world VBO/VAO. Light flags are a constant
integer attribute for each drawn surface, rather than modifications to every
vertex. Existing lightstyle uniforms, dynamic light sets and scrolling uniforms
remain per-view/per-material. GL3 still submits individual visible surfaces.
Reducing those draw calls is a separate opportunity; this change removes their
repeated vertex uploads without trading away culling granularity.

Inline brush models share the world resources and retain their instance
transforms. Resources are freed before the map hunk or GL context is destroyed.
Registration clears cached visibility references even when a map is reloaded
at an identical memory address.

Runtime comparisons:

```text
set gl1_static_world 0   // legacy world submission, GL1/GLES1
set gl1_static_world 1   // default persistent world submission
set gl3_static_world 0   // legacy world streaming, GL3/GLES3
set gl3_static_world 1   // default persistent world submission
```

The buffers are prepared at registration even when the submission toggle is
off. This permits a same-session comparison without map reload or gameplay
changes. It does not make that comparison an estimate of the old engine's
registration memory.

## MD2 topology, static pickups and pose reuse

The existing disk format and loader remain unchanged. Registration builds a
validated command cache. It converts triangle fans/strips to triangle indices
once, preserving winding, and merges only exact `(source position index, s, t)`
tuples. UV seams remain distinct. The cache uses the command stream's actual
triangle count, which also preserves original assets containing duplicate
command triangles that differ from the header count.

Both renderer families upload immutable model indices and UVs once. Models with
one frame also receive decoded static positions and a static position VBO.
Their instances still calculate their own lighting, rotation, alpha and shell
effects. Static positions are used only when there is no shell extrusion and
the entity's old/new origins match. A moving instance takes the interpolation
path even if its model contains one frame.

GL1/GLES1 static instances submit per-instance byte colors while reusing
position, UV and index buffers. GL3/GLES3 static instances upload four color
floats per unique render vertex. Previously they uploaded nine floats per
command vertex, plus indices, and regenerated topology each draw. Shadows also
reuse the immutable model indices; their projected positions remain dynamic.

Interpolated poses have a bounded two-entry cache per model, allocated on
demand. A key contains both frame numbers, shell extrusion state, the complete
local movement vector, and the front/back interpolation vectors. Sharing a
model name or server time is not enough to share a pose. Matching poses copy
the prepared source positions; differing interpolation inputs recompute them.
Lighting remains instance-specific and is not included in the pose cache.

Missing GPU capabilities or an allocation failure preserve a client-array
fallback in GL1/GLES1. A failed GL3 model allocation falls back to its previous
streaming path. Cache and GPU buffers are released with their owning model.
The topology cache validates primitive lengths, termination, finite UVs,
position indices, and its unsigned-short vertex domain before use.

### Equivalent-content workload example

This table is an exact count of requested array/buffer payloads from the code
and the original armor shard at `f2d9366`. It is not an FPS measurement. The
same original 2,000-triangle asset has 3,982 command vertices and 2,107 unique
position/UV vertices. Shadows and shell effects are excluded in this example.

| Per static instance, after registration | Original engine | Updated engine |
| --- | ---: | ---: |
| GL1 position/UV/color/index client payload | 107,568 bytes | 8,428 bytes of colors |
| GL3 dynamic vertex/index `glBufferData` payload | 155,352 bytes | 33,712 bytes of colors |
| Topology conversions | 1 | 0 |
| Compressed position decoding/interpolation | Every draw | 0 for eligible static poses |
| Model draws | 1 | 1 |

GL1 client payload counts are not a claim about exact driver DMA traffic. GL3
figures count vertex and index API upload sizes; uniform uploads and textures
are separate. Registration uploads and resident memory are additional costs.
Asset simplification is independent of these equivalent-content reductions.

## Visibility cache correctness

A four-entry cache retains the actual marked BSP node/leaf pointer sets for
cluster pairs. Switching to a cached pair applies a new shared visibility
stamp to every member of that set. Remembering cluster IDs alone would leave
the other camera's stamps active and is not sufficient.

The existing same-cluster fast path remains. Area portals and frustum rejection
are still evaluated during each view's traversal, so changing area bits does
not reuse an area-filtered surface list. Registration/free clears the pointer
cache. `r_novis` changes cannot accidentally retain an all-visible stamp set
when normal visibility resumes. `r_lockpvs` keeps its existing diagnostic
behavior.

```text
set r_viscache 0   // disable cross-cluster stamp-set reuse
set r_viscache 1   // default
```

Dynamic light marking and GL1 lightmap regeneration still run per view. This
preserves distinct per-view light sets and identities. Sharing that work needs
evidence that the full light and style inputs match; it is not assumed here.

## Texture-size policy

`gl1_picmip` now also applies to native NPOT uploads. For example, picmip 1
reduces a 300×300 skin to 150×150 and a 256×256 skin to 128×128. Non-mipmapped UI
textures are not reduced by picmip. Dimensions also respect the implementation's
maximum texture size. Extreme/negative/non-finite picmip values cannot create
undefined shifts or zero-size textures. The legacy POT path retains its
existing 256-pixel cap. This change is separate from the asset pipeline's
default skin resizing.

## Diagnostics

Enable `r_perf 1`. Each completed `RenderFrame` publishes a new
`r_perf_serial`, including each split-screen view. CPU times use SDL's
high-resolution clock. The values below are per-view, reset before rendering:

| Cvar suffix after `r_perf_` | Meaning |
| --- | --- |
| `cpu_ms` | CPU time inside the renderer's view entry/exit |
| `visibility_ms` | CPU time in visibility marking/cache restoration |
| `model_ms` | Measured pose/topology/color preparation time in cache paths |
| `draws` | Actual renderer draw calls during that view, including effects/postprocessing |
| `world_triangles`, `model_triangles` | Counted brush/model triangle submissions; model shadows are included |
| `static_vertex_bytes`, `static_index_bytes` | Static geometry uploads in the measured view; normally zero |
| `dynamic_vertex_bytes`, `dynamic_index_bytes` | Explicit per-view vertex/index buffer upload bytes |
| `client_vertex_bytes`, `client_index_bytes` | Instrumented client-array payloads, not measured GPU DMA |
| `pose_vertices`, `pose_cache_hits` | Actually decoded/interpolated source positions and equivalent-input pose hits |
| `topology_builds` | Legacy command conversion path invocations |
| `pvs_builds`, `pvs_hits` | Visibility rebuilds and cache/same-cluster hits |
| `lightmap_bytes` | GL1 dynamic lightmap texture upload bytes |
| `static_vertex_total`, `static_index_total` | Cumulative registration upload bytes, including warm-up |

Sky/effect triangles are not counted as world/model triangles. Client-array
byte coverage includes buffered world/models, shadows and particles; auxiliary
debug/sky/sprite client-array draws are counted as draw calls but their byte
payloads are not exhaustive. Uniform uploads are not vertex/index uploads.
`model_ms` is preparation instrumentation, not the complete cost of every
lighting trace or model draw. The outer client profiler supplies shared update,
scene preparation, complete display-frame and presentation timing.

Optional asynchronous desktop GPU timer queries:

```text
set r_perf 1
set r_perf_gpu 1
```

`r_perf_gpu_supported` is 1 only after supported desktop timer-query entry
points are found. `r_perf_gpu_ms` is the most recently completed GPU query;
`r_perf_gpu_serial` identifies its originating render view, which may be
several views behind the current CPU sample. Join by serial before comparing
CPU and GPU measurements. A 16-slot ring checks availability without blocking
and skips sampling if every slot is pending. No `glFinish` is added. GLES
reports unsupported until disjoint-timer handling is implemented. Driver timer
results on llvmpipe measure the software implementation, not a physical Pi GPU.

View serials use 64-bit integers and resume from the engine cvar's exact string
when a renderer DSO reloads. GPU result, capability and query-origin state is
cleared at initialization and shutdown, including when diagnostics are disabled
in the next context. A renderer restart therefore cannot reuse earlier CPU/GPU
sample identities or expose a previous renderer's GPU result as current.

## Executable validation

```sh
python3 tests/run_renderer_tests.py
python3 tests/run_renderer_tests.py --sanitize
python3 tests/run_renderer_tests.py --sanitize --models /path/to/other/models
make -j4 ref_gl1 ref_gles1 ref_gl3 ref_gles3
```

The C fixture links the actual `Mod_LoadMD2`, `Mod_BuildAliasCache`, pose cache,
topology parser, visibility stamp cache and texture-size policy. Focused cases
cover strip/fan winding, exact tuple sharing versus UV seams, truncated and
malformed command lists, non-finite UVs, position bounds, the 65,535-vertex
limit, alternating visibility areas, second-cluster differences, map/reset
invalidation, repeated cleanup, and every pose-key input.

A second fixture directly includes the production profiler and asynchronous
query implementation with engine-cvar/GL-call stubs. It verifies preserved
serials above 2^32, simulated DSO reload, delayed query origins, query cleanup,
disabled-diagnostic context resets, and malformed serial input. It uses SDL's
clock and requires the SDL2 or SDL3 development package, but no display.

Validated in this environment with AddressSanitizer, UndefinedBehaviorSanitizer
and LeakSanitizer:

- All 16 rebuilt repo MD2 assets.
- All 16 unchanged original repo MD2 assets, including padded frame strides
  and the original duplicated command triangles.
- 104 MD2 compatibility models from the locally available Quake II demo,
  including animated players, monsters and first-person weapons.

The fixture also verifies decoded static coordinates exactly against source
frame scale/translation and source vertex mapping, and verifies that animated
models never get the static frame-zero shortcut. LeakSanitizer needs normal
process inspection; the restricted sandbox's `/proc` isolation prevented it
from running, so sanitizer validation used the permitted normal executor.

All four optimized renderer variants were compiled on the host. Full in-game
comparisons, resource lifecycle smoke tests, performance distributions and Pi
validation status belong in the main performance report. These standalone
fixtures do not establish GPU rendering correctness or Raspberry Pi FPS.

## GLES1 context validation on the software host

The host's Ubuntu Mesa package `25.2.8-0ubuntu0.24.04.2` was built with
`-Dgles1=disabled -Dgles2=enabled`. This was verified in `debian/rules` from
the exact version's [official source package](https://snapshot.ubuntu.com/ubuntu/20260828T000000Z/pool/main/m/mesa/mesa_25.2.8-0ubuntu0.24.04.2.debian.tar.xz).
An installed `libGLESv1_CM` dispatch library and an advertised ES1.1 maximum
therefore did not establish working ES1 contexts on this host.

A standalone SDL 2.30.0 context probe reproduced `EGL_BAD_ALLOC` with both
Xvfb and SDL's offscreen driver. Requested accelerated-visual values of 1, 0,
and -1, ES versions 1.0 and 1.1, and reduced depth/stencil requirements did
not repair it. A separate direct-EGL program reproduced the ES1 failure while
successfully creating ES2/ES3 contexts. No engine acceleration default was
changed in response to this packaging limitation.

An isolated upstream Mesa 25.2.8 build with GLES1 enabled subsequently ran the
actual engine at 240×240 with two 240×120 views. It passed the static-world
fallback/restoration, renderer restart and map lifecycle checks. After fixing
the secondary client's map-change handshake/generation handling, the previously
failing fixture → `demo1` → fixture sequence completed 346 display frames and
692 views with strictly increasing renderer serials. See
[the GLES1 host validation record](gles1-host-validation.md) for the driver
recipe, screenshot, exact scope and measured client-array payload reduction.
This software-host test does not establish Pi hardware performance.
