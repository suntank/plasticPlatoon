# Operation Sandwatch

A new single-player / co-op defense mission inspired by Operation Sandkeep's
toy-scale sandbox fortifications. Hold a sandcastle outpost against six waves
over **eight minutes**, then eliminate surviving attackers and enter the southern
extraction bunker. The clock starts after a **20-second preparation period** when
a player touches the command bunker's radio control. Total minimum time from
activation to extraction is 8:20; a final sweep can take longer.

Start with `map pp_sandwatch` in an existing session, or use
`exec sandwatch_solo.cfg` for a medium single-player game. Network hosts can use
`exec sandwatch_coop.cfg`. For local split-screen, start the normal co-op session
first and then load the map, preserving the controller/player configuration.
Restart the game after installing or rebuilding its PK3.

## Encounter

Times below are measured from wave one's arrival, after preparation.
Reinforcements arrive on schedule even if earlier enemies remain alive.

| Wave | Arrival | Assault | Easy / Medium / Hard |
| --- | --- | --- | --- |
| 1 | 0:00 | Northwest scouts | 4 / 6 / 8 |
| 2 | 1:15 | Eastern raiders | 6 / 8 / 10 |
| 3 | 2:30 | Western breach | 8 / 10 / 12 |
| 4 | 3:45 | Northeast grenadiers | 8 / 10 / 12 |
| 5 | 5:00 | Eastern shock troops | 10 / 12 / 14 |
| 6 | 6:15 | Western armored column, including one tank | 12 / 14 / 16 |

Six waves give the squad time to learn the approaches and change weapons between
escalations. Seventy-five-second spacing leaves recovery time early on; heavier
enemies and overlapping survivors increase the pressure later. The last wave has
1:45 to contest the base before the survival objective completes. Enemy totals
are 48 / 60 / 72; difficulty and normal Q2 damage rules apply. This is an initial
balance pass, not a claim of a full human combat playtest.

## Progressive armory

Players begin with shotguns, shared shells, health and light armor. Five labeled
armory shutters sink into the sand **15 seconds before the next wave**. Each
contains the new weapon and a finite stock of its matching ammunition.

| Time | Locker | Unlock |
| --- | --- | --- |
| 1:00 | AUTO | Rifle and 400 bullets |
| 2:15 | CLOSE | Double barrel shotgun and 80 shells |
| 3:30 | BOOM | Grenade launcher and 30 GL rounds |
| 4:45 | HEAVY | Heavy machinegun and 500 bullets |
| 6:00 | ROCKET | Rocket launcher and 40 rockets |

At 0:30, 1:45, 3:00, 4:15, 5:30 and 6:45, the rear supply strip receives
20 shells, 150 bullets, two large health packs and combat armor. Uncollected
reserves remain available. Co-op weapons stay for teammates; ammunition, armor
and health are shared. Leave supplies for players who need them.

## Layout and completion

The outpost has three broad approaches, broken sand breastworks, two miniature
towers, a covered command bunker with side entrances, and stairs to its firing
roof. The armory lies immediately south of the base; walk around its sides to
reach the rear resupply strip and extraction. Alphabet blocks, a tipped bucket,
an oversized spade and wooden spools retain Sandkeep's toy scale.

Each wave has its own sealed deployment room. Triggered enemies materialize
before its shutter opens, and one-use combat points move them toward the
outpost. Future rooms remain closed, preventing spawn telefrags. Once open,
bays stay accessible so the squad can find stragglers. Global alarms announce
waves; the radio operator receives timing messages and the shared F1 objective
updates for the squad. There is no destructible-base health objective: players
must survive, defeat every attacker, and extract. In co-op, standard respawn
rules apply; a player death does not reset the shared mission clock.

Both the 8:00 survival event and all enemy deaths are required before extraction
opens. Touching the extraction volume ends the mission at intermission. Continuing
starts a fresh Sandwatch run. The map uses existing game entities, so normal
saving and loading preserve timers, open shutters, enemies and objective counts.

## Editable source, build and verification

`maps/source/pp_sandwatch.map` is directly editable. Regenerating with
`tools/maps/generate_sandwatch.py` overwrites it, the original `sw_*` signage,
and `build/maps/pp_sandwatch/schedule.json`; preserve manual edits first.
The generator imports Sandkeep's geometry/material helpers and needs Pillow and
NumPy. It reuses the existing Sandkeep textures and sky without replacing its map.

```sh
python3 tools/maps/generate_sandwatch.py
./compile_map.sh --source maps/source/pp_sandwatch.map \
  --basedir build/sandkeep-assets \
  --tool /home/austin-morgan/Documents/q2tools/Linux64/q2tool \
  --profile release --threads 4 --output-dir build/sandwatch-candidate/maps
python3 tools/maps/verify_sandwatch.py
python3 tools/maps/package_sandwatch.py
```

The compile asset directory must contain the Sandkeep WALs, new `sw_*` WALs and
an authentic loose `pics/colormap.pcx` from installed game data. Do not distribute
that support palette with the level. The package installs loose files and the
matching overriding `release/baseq2/operation-sandwatch.pk3`, includes only used
textures and the shared sky, and requires passing verification for exact source
and BSP hashes. Existing replaced files are backed up under the map's build
directory. Operation Sandkeep's package is preserved.

Verification checks all three difficulty counts, timed wave/unlock/resupply
chains, spawn and pickup hulls, enemy spawn separation, source/BSP consistency,
compiler warnings, the rooftop stairs, base routes, and closed/open access to
all deployment bays, lockers and extraction. These are targeted static checks;
real-engine captures and encounter checks provide additional runtime evidence.

```sh
python3 tools/maps/capture_sandkeep.py --label sandwatch-review \
  --map-name pp_sandwatch --map build/sandwatch-candidate/maps/pp_sandwatch.bsp \
  --materials baseq2 --assets /home/austin-morgan/.yq2/baseq2 \
  --views tools/maps/sandwatch_views.json --output-root build/sandwatch-qa
```

The capture harness runs the actual game in an isolated Xvfb/Mesa runtime and
does not change installed game settings or saves. Captures and console logs live
under `build/sandwatch-qa`. Camera teleportation checks appearance, not combat
balance. The PK3 and source are the reviewable deliverables.

The delivered build passed 189 placement/landing hull checks and 31 route/access
checks. `build/sandwatch-qa/encounter-final/result.json` records the real-engine
encounter check for the exact final BSP: all waves, weapon unlocks, survival time,
save/load, two-condition victory gating and extraction intermission passed.
The isolated single-player check accelerated time and telefragged enemies to
exercise the kill counter; it was not a normal combat playthrough. Its console
log, short chained console scripts and completion screenshot are saved beside
the report. The co-op client resets timing cheats even with `cheats 1`, so timing
acceleration is confined to the single-player QA session.
