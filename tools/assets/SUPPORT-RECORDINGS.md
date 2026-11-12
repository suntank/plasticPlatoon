# Approved support recording replacement (2026-11-12)

Austin approved the preview and requested implementation/publication. The source
selection is in `sources/elevenlabs-support-sounds/selection.json`; runtime hashes
are in `support-recordings-manifest.json`. `import_support_recordings.py` imports
or verifies them. Both supported build systems verify before packaging.

37 existing slots are replaced without changing gameplay callbacks: 35 active or
map-dependent support slots plus full armor and shards. Health uses take A for
+2/+10/+25/+100; approved B takes remain available as editable source alternatives.
Full armor uses Ratchet Lock; armor shards use Plastic Snap. All four armor
options remain in the source folder. No new random behavior is introduced.

Important semantic mappings: `protect4.wav` is invulnerability blocked-hit
feedback, not expiration; `bfg__l1a.wav` is the current flamethrower firing loop.
The conditional legacy BFG impact is retained as an audition source but not
installed. Thirty other legacy or unproven-use slots are deferred. Thus 31
procedural support files remain, explicitly listed by the old generator manifest.
Removed installed slots from the procedural generator to prevent tone regression.

One-shots retain the approved mono PCM16 48kHz WAV bytes, including duration and
gain. Four sustained sounds (flies, laser flight, flamethrower, mission alarm)
receive a deterministic 40ms linear wrap crossfade and interior rotation, removing
40ms from each two-second clip. This keeps the cyclic seam at adjacent original
samples, avoiding a boundary click without a silent fade at every cycle. Raw
exports and approved mono sources are preserved. No gain normalization was used.

Generation used ElevenLabs Sound Effects v3. Metadata/prompt provenance is
retained. Provider redistribution rights were not independently verified; this
change makes no new blanket licensing claim.

Validation: importer/PCM/source hash checks, one-shot byte identity, loop seam
continuity tests, remaining procedural generator verification, asset suite and
game/assets build. These do not substitute for in-game listening: balance,
readability, rapid menu navigation, and sustained-loop perception should be tried
on target hardware. Audition source files are not loaded by the runtime; only
baseq2/sound replacements are packaged.
