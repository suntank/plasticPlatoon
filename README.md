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

On a Linux development machine with a C compiler, Make, Python 3 with Pillow, SDL2 headers
and the renderer dependencies installed:

```sh
make -j4 all
./release/play-portable.sh
```

The launcher opens the main menu. New Game starts in the Operation Sandstorm
briefing room. After the General finishes, walk through the Deploy door to
enter Level 1, `pp_garden_infiltration`.
The game uses only its own data
directory and keeps settings and saves in `release/baseq2`. Copy the entire `release` folder
to another compatible machine. No numbered Quake II PAKs are release inputs.
Packaging creates original palette, font, menus, HUD, player icons and support
sounds, and includes all `baseq2/operation-*.pk3` mission packs. The generated
interface and support sounds are provisional artwork.

Use WASD, mouse look, left mouse to fire, right mouse to aim, Space to jump,
and tilde for the console. You start with a knife alongside the pistol. Cycle
weapons or enter `use Knife` in the console to equip it, then use the attack
button to slash. Use the console to launch a test mission.

| Console command | Mission |
| --- | --- |
| `exec bedroom_solo.cfg` | Operation Nightlight / Bedroom |
| `exec endline_solo.cfg` | Operation End of the Line / Toy railway |
| `exec sandstorm_briefing_solo.cfg` | Operation Sandstorm / [Briefing and deployment](maps/README-sandstorm.md) |
| `exec sandkeep_solo.cfg` | Sandkeep |
| `exec sandwatch_solo.cfg` | Sandwatch |
| `map pp_garden` | Garden |
| `exec garden_infiltration_solo.cfg` | Operation Garden Ghost |
| `exec quartermaster_test.cfg` | Quartermaster test range |
| `map pp_loose_thread` | [Operation Loose Thread / Sewing box](maps/README-loose-thread.md) |
| `map pp_attic` | [Attic / The Rooms Remember](maps/attic-level-design.md) |
| `exec smg_test.cfg` | SMG and Thunderhead test range |
| `exec heavy_test.cfg` | Heavy machine gunner range |
| `exec rocket_test.cfg` | Rocket soldier range |
| `exec tank_test.cfg` | Heavy tank range |
| `exec helicopter_test.cfg` | Helicopter range |
| `exec ant_test.cfg` | Giant ant range |
| `exec spider_test.cfg` | Giant spider range |

The Bedroom, Sandstorm briefing, Sandkeep and Sandwatch missions also have `_coop.cfg` launch
configs. See each mission's guide under `maps/` for details. Weapons and muzzle
flashes use [the versioned tuning profile](baseq2/tuning/README.md).

Garden and its mission variant ship as separate operation packs. Garden Ghost
also has `garden_infiltration_coop.cfg`; see [the Garden mission guide](maps/README-garden-infiltration.md)
for editing, rebuilding and verification.

The N64 GoldenEye **Temple** multiplayer recreation is available as `map pp_temple`
or `exec temple_dm.cfg`, and in the split-screen map selector. It follows the
original room coordinates with existing Plastic Platoon materials; see
[the Temple guide](maps/README-temple.md) for scale, reference credits and rebuilds.

**Operation Switchyard** is an original toy-depot deathmatch arena with three
walking elevations and open loading floors for custom blocks and cover.
Use `map pp_switchyard` or `exec switchyard_dm.cfg`; see
[the Switchyard guide](maps/README-switchyard.md) for layout, editing and checks.

**Tile Tide** is an oversized bathroom deathmatch arena with a walk-in tub and
open space below the high fixtures for future toy stairs. Pick `pp_tile_tide`
in the multiplayer map selector or run `exec tile_tide_dm.cfg`.
See [the Tile Tide guide](maps/README-tile-tide.md) for routes and source.

End of the Line also has `endline_easy.cfg`, `endline_hard.cfg`, and
`endline_coop.cfg`. Its shared objectives, double-barrel introduction, alternate
routes and original railway assets are described in [the mission guide](maps/README-endline.md).

## Mission Complete Quartermaster

Campaign kills and secrets award Sprues. In co-op, every connected squad
member earns the full reward and spends from their own wallet. Sprues and
upgrades carry forward with the campaign save. The amber model-kit frame
in the HUD shows your balance and matches the Sprues pickups.

At the Quartermaster, use Up/Down or forward/back to select a row. Use A/D,
Left/Right, or Jump to cycle tabs. Keys 1, 2, and 3 open **Upgrades**,
**Resupply**, and **Weapons** respectively. Press your fire binding to
purchase or confirm **Ready**. In co-op, every player must select **Ready**.

Each upgrade has four tiers. Resupply offers ammo for your current weapons and
hand grenades for quick throws. Prices scale with the amount you can carry.

Weapons lists pickups placed in the completed mission that are missing from your
inventory. Offers cost 175–250 Sprues and include a starter ammo bundle, up to
your ammo cap. Each player shops from their own balance and inventory.

Map authors can place an `item_sprues` pickup with a `count` value to award the
squad that many Sprues. The default is 20.

Run `exec quartermaster_test.cfg` for a fresh solo run or
`exec quartermaster_test_coop.cfg` to host network co-op. For split-screen,
choose cooperative rules and `pp_quartermaster_test`. The staging area has
1,200 Sprues, including three 300-Sprue pickups straight ahead. The blue
opening leads to an optional fight with three soldiers. Walk through the green
**Backyard Exit** on the right whenever you're ready to shop. **Ready** takes
you to Garden Infiltration, where you can check your purchases.

Rebuild the editable test map and its operation pack with
`python3 tools/maps/build_quartermaster_test.py`.

## Local split-screen

Open **Multiplayer**, choose **split-screen** and 2–4 players, then select
**set up split-screen**. Choose the map/rules and **next: controllers**.
With enough connected gamepads, every player gets a gamepad automatically;
otherwise player 1 uses keyboard/mouse and the remaining pads fill later slots.

Each player confirms **Ready** with their own controller (A, or B when using
the reversed confirm setting). Player 1 presses **Start** to launch once
everyone is ready. Cancel clears readiness; player 1 can cancel again to
return to match settings. On keyboard, **Tab** selects a player to edit,
arrows change selections, **F10** starts and **Esc** goes back. An unassigned
pad can press confirm to join. Disconnecting a pad clears its readiness;
reconnect and confirm again before starting.

Standard controller button bindings apply to all local players. Missing
default bindings are installed once when upgrading an older configuration;
existing custom bindings and subsequent unbinds are preserved.
The multiplayer **gamepad settings** entry opens those shared controls.
Secondary players share look speed, inversion and deadzones; advanced stick
curves, flick-stick, gyro and custom command aliases still use the primary
player's input path only.

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
