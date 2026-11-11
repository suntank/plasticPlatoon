# Soldier sound replacements

The light, shotgun, SS machinegun, heavy M60 and rocket launcher soldiers reuse
the custom player recordings originally supplied by the local installation.
Their original source archive is now `sources/player-sounds.zip`; imports and
verification use that repository copy without requiring `~/.yq2`. Their firing, pain,
death, gib-death and footstep sounds are included in `plastic-platoon.pk3`.
Clips are converted to mono PCM16 at their original 48 kHz rate, preserving
duration and level, so world sounds can be positioned at the enemy. NPC copies
use `sound/soldier/player/` so the original player files and the user's
`sound.zip` cannot override them. Original recordings are unchanged.

| Enemy | Firing sound | Pain | Death |
| --- | --- | --- | --- |
| Light | `soldier/player/pistol1.wav`–`pistol4.wav` | `soldier/player/pain25_1.wav` | `soldier/player/death2.wav` |
| Shotgun | `soldier/player/shotgf1b.wav` | `soldier/player/pain50_1.wav` | `soldier/player/death1.wav` |
| SS machinegun | `soldier/player/machgf1b.wav`–`machgf5b.wav` | `soldier/player/pain100_1.wav` | `soldier/player/death3.wav` |
| Heavy M60 | `soldier/player/m601.wav`–`m605.wav` | `soldier/player/pain100_1.wav` | `soldier/player/death3.wav` |
| Rocket launcher | `soldier/player/rocklf1a.wav` | `soldier/player/pain100_1.wav` | `soldier/player/death3.wav` |

Every variant uses `soldier/player/death4.wav` when gibbed and copies of the
player's `step1.wav`–`step4.wav` under `soldier/player/` when
`g_monsterfootsteps` is enabled. Rocket explosions reuse the shared
`weapons/rocklx1a.wav`; a mono copy is packaged, although a user sound archive
can still supply its original stereo version for this shared effect. Heavy
and rocket firing already used player recordings; their dedicated NPC copies
are now packaged with the project. Enemy timing and sound events are unchanged.

## Supplied ElevenLabs replacements

On 2026-11-07 the owner supplied six replacement clips and authorized their
integration. Their unchanged sources are retained in
`sources/elevenlabs-enemy-sounds/`; exact source/output hashes, roles and formats
are in [`enemy-sounds-manifest.json`](enemy-sounds-manifest.json).

| Supplied clip | Runtime path | Event |
| --- | --- | --- |
| `all_quiet.wav` | `soldier/solidle1.wav` | Idle chatter: “All quiet.” |
| `enemy_spotted.wav` | `soldier/solsght1.wav` | Sight alert: “Enemy spotted!” |
| `contact.wav` | `soldier/solsrch1.wav` | Alternate **sight** alert, despite the legacy search filename. |
| `shotgun_cock.wav` | `infantry/infatck3.wav` | Existing weapon-cocking / shotgun-pump callbacks. |
| `rocket_fly.wav` | `weapons/rockfly.wav` | Shared rocket flight loop. |
| `rocket_reload.wav` | `soldier/rocket_reload.wav` | Rocket soldier reload after recovery. |

All six runtime files are mono PCM16 at 48 kHz. Conversion preserves source
frame counts and levels, averaging the stereo mechanical effects and retaining
the voice samples. The five replaced procedural slots have been removed from
`build_support_sounds.py`, so asset rebuilding will not restore placeholders.
The existing source player recordings and their 28-file conversion are unchanged.

The rocket soldier plays the reload once at the end of its recovery animation,
after a successful launch, during the existing 2.5-second cooldown. Cancelled
windups and dead soldiers do not play it; repeated recovery calls and save/load
do not duplicate it. No fire rate, damage, movement, animation duration or
cooldown changes were made. Its dedicated NPC path avoids the player reload
placeholder. The other five effects retain their existing shared runtime paths;
a higher-priority custom sound pack can still override those paths.

