#!/usr/bin/env python3
"""Import the eight additional ElevenLabs soldier alerts as spatial mono PCM16."""
import argparse
import hashlib
import json
from pathlib import Path

from import_soldier_sounds import mono_wav

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/assets/sources/elevenlabs-soldier-callouts'
MANIFEST = ROOT / 'tools/assets/soldier-callouts-manifest.json'
CALLOUTS = {
    'PP_Callout_01_Contact_A': ('contact_a.wav', 'Contact!', 'A'),
    'PP_Callout_02_Contact_B': ('contact_b.wav', 'Contact!', 'B'),
    'PP_Callout_03_EnemySpotted_A': ('enemy_spotted_a.wav', 'Enemy spotted!', 'A'),
    'PP_Callout_04_EnemySpotted_B': ('enemy_spotted_b.wav', 'Enemy spotted!', 'B'),
    'PP_Callout_05_OverHere_A': ('over_here_a.wav', 'Over here!', 'A'),
    'PP_Callout_06_OverHere_B': ('over_here_b.wav', 'Over here!', 'B'),
    'PP_Callout_07_ContactGetHim_A': ('contact_get_him_a.wav', 'Contact, get him!', 'A'),
    'PP_Callout_08_ContactGetHim_B': ('contact_get_him_b.wav', 'Contact, get him!', 'B'),
}


def import_callouts(source=SOURCE, output=ROOT / 'baseq2/sound',
                    manifest_path=MANIFEST, verify=False):
    source, output, manifest_path = Path(source), Path(output), Path(manifest_path)
    report = {
        'schema': 1,
        'provider': 'ElevenLabs',
        'created_date': '2026-11-11',
        'voice': 'Harry - Fierce Warrior',
        'model': 'Eleven v4',
        'settings': {'stability_percent': 50, 'similarity_percent': 75, 'tag': '[urgent]'},
        'conversion': 'Original MP3 exports retained. Canonical WAV sources decoded with ffmpeg to PCM16 at 44100 Hz; mono import preserves sample rate, frame count and level. Normal builds and verification do not require ffmpeg.',
        'rights_note': 'Generated for the owner-requested callout variations. Provider rights and redistribution licensing were not independently verified; no asset license change is made.',
        'files': [],
    }
    converted_files = []
    for stem, (filename, phrase, take) in sorted(CALLOUTS.items()):
        original = (source / (stem + '.mp3')).read_bytes()
        decoded = (source / (stem + '.wav')).read_bytes()
        converted, metadata = mono_wav(decoded)
        runtime = 'soldier/callouts/' + filename
        prefix = 'tools/assets/sources/elevenlabs-soldier-callouts/' + stem
        report['files'].append({
            'original_path': prefix + '.mp3',
            'original_sha256': hashlib.sha256(original).hexdigest(),
            'source_path': prefix + '.wav',
            'source_sha256': hashlib.sha256(decoded).hexdigest(),
            'path': 'sound/' + runtime,
            'phrase': phrase, 'take': take, 'loop': False,
            'sha256': hashlib.sha256(converted).hexdigest(),
            'bytes': len(converted), **metadata,
        })
        converted_files.append((output / runtime, converted))
    if verify:
        for target, converted in converted_files:
            if target.read_bytes() != converted:
                raise ValueError(f'soldier callout differs from source: {target}')
        if json.loads(manifest_path.read_text()) != report:
            raise ValueError('soldier callouts manifest differs from sources')
    else:
        for target, converted in converted_files:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(converted)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=ROOT / 'baseq2/sound')
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    report = import_callouts(args.source, args.output, args.manifest, args.verify)
    print(f'{"Verified" if args.verify else "Imported"} {len(report["files"])} mono soldier callout variations.')


if __name__ == '__main__':
    main()
