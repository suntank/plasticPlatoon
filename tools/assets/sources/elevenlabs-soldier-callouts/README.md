# Additional soldier callouts

Eight new takes were generated in ElevenLabs on 2026-11-11 for the owner's
request for more enemy alert variety. Each of “Contact!”, “Enemy spotted!”,
“Over here!” and “Contact, get him!” has two takes.

The original MP3 exports are retained alongside canonical decoded PCM16 WAV
sources. The source exports are mono, 44.1 kHz, 192 kbps. The generation used
Harry - Fierce Warrior, Eleven v4, stability 50%, similarity 75%, and the
`[urgent]` tag, matching the earlier callout generation settings. These are
new takes, not copies or modifications of the previous two alerts.

WAV sources were decoded without normalization or resampling:

```sh
ffmpeg -i INPUT.mp3 -ac 1 -ar 44100 -c:a pcm_s16le OUTPUT.wav
```

Ordinary builds require only Python, not ffmpeg: `import_soldier_callouts.py`
converts the canonical WAV sources to minimal mono WAVs and checks their exact
sample bytes. `soldier-callouts-manifest.json` records hashes for both original
MP3 and decoded WAV sources, plus every runtime file and its phrase/take.

The original six supplied effects and their importer are unchanged. These
files do not alter the project's asset-license declaration or independently
certify provider rights or redistribution licensing.
