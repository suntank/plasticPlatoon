# Split-Screen Runtime Refactor Progress

Purpose: track the transition from the current server-memory bridge to real per-slot parsed client state for split-screen local players.

## Current stage

- Secondary local clients can connect, send movement and gameplay commands, and keep a netchan alive.
- Split-screen rendering/HUD now prefers parsed per-slot snapshot state for view/HUD/inventory when available.
- Some systems still use the server-memory bridge, especially shared scoreboard data and broader world-state assumptions.
- The next target is to parse real secondary client snapshots into slot-local runtime state.

## Active implementation slice

1. Add per-slot parsed snapshot storage:
   - current `frame`
   - backup `frames`
   - parse entity ring
   - slot-local `layout`
   - slot-local `inventory`
   - slot-local `servercount` / `playernum`
2. Parse secondary slot messages for:
   - `svc_serverdata`
   - `svc_frame`
   - `svc_inventory`
   - `svc_layout`
   - `svc_configstring` where needed
   - common `svc_temp_entity` payloads are now consumed so secondary snapshot parsing can continue during combat
3. Move split-screen camera/HUD consumers onto parsed slot state when available.
   - camera/refdef now prefers slot-local `playerstate` and `areabits`
   - HUD/inventory consumers now prefer slot-local parsed stats and inventory

## Follow-up after this slice

1. Replace remaining server-memory bridge reads used by:
   - view state
   - inventory
   - scoreboard labels/data where practical
2. Add per-slot prediction/runtime fields.
3. Move toward full per-slot client message handling instead of bridge helpers.
