# Approved original insect effects

These eighteen effects were generated in ElevenLabs Sound Effects v3 on
2026-11-11 for the owner's ant/spider sound request. The owner approved
implementation after receiving the audition reel. They are original insect
sound designs, not extracted Half-Life 2 recordings.

`raw/` preserves the downloaded stereo PCM16 WAVs. `game_ready/` preserves the
approved 48 kHz mono PCM16 WAVs exactly, including ffmpeg INFO metadata.
`generation-manifest.json` preserves prompts, settings, source/canonical hashes,
measured formats and the original audition cue list. `GENERATION-README.txt`
is the unchanged delivery readme; its statement that code was not changed
refers to creation of the sound pack, before this integration.

The importer verifies every canonical sample against the stereo arithmetic
mean rounded toward positive infinity, matching the original ffmpeg downmix.
This differs by up to one sample unit from the older soldier importer's floor
rounding. No gain, fades, trimming, resampling, pitch or timing edits are applied.
Normal builds and verification require only Python, not ffmpeg.

The preview reel itself is not a runtime input. Attack bite placement has not
been audibly verified; the original request placed the bite near the middle of
the 0.8-second attack clip. Scuttle clips are 1.2-second bursts, not seamless
loops or individual footsteps. No spider sight sound was requested or generated.

Provider rights and redistribution licensing were not independently verified.
No project asset-license change is made by this integration.
