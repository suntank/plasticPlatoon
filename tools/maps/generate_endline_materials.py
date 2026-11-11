#!/usr/bin/env python3
"""Build original Operation End of the Line railway/garage materials.

All pixels are generated here from deterministic shapes and noise. No external
image, font, Quake II palette, texture, or other game-data input is used. The
small block lettering is the project's original alphabet from Sandkeep's
generator; WALs use the original Plastic Platoon palette. GPL-2.0-or-later.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import random
from pathlib import Path
import struct

from PIL import Image, ImageDraw

from platoon_palette import PROJECT_PALETTE_SHA256, load_palette, quantize_opaque

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'baseq2/textures/endline'
MANIFEST = ROOT / 'tools/maps/endline-materials.json'
CREAM = (238, 221, 165)
INK = (29, 38, 39)
RED = (170, 44, 35)
GREEN = (65, 160, 85)


def text(draw, center_x, y, value, scale, color):
    width = (6 * len(value) - 1) * scale
    left = int(center_x - width / 2)
    for index, char in enumerate(value.upper()):
        for row, pattern in enumerate(FONT[char]):
            for col, bit in enumerate(pattern):
                if bit == '1':
                    x0 = left + (index * 6 + col) * scale
                    y0 = y + row * scale
                    draw.rectangle((x0, y0, x0+scale-1, y0+scale-1), fill=color)


# Read only the existing original alphabet literal, without importing that
# generator's optional NumPy dependency or executing any of its code.
_font_node = next(node.value for node in ast.parse(
    (ROOT/'tools/maps/generate_sandkeep_materials.py').read_text()).body
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FONT'
                                          for t in node.targets))
FONT = {ast.literal_eval(k): ast.literal_eval(v) for k,v in zip(_font_node.keys, _font_node.values)
        if ast.literal_eval(k) != ' '}
FONT[' '] = ['00000'] * 7


def noise(width, height, seed, cells=8):
    """Return a deterministic periodic noise sampler."""
    rng = random.Random(seed)
    lattice = [[rng.uniform(-1, 1) for _ in range(cells)] for _ in range(cells)]
    def sample(x, y):
        u, v = x*cells/width, y*cells/height
        ix, iy = int(u), int(v)
        fx, fy = u-ix, v-iy
        fx, fy = fx*fx*(3-2*fx), fy*fy*(3-2*fy)
        return ((lattice[iy][ix]*(1-fx)+lattice[iy][(ix+1)%cells]*fx)*(1-fy)
                +(lattice[(iy+1)%cells][ix]*(1-fx)+lattice[(iy+1)%cells][(ix+1)%cells]*fx)*fy)
    return sample


def painted(size, color, sampler):
    w, h = size
    im = Image.new('RGB', size)
    im.putdata([tuple(max(0, min(255, int(c+sampler(x,y)))) for c in color)
                for y in range(h) for x in range(w)])
    return im


def surface(color, size=(128, 128), seed=71, amplitude=5):
    w, h = size
    rng = random.Random(seed)
    shade = noise(w, h, seed)
    return painted(size, color, lambda x,y: shade(x,y)*amplitude+rng.gauss(0,.65))


def bolt(d, x, y, size=3):
    d.ellipse((x-size-1, y-size-1, x+size+1, y+size+1), fill=(25, 31, 31))
    d.ellipse((x-size, y-size, x+size, y+size), fill=(142, 153, 145))
    d.line((x-size+1, y, x+size-1, y), fill=(47, 56, 54))
    d.point((x-1, y-1), fill=(222, 223, 193))


def tile_materials():
    result = {}
    size = 256
    rng = random.Random(7142)
    n1, n2 = noise(size,size,18,4), noise(size,size,52,15)
    concrete = painted((size,size), (111,113,106),
                       lambda x,y: n1(x,y)*7+n2(x,y)*4+rng.gauss(0,1.6))
    d = ImageDraw.Draw(concrete)
    for _ in range(1900):
        px, py, tone = rng.randrange(size), rng.randrange(size), rng.randrange(79,145)
        d.point((px,py), fill=(tone,tone+1,tone-5))
    for _ in range(42):
        px, py = rng.randrange(size), rng.randrange(size)
        radius, tone = rng.randrange(1,3), rng.randrange(84,130)
        for dx in (-size,0,size):
            for dy in (-size,0,size):
                d.ellipse((px-radius+dx,py-radius+dy,px+radius+dx,py+radius+dy),
                          fill=(tone,tone+1,tone-4))
    result['concrete'] = concrete

    cardboard = surface((164,124,76), (256,256), 27, 5)
    d = ImageDraw.Draw(cardboard)
    for _ in range(1350):
        px, py = rng.randrange(256), rng.randrange(256)
        length, tone = rng.randrange(1,7), rng.randrange(-12,13)
        for dx in (-256,0,256):
            d.line((px+dx,py,px+length+dx,py), fill=(164+tone,124+tone,76+tone))
    result['cardboard'] = cardboard
    result['corrugation'] = painted((128,128), (140,103,62),
        lambda x,y: math.cos(x*math.tau/16)*28+math.sin(y*math.tau/128)*2)

    red = surface((169,43,34), seed=5, amplitude=2)
    d = ImageDraw.Draw(red)
    d.rectangle((2,2,125,125), outline=(115,29,24), width=2)
    d.line((4,4,123,4), fill=(213,83,60), width=2)
    d.line((4,4,4,123), fill=(194,65,47))
    for px in (10,117):
        for py in (10,117):
            bolt(d,px,py,2)
    result['loco_red'] = red

    blue = surface((40,78,99), seed=32, amplitude=2)
    d = ImageDraw.Draw(blue)
    d.line((0,2,127,2), fill=(69,108,127), width=2)
    d.line((0,125,127,125), fill=(21,45,58), width=3)
    result['toolbox_blue'] = blue
    result['rail_metal'] = surface((77,86,89), seed=31, amplitude=3)
    d = ImageDraw.Draw(result['rail_metal'])
    for _ in range(60):
        py,start,length,tone = rng.randrange(128),rng.randrange(128),rng.randrange(8,50),rng.randrange(-9,10)
        for dx in (-128,0,128):
            d.line((start+dx,py,start+length+dx,py), fill=(77+tone,86+tone,89+tone))
    result['rubber'] = painted((128,128),(32,36,35),
        lambda x,y: 5 if abs((x+y)%32-16)<2 or abs((x-y)%32-16)<2 else 0)

    n1,n2 = noise(256,128,671,4),noise(256,128,151,8)
    wood = painted((256,128),(151,116,72),
        lambda x,y: math.sin((y+n1(x,y)*4)*.58)*5+math.sin((y+n1(x,y)*4)*1.8)*2+n2(x,y)*9)
    d = ImageDraw.Draw(wood)
    d.line((0,0,255,0),fill=(77,59,38),width=2)
    d.line((0,127,255,127),fill=(77,59,38),width=2)
    d.line((0,3,255,3),fill=(184,148,94))
    result['sleeper_wood'] = wood
    hazard = Image.new('RGB',(128,128))
    hazard.putdata([(224,173,52) if (x+y)%64<32 else (34,41,42)
                    for y in range(128) for x in range(128)])
    result['hazard'] = hazard
    return result


def signal(active):
    im = surface((25, 32, 34), (64, 64), 991, 1)
    d = ImageDraw.Draw(im)
    color = (73, 211, 111) if active else (236, 61, 42)
    dark = (32, 82, 50) if active else (92, 32, 28)
    d.ellipse((3, 3, 60, 60), fill=(102, 112, 105))
    d.ellipse((5, 5, 58, 58), fill=(13, 19, 20))
    d.ellipse((9, 9, 54, 54), fill=dark)
    d.ellipse((11, 11, 52, 52), fill=color)
    for yy in range(15, 50, 5):
        half = int(math.sqrt(max(0, 19*19-(yy-32)**2)))
        d.line((32-half, yy, 32+half, yy), fill=dark)
    d.arc((13, 12, 48, 47), 190, 280, fill=(253, 236, 180), width=3)
    return im


def sign(lines, accent=CREAM, icon=None):
    im = surface(INK, (256, 128), 72, 1)
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, 254, 126), fill=accent)
    d.rectangle((5, 5, 250, 122), fill=INK)
    for bx in (12, 243):
        for by in (12, 115):
            bolt(d, bx, by, 2)
    if icon == 'cross':
        d.rectangle((115, 17, 140, 67), fill=accent)
        d.rectangle((103, 29, 152, 54), fill=accent)
    elif icon == 'shells':
        for bx in (102, 136):
            d.rectangle((bx, 20, bx+20, 55), fill=(174, 52, 38))
            d.rectangle((bx-1, 55, bx+21, 66), fill=(213, 173, 69))
    elif icon in ('up', 'down'):
        d.line((70, 65, 70, 30 if icon == 'up' else 90), fill=accent, width=9)
        if icon == 'up':
            d.polygon(((70, 19), (52, 40), (88, 40)), fill=accent)
        else:
            d.polygon(((70, 101), (52, 80), (88, 80)), fill=accent)
    if icon in ('up', 'down'):
        for i, line in enumerate(lines):
            text(d, 163, 37+i*30, line, 2, accent)
    elif icon:
        for i, line in enumerate(lines):
            text(d, 128, 82+i*20, line, 2, accent)
    else:
        scale = min(3, 218 // max(1, max(len(v) * 6 - 1 for v in lines)))
        block_height = len(lines) * 7 * scale + (len(lines)-1)*13
        yy = (128-block_height)//2
        for line in lines:
            text(d, 128, yy, line, scale, accent)
            yy += scale*7 + 13
    return im


def switch(label, active, command):
    im = surface((46, 58, 59), (128, 64), 913, 1)
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, 126, 62), outline=(164, 167, 143), width=2)
    d.rectangle((5, 5, 122, 24), fill=INK)
    text(d, 64, 11, label, 1, CREAM)
    d.rectangle((28, 30, 99, 57), fill=(16, 23, 23))
    d.rectangle((31, 32, 96, 54), fill=GREEN if active else RED)
    d.line((32, 33, 95, 33), fill=(145, 221, 136) if active else (224, 108, 71), width=2)
    text(d, 64, 41, 'GO' if active else command, 1, CREAM)
    for bx in (10, 117):
        for by in (10, 53):
            bolt(d, bx, by, 2)
    return im


def make_materials():
    result = tile_materials()
    result.update(signal_red=signal(False), signal_green=signal(True))
    for prefix, label, command in [('signal_switch', 'DIVERT TRAIN', 'PUSH'),
                                   ('depart_switch', 'DEPARTURE', 'SHOOT')]:
        for suffix, active in [('', False), ('_idle', False), ('_on', True), ('_on_alt', True)]:
            result[prefix+suffix] = switch(label, active, command)
    result['sign_signal'] = sign(['SIGNAL', 'CABIN'])
    result['sign_board'] = sign(['BOARD', 'TRAIN'], (150, 204, 172))
    result['sign_double_barrel'] = sign(['DOUBLE', 'BARREL', 'CLOSE RANGE'], (237, 185, 74))
    result['sign_upper'] = sign(['UPPER', 'WALK'], icon='up')
    result['sign_lower'] = sign(['LOWER', 'YARD'], (150, 204, 172), icon='down')
    result['sign_ammo'] = sign(['AMMUNITION'], icon='shells')
    result['sign_medic'] = sign(['MEDIC'], (150, 204, 172), icon='cross')
    result['sign_freight'] = sign(['PLATOON RAIL', 'FREIGHT 07'])
    result['sign_exit'] = sign(['BACKYARD', 'EXIT'], (150, 204, 172))
    result['sign_mission'] = sign(['OP END OF LINE', 'FOLLOW FREIGHT', 'BOARD THE TRAIN'])
    # Cardboard label intentionally resembles a printed parcel stencil, not a
    # modern floating interface. It can mark the insertion box or supply crates.
    label = result['cardboard'].resize((256, 128))
    d = ImageDraw.Draw(label)
    d.rectangle((8, 8, 247, 119), outline=(72, 63, 42), width=3)
    text(d, 128, 25, 'PLASTIC PLATOON', 2, (62, 59, 38))
    text(d, 128, 52, 'SUPPLY DIVISION', 2, (62, 59, 38))
    text(d, 128, 88, 'HANDLE WITH CARE', 1, (62, 59, 38))
    result['shipping_label'] = label
    return result


def write_wal(path, name, im, anim='', flags=0, value=0):
    palette = load_palette()
    w, h = im.size
    assert min(w, h) >= 8 and w & (w-1) == 0 and h & (h-1) == 0
    levels = [quantize_opaque(im.resize((w >> i, h >> i), Image.Resampling.BOX), palette).tobytes()
              for i in range(4)]
    offsets, offset = [], 100
    for level in levels:
        offsets.append(offset)
        offset += len(level)
    assert len(name.encode()) < 32 and len(anim.encode()) < 32
    path.write_bytes(struct.pack('<32sII4I32siii', name.encode(), w, h, *offsets,
                                 anim.encode(), flags, 0, value) + b''.join(levels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--contact-sheet', type=Path, default=ROOT/'build/maps/pp_endline/materials.png')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    materials = make_materials()
    chains = {}
    for prefix in ('signal_switch', 'depart_switch'):
        names = [prefix+s for s in ('', '_idle', '_on', '_on_alt')]
        chains.update({name: 'endline/'+names[(i+1)%4] for i, name in enumerate(names)})
    manifest = {'license': 'GPL-2.0-or-later', 'generator': 'tools/maps/generate_endline_materials.py',
                'source': 'Original deterministic procedural artwork; no external images or game data.',
                'palette_source': 'tools/assets/build_bootstrap.py:PALETTE',
                'palette_sha256': PROJECT_PALETTE_SHA256,
                'lettering_source': 'tools/maps/generate_sandkeep_materials.py:FONT', 'materials': []}
    for name, im in materials.items():
        png, wal = args.output/(name+'.png'), args.output/(name+'.wal')
        im.save(png)
        glow = name in ('signal_red', 'signal_green')
        write_wal(wal, 'endline/'+name, im, chains.get(name, ''), 1 if glow else 0, 180 if glow else 0)
        manifest['materials'].append({'name': 'endline/'+name, 'dimensions': list(im.size),
                                      'animation_next': chains.get(name),
                                      'surface_light': 180 if glow else 0,
                                      'png_sha256': hashlib.sha256(png.read_bytes()).hexdigest(),
                                      'wal_sha256': hashlib.sha256(wal.read_bytes()).hexdigest()})
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2)+'\n')
    # Non-runtime contact sheet stays in ignored build output.
    visible = [(name, im) for name, im in materials.items() if not name.endswith(('_idle', '_on_alt'))]
    columns, cellw, cellh = 4, 280, 180
    sheet = Image.new('RGB', (columns*cellw, math.ceil(len(visible)/columns)*cellh), (26, 31, 32))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(visible):
        px, py = (i%columns)*cellw, (i//columns)*cellh
        thumb = im.copy()
        thumb.thumbnail((256, 140))
        sheet.paste(thumb, (px+(cellw-thumb.width)//2, py+8+(140-thumb.height)//2))
        d.text((px+12, py+153), name, fill=CREAM)
    args.contact_sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.contact_sheet)
    print(f'Built {len(materials)} original Endline PNG/WAL material pairs.')
    print(args.contact_sheet)


if __name__ == '__main__':
    main()
