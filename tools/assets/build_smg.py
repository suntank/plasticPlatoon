#!/usr/bin/env python3
"""Build the original SMG meshes, authored first-person poses, and HUD icon."""

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from asset_sources import source_bytes
from build_m16 import atlas_uvs, encode_md2, rigid_transforms, texture_bytes
from m16_geometry import Mesh, add_hands
from md2_assets import MD2

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
VIEW = 'models/weapons/v_smg'
PICKUP = 'models/weapons/g_smg'
HELD = 'players/soldier/w_smg.md2'
MUZZLE_X = 72
VIEW_SCALE = .57
VIEW_OFFSET = np.array((-7.8, -7.0, -8.5))


def geometry(view):
    mesh = Mesh()
    mesh.ring_profile('open_stock',
                      [(9, -7.8), (23.5, -4.4), (28.8, -.3), (14, 1.1), (8, -.2)],
                      [(11.4, -5.6), (22, -3.1), (25, -.9), (14, -.55), (10.7, -1.5)],
                      .93)
    mesh.profile('stock_pad', [(7.3, -8.2), (10.1, -8.2), (9.2, .8), (6.9, .6)],
                 1.45, 'grip')
    mesh.tube('receiver', [(25, 0, -.15, 1.7, 3.0), (29, 0, 0, 2.65, 3.7),
                           (53, 0, 0, 2.65, 3.7), (55, 0, -.15, 2.35, 3.25)],
              material='receiver', caps=(True, True))
    mesh.profile('grip', [(27, -13.0), (30, -3.1), (36.6, -3.5), (32.9, -14.6),
                          (28.5, -14.8)], 1.75, 'grip')
    mesh.ring_profile('guard', [(33.8, -3), (43.4, -3), (43, -7.5), (40.5, -9), (33.6, -8)],
                      [(35.3, -4.4), (41.8, -4.4), (41.7, -6.7), (40, -7.5), (35, -6.9)], .75)
    mesh.profile('magazine', [(44.4, -2.7), (50.1, -2.7), (50.9, -11.7), (53, -21.5),
                              (47.7, -22.5), (45.4, -12.4)], 1.55, 'magazine')
    mesh.box('magazine_floor', (47.4, -1.75, -22.5), (53.25, 1.75, -21.25), 'edge')
    mesh.tube('ribbed_fore_end', [(53.8, 0, -.4, 2.55, 3.3), (55, 0, -.4, 3.2, 3.55),
                                  (63.4, 0, -.4, 2.85, 3.2), (65, 0, -.4, 2.15, 2.45)],
              material='handguard', caps=(True, True))
    mesh.tube('short_barrel', [(64.8, 0, 0, 1.0, 1.0), (69.4, 0, 0, 1.0, 1.0)],
              material='dark')
    mesh.tube('muzzle_collar', [(69.0, 0, 0, 1.55, 1.55), (71.5, 0, 0, 1.55, 1.55),
                              (MUZZLE_X, 0, 0, 1.27, 1.27)],
              material='edge', caps=(True, True), end_material='bore')
    mesh.box('rear_sight', (29.8, -1.3, 3.1), (32.0, 1.3, 4.8), 'dark')
    mesh.box('front_sight', (61.0, -.35, 2.4), (62.2, .35, 5.7), 'edge')
    for side in (-1, 1):
        y = side * 1.07
        mesh.box(f'rear_sight_ear_{side}', (29.8, y-.25, 4.5), (32.0, y+.25, 6.25), 'edge')
    if view:
        mesh.box('ejection_port', (40.0, -2.63, .45), (51.0, -2.38, 2.32), 'bore')
        mesh.box('bolt', (46.4, -2.94, .60), (50.3, -2.54, 2.13), 'dark')
        mesh.box('charging_tab', (47.0, -3.65, .9), (48.7, -2.87, 1.8), 'edge')
        add_hands(mesh)
        # Keep the rifle's straight support wrist and seat the whole left
        # arm slightly farther back on the SMG's shorter fore-end.
        left_arm = next(part for part in mesh.parts if part['name'] == 'arm_left')
        left_vertices = {index for face in mesh.faces[left_arm['first_triangle']:] for index in face}
        for index in left_vertices:
            mesh.vertices[index][0] -= 3.5
    return mesh.finish('view' if view else 'world')


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, format='PNG', compress_level=9)
    return output.getvalue()


def plastic_atlas():
    atlas = Image.open(io.BytesIO(texture_bytes())).convert('RGB')
    draw = ImageDraw.Draw(atlas)
    # Short vertical grips and a molded stamp on the receiver.
    for x in range(15, 57, 9):
        draw.line((x, 10, x, 53), fill=(25, 35, 14), width=2)
        draw.line((x+2, 11, x+2, 52), fill=(53, 70, 27))
    draw.rounded_rectangle((148, 88, 180, 105), radius=3, outline=(28, 39, 16))
    draw.text((153, 90), 'SMG', fill=(93, 113, 53))
    return png_bytes(atlas)


def icon(mesh):
    image = Image.new('RGBA', (128, 128))
    draw = ImageDraw.Draw(image)
    vertices = np.asarray(mesh['vertices'])
    triangles = vertices[mesh['faces']]
    shades = {'dark': (65, 85, 38), 'edge': (131, 163, 77), 'grip': (78, 113, 43),
              'magazine': (98, 133, 54), 'handguard': (113, 153, 57)}
    for i in np.argsort(triangles.mean(axis=1)[:, 1])[::-1]:
        points = [(round(8 + x * 1.52), round(53 - z * 2.9)) for x, _, z in triangles[i]]
        draw.polygon(points, fill=shades.get(mesh['materials'][i], (106, 148, 59)))
    return png_bytes(image.resize((32, 32), Image.Resampling.LANCZOS))


