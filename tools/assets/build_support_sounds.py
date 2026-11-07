#!/usr/bin/env python3
"""Build original temporary audio for standalone Plastic Platoon event slots.

No sound recordings, game PAKs, or other assets are read. Every WAV is synthesized
from oscillators and a seeded noise generator. These are audible support effects
for testing; authored recordings can replace them in a later sound-design pass.
Code and newly synthesized output: SPDX-License-Identifier: GPL-2.0-or-later.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import wave

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'tools/assets/support-sounds-manifest.json'
RATE = 22050
LICENSE = 'GPL-2.0-or-later'
# Only these documented missing slots may be created. Existing project recordings
# are not source inputs and are never overwritten with different bytes.
SOUNDS = {
    'gunner/death1.wav': ('impact', 0.48, 85, 'Toy heavy enemy destruction'),
    'gunner/gunatck1.wav': ('impact', 0.22, 110, 'Toy heavy enemy weapon report one'),
    'gunner/gunatck2.wav': ('impact', 0.17, 180, 'Toy heavy enemy weapon report two'),
    'gunner/gunatck3.wav': ('impact', 0.24, 145, 'Toy heavy enemy weapon report three'),
    'gunner/gunidle1.wav': ('chatter', 0.36, 190, 'Toy heavy enemy idle electronic chatter'),
    'gunner/gunpain1.wav': ('chatter', 0.21, 320, 'Toy heavy enemy damage alert one'),
    'gunner/gunpain2.wav': ('chatter', 0.27, 270, 'Toy heavy enemy damage alert two'),
    'gunner/gunsrch1.wav': ('chatter', 0.42, 280, 'Toy heavy enemy search electronic chatter'),
    'gunner/sight1.wav': ('alert', 0.3, 620, 'Toy heavy enemy sight alert'),
    'misc/keytry.wav': ('tone_down', 0.17, 430, 'Locked interaction denied chime'),
    'misc/keyuse.wav': ('tone', 0.21, 620, 'Key interaction accepted chime'),
    'switches/butn2.wav': ('impact_tone', 0.13, 480, 'Mission switch press click'),
    'tank/death.wav': ('energy_hit', 0.8, 70, 'Toy tank destruction burst'),
    'tank/sight1.wav': ('alert', 0.44, 360, 'Toy tank target acquisition alert'),
    'tank/step.wav': ('impact', 0.2, 65, 'Toy tank tread / step impact'),
    'tank/tnkatck1.wav': ('impact', 0.24, 95, 'Toy tank attack mechanical report one'),
    'tank/tnkatck3.wav': ('impact', 0.32, 80, 'Toy tank cannon report'),
    'tank/tnkatck4.wav': ('impact', 0.26, 110, 'Toy tank attack mechanical report four'),
    'tank/tnkatck5.wav': ('impact', 0.28, 120, 'Toy tank attack mechanical report five'),
    'tank/tnkatk2a.wav': ('impact', 0.14, 150, 'Toy tank machinegun report A'),
    'tank/tnkatk2b.wav': ('impact', 0.14, 160, 'Toy tank machinegun report B'),
    'tank/tnkatk2c.wav': ('impact', 0.14, 170, 'Toy tank machinegun report C'),
    'tank/tnkatk2d.wav': ('impact', 0.14, 155, 'Toy tank machinegun report D'),
    'tank/tnkatk2e.wav': ('impact', 0.14, 165, 'Toy tank machinegun report E'),
    'tank/tnkdeth2.wav': ('impact', 0.55, 58, 'Toy tank debris and hull impact'),
    'tank/tnkidle1.wav': ('buzz', 1.0, 60, 'Toy tank low motor idle loop'),
    'tank/tnkpain2.wav': ('chatter', 0.28, 210, 'Toy tank hull damage signal'),
    'infantry/inflies1.wav': ('buzz', 1.0, 95, 'Quiet synthetic insect / mechanical idle loop'),
    'items/damage.wav': ('tone', .42, 330, 'Damage-powerup ascending signal'),
    'items/l_health.wav': ('tone', .25, 660, 'Large health pickup rising chime'),
    'items/m_health.wav': ('tone', .36, 880, 'Mega health pickup rising chime'),
    'items/n_health.wav': ('tone', .19, 550, 'Normal health pickup rising chime'),
    'items/pkup.wav': ('tone', .18, 700, 'Generic item pickup chirp'),
    'items/protect.wav': ('tone', .44, 440, 'Protection powerup signal'),
    'items/protect4.wav': ('tone_down', .32, 880, 'Protection powerup expiration signal'),
    'items/respawn1.wav': ('tone', .34, 370, 'Item materialization signal'),
    'items/s_health.wav': ('tone', .14, 440, 'Small health pickup chirp'),
    'misc/ar1_pkup.wav': ('impact_tone', .21, 470, 'Light armor pickup plastic click and chime'),
    'misc/ar2_pkup.wav': ('impact_tone', .28, 350, 'Heavy armor pickup plastic click and chime'),
    'misc/h2ohit1.wav': ('water', .38, 180, 'Water splash / landing noise'),
    'misc/lasfly.wav': ('energy', 1.0, 240, 'Toy energy projectile flight loop'),
    'misc/menu1.wav': ('tone', .075, 580, 'Menu move tick'),
    'misc/menu2.wav': ('tone', .12, 760, 'Menu confirm chirp'),
    'misc/menu3.wav': ('tone_down', .10, 640, 'Menu back chirp'),
    'misc/pc_up.wav': ('tone', .22, 830, 'Objective / computer interaction chime'),
    'misc/secret.wav': ('tone', .45, 990, 'Secret discovery ascending chime'),
    'misc/talk1.wav': ('tone', .10, 520, 'Chat notification beep'),
    'misc/udeath.wav': ('impact', .44, 95, 'Plastic shatter / gib event'),
    'player/fall1.wav': ('impact', .22, 100, 'Light fall landing impact'),
    'player/fall2.wav': ('impact', .33, 75, 'Heavy fall landing impact'),
    'player/u_breath1.wav': ('breath', .65, 150, 'Underwater breathing wind inhale'),
    'player/u_breath2.wav': ('breath', .75, 130, 'Underwater breathing wind exhale'),
    'weapons/bfg__l1a.wav': ('energy', 1.0, 110, 'Large toy energy weapon flight loop'),
    'weapons/bfg__x1b.wav': ('energy_hit', .65, 120, 'Large toy energy weapon impact'),
    'weapons/disrupthit.wav': ('energy_hit', .27, 740, 'Toy disruptor impact'),
    'weapons/hyprbd1a.wav': ('tone_down', .30, 980, 'Toy energy weapon spin down'),
    'weapons/hyprbl1a.wav': ('energy', 1.0, 300, 'Toy energy weapon operating loop'),
    'weapons/hyprbu1a.wav': ('tone', .28, 420, 'Toy energy weapon spin up'),
    'weapons/lashit.wav': ('energy_hit', .17, 940, 'Toy laser impact'),
    'weapons/tesla.wav': ('energy', 1.0, 180, 'Toy electrical beam loop'),
    'world/klaxon1.wav': ('klaxon', 1.0, 540, 'Mission alarm alternating electronic klaxon'),
    'world/land.wav': ('impact', .15, 120, 'World landing thud'),
    'world/ric1.wav': ('ricochet', .16, 2250, 'Plastic ricochet variant one'),
    'world/ric2.wav': ('ricochet', .19, 2600, 'Plastic ricochet variant two'),
    'world/ric3.wav': ('ricochet', .14, 1900, 'Plastic ricochet variant three'),
    'world/spark5.wav': ('spark', .16, 1800, 'Electrical spark variant one'),
    'world/spark6.wav': ('spark', .21, 2100, 'Electrical spark variant two'),
    'world/spark7.wav': ('spark', .13, 1550, 'Electrical spark variant three'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def synthesize(name, spec):
    """Return deterministic mono PCM16 WAV bytes without external sound inputs."""
    kind, duration, frequency, _ = spec
    frames = round(RATE * duration)
    seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], 'little')
    filtered = 0.0
    previous_noise = 0.0
    samples = []
    loop = kind in ('buzz', 'energy', 'rocket', 'klaxon')
    for i in range(frames):
        t = i / RATE
        u = i / frames
        seed = (1664525 * seed + 1013904223) & 0xffffffff
        noise = seed / 2147483648 - 1
        filtered = .88 * filtered + .12 * noise
        tone = math.sin(2 * math.pi * frequency * t)
        # Sustained effects use integer-frequency partials, giving a periodic
        # sample and avoiding a noise discontinuity at each loop boundary.
        periodic = sum(math.sin(2 * math.pi * (frequency * j + j*j) * t + j)
                       / j for j in range(1, 7)) / 2.45 if loop else 0
        if kind in ('tone', 'tone_down', 'impact_tone'):
            part = min(2, int(u * 3))
            ratio = (1, 1.25, 1.5)[part]
            if kind == 'tone_down':
                ratio = (1.5, 1.25, 1)[part]
            phase = (u * 3) % 1
            signal = .32 * math.sin(math.pi * phase) * math.sin(2*math.pi*frequency*ratio*t)
            if kind == 'impact_tone':
                signal += .25 * noise * math.exp(-45*t)
        elif kind == 'impact':
            signal = (.55 * filtered + .30 * tone) * math.exp(-12*u)
            signal += .16 * noise * math.exp(-90*t)
        elif kind == 'ricochet':
            phase = 2*math.pi*(frequency*t - .42*frequency*t*t/duration)
            signal = .33 * math.sin(phase) * math.exp(-5*u) + .12*noise*math.exp(-70*t)
        elif kind == 'spark':
            signal = .27 * (noise - previous_noise) * math.exp(-5*u)
            signal += .12 * tone * math.exp(-8*u)
        elif kind in ('breath', 'water'):
            swell = math.sin(math.pi*u) ** .65
            signal = (.85*filtered + .10*noise) * swell
            if kind == 'water':
                signal += .12*math.sin(2*math.pi*(frequency*t+90*t*t))*math.exp(-4*u)
        elif kind in ('chatter', 'alert'):
            pulses = 3 if kind == 'chatter' else 2
            phase = (u*pulses) % 1
            note = int(u*pulses)
            signal = .25 * math.sin(math.pi*phase)**2 * math.sin(2*math.pi*(frequency+90*note)*t)
            signal += .035 * noise * math.sin(math.pi*phase)**2
        elif kind == 'energy_hit':
            signal = (.32*noise + .28*math.sin(2*math.pi*(frequency*t+220*t*t))) * math.exp(-5*u)
        elif kind == 'rocket':
            signal = .28 * periodic + .10 * math.sin(2*math.pi*frequency*t)
        elif kind == 'buzz':
            signal = .12 * periodic * (.8 + .2*math.sin(2*math.pi*5*t))
        elif kind == 'energy':
            signal = .20 * periodic + .08 * math.sin(2*math.pi*2*frequency*t)
        elif kind == 'klaxon':
            # Smoothly modulate between two pitches with a periodic FM phase.
            signal = .24 * math.sin(2*math.pi*frequency*t + 45*math.sin(2*math.pi*2*t))
        else:
            raise ValueError(f'unknown procedural role: {kind}')
        if not loop:
            signal *= min(1.0, t/.004, (frames-1-i)/(RATE*.012))
        # Comfortable headroom, with a hard guard against sample overflow.
        samples.append(max(-28000, min(28000, round(signal*32767))))
        previous_noise = noise
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(struct.pack('<' + str(frames) + 'h', *samples))
    return output.getvalue()


def expected_outputs():
    files = {}
    for name, spec in sorted(SOUNDS.items()):
        files['sound/' + name] = synthesize(name, spec)
    return files


def manifest_for(files):
    return {
        'schema': 1,
        'purpose': 'Original temporary support sounds for standalone runtime testing.',
        'source': 'Deterministic oscillators and seeded noise in tools/assets/build_support_sounds.py; no sampled or external sound input.',
        'license': LICENSE,
        'quality_note': 'Audible procedural replacements; these are not final voice acting or authored sound-design recordings.',
        'sample_rate_hz': RATE,
        'channels': 1,
        'sample_width_bytes': 2,
        'files': [dict(path=name, role=SOUNDS[name[6:]][3], synthesis=SOUNDS[name[6:]][0],
                       duration_seconds=round((len(data)-44)/(RATE*2), 6),
                       loop=SOUNDS[name[6:]][0] in ('buzz', 'energy', 'rocket', 'klaxon'),
                       bytes=len(data), sha256=sha(data), license=LICENSE)
                  for name, data in sorted(files.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='check fixed generated bytes and manifest without writing')
    args = parser.parse_args()
    files = expected_outputs()
    report = manifest_for(files)
    # Preflight every existing file so a collision cannot cause a partial build.
    for name, data in files.items():
        path = ROOT / 'baseq2' / name
        if path.exists() and (not path.is_file() or path.read_bytes() != data):
            raise ValueError(f'refusing to overwrite unexpected project sound: {path}')
        if args.verify and not path.is_file():
            raise ValueError(f'missing procedural support sound: {path}')
    if args.verify:
        if not MANIFEST.is_file() or json.loads(MANIFEST.read_text()) != report:
            raise ValueError('procedural support sound manifest differs from generated content')
    else:
        for name, data in files.items():
            path = ROOT / 'baseq2' / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        MANIFEST.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{"Verified" if args.verify else "Generated"} {len(files)} original mono PCM16 support effects ({sum(map(len, files.values())):,} bytes).')


if __name__ == '__main__':
    main()
