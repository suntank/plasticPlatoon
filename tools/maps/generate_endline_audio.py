#!/usr/bin/env python3
"""Synthesize original toy-train audio for Operation End of the Line.

Python standard library only. All samples originate in deterministic oscillators
and seeded noise here, without recordings, samples, or third-party game data.
GPL-2.0-or-later, matching Plastic Platoon's original asset license.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[2]
RATE = 22050
TAU = math.tau


def normalize(samples, peak):
    factor = peak / max(abs(v) for v in samples)
    return [max(-32767, min(32767, round(v * factor * 32767))) for v in samples]


def whistle():
    """Two short blows from a small electric toy-locomotive whistle."""
    rng = random.Random(7701)
    samples = []
    for i in range(round(1.85 * RATE)):
        t = i / RATE
        env = 0
        for onset, duration in ((.04, .55), (.79, .92)):
            p = t-onset
            if 0 <= p < duration:
                env += min(1., p/.065, (duration-p)/.14)
        # Deliberately pitched above a full-size steam engine: a toy-scale
        # 3:4:5 chord, with slight breath noise and electric vibrato.
        vibrato = .006 * math.sin(TAU * 5.2 * t)
        tone = sum(amp * math.sin(TAU * freq * t + vibrato)
                   for freq, amp in ((660,.68),(880,.32),(1100,.20),(1320,.08)))
        samples.append(env*(tone + rng.uniform(-.075,.075)))
    return normalize(samples,.62)


def wheels():
    """Seamless 1.6-second rolling loop, with eight paired rail-joint taps."""
    n = round(1.6 * RATE)
    rng = random.Random(7702)
    noise = [rng.uniform(-1,1) for _ in range(n)]
    # Circular smoothing makes the low rumble wrap without a noise seam.
    smooth = [sum(noise[(i+j)%n] for j in range(-4,5))/9 for i in range(n)]
    samples = []
    for i in range(n):
        t = i/RATE
        # Integer cycles over the loop produce continuous periodic motor hum.
        motor = .18*math.sin(TAU*112*t/1.6)+.08*math.sin(TAU*224*t/1.6)
        beat = t % .2
        clack = 0
        for phase, strength in ((0.,1.),(.045,.55)):
            age = (beat-phase) % .2
            clack += strength*math.exp(-age*95)*(
                math.sin(TAU*725*age)*.24 + noise[i]*.43)
        samples.append(motor+smooth[i]*.23+clack)
    return normalize(samples,.44)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'baseq2/sound/endline')
    p.add_argument('--manifest',type=Path,default=ROOT/'tools/maps/endline-audio.json')
    args = p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest = {'license':'GPL-2.0-or-later',
                'generator':'tools/maps/generate_endline_audio.py',
                'source':'Original deterministic synthesized oscillators and seeded noise; no recordings or game samples.',
                'format':'mono signed 16-bit PCM WAV, 22050 Hz', 'sounds':[]}
    for name, samples, loop in (('whistle',whistle(),False),('wheels',wheels(),True)):
        path = args.output/(name+'.wav')
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes(struct.pack('<'+'h'*len(samples),*samples))
        manifest['sounds'].append({'name':'endline/'+name+'.wav',
            'duration_seconds':len(samples)/RATE,'loop_suitable':loop,
            'sample_peak':max(abs(v) for v in samples)/32767,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built original endline/whistle.wav (1.85 s) and endline/wheels.wav (1.6 s loop).')


if __name__ == '__main__':
    main()