def encode(mesh, positions, normals, skin, names):
    return encode_md2(positions, normals, mesh['faces'], atlas_uvs(mesh), [skin], names)[0]


def view_model(mesh):
    # (pitch up, rearward travel, vertical travel, bolt travel), in model units.
    poses = [
        ('raise1', -12, -2.0, -4.5, 0), ('raise2', -7, -1.2, -2.6, 0),
        ('raise3', -3, -.5, -1.0, 0), ('raise4', 0, 0, 0, 0),
        ('fire1', .6, -.12, 0, 0), ('fire2', 1.8, -.36, .06, 3.1),
        ('recover', .4, -.08, 0, .7),
        ('idle1', 0, 0, 0, 0), ('idle2', .15, 0, .07, 0),
        ('idle3', .2, 0, .11, 0), ('idle4', .15, 0, .07, 0),
        ('idle5', 0, 0, 0, 0), ('idle6', -.12, 0, -.06, 0),
        ('idle7', -.14, 0, -.09, 0), ('idle8', -.1, 0, -.06, 0),
        ('lower1', -2, -.4, -.7, 0), ('lower2', -6, -.85, -2, 0),
        ('lower3', -10, -1.4, -3.4, 0), ('lower4', -15, -2.1, -5, 0),
    ]
    return animated_model(mesh, poses, VIEW_SCALE, VIEW_OFFSET, (10, -7, -13), VIEW + '/skin.png')


def animated_model(mesh, poses, scale, offset, pivot, skin):
    vertices = np.asarray(mesh['vertices']) * scale + offset
    directions = np.asarray(mesh['normals'])
    actuator_faces = [mesh['faces'][i]
                      for part in mesh['parts'] if part['name'] in ('bolt', 'charging_tab')
                      for i in range(part['first_triangle'], part['first_triangle'] + part['triangle_count'])]
    actuator = np.unique(actuator_faces)
    pivot = np.asarray(pivot)
    positions, normals = [], []
    for _, pitch, back, drop, bolt in poses:
        sine, cosine = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
        rotation = np.array(((cosine, 0, sine), (0, 1, 0), (-sine, 0, cosine)))
        points = vertices.copy()
        points[actuator, 0] -= bolt * scale
        positions.append((points - pivot) @ rotation + pivot + (back, 0, drop))
        normals.append(directions @ rotation)
    names = [pose[0] for pose in poses]
    return encode(mesh, positions, normals, skin, names), len(names)


def held_model(mesh):
    return encode_held_model(mesh, .28, (33, 0, -8), (10.2, -4.75, 12.8), VIEW + '/skin.png')


def encode_held_model(mesh, scale, grip, attachment, skin):
    # Carry the mesh through the soldier's existing 198 weapon poses.
    source_path = 'baseq2/players/soldier/w_machinegun.md2'
    originals = json.loads((ROOT / 'tools/assets/platoon-originals.json').read_text())
    source = MD2.read(source_bytes(originals, source_path), source_compat=True)
    rotations, offsets, _ = rigid_transforms(source)
    offset = np.asarray(attachment) - np.asarray(grip) * scale
    rest = np.asarray(mesh['vertices']) * scale + offset
    positions = [rest @ rotation + shift for rotation, shift in zip(rotations, offsets)]
    normals = [np.asarray(mesh['normals']) @ rotation for rotation in rotations]
    return encode(mesh, positions, normals, skin, source.names)


def alignment_header(frames):
    rear = np.array((31, 0, 5.7)) * VIEW_SCALE + VIEW_OFFSET
    muzzle = np.array((MUZZLE_X, 0, 0)) * VIEW_SCALE + VIEW_OFFSET
    values = dict(ADS_FORWARD=9.5-rear[0], ADS_RIGHT=rear[1], ADS_UP=-rear[2],
                  MUZZLE_FORWARD=muzzle[0], MUZZLE_RIGHT=-muzzle[1], MUZZLE_UP=muzzle[2])
    defines = ''.join(f'#define PP_SMG_{name} ({value:.8f}f)\n' for name, value in values.items())
    return ('/* Generated by tools/assets/build_smg.py. */\n'
            '#ifndef PP_SMG_MODEL_ADS_H\n#define PP_SMG_MODEL_ADS_H\n'
            f'{defines}#define PP_SMG_VIEW_FRAMES {frames}\n#endif\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    verify = parser.parse_args().verify
    world = geometry(view=False)
    view, frames = view_model(geometry(view=True))
    atlas = plastic_atlas()
    pickup_rotation = np.diag((-1, -1, 1))
    positions = np.asarray(world['vertices']) @ pickup_rotation * .49 + (19, 0, 19)
    normals = np.asarray(world['normals']) @ pickup_rotation
    pickup = encode(world, [positions], [normals], PICKUP + '/skin.png', ['idle'])
    outputs = {
        BASE / (VIEW + '/tris.md2'): view,
        BASE / (PICKUP + '/tris.md2'): pickup,
        BASE / (VIEW + '/skin.png'): atlas,
        BASE / (PICKUP + '/skin.png'): atlas,
        BASE / HELD: held_model(world),
        BASE / 'pics/w_smg.png': icon(world),
        ROOT / 'src/client/header/smg_model_ads.h': alignment_header(frames),
    }
    for path, data in outputs.items():
        if path.is_file() and path.read_bytes() == data:
            continue
        if verify:
            raise ValueError(f'Stale SMG output: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print('Verified SMG assets' if verify else 'Built SMG assets')


if __name__ == '__main__':
    main()
