#!/usr/bin/env python3
"""Build the Plastic Platoon mine models, skins, HUD icon and shop portrait."""

import argparse
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ammo_geometry import REGIONS, atlas_uvs, turned
from build_m16 import encode_md2
from m16_geometry import Mesh


BASE = Path(__file__).resolve().parents[2] / 'baseq2'
PROJECTILE = 'models/objects/prox_mine'
PICKUP = 'models/items/ammo/prox_mines'
COLORS = {
    'dark': (40, 54, 37), 'plastic': (86, 112, 49),
    'edge': (140, 158, 77), 'band': (211, 140, 54), 'brass': (96, 53, 27),
}


def mine_body(mesh, size=1.0, height=0.0, center=(0.0, 0.0)):
    def profile(rings):
        return [(height + z * size, radius * size) for z, radius in rings]

    turned(mesh, 'molded_case', profile([(0, 6.5), (0.8, 7.4), (2.3, 7.4),
                                        (3.3, 6.1), (3.7, 4.8)]),
           sides=10, material='plastic', bands=['dark', 'band', 'plastic', 'edge'], center=center)
    turned(mesh, 'detector', profile([(3.6, 2.8), (4.1, 2.8), (4.5, 1.8)]),
           sides=8, material='brass', bands=['dark', 'brass'], center=center)


def skin(colors):
    image = Image.new('RGB', (256, 256), colors['plastic'])
    draw = ImageDraw.Draw(image)
    for part, color in colors.items():
        x, y, right, bottom = REGIONS[part]
        for row in range(y - 2, bottom + 2):
            lift = 1.07 - 0.14 * (row - y) / (bottom - y)
            ramp = tuple(min(255, round(channel * lift)) for channel in color)
            draw.line((x - 2, row, right + 2, row), fill=ramp)
    return image


def render(mesh, colors, size, portrait=False):
    """Orthographic render of the actual game mesh at an oblique angle."""
    points = np.asarray(mesh['vertices'])
    right = np.array([0.8, 0.6, 0.0])
    rear = np.array([-0.6, 0.8, 0.0])
    up = rear * 0.57 + np.array([0., 0., 0.8216])
    camera = np.cross(right, up)
    light = camera + right * 0.4 + up * 1.3
    light /= np.linalg.norm(light)
    xy = np.column_stack((points @ right, -points @ up))
    span = np.ptp(xy, axis=0)
    xy -= (xy.max(axis=0) + xy.min(axis=0)) * 0.5
    xy = xy * (size * (0.73 if portrait else 0.87) / span.max()) + size * 0.5
    depth = points @ camera
    image = Image.new('RGBA', (size, size), (16, 23, 19, 255) if portrait else (0, 0, 0, 0))
    if portrait:
        shade = Image.new('RGBA', image.size)
        ImageDraw.Draw(shade).ellipse((size * .21, size * .55, size * .8, size * .78),
                                      fill=(0, 0, 0, 190))
        image.alpha_composite(shade.filter(ImageFilter.GaussianBlur(size * .043)))
    draw = ImageDraw.Draw(image)
    faces = np.asarray(mesh['faces'])
    for index in np.argsort(depth[faces].mean(axis=1)):
        face = faces[index]
        a, b, c = points[face]
        normal = np.cross(b - a, c - a)
        normal /= np.linalg.norm(normal)
        if normal @ camera <= 0:
            continue
        brightness = 0.67 + 0.54 * max(0, normal @ light)
        color = tuple(min(255, round(v * brightness)) for v in colors[mesh['materials'][index]])
        draw.polygon([tuple(p) for p in xy[face]], fill=color + (255,))
    return image


def image_bytes(image, kind, **kwargs):
    data = BytesIO()
    image.save(data, format=kind, **kwargs)
    return data.getvalue()


def model_bytes(mesh, skins, align_surface=False):
    points = np.asarray(mesh['vertices'])
    normals = np.asarray(mesh['normals'])
    if align_surface:
        # The engine points the local +X axis along the contact normal.
        points = points[:, [2, 1, 0]] * [1, 1, -1]
        normals = normals[:, [2, 1, 0]] * [1, 1, -1]
    raw, _ = encode_md2(points[None], normals[None], mesh['faces'], atlas_uvs(mesh), skins, ['idle'])
    return raw


def build():
    projectile = Mesh()
    mine_body(projectile)
    projectile = projectile.finish('projectile')

    pickup = Mesh()
    turned(pickup, 'lower_mine', [(-14.5, 10), (-13.4, 11.4), (-9.6, 11.4), (-7.8, 9.5)],
           sides=10, material='plastic', bands=['dark', 'band', 'plastic'], center=(-1.9, 0.8))
    mine_body(pickup, size=1.53, height=-8.3, center=(2.3, -1.2))
    pickup = pickup.finish('pickup')

    armed_colors = {**COLORS, 'brass': (253, 80, 46)}
    icon = render(projectile, {**COLORS, 'brass': (255, 174, 70)}, 192)
    portrait = render(pickup, COLORS, 384, portrait=True)
    return {
        f'{PROJECTILE}/tris.md2': model_bytes(projectile, [f'{PROJECTILE}/skin.png',
                                                          f'{PROJECTILE}/armed.png'], align_surface=True),
        f'{PROJECTILE}/skin.png': image_bytes(skin(COLORS), 'PNG'),
        f'{PROJECTILE}/armed.png': image_bytes(skin(armed_colors), 'PNG'),
        f'{PICKUP}/tris.md2': model_bytes(pickup, [f'{PROJECTILE}/skin.png']),
        'pics/a_throwable_mine.png': image_bytes(icon.resize((32, 32), Image.Resampling.LANCZOS), 'PNG'),
        'pics/pp_qm_supply_mines.jpg': image_bytes(portrait.convert('RGB'), 'JPEG', quality=91),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    for name, data in build().items():
        path = BASE / name
        if args.verify:
            if not path.is_file() or path.read_bytes() != data:
                raise ValueError(f'Missing or stale mine asset: {name}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


if __name__ == '__main__':
    main()
