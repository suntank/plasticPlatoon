# Plastic Platoon / Yamagi Split-Screen Design

## Purpose

Add an engine-level local split-screen multiplayer system to the Yamagi-based
engine and Plastic Platoon mod stack. The feature must support 2 to 4 local
players, work with standard Quake II multiplayer semantics, and avoid
mode-specific hacks.

This document also includes the required pre-match local player setup lobby and
the in-game per-player start menu for drop-out and session exit.

## Current Code Reality

The current client is built around a single local player:

- `src/client/header/client.h` exposes one global `client_state_t cl` and one
  global `client_static_t cls`.
- `src/client/cl_input.c` builds one `usercmd_t` path and tracks one set of
  button states.
- `src/client/input/sdl2.c` and `src/client/input/sdl3.c` manage one active
  SDL game controller, not a device pool.
- `src/client/menu/menu.c` owns a single global menu stack and current
  multiplayer/player-setup flows.

That means split-screen is not an incremental viewport feature. It requires
breaking the client assumption that "one process == one local player".

## Core Principle

Each split-screen participant must be a real local client slot connected to one
local listen server in the same process.

Do not implement extra players as:

- fake cameras
- view-only spectators
- HUD-only overlays attached to player 1

The server and game DLL should see normal multiplayer clients. Split-screen is a
client/session transport mode plus a multi-viewport presentation layer.

## Supported Modes

The architecture must work for:

- deathmatch
- coop
- future team modes such as CTF
- future custom multiplayer rules that already work with multiple clients

Version 1 non-goals:

- online + local hybrid sessions in the same match
- save/load support for split-screen campaign sessions
- full front-end ownership by every player in every menu
- per-player arbitrary render scaling/preset tuning

One important adjustment from the original non-goal list: this design does
intentionally add two multi-user menu surfaces:

- a split-screen local player setup lobby before the match
- a per-player in-game start menu

These are narrow, purpose-built session UIs, not a general fully independent
menu stack for every player.

## Session Model

Add a transport/session distinction:

```c
typedef enum {
    MP_TRANSPORT_INTERNET,
    MP_TRANSPORT_LOCAL,
    MP_TRANSPORT_SPLITSCREEN
} mp_transport_t;
```

Split-screen sessions run as:

- one in-process local listen server
- `N` in-process loopback-backed local clients
- one render pass per active local client
- one input stream per local client

Recommended limits:

```c
#define MAX_LOCAL_PLAYERS 4
```

## Split-Screen Runtime State

Create a dedicated subsystem:

- `src/client/cl_splitscreen.c`
- `src/client/cl_splitscreen.h`

Suggested structures:

```c
typedef enum {
    INPUT_DEVICE_NONE,
    INPUT_DEVICE_KEYBOARD_MOUSE,
    INPUT_DEVICE_GAMEPAD0,
    INPUT_DEVICE_GAMEPAD1,
    INPUT_DEVICE_GAMEPAD2,
    INPUT_DEVICE_GAMEPAD3
} input_device_t;

typedef enum {
    SS_SLOT_EMPTY,
    SS_SLOT_SETUP,
    SS_SLOT_READY,
    SS_SLOT_CONNECTING,
    SS_SLOT_ACTIVE,
    SS_SLOT_DROPPED
} ss_slot_state_t;

typedef struct {
    int x, y, w, h;
    qboolean active;
    qboolean black_fill;
} ss_viewport_t;

typedef struct {
    int local_index;
    ss_slot_state_t state;
    qboolean connected;
    qboolean spawned;
    qboolean ready;

    input_device_t device;
    int device_id; /* SDL instance id or internal keyboard/mouse token */

    char name[32];
    char model[MAX_QPATH];
    char skin[MAX_QPATH];

    int server_client_num;

    vec3_t viewangles;
    usercmd_t cmd;

    ss_viewport_t viewport;

    qboolean scoreboard_active;
    qboolean inventory_active;
    qboolean local_menu_open;
    int exit_hold_msec;
} local_player_t;

typedef struct {
    qboolean enabled;
    int requested_players; /* 2..4 */
    mp_transport_t transport;
    qboolean manual_device_assignment;
} splitscreen_config_t;
```

