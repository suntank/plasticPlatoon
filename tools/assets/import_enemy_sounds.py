#!/usr/bin/env python3
"""Import the six owner-supplied ElevenLabs soldier sounds as mono PCM16."""
import argparse
import hashlib
import json
from pathlib import Path

from import_soldier_sounds import mono_wav

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/assets/sources/elevenlabs-enemy-sounds'
MANIFEST = ROOT / 'tools/assets/enemy-sounds-manifest.json'
EFFECTS = {
    'all_quiet.wav': ('soldier/solidle1.wav', 'Soldier idle: All quiet.', False),
    'contact.wav': ('soldier/solsrch1.wav', 'Alternate sight alert: Contact!', False),
    'enemy_spotted.wav': ('soldier/solsght1.wav', 'Sight alert: Enemy spotted!', False),
    'rocket_fly.wav': ('weapons/rockfly.wav', 'Shared rocket flight loop', True),
    'rocket_reload.wav': ('soldier/rocket_reload.wav', 'Rocket soldier recovery reload', False),
    'shotgun_cock.wav': ('infantry/infatck3.wav', 'Existing weapon-cock / shotgun-pump event', False),
}


def import_effects(source=SOURCE, output=ROOT / 'baseq2/sound',
                   manifest_path=MANIFEST, verify=False):
    source, output, manifest_path = Path(source), Path(output), Path(manifest_path)
    report = {
        'schema': 1,
        'provider': 'ElevenLabs',
        'source': 'Six files supplied by the project owner on 2026-11-07.',
        'conversion': 'Stereo PCM16 averaged to mono PCM16; original sample rate, frame count and level preserved.',
        'rights_note': 'User authorized integration. Provider rights and redistribution licensing were not independently verified; no asset license change is made.',
        'files': [],
    }
    converted_files = []
    for filename, (runtime, role, loop) in sorted(EFFECTS.items()):
        original = (source / filename).read_bytes()
        converted, metadata = mono_wav(original)
        target = output / runtime
        report['files'].append({
            'source_path': 'tools/assets/sources/elevenlabs-enemy-sounds/' + filename,
            'path': 'sound/' + runtime, 'role': role, 'loop': loop,
            'source_sha256': hashlib.sha256(original).hexdigest(),
            'sha256': hashlib.sha256(converted).hexdigest(),
            'bytes': len(converted), **metadata,
        })
        converted_files.append((target, converted))
    if verify:
        for target, converted in converted_files:
            if target.read_bytes() != converted:
                raise ValueError(f'enemy sound differs from supplied source: {target}')
        if json.loads(manifest_path.read_text()) != report:
            raise ValueError('enemy sounds manifest differs from supplied sources')
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
    report = import_effects(args.source, args.output, args.manifest, args.verify)
    print(f'{"Verified" if args.verify else "Imported"} {len(report["files"])} owner-supplied mono enemy sounds.')


if __name__ == '__main__':
    main()
