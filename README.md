# Plastic Platoon

Plastic Platoon is a toy-soldier total conversion built on Yamagi Quake II.
The source includes the client, game module, custom soldiers and weapons,
a tank, attack helicopter, giant ant and spider, sandbox maps and mission/test ranges.

The game uses original Plastic Platoon assets and needs no Quake II PAKs.
The public source includes editable artwork, explicit source archives and build
tools; asset conversion does not require old Git commits or home-directory data.
See [the cleanup and verification record](tools/assets/STANDALONE.md) and
[history and upstream credits](HISTORY.md).

## Build and play

On a Linux development machine with a C compiler, Make, Python 3, SDL2 headers
and the renderer dependencies installed:

```sh
make -j4 all
./release/play-portable.sh
```

The launcher starts `pp_sandbox_coop1`, uses only its own data directory, and
keeps settings and saves in `release/baseq2`. Copy the entire `release` folder
to another compatible machine. No numbered Quake II PAKs are release inputs.
Packaging creates original palette, font, menus, HUD, player icons and support
sounds, and includes all `baseq2/operation-*.pk3` mission packs. The generated
interface and support sounds are provisional artwork.

Use WASD, mouse look, left mouse to fire, right mouse to aim, Space to jump,
and tilde for the console. Test missions are available there:

| Console command | Mission |
| --- | --- |
| `exec bedroom_solo.cfg` | Operation Nightlight / Bedroom |
| `exec sandkeep_solo.cfg` | Sandkeep |
| `exec sandwatch_solo.cfg` | Sandwatch |
| `exec heavy_test.cfg` | Heavy machine gunner range |
| `exec rocket_test.cfg` | Rocket soldier range |
| `exec tank_test.cfg` | Heavy tank range |
| `exec helicopter_test.cfg` | Helicopter range |
| `exec ant_test.cfg` | Giant ant range |
| `exec spider_test.cfg` | Giant spider range |

The Bedroom, Sandkeep and Sandwatch missions also have `_coop.cfg` launch
configs. See each mission's guide under `maps/` for details. Weapons and muzzle
flashes use [the versioned tuning profile](baseq2/tuning/README.md).

## Verify a standalone build

```sh
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify
python3 tests/assets/test_bootstrap.py
python3 tests/assets/test_support_models.py
python3 tests/assets/test_overlay.py
python3 tests/assets/test_portable_assets.py
python3 tests/assets/test_standalone_audit.py
python3 tests/assets/test_public_source_audit.py
python3 tools/assets/audit_public_source.py --history --strict
python3 tools/assets/audit_standalone.py --strict --output /tmp/platoon-audit.json
python3 tools/assets/smoke_standalone.py --help
```

The static auditor reports file dependencies and provenance gaps. Passing it
is not an authorship or licensing certification. The smoke tool runs isolated
map loads and captures actual rendered frames without home-directory assets.

## Source and credits

Engine/game code retains its GPL version 2 or later notices; see [LICENSE](LICENSE)
and individual source headers. Newly generated bootstrap/support assets use
GPL-2.0-or-later. Original project artwork and recordings use the same GPL-2.0-or-later terms;
see [the asset license and owner declaration](ASSET-LICENSE.md). Legacy stock
fallbacks and old history are excluded from the public repository.

Yamagi Quake II builds on Icculus Quake II and id Software's GPL source release.
See [the preserved upstream README](packaging/UPSTREAM-README.md),
[asset rebuilding notes](tools/assets/README.md).
