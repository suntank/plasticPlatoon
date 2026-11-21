#!/usr/bin/env python3
"""Build an original model-kit sprue pickup and an icon from the same mesh.

The geometry and atlas are Plastic Platoon source artwork under GPL-2.0-or-later.
"""

import argparse
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from build_m16 import ATLAS_SIZE, encode_md2
from m16_geometry import Mesh

BASE = Path(__file__).resolve().parents[2] / 'baseq2'
PICKUP = 'models/items/sprues'
MATERIALS = {
    'plastic': (231, 139, 41),
    'edge': (181, 86, 28),
    'dark': (131, 59, 24),
    'part': (247, 172, 62),
    'gate': (208, 108, 30),
}
TILE = ATLAS_SIZE // 4


def chamfered_rectangle(width, height, corner):
    x, z = width / 2, height / 2
    return [(-x + corner, -z), (x - corner, -z), (x, -z + corner),
            (x, z - corner), (x - corner, z), (-x + corner, z),
            (-x, z - corner), (-x, -z + corner)]


def build_mesh():
    mesh = Mesh()
    mesh.ring_profile('sprue frame', chamfered_rectangle(27, 21, 2.8),
                      chamfered_rectangle(22, 16, 1.5), 1.25)
    mesh.limb('central runner', (-1, 0, -8.8), (-1, 0, 8.8), .84, .84,
              'gate', 6)
    mesh.limb('left gate', (-7, 0, 1.5), (-1, 0, 1.5), .58, .66, 'gate', 6)
    mesh.limb('right gate', (-1, 0, -1.8), (5.1, 0, -1.8), .62, .53,
              'gate', 6)
    mesh.limb('trimmed gate', (-11.7, 0, -4.9), (-8.5, 0, -4.9), .68, .45,
              'gate', 6)

    def washer(radius):
        return [(radius * math.cos(i * math.tau / 8) - 7.5,
                 radius * math.sin(i * math.tau / 8) + 1.5) for i in range(8)]

    mesh.ring_profile('molded hub', washer(3.35), washer(1.29), 1.6, 'part')
    mesh.profile('molded bracket',
                 [(3.1, -4.5), (8.5, -4.5), (9.0, -3.7), (9.0, -1.3),
                  (6.9, -1.3), (6.9, 3.6), (5.9, 4.4), (3.9, 4.4),
                  (3.1, 3.6)], 1.7, 'part', 'edge')
    mesh.profile('kit tab',
                 [(4.7, 9.1), (9.5, 9.1), (9.5, 11.4),
                  (8.9, 12), (5.3, 12), (4.7, 11.4)], 1.35, 'part', 'edge')

    asset = mesh.finish('pickup')
    tip = math.radians(14)
    c, s = math.cos(tip), math.sin(tip)
    rotation = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    asset['vertices'] = np.asarray(asset['vertices']) @ rotation
    asset['normals'] = np.asarray(asset['normals']) @ rotation
    return asset


def png(image):
    result = io.BytesIO()
    image.save(result, 'PNG', compress_level=9)
    return result.getvalue()


def make_skin_and_uvs(mesh):
    image = Image.new('RGB', (ATLAS_SIZE, ATLAS_SIZE), MATERIALS['plastic'])
    tiles = {}
    for index, (name, color) in enumerate(MATERIALS.items()):
        x, y = index % 4 * TILE, index // 4 * TILE
        tiles[name] = (x, y)
        # Subtle molded-plastic flecks at texture resolution.
        tile = Image.new('RGB', (TILE, TILE))
        tile.putdata([tuple(channel + ((u * 13 + v * 7) % 5) - 2 for channel in color)
                      for v in range(TILE) for u in range(TILE)])
        image.paste(tile, (x, y))

    uvs = []
    for coordinates, material in zip(mesh['uvs'], mesh['materials']):
        x, y = tiles[material]
        uvs.append([((x + 5 + u * (TILE - 11)) / ATLAS_SIZE,
                     (y + 5 + v * (TILE - 11)) / ATLAS_SIZE) for u, v in coordinates])
    return png(image), uvs


def make_icon(mesh):
    size = 128
    vertices = mesh['vertices']
    faces = np.asarray(mesh['faces'])
    camera = np.array([.29, -.95, .33])
    camera /= np.linalg.norm(camera)
    right = np.cross([0, 0, 1], camera)
    right /= np.linalg.norm(right)
    up = np.cross(camera, right)
    view = np.column_stack((vertices @ right, vertices @ up))
    roll = math.radians(18)
    c, s = math.cos(roll), math.sin(roll)
    view = view @ [[c, s], [-s, c]]
    low, high = view.min(axis=0), view.max(axis=0)
    pixels = (view - (low + high) / 2) * ((size - 22) / (high - low).max())
    pixels = pixels * [1, -1] + size / 2

    image = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(image)
    points = vertices[faces]
    normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    lights = np.array([-.25, -.78, .57])
    for i in np.argsort(points.mean(axis=1) @ camera):
        normal = normals[i]
        if normal @ camera <= 0:
            continue
        shade = .73 + .34 * max(0., normal @ lights)
        color = tuple(min(255, round(shade * channel))
                      for channel in MATERIALS[mesh['materials'][i]])
        draw.polygon([tuple(point) for point in pixels[faces[i]]], fill=color + (255,))

    outlined = Image.new('RGBA', image.size, (58, 32, 19))
    outlined.putalpha(image.getchannel('A').filter(ImageFilter.MaxFilter(5)))
    outlined.alpha_composite(image)
    return png(outlined.resize((32, 32), Image.Resampling.LANCZOS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    mesh = build_mesh()
    skin, uvs = make_skin_and_uvs(mesh)
    model, _ = encode_md2([mesh['vertices']], [mesh['normals']], mesh['faces'],
                         uvs, [PICKUP + '/skin.png'], ['idle'])
    assets = {
        BASE / PICKUP / 'tris.md2': model,
        BASE / PICKUP / 'skin.png': skin,
        BASE / 'pics/i_sprues.png': make_icon(mesh),
    }
    for path, contents in assets.items():
        if args.verify:
            if not path.is_file() or path.read_bytes() != contents:
                raise SystemExit(f'Rebuild outdated Sprues asset: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)


if __name__ == '__main__':
    main()
