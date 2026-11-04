# Sandkeep visual captures

Run the actual game without changing the installed game configuration or saves:

```sh
python3 tools/maps/capture_sandkeep.py --label review-01
```

The script uses `release/quake2`, a private temporary runtime, Xvfb, Mesa software
OpenGL, and a localhost-only co-op server with one connected player. This keeps
the normal full-screen camera while permitting remote console control. It needs
permission to create local X11 and UDP sockets. It does not use the desktop.

For a newly compiled candidate with materials that have not been installed:

```sh
python3 tools/maps/capture_sandkeep.py --label candidate-review \
  --map build/sandkeep-candidate/maps/pp_sandkeep.bsp --materials baseq2 \
  --assets /home/austin-morgan/.yq2/baseq2
```

The isolated runtime deliberately excludes `operation-sandkeep.pk3`. Named PK3
archives have priority over loose files, so keeping the old package would test
an old map even when a new loose BSP is present. Existing numbered game PAKs and
`plastic-platoon.pk3` are read through symlinks; binaries, map, loose materials,
and configuration are copied into the private runtime.

`--assets` adds only supported game art from `models`, `sound`, `pics`,
`sprites`, and `players` through a private overriding PK3. It excludes maps,
settings, saves and source archives. Use the user's art directory when present
so custom toy soldiers, weapon models and sprites match the installed game.

`--map-name sandbox2 --views path/to/comparison-views.json` can capture another
installed map with its own camera list. Sandkeep's default views and interaction
fixture apply to Sandkeep only.

Each fresh label produces `build/sandkeep-qa/LABEL/` with twenty-one named PNG
views, a contact sheet (when Pillow is installed), console logs, exact settings,
the compiled map hash, material hashes, renderer camera coordinates, and a JSON
manifest. The measured eye position is checked against the compiled BSP's world
and solid brush models, including static `func_wall` terrain; a camera inside
solid geometry fails the run. This uses a zero-size point rather than a player
hull, so an aerial camera need not fit a full player body. Use `--only armory_control
radio_control` for a focused pass. Existing
labels are refused to preserve earlier evidence. Runtime data is deleted after
the capture unless `--keep-runtime` is given.

Walk through the permanent entry crack, exercise both breakable secret walls,
walk into both objective buttons, and inspect the outdoor extraction area:

```sh
python3 tools/maps/capture_sandkeep.py --label interactions-01 \
  --views tools/maps/sandkeep_interactions.json
```

Check the final landing-pad trigger separately:

```sh
python3 tools/maps/capture_sandkeep.py --label completion-01 \
  --views tools/maps/sandkeep_completion.json \
  --assets /home/austin-morgan/.yq2/baseq2
```

This starts the player immediately south of the pad, walks into its trigger
with normal collision, and requires the real intermission camera at
origin `(384, 3408, 256)` facing pitch `20`, yaw `144`. The engine retains its
last player view offset during intermission, so the measured eye is about
22 units higher. It checks mission completion
after reaching extraction; teleporting there bypasses combat and the rear gate,
so this is not a combat playthrough.

Interaction definitions are ordered and share one level state. Each view has a
`name`, a five-number `pose` (`x y z pitch yaw`), optional console `commands`
before teleporting, and optional `after_pose` actions with `command` and `wait`
seconds. Teleport coordinates refer to the player, and the engine adds ten
units before the player's eye offset. The manifest records the measured eye
position rather than assuming these offsets. Console actions are single
commands; semicolon-separated rcon strings are not executed as a sequence.
An optional `expect_log` list requires gameplay messages to appear in the
engine log. The interaction fixture checks both secret discoveries and both
control activations, including the keep-access message. It briefly disables
noclip inside the breached rooms so real trigger touches award the secrets.
An optional `expect_eye_bounds` object maps camera coordinate axes to inclusive
`[minimum, maximum]` intervals. The entry traversal uses this to require that
normal walking actually carries the player through the permanent wall crack.

The outdoor start overview looks north from `(0, -2656, 30)`. A closer crack
view and a reverse view from inside cover its irregular wall edges. Extraction
views cover the retained inner gate, the north outdoor arrival, and the helipad
from above. The aerial camera remains above the exit trigger, and the ground
arrival camera remains south of it, so architecture captures do not end the
mission.

Review these captures for texture seams, coplanar surfaces, fitted sign and
button art, supported castle features, visible button state changes, hidden
supplies before a breach, and a clear keep passage after both buttons. Compare
intact and breached views and the keep before and after the controls. Captures
are visual evidence and use real collision and entity behavior; they are not
an automatic visual oracle, a complete combat playthrough, or GPU benchmarks.

The bare assembled release runtime lacks several custom soldier weapon models
and a grenade-ammo model. `--assets` supplies those from the user's art
directory. Any unresolved files, such as a helicopter propeller model absent
from that directory, remain visible in the console log. GL3 does not implement the
`r_fullbright` cvar, and the client forces several render cheats off in co-op,
so `r_fullbright 1` is not a reliable lighting diagnostic in this harness.
