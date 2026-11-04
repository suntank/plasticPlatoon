# Shared effects and split-screen correctness

## Changes

Shared temporary events are routed at `SV_Multicast`, where each game-module
multicast call is an exact occurrence. After the usual PVS/PHS and connected-area
checks, one consuming local connection receives the shared temp commands.
The primary connection is preferred when eligible, including after reconnects
that change server-client array order. Otherwise an eligible secondary receives
them. A full or already-overflowed local message buffer falls back to another
eligible local recipient. Reliable multicast preserves the existing eligibility
of connected clients that are still loading or reconnecting; unreliable
multicast still requires a spawned client.
A dropped secondary is excluded immediately, before its disconnect reaches the
server. A dropped primary continues to consume the host connection and can still
receive a shared effect.

This has no payload-hash cache or display-frame identity. Two identical commands
in one multicast, two identical multicast calls in the same tick, identical calls
in successive ticks, and delayed parsing all remain separate occurrences. No
session-generation cache has to be expired on a map change or reconnect.

The secondary parser now uses the same `CL_ParseTEnt` implementation as the
primary. The old hash cache is removed. Observer-scoped muzzle-flash parsing also
no longer discards identical consecutive shots in one display frame.

There is one explicit preparation phase before drawing the local cameras:

1. Clamp the presentation clock once using the primary snapshot, as before.
2. Visit each local snapshot with that slot's entity history, interpolation,
   visibility-derived entity list, and first-person exclusion.
3. Group only equivalent effect inputs. Equivalence includes current and previous
   entity state, server frame, interpolation, previous trail origin, diminishing
   trail count, and fly-effect state. Prepare each group once.
4. Preserve the union of entities from different views. If an entity has distinct
   representations, give the resulting particles the corresponding view masks.
5. Prepare shared sprites, sustains, and world beam particles once. Prepare
   first-person beam rings with the owner's camera and snapshot history.
6. Evaluate, expire, and compact particles once, producing immutable render
   particles for every eligible view.

Per-camera submission retains entity transforms and interpolation, view weapons,
scoped muzzle flashes and lights, beam alignment, and renderer-facing
billboarding. It no longer emits shared trails, consumes instant particles,
updates shared sprites, advances sustains, or consumes shared random numbers.
Beam roll/color and trap-light variation use stateless presentation noise instead
of advancing the effect PRNG each time another camera draws.

Sprite velocity extrapolation now starts from an immutable spawn position. The
old code reused an already moved `oldorigin`, so repeated views and subsequent
frames could accumulate displacement incorrectly.

Paused scenes retain their prepared output, including instantaneous particles.
Resume and irregular display cadence evaluate the actual presentation time once.
The one server simulation, networking/prediction cadence, and begin/present cycle
are unchanged.

## Protocol and demo behavior

The network protocol and temp-entity wire format are unchanged. Remote clients
receive the same multicast bytes. Dedicated-server builds do not include local
coalescing. Player-specific unicast calls are unchanged and never payload-deduped.
Standard server-demo capture still records the original multicast before local
routing. Ordinary primary-client demos retain primary-visible events because
routing prefers the eligible primary connection. Secondary-only events still
reach the shared live display; ordinary primary demos, as before, are not a
recording of all split-screen viewpoints.

The server checks complete known temp-command lengths before coalescing a buffer.
Mixed multicast buffers containing other service commands, unknown extensions,
or incomplete temp commands retain ordinary delivery. This protects game modules
that bundle player-dependent commands. Plastic Platoon's native effect calls use
separate temp multicasts; custom modules that mix service types should split
shared effects into their own multicast calls to obtain coalescing.

Unreliable events remain unreliable. Coalescing does not add retransmission or
change server packet size limits. The transport's existing behavior still applies
if every eligible local buffer is full or a completed packet is lost. No claim of
reliable delivery is made for an unreliable protocol message.

## Secondary map transitions and snapshot generations

The secondary client now handles the server's `changing` and `reconnect`
stufftext commands. Previously it ignored both and could keep rendering an old
map's entity model indices after the primary had registered a different map.
The local connection stays intact during a level transition and requests fresh
serverdata/configstrings/baselines with the ordinary `new` command.

Changing, reconnecting, and receiving new serverdata clear the secondary frame
ring, parse-entity ring, entity history, old command history, inventory/layout,
and transient weapon presentation. Local profiles, device bindings, and held
controls survive. Clearing the full history prevents a recycled server-frame
number from being accepted as an old map's delta base.

Secondary shared-effect preparation, camera rendering, and HUD presentation
require its own active connection, valid snapshot, and a server generation that
matches the primary's current map registration. A waiting viewport is filled
black until that snapshot arrives. No authoritative server playerstate is mixed
with an old or empty secondary entity stream during loading. Primary connection
behavior is unchanged.

