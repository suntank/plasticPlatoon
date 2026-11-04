#!/usr/bin/env python3
"""Build original provisional props and energy effects for standalone play.

All geometry, texture pixels and sprite pixels are procedural source artwork
defined here. No imported models, texture files, fonts or third-party Python
packages are read. Legacy resource names are compatibility paths only.
Outputs use the repository's GPL-2.0-or-later license. These deliberately simple
functional replacements still need an art pass; the grenade uses 49 identical
poses so every frame requested by Weapon_Grenade is valid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
SKIN = 'models/support/plastic_atlas.tga'
ATLAS_SIZE = 128
COLORS = ((65, 132, 64), (31, 57, 35), (197, 158, 104), (156, 247, 109),
          (214, 184, 98), (107, 121, 113), (231, 234, 207), (164, 75, 54),
          (91, 153, 79), (45, 91, 46), (225, 194, 142), (222, 255, 178),
          (162, 133, 68), (74, 84, 79), (160, 168, 145), (103, 49, 35))
# Cardinal directions in the MD2 codec's fixed 162-normal table. These numeric
# indices describe the file format, not imported model geometry or artwork.
NORMALS = {(1, 0, 0): 52, (-1, 0, 0): 143, (0, 1, 0): 32,
           (0, -1, 0): 104, (0, 0, 1): 5, (0, 0, -1): 84}


def tga(width, height, pixel_at):
    data = bytearray(struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0,
                                 width, height, 32, 40))
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixel_at(x, y)
            data.extend((b, g, r, a))
    return bytes(data)


def atlas():
    def pixel(x, y):
        tile = (y // 32) * 4 + x // 32
        color = COLORS[tile]
        # Slight deterministic molded-plastic flecks inside each flat tile.
        shift = ((x * 13 + y * 7) % 5) - 2
        return tuple(max(0, min(255, c + shift)) for c in color) + (255,)
    return tga(ATLAS_SIZE, ATLAS_SIZE, pixel)


class Mesh:
    def __init__(self):
        self.vertices, self.normals, self.uvs, self.faces = [], [], [], []

    def quad(self, points, direction, material):
        """Author outward CCW faces, then export engine-required clockwise."""
        base = len(self.vertices)
        self.vertices.extend(points)
        self.normals.extend([NORMALS[direction]] * 4)
        x, y = material % 4 * 32, material // 4 * 32
        self.uvs.extend(((x + 5, y + 5), (x + 26, y + 5),
                         (x + 26, y + 26), (x + 5, y + 26)))
        self.faces.extend(((base + 2, base + 1, base), (base + 3, base + 2, base)))

    def box(self, low, high, material=0, top=None):
        x, y, z = low
        X, Y, Z = high
        self.quad(((x,Y,z), (X,Y,z), (X,y,z), (x,y,z)), (0,0,-1), material)
        self.quad(((x,y,Z), (X,y,Z), (X,Y,Z), (x,Y,Z)), (0,0,1), material if top is None else top)
        self.quad(((x,y,z), (X,y,z), (X,y,Z), (x,y,Z)), (0,-1,0), material)
        self.quad(((x,Y,Z), (X,Y,Z), (X,Y,z), (x,Y,z)), (0,1,0), material)
        self.quad(((x,y,Z), (x,Y,Z), (x,Y,z), (x,y,z)), (-1,0,0), material)
        self.quad(((X,y,z), (X,Y,z), (X,Y,Z), (X,y,Z)), (1,0,0), material)


def encode_md2(mesh, frames=1):
    low = tuple(min(v[axis] for v in mesh.vertices) for axis in range(3))
    high = tuple(max(v[axis] for v in mesh.vertices) for axis in range(3))
    scale = tuple((b - a) / 255 for a, b in zip(low, high))
    vertices = b''.join(bytes(tuple(max(0, min(255, round((v[a] - low[a]) / scale[a])))
                                    for a in range(3)) + (normal,))
                        for v, normal in zip(mesh.vertices, mesh.normals))
    frame_data = b''.join(struct.pack('<6f16s', *scale, *low,
                                      f'pose{i:03}'.encode()) + vertices for i in range(frames))
    st = b''.join(struct.pack('<2h', *uv) for uv in mesh.uvs)
    triangles = b''.join(struct.pack('<6H', *face, *face) for face in mesh.faces)
    commands = bytearray()
    for face in mesh.faces:
        commands.extend(struct.pack('<i', 3))
        for index in face:
            u, v = mesh.uvs[index]
            commands.extend(struct.pack('<ffi', (u + .5) / ATLAS_SIZE,
                                         (v + .5) / ATLAS_SIZE, index))
    commands.extend(struct.pack('<i', 0))
    sections = (SKIN.encode().ljust(64, b'\0'), st, triangles, frame_data, commands)
    offsets, end = [], 68
    for section in sections:
        offsets.append(end)
        end += len(section)
    header = struct.pack('<17i', 844121161, 8, ATLAS_SIZE, ATLAS_SIZE,
                         40 + len(vertices), 1, len(mesh.vertices), len(mesh.uvs),
                         len(mesh.faces), len(commands) // 4, frames, *offsets, end)
    return header + b''.join(sections), {'vertices': len(mesh.vertices),
            'triangles': len(mesh.faces), 'frames': frames, 'bounds': [low, high], 'skin': SKIN}


def battery():
    mesh = Mesh()
    mesh.box((-6,-5,-8), (6,5,8), 0, 8)
    mesh.box((-4,-3,8), (4,3,10), 4, 6)
    mesh.box((6.2,-3,-5), (6.8,3,5), 4)
    mesh.box((-6.8,-3,-5), (-6.2,3,5), 4)
    return mesh


def grenade_view():
    mesh = Mesh()
    # +X points ahead of the camera, -Y sits to the player's right, -Z below
    # eye level. The grip and glove keep the first-person shape readable.
    mesh.box((12,-9,-16), (20,-3,-6), 0, 8)
    mesh.box((13,-8,-6), (19,-4,-4), 1, 5)
    mesh.box((14,-8.5,-5), (17,-3.5,-3), 5)
    mesh.box((9,-9.5,-22), (15,-2.5,-14), 2, 10)
    for z in (-14, -11, -8):
        mesh.box((11.5,-9.3,z), (20.5,-2.7,z + .7), 9)
    return mesh


def energy_sprite(variant, frame, count):
    def pixel(x, y):
        distance = math.hypot(x - 31.5, y - 31.5) / 31.5
        phase = frame / max(1, count - 1)
        radius = .68 + .12 * math.sin(frame * math.tau / count) if variant == 1 else .3 + .65 * phase
        normalized = distance / radius
        if normalized >= 1:
            return 0, 0, 0, 0
        fade = 1 if variant == 1 else 1 - .65 * phase
        alpha = round(255 * (1 - normalized) ** .55 * fade)
        core = max(0, 1 - normalized * 2)
        return round(70 + core * 150), 255, round(40 + core * 120), alpha
    return tga(64, 64, pixel)


def battery_icon():
    def pixel(x, y):
        if 11 <= x <= 20 and 3 <= y <= 6:
            return COLORS[4] + (255,)
        if 6 <= x <= 25 and 7 <= y <= 28:
            if x in (6, 25) or y in (7, 28):
                return COLORS[1] + (255,)
            if 14 <= x <= 17 and 11 <= y <= 24 or 10 <= x <= 21 and 16 <= y <= 19:
                return COLORS[4] + (255,)
            return COLORS[8 if x < 13 else 0] + (255,)
        return 0, 0, 0, 0
    return tga(32, 32, pixel)


def build_assets():
    assets, models = {SKIN: atlas(), 'pics/k_powercube.tga': battery_icon()}, []
    meshes = {'models/items/keys/power/tris.md2': (battery(), 1),
              'models/weapons/v_handgr/tris.md2': (grenade_view(), 49)}
    debris1, debris2, laser = Mesh(), Mesh(), Mesh()
    debris1.box((-3,-2,-1.5), (3,2,1.5), 2, 10)
    debris2.box((-1.5,-1,-1), (1.5,1,1), 0, 8)
    laser.box((-8,-.7,-.7), (8,.7,.7), 3, 11)
    laser.box((-3,-1,-1), (3,1,1), 11)
    meshes.update({'models/objects/debris1/tris.md2': (debris1, 1),
                   'models/objects/debris2/tris.md2': (debris2, 1),
                   'models/objects/laser/tris.md2': (laser, 1)})
    for name, (mesh, frames) in sorted(meshes.items()):
        assets[name], metadata = encode_md2(mesh, frames)
        models.append({'path': name, **metadata})
    sprites = []
    for variant, count, display_size in ((1, 4, 32), (2, 6, 80), (3, 6, 112)):
        path = f'sprites/s_bfg{variant}.sp2'
        data = bytearray(struct.pack('<3i', 844317769, 2, count))
        images = []
        for frame in range(count):
            image = f'sprites/pp_energy/bfg{variant}_{frame}.tga'
            assets[image] = energy_sprite(variant, frame, count)
            data.extend(struct.pack('<4i64s', display_size, display_size,
                                    display_size // 2, display_size // 2, image.encode()))
            images.append(image)
        assets[path] = bytes(data)
        sprites.append({'path': path, 'frames': count, 'display_size': display_size, 'images': images})
    manifest = {'schema': 1, 'generator': 'tools/assets/build_support_models.py',
                'provenance': 'Original procedural source artwork defined entirely in the generator',
                'license': 'GPL-2.0-or-later', 'external_inputs': [],
                'status': 'Provisional functional replacements requiring an art review',
                'animation_note': 'The first-person grenade has 49 identical poses matching the requested frame range',
                'models': models, 'sprites': sprites,
                'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(assets.items())]}
    return assets, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'baseq2')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'tools/assets/support-models-manifest.json')
    parser.add_argument('--verify', action='store_true', help='check output bytes and manifest without writing')
    args = parser.parse_args()
    assets, manifest = build_assets()
    outputs = {args.output / name: data for name, data in assets.items()}
    outputs[args.manifest] = (json.dumps(manifest, indent=2) + '\n').encode()
    mismatches = []
    for path, data in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes() != data:
                mismatches.append(str(path))
        elif not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if mismatches:
        parser.error('Missing or changed generated files: ' + ', '.join(mismatches))
    print(f'{"Verified" if args.verify else "Built"} {len(assets)} original provisional support assets')


if __name__ == '__main__':
    main()