The subsystem owns:

- config chosen from menus
- local slot lifecycle
- device assignment table
- viewport calculations
- helpers for input, rendering, and UI iteration

## Viewport Rules

All layout math must live in one helper:

```c
void SS_CalcViewports(int player_count, int screen_w, int screen_h,
    ss_viewport_t out[4]);
```

Rules:

- 2 players: top/bottom horizontal split
- 3 players: top-left, top-right, bottom-left, bottom-right black
- 4 players: quadrant layout

Every viewport uses its own:

- aspect ratio
- FOV calculation
- crosshair center
- HUD anchor bounds
- weapon model projection inputs

Do not duplicate layout calculations in HUD, renderer, and menus.

## Input Architecture

Refactor input into two layers:

1. Device polling
2. Per-local-player command building

Current input entrypoints such as `IN_Update()` and `IN_Move(usercmd_t *cmd)`
need a split-screen-aware replacement. Recommended direction:

```c
void IN_UpdateAllDevices(void);
void CL_BuildUserCmds(void);
void CL_BuildUserCmdForLocalPlayer(int local_index);
```

### Device model

The SDL backend must enumerate and retain multiple gamepads rather than a
single `controller` pointer. A small device registry is enough for v1:

- keyboard/mouse pseudo-device
- up to 4 gamepads tracked by SDL instance id
- hotplug state
- user-facing label such as `Keyboard+Mouse`, `Gamepad1`, `Gamepad2`

### Default assignment

- player 1 defaults to `Keyboard+Mouse`
- players 2 to 4 default to the first free gamepads

### Manual reassignment

The lobby must allow any player to choose any free peripheral. This includes:

- player 1 moving off keyboard/mouse onto a gamepad
- keyboard/mouse remaining unused if enough gamepads exist
- rejecting duplicate device ownership unless an explicit swap is performed

Recommended rule set:

- each active slot owns exactly one device
- a device can belong to only one slot at a time
- changing to an occupied device swaps with the other unready slot, or is
  blocked if the target slot is ready
- if a device disappears, that slot becomes unready and shows a reconnect
  warning

## Network / Local Client Model

Version 1 should extend loopback transport instead of inventing a new gameplay
path.

Requirements:

- the local server sees `N` distinct connected clients
- each local client has its own netchan/loopback queue
- each local client receives its own snapshots and sends its own `usercmd_t`
- the game DLL remains unaware of split-screen

This will require replacing old code that assumes one loopback client or one
active local connection.

## Rendering Architecture

Refactor the client render frame into:

1. gather active local players
2. compute viewports
3. for each active local player:
   - build refdef
   - set viewport/scissor
   - render world
   - render weapon model
   - render per-player HUD
4. render global overlays once

Global overlays remain full-screen:

- loading plaque
- console
- fatal errors
- main menu
- shared scoreboard if enabled

Per-player overlays remain inside each viewport:

- HUD
- crosshair
- damage flash
- weapon state
- local drop-out menu

For 3-player mode, the unused bottom-right pane is filled black in the same
viewport pass that draws separators.

## HUD and Weapon State

Each local player needs independent:

- predicted view angles
- damage roll/pitch
- screen blends
- weapon animation/frame state
- HUD strings/layout bindings
- inventory/scoreboard flags where applicable

Anything currently read indirectly from global `cl` state must either:

- become indexed by local player, or
- accept an explicit local player/render context

## Audio

Version 1 uses player 1 as the shared listener.

This is acceptable for a first shipping pass and should be documented in the UI
or release notes as a known limitation.

## Save / Load Policy

Disable save/load in split-screen sessions for v1.

Reason:

- the current save path assumes one local client context
- restoring multiple local clients correctly is extra state work

User-facing message:

`Save/load is unavailable in split-screen sessions in this version.`

## Menu and UX Flow

### Multiplayer Entry

Extend the existing multiplayer menu in
`src/client/menu/menu.c` around `Multiplayer_MenuInit()` with:

