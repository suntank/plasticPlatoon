ARCHIVED AUDITION NOTES: The notes below describe the delivered audition ZIP, before implementation. Preview reels are not duplicated in this repository. See ../../SUPPORT-RECORDINGS.md and selection.json for the installed subset and loop processing.

Plastic Platoon | Remaining Sound Auditions

39 new exported candidates cover 35 active or map-dependent placeholder slots. One additional legacy-boss impact candidate is provided separately as conditional. Four previous armor choices are reused for two armor slots. No game files or code were changed.

LISTENING
Plastic_Platoon_Remaining_Sounds_Preview.mp3 plays the core candidates and reused armor in the cue-list order with one second between sounds. Original levels are preserved. Grouped MP3s are included for pickups/interface, player/world, energy weapons and previous armor choices. The conditional legacy-boss impact has its own separate preview and is not mixed into the main preview. Health pickups have A/B takes. Ricochets and sparks each have three variations. Other new categories have one exported take; the other generated takes remain in ElevenLabs history.

CONTENTS
raw/: new unmodified stereo WAV exports.
mono/: full-length mono PCM16 48 kHz copies.
reused_armor/: four previously delivered armor options and mono copies, not newly generated.
previews/: MP3 audition reels.
slot_mapping.json: exact engine file slots associated with each candidate.
qc_manifest.json: prompts, durations, levels and original-file hashes.
preview_cues.json: exact cue times.

TESTING NOTES
All files were technically checked for valid decoding, expected duration, distinct content, nonzero signal and no full-scale PCM samples. I could not listen to them in this workflow or play-test them in Plastic Platoon. Audible quality, combat readability, event timing and loop seams remain unverified. These are audition candidates, not a finished in-game mix.
Generated clips retain their full duration. The minimum reliable explicit generation length was 0.5 seconds, so the shortest pickup, interface and impact clips can be longer than their placeholder slots. Exact durations are in the manifest. No timing edits were guessed. Looping categories were requested as seamless loops, but should be auditioned through repeated playback before installation.
Armor slot correction: ar1_pkup.wav is used for all full armor types; ar2_pkup.wav is for armor shards, not heavy armor.
The audit found 24 additional packaged legacy gunner/tank placeholders, but normal map spawns redirect to custom replacements. Those unconfirmed legacy slots were excluded instead of spending credits on unused variants. Six other slots without proven live playback were deferred: computer objective cue, disruptor impact, energy-weapon spin-up/operating/spin-down and electrical beam. The conditional legacy-boss impact is isolated separately. Remaining map/weapon-dependent effects may not be heard in every level. The bfg__l1a.wav slot is actually used by the flamethrower, and its new candidate is a sustained flame effect. protect4.wav is protection blocked-hit feedback, not expiration.

CUE LIST
000.000s  Health +2 A
001.486s  Health +2 B
002.973s  Health +10 A
004.460s  Health +10 B
005.946s  Health +25 A
007.553s  Health +25 B
009.159s  Health +100 A
010.966s  Health +100 B
012.772s  Pickup Generic
014.258s  Item Respawn
015.945s  Damage Powerup
017.631s  Protection Powerup
019.318s  Protection Blocked Hit
020.804s  Key Denied
022.291s  Key Accepted
023.777s  Switch Press
025.264s  Menu Move
026.750s  Menu Confirm
028.237s  Menu Back
029.723s  Secret Found
031.610s  Chat Notification
033.096s  Water Splash
034.783s  Plastic Shatter
036.589s  Landing Light
038.076s  Landing Heavy
039.682s  World Landing
041.169s  Breathing In
042.975s  Breathing Out
044.862s  Corpse Flies
047.862s  Mission Alarm
050.862s  Ricochet A
052.348s  Ricochet B
053.835s  Ricochet C
055.321s  Spark A
056.808s  Spark B
058.294s  Spark C
059.781s  Laser Flight
062.781s  Flamethrower Sustained Flame
065.781s  Laser Impact
067.267s  Pp Armor 01 Plasticsnap
069.074s  Pp Armor 02 Shieldpulse
070.880s  Pp Armor 03 Ratchetlock
072.687s  Pp Armor 04 Helmetpop
