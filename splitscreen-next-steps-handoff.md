# Split-Screen Handoff

Purpose: give the next implementing agent enough context to continue the local split-screen feature without re-deriving the current architecture.

## Current status

The split-screen feature is partially implemented and currently works as a hybrid of:

- real local loopback client slots for players 2-4
- a split-screen-specific runtime in `src/client/cl_splitscreen.c`
- a mix of parsed per-slot snapshot state and temporary server-memory bridge reads

Working areas already in place:

- multiplayer menu support for split-screen mode
- split-screen lobby with per-player model/skin/device selection and ready-up
- per-player in-game start menu with drop-out and hold-to-exit behavior
- multi-loopback transport identities for local clients
- extra local slot connect/keepalive/usercmd traffic
- multi-viewport rendering
- per-viewport HUD/crosshair
- per-slot ADS overlays and basic viewmodel recoil polish
- shared fullscreen scoreboard
- split-screen inventory overlay and basic inventory command routing
- secondary slot snapshot parsing for:
  - `svc_serverdata`
  - `svc_frame`
  - `svc_inventory`
  - `svc_layout`
  - `svc_configstring`
  - common `svc_temp_entity` packet consumption

Latest verified build status:

- `make -j4 client` passes

## Primary files

- [src/client/cl_splitscreen.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_splitscreen.c)
- [src/client/cl_splitscreen.h](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_splitscreen.h)
- [src/client/cl_screen.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_screen.c)
- [src/client/cl_keyboard.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_keyboard.c)
- [src/client/cl_network.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_network.c)
- [src/client/input/sdl2.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/input/sdl2.c)
- [src/client/input/sdl3.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/input/sdl3.c)
- [src/client/menu/menu.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/menu/menu.c)
- [src/backends/unix/network.c](/home/austin-morgan/Documents/plasticPlatoon/src/backends/unix/network.c)
- [splitscreen-runtime-progress.md](/home/austin-morgan/Documents/plasticPlatoon/splitscreen-runtime-progress.md)

## Most important architectural fact

This is still not a full "N real client runtimes" implementation.

What exists now:

- secondary local slots have their own loopback identity
- they handshake, send string commands, and send independent `usercmd_t` streams
- they now parse enough server traffic to maintain slot-local `frame`, `inventory`, `layout`, `servercount`, and `playernum`
- rendering/HUD/inventory prefer parsed slot-local state when available

What does not exist yet:

- full secondary client-side prediction
- full secondary snapshot/runtime feature parity with the primary `cl` path
- clean removal of all server-memory bridge reads

## Recently completed runtime refactor

The last slice added and/or stabilized the following:

1. Slot-local parsed snapshot storage in `ss_local_player_t`
   - `frame`
   - `frames`
   - `parse_entities`
   - `parse_entities_num`
   - `inventory`
   - `layout`
   - `servercount`
   - `playernum`
   - `snapshot_valid`

2. Secondary packet parsing in `cl_splitscreen.c`
   - `SS_ParseServerMessage()`
   - `SS_ParseFrame()`
   - `SS_ParsePlayerstate()`
   - `SS_ParsePacketEntities()`
   - configstring/inventory/layout handling

3. Secondary parser survivability
   - common `svc_temp_entity` payloads are consumed so parsing continues during combat
   - frame parser no longer corrupts `valid` while reading the protocol suppress-count byte
   - `precache`/`begin` handling is now ordered correctly

4. Render path movement onto parsed state
   - `SS_GetSlotPlayerState()` prefers `slot->frame.playerstate`
   - `SS_GetSlotAreaBits()` prefers `slot->frame.areabits`
   - `SS_GetSlotRenderPlayernum()` prefers `slot->playernum`
   - `SS_RenderSlotView()` now builds per-slot refdefs from parsed slot state when available

## Highest-value next steps

These are listed in the order I would implement them.

### 1. Remove more server-memory bridge dependencies

Goal: keep secondary slots operating from their own parsed client state as much as possible.

Current bridge-heavy areas:

- shared scoreboard data still comes from server client state
- some player naming/score extraction still assumes server-side client structs
- world/entity presentation is still largely driven through the primary client scene path

Recommended work:

- audit `cl_splitscreen.c` for `sv`, `svs`, `client_t`, and `server_client` reads
- keep only the minimum unavoidable bridge reads
- where possible, source values from:
  - `slot->frame.playerstate`
  - `slot->inventory`
  - `slot->layout`
  - `slot->playernum`
  - `slot->parse_entities`

Success criteria:

- viewport HUD and session overlays no longer need server-client frame access for normal operation
- scoreboard either uses parsed/local data where possible or is clearly isolated as a temporary bridge