- `Play Mode`: Internet / Local / Split-screen
- `Split-screen Players`: 2 / 3 / 4, shown only for split-screen
- existing game type and map flow

When `Split-screen` is chosen and the host confirms settings, do not launch the
server immediately. Push a new local player setup lobby first.

## New Pre-Match Local Player Setup Lobby

This is the major addition requested beyond the base split-screen design.

### Purpose

After the multiplayer menu, show a dedicated lobby containing 2 to 4 player
setup panels, one per requested slot. Each player controls their own panel using
their currently assigned peripheral.

### Why this must be a custom screen

The existing menu framework is single-cursor, single-owner. Reusing
`menuframework_s` directly for four simultaneous operators will turn into a
fight against the current stack semantics.

Recommended implementation:

- one custom split-screen lobby screen/state
- custom draw routine
- one lightweight cursor/index per local slot
- menu widgets limited to model, skin, device, ready

Do not try to shoehorn four simultaneous users into the normal global
`M_PushMenu()` stack.

### Panel contents

Each player panel shows:

- `Player N`
- model selector
- skin selector
- device selector
- ready state
- small preview icon or model/skin portrait using existing player setup assets
- footer text with current control type, for example `Keyboard+Mouse` or
  `Gamepad1`

### Data reuse

Reuse the existing player setup scanning logic from `menu.c`:

- model enumeration
- skin enumeration
- icon lookup

That avoids duplicating the player model database logic already used by
`M_Menu_PlayerConfig_f()`.

### Input behavior

Each local player can:

- move their own cursor within their own panel
- change model
- change skin
- cycle available devices
- press start / confirm to toggle ready

Player 1 does not own this screen exclusively. This screen is a controlled
exception to the normal "player 1 owns front-end menus" rule.

### Ready rules

- the match cannot begin until every active slot is ready
- changing model, skin, or device clears ready for that slot
- slots with missing devices cannot ready
- a `Start Match` banner appears automatically when all slots are ready
- once all are ready, either:
  - the host auto-continues after a short countdown, or
  - any ready player pressing start begins immediately

Recommended v1 behavior: begin immediately when all players are ready and one of
them presses start again.

### Device selection rules

Available device choices should list:

- `Keyboard+Mouse` if not claimed
- each connected free gamepad
- optionally an occupied device as `in use by Pn` but not selectable

This directly supports the laptop case where player 1 moves off keyboard/mouse
and onto a gamepad.

### Layout

Recommended lobby layout:

- 2 players: two stacked half-screen panels, matching the eventual gameplay
  split
- 3 or 4 players: quadrant panels matching the gameplay split

That creates spatial continuity between setup and match start.

## In-Game Per-Player Start Menu

This is the second major addition beyond the base split-screen architecture.

### Trigger

During gameplay, if a local player presses that slot's start/menu button, open a
local menu for that player only.

Recommended trigger mapping:

- keyboard player: `ESC`
- gamepad players: controller `Start/Menu`

### Why this should not use the normal pause menu

The existing pause/menu system is global and player-1-owned. The requested
behavior is per-player and needs to work while other players remain active.

Implement this as a split-screen runtime overlay, not as a normal front-end menu
stack.

### Menu options

Each local player's menu contains:

- `Resume`
- `Drop Out`
- `Exit Match`

If `Exit Match` is chosen, replace it with:

- `Hold A for 3 seconds to exit`

or the equivalent confirm button for that device style.

### Drop-out behavior

If a player chooses `Drop Out`:

- their local client disconnects from the server cleanly
- their slot moves to `SS_SLOT_DROPPED`
- their viewport becomes black
- divider lines remain stable
- the match continues for remaining local players

This is preferable to keeping a dead spectator shell because the requirement is
to truly leave the match.

### All players dropped

If every local slot is dropped or inactive:

- end the split-screen session
- shut down the local server
- return to the multiplayer menu

### Exit match behavior

If any local player completes the 3 second hold-to-exit confirmation:

- disconnect all local clients
- stop the local server
- clear split-screen runtime state
- return everyone to the multiplayer menu

This must be a session-wide action.

### Pause semantics

Recommended v1 behavior:

