#!/usr/bin/env python3
"""Build Thunderhead's original drum-fed shotgun and authored view poses."""

import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from build_m16 import texture_bytes
from build_smg import animated_model, encode, encode_held_model, png_bytes
from m16_geometry import Mesh, add_hands

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
PICKUP = 'models/weapons/g_thunderhead'
VIEW = 'models/weapons/v_thunderhead'
VIEW_SCALE = .62
VIEW_OFFSET = np.array((-8.0, -7.6, -9.1))
MUZZLE = (86, 0, 0)
SIGHT_LINE = (31, 0, 7.0)

POSES = [
    ('raise1', -15, -2.3, -4.8, 0), ('raise2', -8, -1.2, -2.3, 0),
    ('raise3', -3, -.5, -1.0, 0), ('raise4', 0, 0, 0, 0),
    ('battery', 0, 0, 0, 0), ('fire', 1.3, -.5, .08, 4.0),
    ('recover', .35, -.15, 0, 1.3),
    ('idle1', 0, 0, 0, 0), ('idle2', .13, 0, .05, 0),
    ('idle3', .18, 0, .08, 0), ('idle4', .12, 0, .05, 0),
    ('idle5', 0, 0, 0, 0), ('idle6', -.12, 0, -.04, 0),
    ('idle7', -.15, 0, -.06, 0), ('idle8', -.08, 0, -.03, 0),
    ('lower1', -3, -.5, -.8, 0), ('lower2', -7, -1.0, -2.4, 0),
    ('lower3', -11, -1.6, -3.7, 0), ('lower4', -16, -2.4, -5.0, 0),
]


def geometry(view):
    mesh = Mesh()
    mesh.tube('stock', [(4, 0, -4.9, 2.2, 5.0), (8, 0, -4.4, 2.5, 5.4),
                        (22, 0, -1.0, 1.7, 2.0), (30, 0, -.3, 1.8, 2.2)],
              material='plastic', caps=(True, True))
    mesh.tube('butt_pad', [(2, 0, -5.0, 2.15, 4.95), (4.5, 0, -4.9, 2.28, 5.10)],
              material='dark', caps=(True, True))
    mesh.tube('heavy_receiver', [(25, 0, -.4, 2.15, 3.8), (30, 0, 0, 3.6, 4.7),
                                 (54, 0, 0, 3.6, 4.7), (58, 0, 0, 2.85, 3.65)],
              material='receiver', caps=(True, True))
    mesh.profile('grip', [(26.8, -13.2), (30, -4.0), (36, -4.1), (32.8, -14.8),
                          (28.5, -15.0)], 1.76, 'grip')
    mesh.ring_profile('guard', [(34, -4), (44, -4), (43.7, -8), (41, -9.4), (33.6, -8.8)],
                      [(35.5, -5.2), (42.4, -5.2), (42.2, -7.2), (40.5, -8), (35, -7.5)], .74)
    mesh.box('drum_neck', (44, -2.65, -8.0), (53.2, 2.65, -3.8), 'grip')
    # Rotate the molded drum and its raised end caps to face either side.
    first = len(mesh.vertices)
    mesh.tube('drum', [(-4.7, 0, 0, 7.45, 7.45), (-3.4, 0, 0, 8.15, 8.15),
                       (3.4, 0, 0, 8.15, 8.15), (4.7, 0, 0, 7.45, 7.45)],
              sides=12, material='magazine', caps=(True, True), end_material='dark')
    for center in (-4.9, 4.9):
        mesh.tube(f'drum_cap_{center}', [(center-.52, 0, 0, 4.8, 4.8),
                                         (center+.52, 0, 0, 4.8, 4.8)],
                  sides=8, material='edge', caps=(True, True))
    for point in mesh.vertices[first:]:
        x, y, z = point
        point[:] = [49-y, x, z-12.5]

    mesh.tube('fixed_fore_end', [(54.2, 0, -.30, 3.05, 3.25), (57, 0, -.3, 3.62, 3.73),
                                 (70, 0, -.3, 3.25, 3.4), (74, 0, -.24, 2.85, 2.9)],
              material='handguard', caps=(True, True))
    mesh.tube('barrel', [(73.5, 0, 0, 1.55, 1.55), (82.4, 0, 0, 1.55, 1.55)],
              material='dark')
    mesh.tube('muzzle_rim', [(81.5, 0, 0, 2.30, 2.30), (85.3, 0, 0, 2.30, 2.30),
                             (MUZZLE[0], 0, 0, 1.95, 1.95)],
              material='edge', caps=(True, True), end_material='bore')
    mesh.box('sight_base', (29, -1.75, 4), (33, 1.75, 6.0), 'dark')
    for side in (-1, 1):
        y = side*1.20
        mesh.box(f'rear_sight_{side}', (29.8, y-.32, 5.9), (32.4, y+.32, 7.7), 'edge')
    mesh.profile('front_ramp', [(69, 2.1), (77.2, 1.5), (77, 5.4), (72.4, 5.4)],
                 1.25, 'dark', 'edge')
    mesh.box('front_post', (73.7, -.38, 5.2), (74.9, .38, SIGHT_LINE[2]), 'edge')
    if view:
        mesh.box('ejection_port', (40.5, -3.53, .35), (53, -3.25, 2.80), 'bore')
        mesh.box('bolt', (47, -3.82, .55), (52, -3.46, 2.58), 'dark')
        mesh.box('charging_tab', (48.5, -4.42, 1.1), (50.4, -3.7, 2.0), 'edge')
        add_hands(mesh)
    return mesh.finish('view' if view else 'world')


