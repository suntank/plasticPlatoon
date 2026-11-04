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

## Sounds still needed

Existing runtime sounds are retained where a suitable custom recording is
missing. The near-silent player placeholders are not used as replacements.

| Event | Current sound / replacement slot | Missing content |
| --- | --- | --- |
| Idle chatter | `soldier/solidle1.wav` | No matching player recording. |
| Sight alert | `soldier/solsght1.wav` | No matching player recording. |
| Alternate alert/search | `soldier/solsrch1.wav` | No matching player recording. |
| Weapon cock / shotgun pump | `infantry/infatck3.wav` | Player `weapons/shotgr1b.wav` is only a near-silent 55 ms placeholder. |
| Rocket flight loop | `weapons/rockfly.wav` | No custom player replacement. |
| Rocket reload | `weapons/rocklr1b.wav` | Near-silent 55 ms player placeholder; the NPC does not currently play a reload event. |

For the first five rows, add a mono PCM WAV under `baseq2/sound/` at the current
sound path, then rebuild the asset pack. The rocket reload would also need a
sound event during the existing recovery animation. No new dialogue or effects
were generated: ElevenLabs was checked but required account sign-in.

## Rebuild and verify

The source/output hashes, exact mappings and missing events are recorded in
[`soldier-sounds-manifest.json`](soldier-sounds-manifest.json).

```sh
# Re-import only when changing the source player recordings:
python3 tools/assets/import_soldier_sounds.py
python3 tools/assets/import_soldier_sounds.py --verify
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

Validation passed for all five variants' sound registration, pain/death/gib
callbacks and optional footsteps; every legacy firing animation's sound
selection; and existing heavy/rocket gameplay and save/load checks. Ten asset
regressions and the source conversion/archive verification passed. Release
and debug builds contain identical updated asset packs. An isolated 240-frame
GL1 run with the original user `sound.zip` present loaded all 27 NPC aliases
as mono and exited cleanly. That run used SDL's dummy audio output to exercise
decoding and mixing without playing sound aloud.