- do not pause deathmatch
- for local coop, either keep simulation running or pause only if all active
  local players are inside their local menus

To minimize gameplay special cases, the cleaner rule is:

- local player menus do not pause the server

That keeps behavior consistent across DM and coop, even if it is less forgiving.

## Scoreboard Policy

Recommended v1:

- if any local player holds scoreboard, show one full-screen shared scoreboard

This is simpler and more readable than trying to compress the scoreboard into
each viewport.

## Implementation Phases

### Phase 1: session config and local slot runtime

- add split-screen transport/config structures
- add `MAX_LOCAL_PLAYERS`
- add viewport calculator
- add local slot array and lifecycle
- extend multiplayer menu with split-screen options
- create split-screen lobby state and per-slot setup data

Success:

- the user can reach the split-screen lobby from multiplayer
- the lobby shows 2 to 4 panels with model/skin/device/ready controls

### Phase 2: device registry and per-slot usercmds

- convert SDL backend from one controller to a controller registry
- build one input state and one `usercmd_t` per local slot
- route commands to distinct local client connections
- support device reassignment and hot-unplug warnings

Success:

- 2 to 4 local players can ready up and move independently

### Phase 3: multi-local loopback clients

- extend loopback/local networking to support multiple in-process clients
- ensure server sees normal connected players
- verify coop and DM spawn flow without split-specific game hacks

Success:

- server reports `N` local players and gameplay logic treats them as ordinary
  clients

### Phase 4: multi-viewport rendering and HUD

- iterate local players in render path
- compute per-player refdefs
- render per-player world, weapon, HUD
- render black unused quadrant for 3-player mode
- add divider lines

Success:

- 2, 3, and 4 player layouts render correctly with independent cameras and HUDs

### Phase 5: in-game local menus and drop-out

- add per-slot start menu overlays
- add drop-out flow
- add hold-to-exit confirmation
- return to multiplayer menu when all drop or one confirms exit

Success:

- players can leave individually without crashing the session

### Phase 6: validation and cleanup

- test coop, DM, map changes, respawns, intermission
- block save/load in split-screen
- validate controller unplug/replug behavior
- remove remaining one-local-client assumptions where found

## Files Most Likely To Change

- `src/client/header/client.h`
- `src/client/cl_main.c`
- `src/client/cl_input.c`
- `src/client/cl_view.c`
- `src/client/cl_screen.c`
- `src/client/menu/menu.c`
- `src/client/input/sdl2.c`
- `src/client/input/sdl3.c`
- `src/common/netchan.c`
- local loopback/client-server transport code around `src/common/clientserver.c`
- server startup/connection flow in `src/server/*`

New files:

- `src/client/cl_splitscreen.c`
- `src/client/cl_splitscreen.h`

Optional but recommended if menu code is split out cleanly:

- `src/client/menu_splitscreen.c`
- `src/client/menu_splitscreen.h`

## Architectural Rules

- do not fake extra players as cameras
- do not special-case coop or deathmatch in the split-screen layer
- keep viewport math centralized
- keep drop-out and ready-up in the split-screen subsystem, not the game DLL
- move old single-client helpers toward explicit local-player context arguments
- use the existing player setup asset/model scan code instead of duplicating it

## Recommended First Milestone

The fastest proof of architecture is still a restricted milestone:

- 2 players only
- top/bottom split
- player 1 keyboard/mouse
- player 2 gamepad
- deathmatch only
- split-screen lobby with model/skin/device/ready
- in-game drop-out/exit menu

That proves the two hardest UX additions as well as the multi-client core.

After that:

- add 3 and 4 players
- add coop
- polish HUD and scoreboards
- expand device reassignment and hotplug handling

## Final Recommendation

The key decision remains unchanged:

Implement split-screen as multiple real local clients connected to one local
server, with one viewport, one input context, and one setup state per local
client.

The extra lobby and per-player in-game menus should be treated as split-screen
session UI overlays on top of that core, not as gameplay exceptions. That keeps
the system compatible with deathmatch, coop, team modes, and future rulesets
without rewriting the game logic per mode.