def skin_bytes():
    atlas = Image.open(io.BytesIO(texture_bytes())).convert('RGB')
    draw = ImageDraw.Draw(atlas)
    for x in (12, 24, 36, 48):
        draw.line((64+x, 74, 64+x, 115), fill=(29, 41, 20), width=2)
    for y in (22, 42):
        draw.line((16, 64+y, 52, 64+y), fill=(60, 78, 35), width=2)
    return png_bytes(atlas)


def hud_icon(mesh):
    image = Image.new('RGBA', (128, 128))
    draw = ImageDraw.Draw(image)
    triangles = np.asarray(mesh['vertices'])[mesh['faces']]
    colors = {'edge': (146, 172, 93), 'dark': (61, 80, 38), 'magazine': (89, 121, 62)}
    for i in np.argsort(triangles.mean(axis=1)[:, 1])[::-1]:
        points = [(6+1.34*x, 56-2.7*z) for x, _, z in triangles[i]]
        draw.polygon(points, fill=colors.get(mesh['materials'][i], (111, 147, 72)))
    return png_bytes(image.resize((32, 32), Image.Resampling.LANCZOS))


def ads_header(frames):
    rear = np.asarray(SIGHT_LINE) * VIEW_SCALE + VIEW_OFFSET
    muzzle = np.asarray(MUZZLE) * VIEW_SCALE + VIEW_OFFSET
    values = {'ADS_FORWARD': 9.5-rear[0], 'ADS_RIGHT': rear[1], 'ADS_UP': -rear[2],
              'MUZZLE_FORWARD': muzzle[0], 'MUZZLE_RIGHT': -muzzle[1], 'MUZZLE_UP': muzzle[2]}
    defines = ''.join(f'#define PP_THUNDERHEAD_{key} ({value:.8f}f)\n' for key, value in values.items())
    return ('/* Generated by tools/assets/build_thunderhead.py. */\n'
            '#ifndef PP_THUNDERHEAD_MODEL_ADS_H\n#define PP_THUNDERHEAD_MODEL_ADS_H\n'
            f'{defines}#define PP_THUNDERHEAD_VIEW_FRAMES {frames}\n#endif\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    verify = parser.parse_args().verify
    world = geometry(view=False)
    view, frames = animated_model(geometry(view=True), POSES, VIEW_SCALE, VIEW_OFFSET,
                                  (10, -7.6, -14), VIEW + '/skin.png')
    atlas = skin_bytes()
    pickup_rotation = np.diag((-1, -1, 1))
    poses = np.asarray(world['vertices']) @ pickup_rotation * .46 + (20, 0, 18)
    normals = np.asarray(world['normals']) @ pickup_rotation
    pickup = encode(world, [poses], [normals], PICKUP + '/skin.png', ['idle'])
    held = encode_held_model(world, .28, (33, 0, -8), (10.2, -4.75, 13.3), VIEW + '/skin.png')
    outputs = {
        BASE / (VIEW + '/tris.md2'): view,
        BASE / (VIEW + '/skin.png'): atlas,
        BASE / (PICKUP + '/tris.md2'): pickup,
        BASE / (PICKUP + '/skin.png'): atlas,
        BASE / 'players/soldier/w_thunderhead.md2': held,
        BASE / 'pics/w_thunderhead.png': hud_icon(world),
        ROOT / 'src/client/header/thunderhead_model_ads.h': ads_header(frames),
    }
    for path, data in outputs.items():
        if path.is_file() and path.read_bytes() == data:
            continue
        if verify:
            raise ValueError(f'Stale Thunderhead output: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print('Verified Thunderhead assets' if verify else 'Built Thunderhead assets')


if __name__ == '__main__':
    main()