### 2. Parse or safely consume more server commands

Goal: make the secondary parser robust enough for long gameplay sessions and more mods/rulesets.

Known limitations:

- `SS_ParseServerMessage()` still does not handle every server opcode
- unsupported commands currently early-return from parsing
- temp entities are only consumed, not replayed

Recommended work:

- compare `SS_ParseServerMessage()` against `CL_ParseServerMessage()` in [src/client/cl_parse.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_parse.c)
- add safe handling for additional opcodes that may appear in normal play
- keep the rule: do not duplicate global one-shot effects that are already being parsed by the primary client unless you intend to make them per-slot

Success criteria:

- secondary snapshot parsing does not silently stop during ordinary DM/coop play
- parser logs are quiet in normal sessions

### 3. Introduce per-slot prediction/runtime fields

Goal: stop relying purely on authoritative camera state for secondaries.

Why this matters:

- the current parsed slot frame is enough for display, but not enough for parity with the primary local client experience
- secondary slots still lack true predicted origin/angles/error smoothing

Recommended work:

- add lightweight per-slot prediction fields modeled after the relevant parts of `client_state_t`
- start with:
  - predicted origin
  - predicted angles
  - prediction error
  - maybe predicted step smoothing if needed
- keep it scoped to what split-screen actually needs first

Success criteria:

- secondary views are less dependent on raw server camera state
- movement/aim feels less delayed relative to player 1

### 4. Decide how to handle temp effects and short-lived view feedback

Goal: close the presentation gap between player 1 and secondary players.

Current state:

- temp entities for secondaries are only skipped/consumed
- secondary players do not get full per-slot playback of local temp effects
- audio is still globally shared and based on player 1

Options:

- minimal path:
  - keep temp entities global and accept that only the primary client drives them
  - add only the most important local viewport feedback manually
- fuller path:
  - build a split-screen temp-effect layer that can render per-slot visual feedback without duplicating every global effect

Recommendation:

- do the minimal path first
- add only obviously missing local feedback that hurts readability or aiming

### 5. Revisit the scoreboard and other global overlays

Goal: clarify what stays global and what should become per-slot.

Current policy is acceptable for v1:

- scoreboard is fullscreen shared
- pause/menu/console are global

What still needs cleanup:

- scoreboard data assembly is bridge-heavy
- inventory/help/layout ownership is still mixed

Recommended work:

- keep scoreboard fullscreen
- isolate its data source behind helper functions so it is easy to swap later
- decide whether `slot->layout` should render per-viewport for secondary clients

### 6. Validate mode coverage

Goal: make sure the system actually works across the intended rulesets.

Run at least:

- 2-player DM
- 2-player coop
- 3-player DM
- 4-player DM
- respawn/intermission/map change
- controller disconnect/reconnect
- player drop-out and return to multiplayer menu

Watch for:

- parser warnings
- desynced secondary cameras
- HUD values not matching actual player state
- server bridge assumptions failing after level transitions

## Recommended immediate task for the next agent

If the next agent is continuing from the current state, the best first target is:

1. Audit and reduce remaining `server_client`/`svs.clients`/`sv` reads in `cl_splitscreen.c`.
2. Expand `SS_ParseServerMessage()` coverage so ordinary gameplay no longer trips unsupported-command exits.
3. Only after that, begin adding per-slot prediction fields.

That sequence has the best payoff because it reduces architectural debt before adding more polish on top of the bridge.

## Practical guidance

- Use `ripgrep` first:
  - `rg -n "server_client|svs\\.clients|sv\\.|snapshot_valid|ParseServerMessage|layout|inventory" src/client/cl_splitscreen.c`
- Compare against:
  - [src/client/cl_parse.c](/home/austin-morgan/Documents/plasticPlatoon/src/client/cl_parse.c)
  - [src/client/header/client.h](/home/austin-morgan/Documents/plasticPlatoon/src/client/header/client.h)
- Keep edits in `cl_splitscreen.c` as centralized as possible.
- Do not remove the current bridge fallback until the parsed-path replacement is confirmed working.
- Rebuild after each parser change:
  - `make -j4 client`

## Known risks

- It is easy to over-copy large parts of the primary client runtime and create a second fragile `cl` clone inside split-screen code.
- Duplicating temp entities or sounds per slot will likely create visual/audio spam if done naively.
- Some mods may send command/layout patterns that the current slot parser still does not understand.

## Minimal definition of done for the next slice

The next slice is successful if:

- a secondary split-screen slot can survive ordinary combat and map progression using its own parsed snapshot path
- the viewport camera/HUD no longer depends on server-client frame data in common cases
- parser warnings do not spam during a normal local DM/coop session
