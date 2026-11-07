# Mission 01: Operation Sandstorm

Infiltrate Sandcastle One, destroy the radio, fight through the rooftop defenses,
and assemble the living squad at the extraction helicopter. This version includes
four giant ants. Start it with `exec sandstorm_solo.cfg` or
`exec sandstorm_coop.cfg`; for local split-screen, start co-op first and then
enter `map pp_sandstorm`.

The editable map is `maps/source/pp_sandstorm.map`. Its current source came from
the user's moved `baseq2/maps/pp_sandstorm.map` and differs from the older
Documents copy. The Sandstorm signs and mission entity implementations were
restored from that copy. The sandbox WALs are built from the existing sandbox
artwork using `python3 tools/maps/build_sandstorm_wals.py`; Pillow is required.

The game module must include the Sandstorm helicopter, extraction and cinematic
entities and the giant ant. `sh tests/sandstorm/run_tests.sh` checks the mission
entities and save/load. Map source, BSP and route verification must pass before
`tools/maps/package_sandstorm.py` installs the mission.

The preview package is `release/baseq2/operation-sandstorm-preview.pk3`. The
moved map had lost the helicopter's departure path; two original path corners
were restored. The untouched moved file is backed up locally under
`build/maps/pp_sandstorm/backups/user-moved/pp_sandstorm.map` (build files are
not tracked). The adrenaline
pickup temporarily uses the existing large-health model, and the explosion
sound uses the existing grenade explosion. These are fallback assets.

The old route verifier was written for the earlier geometry and reports blocked
routes in the edited map; these require investigation before treating the level
as fully verified. A successful initial render is not a playthrough.