The executable fixture checks the handshake and all three presentation gates.
See `lifecycle-validation.md` for the separate live transition investigation,
including the original baseline failure and any validated fixed-client result.

## Diagnostics

`CL_GetEffectStats()` returns cumulative counters for:

- Created, evaluated, and expired particles.
- Complete shared preparation passes.
- Entity-effect evaluations and equivalent-input reuse.
- Parsed temp-event occurrences.
- Shared sprite updates.

It also reports current allocated particle count and prepared output count.
Allocated count includes consumed instant particles until the following update
returns them to the free list. Counter deltas are sampled by the complete-display
frame profiler, including events parsed before screen rendering begins.

Preparation and each actual `R_RenderFrame` call have profiler hooks in both
single-player and split-screen paths. Legacy `cl_stats` reports each split-screen
view, and `log_stats` receives aggregate submitted entities/lights/particles.

## Executable regression checks

Run from the repository root:

```sh
tests/performance/run_effects_tests.sh
ASAN_OPTIONS=detect_leaks=0 \
  TEST_CFLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  tests/performance/run_effects_tests.sh
```

The harness compiles the production particle, entity, specialized-effect,
lighting, server-multicast, message, and buffer implementations. It includes the
production split-screen and temporary-entity files to access their private
parsers and sprite state. Audio, graphics, and BSP I/O are controlled fixtures;
the particle/trail algorithms, multicast eligibility/routing, message parsing,
sprite updates, and per-view entity/effect submissions are production code.
The test RNG is deterministic so creation counts and random-state consumption can
be compared. This is not a visual or whole-game GPU benchmark.

Observed results with assertions enabled in an optimized x86-64 build:

| Fixture | Observed result |
| --- | --- |
| One rocket explosion eligible for both local clients | One parser invocation, 296 particles, one sound |
| One rocket explosion eligible only for player two | One parser invocation, 296 particles |
| Two identical occurrences in one server tick | Two invocations, 592 particles |
| Another identical occurrence in a successive tick, parsed 37 display frames later | Third invocation retained, 888 cumulative particles |
| Reliable temp event after a session/map-state reset | One occurrence retained |
| Separate visibility area | Ineligible primary skipped; secondary receives the event |
| Full or already-overflowed primary message buffer | Eligible secondary receives the occurrence; reliable and unreliable cases covered |
| Connected clients still loading/reconnecting | One reliable occurrence retained; unreliable delivery waits for spawned state |
| Dropped primary viewport | Host connection still consumes the one shared occurrence |
| Reordered server clients after reconnect | Primary connection still preferred |
| Non-temp multicast and server-demo capture | Original recipients/bytes retained |
| One normal plus one instant particle | Both views submit two, including reversed draw order |
| Additional view submission | No particle updates, creation, PRNG calls, or shared trail mutation |
| Pause/resume and a later two-second time jump | Frozen prepared output, then correct expiry; pool returns to zero active |
| Controlled rocket trail with equivalent one/two-view inputs | 11 created particles in either case; two views use one evaluation and one reuse |
| Differing interpolation inputs for one projectile | Two evaluations, with output restricted to the corresponding views |
| Disjoint snapshot entity sets | Both entities retained in the shared union |
| Scoped muzzle sprite after 100 ms / 200 ms at 20 units/s | Positions 12 / 14 from initial position 10; no extra displacement from another view |
| Secondary heatbeam snapshot history | Owner uses the secondary previous player state |
| First-person heatbeam plus world representation | Owner rings and shared world shell remain separately scoped; drawing consumes no RNG or particles |
| Secondary `changing` / `reconnect` | Old history cleared; exactly one `new` command sent on the secondary connection; held input preserved |
| New serverdata without a preceding `changing` | Full frame/parse/entity history cleared; an old-generation delta tick is invalid |
| Secondary snapshot from a different map, incomplete snapshot, or inactive connection | Presentation rejected until its own active, valid, matching-generation snapshot arrives |

Both the normal optimized run and the AddressSanitizer/UndefinedBehaviorSanitizer
run passed. LeakSanitizer could not inspect `/proc` in the managed test container,
so leak detection was disabled for that sanitizer run. No Pi hardware or complete
sandbox GPU result is established by these fixtures; use the full-game benchmark
procedure for frame times and sustained memory measurements.

The audited old paths created up to 592 particles for one shared rocket because
both local parsers created it, and consumed an instant particle in the first
viewport. Those are source/reproduction baselines supplied with the task. The
new counts in the table are observed executable-fixture results. They are not
presented as an FPS improvement percentage.
