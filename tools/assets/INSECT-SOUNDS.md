# Ant and spider effects

The approved 2026-11-11 original ElevenLabs pack supplies two takes per event:

- Ant: sight alert, pain, attack, idle and combat scuttle.
- Spider: pain, attack, idle and combat scuttle. Sight is intentionally silent.

Runtime files live under `baseq2/sound/ant/` and `baseq2/sound/spider/`, using
`<event>_01.wav` and `<event>_02.wav`. All eighteen clips are mono PCM16 at 48 kHz.
Existing shared sounds, including the insect gib sound `misc/udeath.wav`, are
not replaced. The overlay automatically includes both insect namespaces.

The raw stereo downloads and approved mono copies are retained in
`sources/elevenlabs-insect-sounds/`. Its original generation manifest records
prompts, settings, hashes and technical measurements. The generated runtime
manifest is `insect-sounds-manifest.json`. Import preserves the approved bytes
exactly, and verifies the PCM against a reproducible stereo downmix. Normal
builds need only Python. There are no gain, trim, pitch or timing changes.

Scuttle clips are short gait bursts, not seamless loops. Attack prompts requested
the bite near the middle of the 0.8-second clip, but actual audible alignment
still needs an in-game listening pass. Technical verification does not certify
the final audible mix. Provider rights and redistribution licensing have not
been independently verified; no asset license change is made.

## Runtime behavior

Each species alternates its two takes per event. The selection is cosmetic,
shared by that species, and does not use the gameplay random generator. Take
history may restart when the game module restarts. Standard engine idle/search
scheduling still uses its normal random initial delay and 15–30-second spacing.

- **Ant sight:** full-volume `CHAN_VOICE`, normal distance attenuation, only
  through the existing visible-target acquisition hook. Spider sight remains
  `NULL`, including when upgrading an old save.
- **Pain:** `CHAN_VOICE` at the existing three-second pain debounce. Nightmare
  still suppresses only the pain animation, not the sound.
- **Attack:** `CHAN_WEAPON` at the start of the existing 0.8-second attack.
  The bite still damages exactly once at frame 36; reach, obstruction, damage,
  movement, animation lengths and attack decisions are unchanged.
- **Idle/search:** quiet `CHAN_VOICE` using `ATTN_IDLE`, volume 0.65 for ants
  and 0.45 for spiders. No idle vocalization is started during an active fight.
  The engine retains its normal ambush-idle suppression.
- **Combat scuttle:** `CHAN_BODY`, volume 0.55 for ants and 0.40 for spiders.
  A burst starts only after actual horizontal walking/running movement with a
  live target, grounded and not submerged, held or standing ground. Bursts are
  at least 1.5 seconds apart, leaving space beyond the 1.2-second clip. Blocked,
  idle and noncombat patrol movement does not start bursts. These are creature
  combat sounds and intentionally work independently of `g_monsterfootsteps`,
  whose default is off; no existing footstep setting or other enemy is changed.

All samples are precached at spawn and resolved by name at playback to avoid
stale sound indices after a map/load change. New idle/sight callbacks are
registered with the save system. Old saves with NULL hooks receive the missing
callbacks on load without changing combat state. Scuttle uses the insects'
previously unused, already-serialized `last_move_time` for its next allowed
burst. No entity layout or save format changed.

There is no persistent looping entity sound. No new vocalization or scuttle
starts after death; an already-playing one-shot may naturally finish. The
shared gib/death behavior remains unchanged.

## Rebuild and verify

```sh
python3 tools/assets/import_insect_sounds.py
python3 tools/assets/import_insect_sounds.py --verify
python3 tests/assets/test_insect_sounds.py
python3 tools/assets/build_overlay.py --output baseq2/plastic-platoon.pk3
python3 tools/assets/build_overlay.py --verify --output baseq2/plastic-platoon.pk3
make -j4 game assets
tests/ant/run_tests.sh
tests/spider/run_tests.sh
tests/insect_sounds/run_wave_tests.sh
```

Make and CMake asset builds verify the imported files before packaging them.
Restart the game after replacing the game module and asset pack. Existing
`exec ant_test.cfg` and `exec spider_test.cfg` launch the creature test ranges.

## Integration verification (2026-11-11)

- Debug and release game modules, dedicated server and asset packaging built.
- Ant/spider behavior tests passed, including real visible-target acquisition,
  silent spider detection, both takes, pain debounce/nightmare, movement
  distances/cadence, blocked/stationary/noncombat silence and save/load migration.
  Existing bite damage, reach/obstruction, death and gib checks still pass.
- All 18 files passed the actual engine WAV parser, including AddressSanitizer
  and UndefinedBehaviorSanitizer. Leak detection was disabled for that local
  sanitizer run because LeakSanitizer does not operate under this environment's
  process tracing. The normal test run also passed.
- The complete asset suite ran 100 tests: 99 passed and one optional mesh
  conversion test was skipped because pymeshlab is not installed.
- Soldier sounds, heavy gunner, rocket soldier, tank and helicopter regressions
  passed. Both packaged overlays verify all 579 assets and 115 model/sprite
  image dependencies. Standalone/public-source audits passed their strict checks;
  the standalone audit still reports legacy source-only literals, not missing
  packaged model references.
- Dedicated-server map loads for the ant range, spider range and End of the Line
  completed without asset/index overflow. Existing ammo-profile warnings remain.
- Full client build and rendered/listening QA are not complete: this environment
  lacks OpenAL/SDL development headers. Final audible bite alignment and balance
  still need a listening pass in the game's client.

The Linux CI workflow now runs the new asset, creature and WAV parser checks.
