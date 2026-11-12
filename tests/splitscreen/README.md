# Split-screen checks

Build the SDL2 client, then run the production-code regression suites:

```sh
make -j4 client
sh tests/input/run_event_tests.sh
sh tests/splitscreen/run_state_tests.sh
sh tests/splitscreen/run_sound_delivery_tests.sh
sh tests/sound/run_tests.sh
python3 tests/input/test_controller_migration.py
```

The real-client smoke test attaches SDL virtual controllers, navigates the
normal menus, checks assignment/readiness/hotplug/launch and independent
gameplay input, and saves screenshots plus a JSON report:

```sh
python3 tests/splitscreen/smoke_lobby.py --size 1280x720 --players 2 --output /tmp/platoon-lobby-check
```

Use `--check-back` to exercise controller-only back/reentry, `--launch f10`
for the keyboard launch shortcut, and `--from-match` to verify switching from
an active solo game (including manual controller swaps). `--players 3` and
`--players 4` cover the larger lobbies; `--menuscale 8` checks scale fitting.

The handheld escape regression loads Game Bird bindings at 240×240 with one
controller, covering ready cancellation, B/Select back, blocked guest Start,
return to the main menu and cancellation from an unassigned controller:

```sh
python3 tests/splitscreen/smoke_single_pad.py --output /tmp/platoon-one-pad-check
```

Use `--client /path/to/quake2` to reproduce the same inputs on an older build.

It needs SDL2 2.24 or newer, an unstripped client, the GL1 renderer and game
module in `release`, and the bundled asset archive. It runs with an isolated
portable configuration and an offscreen software GL driver. The test reads
state using the executable's own symbol table; rebuild after header changes
so the fixture and executable agree. It never changes game state directly.

Virtual controllers validate routing and flow, but cannot verify a specific
physical controller's driver, mapping, wireless connection or rumble. SDL3
uses the matching backend changes and needs its own platform build/test.
