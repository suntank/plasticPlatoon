#!/usr/bin/env python3
"""Import the approved ant/spider effects without altering their PCM or metadata."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import wave

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/assets/sources/elevenlabs-insect-sounds'
MANIFEST = ROOT / 'tools/assets/insect-sounds-manifest.json'
EVENTS = {'ant': ('sight', 'pain', 'attack', 'idle', 'scuttle'),
          'spider': ('pain', 'attack', 'idle', 'scuttle')}
SOUNDS = tuple(f'{creature}/{event}_{take:02}.wav'
               for creature, events in EVENTS.items() for event in events
               for take in (1, 2))


def pcm(data, channels):
    with wave.open(io.BytesIO(data), 'rb') as sound:
        if (sound.getcomptype(), sound.getnchannels(), sound.getsampwidth(),
                sound.getframerate()) != ('NONE', channels, 2, 48000):
            raise ValueError('expected 48 kHz PCM16 WAV with specified channels')
        frames = sound.getnframes()
        samples = sound.readframes(frames)
    if not frames or len(samples) != frames * channels * 2:
        raise ValueError('empty or truncated WAV samples')
    return frames, samples


def import_sounds(source=SOURCE, output=ROOT / 'baseq2/sound',
                  manifest_path=MANIFEST, verify=False):
    source, output, manifest_path = Path(source), Path(output), Path(manifest_path)
    generation_bytes = (source / 'generation-manifest.json').read_bytes()
    generation = json.loads(generation_bytes)
    generated = {f['game_ready_file'][len('game_ready/'):]: f for f in generation['files']}
    if set(generated) != set(SOUNDS) or len(generation['files']) != len(SOUNDS):
        raise ValueError('generation manifest must describe exactly the 18 approved takes')
    report = {
        'schema': 1, 'provider': generation['source'],
        'created_date': generation['created_date'],
        'generation_settings': generation['generation_settings'],
        'generation_manifest': 'tools/assets/sources/elevenlabs-insect-sounds/generation-manifest.json',
        'generation_manifest_sha256': hashlib.sha256(generation_bytes).hexdigest(),
        'conversion': 'Approved mono WAV bytes retained including INFO metadata. PCM independently verified against stereo arithmetic mean rounded toward positive infinity, matching the original ffmpeg downmix. No trim, gain, pitch, resampling or timing changes.',
        'rights_note': 'Generated for the owner-requested insect effects. Provider rights and redistribution licensing were not independently verified; no asset license change is made.',
        'spider_sight': 'Intentionally silent; no sight asset.',
        'files': [],
    }
    converted = []
    for name in SOUNDS:
        raw = (source / 'raw' / name).read_bytes()
        mono = (source / 'game_ready' / name).read_bytes()
        raw_hash, mono_hash = hashlib.sha256(raw).hexdigest(), hashlib.sha256(mono).hexdigest()
        item = generated[name]
        if raw_hash != item['raw_sha256'] or mono_hash != item['game_ready_sha256']:
            raise ValueError(f'approved source hash mismatch: {name}')
        frames, stereo_samples = pcm(raw, 2)
        mono_frames, mono_samples = pcm(mono, 1)
        expected = b''.join(struct.pack('<h', (left + right + 1) // 2)
                            for left, right in struct.iter_unpack('<hh', stereo_samples))
        if frames != mono_frames or mono_samples != expected:
            raise ValueError(f'approved mono PCM differs from stereo downmix: {name}')
        if not any(mono_samples):
            raise ValueError(f'silent PCM: {name}')
        report['files'].append({
            'source_path': f'tools/assets/sources/elevenlabs-insect-sounds/raw/{name}',
            'canonical_path': f'tools/assets/sources/elevenlabs-insect-sounds/game_ready/{name}',
            'source_sha256': raw_hash, 'path': 'sound/' + name,
            'sha256': mono_hash, 'bytes': len(mono), 'frames': frames,
            'channels': 1, 'sample_width': 2, 'sample_rate': 48000,
            'duration_seconds': frames / 48000,
            'creature': item['creature'], 'event': item['event'], 'take': item['take'],
            'loop': False,
        })
        converted.append((output / name, mono))
    if verify:
        for target, data in converted:
            if target.read_bytes() != data:
                raise ValueError(f'insect sound differs from approved source: {target}')
        if json.loads(manifest_path.read_text()) != report:
            raise ValueError('insect sounds manifest differs from sources')
    else:
        for target, data in converted:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
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
    report = import_sounds(args.source, args.output, args.manifest, args.verify)
    print(f'{"Verified" if args.verify else "Imported"} {len(report["files"])} approved mono insect effects.')


if __name__ == '__main__':
    main()
