#!/usr/bin/env python3
"""Import the player's custom soldier sounds as spatial mono PCM WAV files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOUNDS = sorted(
    [f'weapons/pistol{i}.wav' for i in range(1, 5)]
    + ['weapons/shotgf1b.wav']
    + [f'weapons/machgf{i}b.wav' for i in range(1, 6)]
    + [f'weapons/m60{i}.wav' for i in range(1, 6)]
    + ['weapons/rocklf1a.wav', 'weapons/rocklx1a.wav']
    + [f'player/step{i}.wav' for i in range(1, 5)]
    + [f'player/male/pain{health}_1.wav' for health in (25, 50, 100)]
    + [f'player/male/death{i}.wav' for i in range(1, 5)]
)


def sound_path(source_path):
    """Keep NPC samples separate from the player's higher-priority stereo assets."""
    if source_path == 'weapons/rocklx1a.wav':
        return source_path  # Rocket impact uses the shared player explosion event.
    return f'soldier/player/{Path(source_path).name}'


MAPPINGS = {
    'monster_soldier_light': {
        'fire': [f'soldier/player/pistol{i}.wav' for i in range(1, 5)],
        'pain': 'soldier/player/pain25_1.wav', 'death': 'soldier/player/death2.wav'},
    'monster_soldier': {
        'fire': ['soldier/player/shotgf1b.wav'],
        'pain': 'soldier/player/pain50_1.wav', 'death': 'soldier/player/death1.wav'},
    'monster_soldier_ss': {
        'fire': [f'soldier/player/machgf{i}b.wav' for i in range(1, 6)],
        'pain': 'soldier/player/pain100_1.wav', 'death': 'soldier/player/death3.wav'},
    'monster_soldier_heavy': {
        'fire': [f'soldier/player/m60{i}.wav' for i in range(1, 6)],
        'pain': 'soldier/player/pain100_1.wav', 'death': 'soldier/player/death3.wav'},
    'monster_soldier_rocket': {
        'fire': ['soldier/player/rocklf1a.wav'], 'explosion': 'weapons/rocklx1a.wav',
        'pain': 'soldier/player/pain100_1.wav', 'death': 'soldier/player/death3.wav'},
    'all_soldiers': {
        'footsteps': [f'soldier/player/step{i}.wav' for i in range(1, 5)],
        'gib_death': 'soldier/player/death4.wav'},
}

MISSING = [
    {'event': 'idle chatter', 'runtime_sound': 'soldier/solidle1.wav',
     'reason': 'No custom player equivalent; existing runtime sound retained.'},
    {'event': 'sight alert', 'runtime_sound': 'soldier/solsght1.wav',
     'reason': 'No custom player equivalent; existing runtime sound retained.'},
    {'event': 'search callout', 'runtime_sound': 'soldier/solsrch1.wav',
     'reason': 'No custom player equivalent; existing runtime sound retained.'},
    {'event': 'weapon cock / shotgun pump', 'runtime_sound': 'infantry/infatck3.wav',
     'candidate': 'weapons/shotgr1b.wav',
     'reason': 'Player candidate is a near-silent 55 ms placeholder; existing runtime sound retained.'},
    {'event': 'rocket flight loop', 'runtime_sound': 'weapons/rockfly.wav',
     'reason': 'No custom player equivalent; existing runtime sound retained.'},
    {'event': 'rocket reload', 'candidate': 'weapons/rocklr1b.wav',
     'reason': 'Player candidate is a near-silent 55 ms placeholder. The NPC currently has no reload sound event.'},
]


def mono_wav(data):
    """Average stereo channels without resampling, normalization or clipping."""
    with wave.open(io.BytesIO(data), 'rb') as source:
        channels = source.getnchannels()
        if source.getcomptype() != 'NONE' or source.getsampwidth() != 2 or channels not in (1, 2):
            raise ValueError('expected mono or stereo uncompressed PCM16 WAV')
        rate, frames = source.getframerate(), source.getnframes()
        samples = source.readframes(frames)
    if len(samples) != frames * channels * 2:
        raise ValueError('truncated WAV samples')
    if channels == 2:
        samples = b''.join(struct.pack('<h', (left + right) // 2)
                           for left, right in struct.iter_unpack('<hh', samples))
    output = io.BytesIO()
    with wave.open(output, 'wb') as destination:
        destination.setparams((1, 2, rate, frames, 'NONE', 'not compressed'))
        destination.writeframes(samples)
    metadata = {'source_channels': channels, 'channels': 1, 'sample_width': 2,
                'sample_rate': rate, 'frames': frames}
    return output.getvalue(), metadata


def import_sounds(source, output, manifest_path, verify=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    originals = None
    if source.is_file():
        with zipfile.ZipFile(source) as archive:
            originals = {name: archive.read('sound/' + name) for name in SOUNDS}
    source_label = str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source)
    report = {'schema': 1, 'source_root': source_label,
              'conversion': 'Stereo PCM16 averaged to mono PCM16; original rate and frame count preserved.',
              'namespace': 'Dedicated soldier/player paths avoid overrides by existing player WAVs and sound.zip; rocket explosion remains shared.',
              'mappings': MAPPINGS, 'missing': MISSING, 'files': []}
    for name in SOUNDS:
        original = originals[name] if originals is not None else (source / name).read_bytes()
        converted, metadata = mono_wav(original)
        target_name = sound_path(name)
        target = output / target_name
        if verify:
            if target.read_bytes() != converted:
                raise ValueError(f'imported sound differs from mono player source: {name}')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(converted)
        report['files'].append({'source_path': f'sound/{name}', 'path': f'sound/{target_name}',
                                'source_sha256': hashlib.sha256(original).hexdigest(),
                                'sha256': hashlib.sha256(converted).hexdigest(),
                                'bytes': len(converted), **metadata})
    manifest_path = Path(manifest_path)
    if verify:
        if json.loads(manifest_path.read_text()) != report:
            raise ValueError('soldier sound manifest differs from imported player sounds')
    else:
        manifest_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'tools/assets/sources/player-sounds.zip')
    parser.add_argument('--output', type=Path, default=ROOT / 'baseq2/sound')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'tools/assets/soldier-sounds-manifest.json')
    parser.add_argument('--verify', action='store_true', help='verify source conversion and manifest without writing')
    args = parser.parse_args()
    report = import_sounds(args.source, args.output, args.manifest, args.verify)
    print(f'{"Verified" if args.verify else "Imported"} {len(report["files"])} mono player sounds; '
          f'{sum(item["bytes"] for item in report["files"])} bytes. '
          f'{len(report["missing"])} missing custom sound events recorded.')


if __name__ == '__main__':
    main()
