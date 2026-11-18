#!/usr/bin/env python3
"""Build the unmarked Light Bullets clip and its HUD icon."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from build_m16 import atlas_uvs, encode_md2
from build_smg import png_bytes
from m16_geometry import MATERIALS, Mesh

BASE = Path(__file__).resolve().parents[2] / 'baseq2'
CLIP = 'models/items/ammo/light_bullets'
BODY = [(-7, 11.8), (4.2, 11.8), (4.2, 3), (4.9, -4.5),
        (7.1, -12), (5.7, -14), (-3.7, -14), (-6.1, -6), (-7, 2)]
BASEPLATE = [(-4.6, -14.5), (7.2, -14.5), (8, -13.5), (7.1, -11.8), (-5.2, -12.8)]
PALETTE = {'plastic': (61, 79, 47), 'edge': (89, 109, 65), 'dark': (28, 39, 27),
           'grip': (40, 53, 36), 'magazine': (166, 131, 60), 'receiver': (121, 94, 49)}


def clip_model():
    mesh = Mesh()
    mesh.profile('clip_body', BODY, 3.0, 'plastic')
    mesh.profile('floor_plate', BASEPLATE, 3.65, 'grip', 'edge')
    for side in (-1, 1):
        mesh.profile(f'pressed_rib_{side}',
                     [(-2.9, 8.7), (-1.5, 8.7), (-1.4, 1), (.3, -8.7),
                      (-.8, -10.0), (-2.7, .8)],
                     .32, 'edge', 'grip', y=side * 3)
        y = side * 2.35
        mesh.box(f'feed_lip_{side}', (-6.25, y-.55, 10.5), (3.7, y+.55, 12.7), 'dark')
    mesh.tube('visible_round', [(-6.0, 0, 12, 1.55, 1.55), (-1.5, 0, 12, 1.55, 1.55)],
              material='magazine', caps=(True, True))
    mesh.tube('round_tip', [(-1.6, 0, 12, 1.35, 1.35), (1.15, 0, 12, 1.12, 1.12),
                           (2.6, 0, 12, .52, .52)], material='receiver', caps=(True, True))
    geometry = mesh.finish('pickup')
    return encode_md2([geometry['vertices']], [geometry['normals']], geometry['faces'],
                      atlas_uvs(geometry), [CLIP + '/skin.png'], ['idle'])[0]


def clip_skin():
    atlas = Image.new('RGB', (256, 256), PALETTE['plastic'])
    draw = ImageDraw.Draw(atlas)
    for material, color in PALETTE.items():
        tile = MATERIALS.index(material)
        x, y = (tile % 4) * 64, (tile // 4) * 64
        for row in range(64):
            tint = 1.06 - row / 330
            draw.line((x, y+row, x+63, y+row), fill=tuple(round(c*tint) for c in color))
    return png_bytes(atlas)


def clip_icon():
    icon = Image.new('RGBA', (128, 128))
    draw = ImageDraw.Draw(icon)
    profile = lambda points: [(57 + 6*x + z, 65 - 3.6*z) for x, z in points]
    draw.polygon(profile(BODY), fill=(91, 122, 64), outline=(169, 190, 117), width=3)
    draw.line(profile([(-1.8, 9), (-1.7, 1), (.5, -10.8)]), fill=(57, 81, 47), width=5)
    draw.polygon(profile(BASEPLATE), fill=(56, 77, 46), outline=(124, 151, 86), width=3)
    draw.line(profile([(-5.5, 12.6), (2.1, 12.6)]), fill=(203, 159, 72), width=7)
    return png_bytes(icon.resize((32, 32), Image.Resampling.LANCZOS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    verify = parser.parse_args().verify
    outputs = {CLIP + '/tris.md2': clip_model(), CLIP + '/skin.png': clip_skin(),
               'pics/a_light_bullets.png': clip_icon()}
    for name, data in outputs.items():
        path = BASE / name
        if path.is_file() and path.read_bytes() == data:
            continue
        if verify:
            raise ValueError(f'Stale Light Bullets asset: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print('Verified Light Bullets assets' if verify else 'Built Light Bullets assets')


if __name__ == '__main__':
    main()
