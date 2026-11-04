# Release weapon and muzzle-flash tuning

`default.json` is the approved laptop profile, captured unchanged from
`release/baseq2/tuning/default.json` on 2026-11-04. Its SHA-256 is
`219e0f1ec97fa6b944336f263726564a3eb0a176351f5fd19f805913d24a22ea`.

The laptop log confirmed that the game loaded this release file. The old
`plastic_platoon/tuning/default.json` differed only in two M60 fields:

| Field | Approved release | Older source copy |
| --- | ---: | ---: |
| `fire_mode.rate_rps` | 35 | 60 |
| `fire_mode.spread_standing_hip` | 3 | 2 |

The older source copy has been removed. Edit `baseq2/tuning/default.json` for
future intentional changes; the release regression pins the approved bytes.
The desktop's copy has not been inspected.

## How the game loads it

The client reads `tuning/default.json` through the engine filesystem for
first-person, third-person and ADS muzzle flashes. `plastic-platoon.pk3` now
contains that path.

The game module reads profiles with `fopen`, so it also needs a loose
`baseq2/tuning/default.json`. The asset builder stages that file beside the PK3
from the exact same bytes, and verification rejects a missing or different
loose copy. Both Make and CMake use this builder.

Weapons use `sv_weapon_profile` (default `default`) and
`sv_weapon_profile_dir` (default `tuning`). An explicit profile directory still
works. Otherwise the loader checks the selected data directory and executable
directory before its legacy relative-path fallbacks, so launching from another
folder does not silently select compiled defaults. The engine exposes those
installation roots through read-only `fs_datadir` and `fs_binarydir` cvars
without changing the game-module API.

The local `~/.yq2` installation has no tuning JSON or tuning archive entry.
Its muzzle-flash cvars match the compiled defaults; its personal config is not
included in the release. Normal filesystem overrides remain available.

## Build and verify

```sh
make -j4 client game assets
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify
python3 tests/assets/test_overlay.py
python3 tests/tuning/test_runtime.py
```

The runtime tests use the real engine and game module in a temporary portable
installation. They verify the M60 values from the release folder, another
working directory, executable-directory fallback, an explicit custom profile
directory, and a separately selected data directory. Logs go to
`build/tuning-qa/`. The original laptop JSON values are preserved, including
fields whose existing handling is outside this packaging change.
The [validation record](../../tools/assets/review/tuning-validation.json)
includes the profile, package and binary hashes and the GL1/GL3 checks.
