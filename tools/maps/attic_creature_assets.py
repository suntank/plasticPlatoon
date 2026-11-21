"""Original Attic sound design and the Melted Soldier's derived MD2."""
import io
from math import exp, pi, sin, tanh, tau
import random
import struct
import wave

from PIL import Image, ImageDraw, ImageFilter

from build_endline import BASE


def melted_model():
    original = (BASE / 'models/monsters/soldier/tall/tris.md2').read_bytes()
    header = struct.unpack_from('<17i', original)
    _, _, _, _, stride, skins, verts, _, _, _, frames, skin_offset, _, _, start, _, _ = header
    model = bytearray(original)
    for index in range(skins):
        struct.pack_into('<64s', model, skin_offset + index * 64, b'models/monsters/melted/skin.png')
    swing = (0, .13, .58, 1, .65, .35, .15, .07, 0)
    for frame in range(frames):
        attack = 30 <= frame <= 38
        source_frame = frame - 30 if attack else frame
        offset = start + stride * source_frame
        current = start + stride * frame
        values = struct.unpack_from('<6f', original, offset)
        data = original[offset + 40:offset + 40 + 4 * verts]
        new = []
        for index in range(verts):
            x, y, z = (data[index * 4 + axis] * values[axis] + values[3 + axis]
                       for axis in range(3))
            height = max(z + 24, 0)
            head = max(z - 19, 0)
            shoulder = exp(-((z - 13) / 12)**2)
            x = x * .91 + head * .24
            y = y * (.79 - .08 * shoulder) + head * .21
            z = -24 + height * 1.27 + head * .16 - max(y, 0) * .35 * shoulder
            if attack:
                amount = swing[frame - 30] * max(x - 7, 0)
                x += amount * 1.35
                y -= amount * .68
                z += amount * .3
            new.append((x, y, z))
        low = [min(point[axis] for point in new) for axis in range(3)]
        scale = [max(1e-6, (max(point[axis] for point in new) - low[axis]) / 255)
                 for axis in range(3)]
        struct.pack_into('<6f', model, current, *scale, *low)
        for index, point in enumerate(new):
            quantized = [min(255, max(0, round((point[axis] - low[axis]) / scale[axis])))
                         for axis in range(3)]
            quantized.append(data[index * 4 + 3])
            struct.pack_into('<4B', model, current + 40 + index * 4, *quantized)
    return bytes(model)


def melted_skin():
    with Image.open(BASE / 'models/monsters/soldier/skin.png') as original:
        base = original.convert('L')
    rng = random.Random(92)
    w, h = base.size
    mottling = Image.new('L', (w//8, h//8))
    mottling.putdata([rng.randrange(256) for _ in range(mottling.width * mottling.height)])
    mottling = mottling.resize((w,h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    skin = Image.new('RGB', (w,h))
    skin.putdata([(max(8, round(v * .89 + n * .25 + 9)),
                   max(7, round(v * .73 + n * .18 + 5)),
                   max(6, round(v * .68 + n * .16 + 5)))
                  for v,n in zip(base.getdata(), mottling.getdata())])
    draw = ImageDraw.Draw(skin)
    for _ in range(112):
        x,y = rng.randrange(w),rng.randrange(h)
        length = rng.randrange(4,27)
        points = [(x, y), (x+rng.randrange(-3,4), y+length//2), (x+2, y+length)]
        draw.line(points, fill=rng.choice(((109,74,47),(32,25,22),(126,100,74))))
    output = io.BytesIO()
    skin.save(output, format='PNG', optimize=True)
    return output.getvalue()


RATE = 22050


def sound(kind, duration):
    rng = random.Random(721)
    low = mid = 0
    samples = []
    for i in range(round(RATE * duration)):
        t = i / RATE
        phase = t / duration
        noise = rng.uniform(-1, 1)
        low += (noise - low) * .03
        mid += (noise - mid) * .25
        rasp = mid - low
        if kind == 'hunt':
            # Two shifting throat tones, with heel strikes carried on the same loop.
            stride = min((t - .10) % .6, (t - .39) % .6)
            foot = exp(-36 * stride) * (.32*sin(tau * 72 * stride) + .8 * mid)
            breathing = .56 + .35*sin(tau*phase*2 - .8) + .09*sin(tau*phase*7)
            throat = tanh(2.5*sin(tau*69.1666667*t + .67*sin(tau*phase*3)))
            voice = breathing * (.32*throat + .17*sin(tau*98.3333333*t) + 1.1*rasp)
            sample = .58 * (foot + voice)
            envelope = min(1, t*125, (duration-t)*125)
        elif kind == 'ballast':
            envelope = min(1, t*150, (duration-t)*150)
            buzz = .7 + .20*sin(tau*phase*3) + .07*sin(tau*phase*13)
            sample = buzz * (.09*sin(tau*120*t) + .09*sin(tau*240*t) +
                             .045*sin(tau*360*t) + .025*sin(tau*720*t) + .18*rasp)
        else:
            envelope = min(1, t*45, (duration-t)*10)
            if kind == 'scrape':
                pulse = (.16 + .5*sin(pi*phase)**2) * (.65 + .35*sin(tau*t*4.2)**2)
                sample = pulse * (1.7*rasp + .19*sin(tau*(118*t - 8*t*t) + 2*low))
            elif kind == 'swipe':
                rush = exp(-8*(phase-.25)**2)
                overtone = sin(tau*(166*t - 79*t*t) + 6*low)
                sample = rush * (.33*overtone + .19*sin(tau*82*t) + .85*rasp)
            elif kind == 'impact':
                sample = exp(-8*phase) * (1.45*rasp + .29*sin(tau*(171*t - 94*t*t)))
            elif kind == 'slag':
                sample = exp(-1.75*phase) * (1.05*(noise-mid) + .8*rasp + .37*sin(tau*(89*t - 19*t*t)))
            else:
                raise ValueError(kind)
        samples.append(round(26000 * tanh(sample * envelope)))
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setparams((1, 2, RATE, len(samples), 'NONE', ''))
        writer.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    return output.getvalue()


def creature_assets():
    assets = {'models/monsters/melted/tris.md2': melted_model(),
              'models/monsters/melted/skin.png': melted_skin()}
    for name, duration in (('hunt',1.2), ('impact',.36), ('swipe',.74),
                           ('slag',1.7), ('scrape',1.6), ('ballast',1.4)):
        assets[f'sound/attic/{name}.wav'] = sound(name, duration)
    return assets
