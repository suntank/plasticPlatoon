#!/usr/bin/env python3
"""Install approved support recordings; retain audition sources and deterministic loop seam treatment."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import wave

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/assets/sources/elevenlabs-support-sounds'
MANIFEST = ROOT / 'tools/assets/support-recordings-manifest.json'

def convert(data, loop):
    with wave.open(io.BytesIO(data), 'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) != (1, 2, 48000, 'NONE'):
            raise ValueError('expected mono PCM16 48kHz')
        frames = w.getnframes()
        samples = list(struct.unpack('<' + 'h' * frames, w.readframes(frames)))
    if not samples or not any(samples):
        raise ValueError('empty or silent sound')
    if not loop:
        return data
    # Rotate into the interior of the recording, blending the end into its start.
    # This preserves the join between the crossfade and the unmodified interior.
    n = min(1920, len(samples)//4)
    blend = [round(samples[-n+i]*(1-i/(n-1)) + samples[i]*i/(n-1)) for i in range(n)]
    samples = samples[n:-n] + blend
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        w.writeframes(struct.pack('<'+'h'*len(samples), *samples))
    return out.getvalue()

def run(verify=False):
    entries = json.loads((SOURCE/'selection.json').read_text())
    report = {'schema':1, 'provider':'ElevenLabs Sound Effects v3', 'date':'2026-11-12',
      'rights_note':'Owner-requested generated audio; provider redistribution rights not independently verified. No new license declaration.',
      'processing':'One-shots retain approved mono bytes. Loops have deterministic 40 ms linear wrap crossfade; no gain change. In-game listening still required.', 'files':[]}
    for entry in entries:
        data = (SOURCE/entry['source']).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['source_sha256']:
            raise ValueError('source hash mismatch: '+entry['source'])
        output = convert(data, entry['loop'])
        path = ROOT/'baseq2'/entry['target']
        if verify:
            if path.read_bytes() != output: raise ValueError('runtime mismatch: '+str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(output)
        report['files'].append(dict(entry,sha256=hashlib.sha256(output).hexdigest(),bytes=len(output)))
    if verify:
        if json.loads(MANIFEST.read_text()) != report: raise ValueError('support recordings manifest mismatch')
    else: MANIFEST.write_text(json.dumps(report,indent=2)+'\n')
    print(('Verified' if verify else 'Imported')+f' {len(entries)} support recordings')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    run(parser.parse_args().verify)