These are the supplied clips, not regenerated or voice-matched takes. Technical
checks do not replace a listening pass against the rest of the game. Integration
is local; no publication or asset-license change was made. Provider rights and
redistribution licensing have not been independently verified.

## Rebuild and verify

### Additional alert variations (2026-11-11)

All five soldier types now share ten sight-alert clips: both existing alerts
plus eight newly generated ElevenLabs takes. The new set has two takes each of
“Contact!”, “Enemy spotted!”, “Over here!” and “Contact, get him!”. The previous
two audio files, idle chatter and mechanical effects remain unchanged.

The selector excludes the last spoken phrase across all soldiers, including
different takes of that phrase, then randomly chooses from the remaining clips.
Consecutive sightings therefore cannot repeat “Contact, get him!” or any other
wording. The original normal-soldier run-and-fire decision remains intact, and
heavy/rocket sight callbacks still only alert. No entity layout, savegame
callback, attack timing, damage or cooldown changed. Cosmetic selection history
is not saved; the first alert after a fresh process/load may repeat the last
phrase heard before quitting.

The new runtime paths are `soldier/callouts/contact_a.wav`, `contact_b.wav`,
`enemy_spotted_a.wav`, `enemy_spotted_b.wav`, `over_here_a.wav`, `over_here_b.wav`,
`contact_get_him_a.wav` and `contact_get_him_b.wav`. Each is mono PCM16 at its
original 44.1 kHz rate. All ten alerts are precached when a soldier spawns; sound
indices are resolved by name when played, including after loading an old save.

The original MP3 exports and canonical decoded WAVs are retained under
`sources/elevenlabs-soldier-callouts/`. Source settings, hashes, phrases, takes
and sample metadata are in `soldier-callouts-manifest.json`. The separate
importer preserves the old six-source manifest and needs only Python during
normal builds. New takes have not had an in-game listening pass. Provider
rights and redistribution licensing have not been independently verified.

```sh
python3 tools/assets/import_soldier_callouts.py
python3 tools/assets/import_soldier_callouts.py --verify
python3 tests/assets/test_soldier_callouts.py
```

### Common build checks

The source/output hashes, exact mappings and missing events are recorded in
[`soldier-sounds-manifest.json`](soldier-sounds-manifest.json).

```sh
# Re-import only when changing the source player recordings:
python3 tools/assets/import_soldier_sounds.py
python3 tools/assets/import_soldier_sounds.py --verify
# Re-import only when changing the six supplied sources:
python3 tools/assets/import_enemy_sounds.py
python3 tools/assets/import_enemy_sounds.py --verify
python3 tools/assets/build_support_sounds.py --verify
python3 tests/assets/test_enemy_sounds.py
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
make -j4 client game assets
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
python3 tests/assets/test_overlay.py
tests/soldier_sounds/run_tests.sh
tests/performance/run_effects_tests.sh
tests/heavy_gunner/run_tests.sh
tests/rocket_soldier/run_tests.sh
```

Restart the game after rebuilding to load the changed client, game module and
asset archive. `exec heavy_test.cfg` and `exec rocket_test.cfg` provide the
existing heavy/rocket test ranges; ordinary maps provide the other soldiers.

The prior player-recording integration was validated for all five variants' sound registration, pain/death/gib
callbacks and optional footsteps; every legacy firing animation's sound
selection; and existing heavy/rocket gameplay and save/load checks. Ten asset
regressions and the source conversion/archive verification passed. Release
and debug builds contain identical updated asset packs. An isolated 240-frame
GL1 run with the original user `sound.zip` present loaded all 27 NPC aliases
as mono and exited cleanly. That run used SDL's dummy audio output to exercise
decoding and mixing without playing sound aloud.

### 2026-11-07 integration verification

See the delivery README for the checks actually run for this change and any
environment limitations. In particular, the older GL1 validation above predates
these six replacements and is not a listening or rendered test of this change.
