#!/usr/bin/env python3
"""Build the original animated ant MD2 and its skin without external assets.

Coordinates are Quake units, +X forward. Run with --review to inspect decoded
frames; --verify checks that the checked-in assets match this generator.
"""
import argparse
from dataclasses import replace
import io
import math
import struct

import numpy as np
from PIL import Image, ImageDraw

from build_heavy_tank import Mesh
from md2_assets import HEADER, IDENT, MD2, ROOT, gl_strips, normal_table, raster

DIRECTORY = 'models/monsters/ant'
SKIN = DIRECTORY + '/skin.png'
FRAMES = [('idle', 8), ('walk', 12), ('run', 12), ('attack', 8), ('pain', 4), ('death', 10)]


def skin():
    image = Image.new('RGB', (256, 256))
    draw = ImageDraw.Draw(image)
    colors = [(91, 38, 25), (128, 53, 31), (62, 25, 21), (34, 19, 17),
              (157, 72, 42), (202, 124, 72), (45, 24, 21), (110, 43, 25),
              (87, 35, 24), (115, 47, 28), (79, 31, 23), (142, 60, 34),
              (68, 28, 21), (102, 40, 25), (123, 50, 29), (51, 25, 21)]
    for i, color in enumerate(colors):
        x, y = i % 4 * 64, i // 4 * 64
        draw.rectangle((x, y, x + 63, y + 63), fill=color)
        for py in range(4, 60, 8):
            for px in range(4, 60, 8):
                v = ((px * 13 + py * 7 + i) % 5) - 2
                draw.point((x + px, y + py), fill=tuple(max(0, min(255, c + v)) for c in color))
    out = io.BytesIO()
    image.save(out, format='PNG', compress_level=9)
    return out.getvalue()


def ellipsoid(m, center, radii, material, rings=5, sides=10):
    c, r = np.array(center), np.array(radii)
    start = len(m.vertices)
    loops = []
    for j in range(rings):
        lat = -math.pi * .4 + j * math.pi * .8 / (rings - 1)
        loops.append([c + r * [math.cos(lat)*math.cos(i*math.tau/sides),
                                math.cos(lat)*math.sin(i*math.tau/sides), math.sin(lat)]
                      for i in range(sides)])
    for a, b in zip(loops, loops[1:]):
        for i in range(sides):
            pts = [a[i], a[(i+1)%sides], b[(i+1)%sides], b[i]]
            m.poly(pts, material, np.mean(pts, axis=0) - c)
    m.poly(loops[0], material, [0, 0, -1])
    m.poly(loops[-1], material, [0, 0, 1])
    # Use the ellipsoid's surface gradient at every vertex. Mesh.poly makes
    # separate vertices for each face, so assigning its face normals directly
    # would leave visible hard seams even at identical positions.
    normals = (np.asarray(m.vertices[start:]) - c) / (r * r)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    m.normals[start:] = normals.tolist()


def make_frame(kind, index, count):
    m = Mesh()
    phase = math.tau * index / count
    moving = kind in ('walk', 'run')
    gait = (1.25 if kind == 'walk' else 1.9) if moving else 0
    bob = (1.5 * math.sin(2 * phase)) if moving else (.8 * math.sin(phase) if kind == 'idle' else 0)
    # Wind back and open, then snap forward on the gameplay hit frame (36).
    bite = (0, -.25, -.65, -.35, 1, .55, .2, 0)[index] if kind == 'attack' else 0
    jaw_open = (0, .5, 1, 1, .05, .15, .1, 0)[index] if kind == 'attack' else 0
    recoil = math.sin(math.pi * index / (count - 1)) if kind == 'pain' else 0
    bob -= 1.5 * recoil
    head_shift = 7*bite - 5*recoil
    # Large gaster, narrow waist, thorax and a distinct head.
    ellipsoid(m, (-20, 0, -3+bob), (14, 11, 12), 0)
    ellipsoid(m, (-6, 0, -4+bob), (5, 4.5, 5), 2, 4, 8)
    ellipsoid(m, (2, 0, -3+bob), (10, 8, 8), 1, 5, 10)
    ellipsoid(m, (17+head_shift, 0, -2+bob), (10, 9, 9), 0, 5, 10)
    # Narrow raised petiole and dark compound eyes.
    ellipsoid(m, (-8, 0, 1+bob), (3.7, 4, 5), 1, 4, 8)
    for side in (-1, 1):
        ellipsoid(m, (20+head_shift, side*7.4, 1+bob), (3.4, 2.4, 3.1), 3, 4, 8)
        # Elbowed antennae and paired inward-curving pincers.
        feeler_phase = 0 if kind == 'death' else phase
        feeler = 2.7 * math.sin(feeler_phase + side*.6)
        # Fold the feelers against the shell during the roll so they do not
        # prop the upside-down body above the floor.
        fold = min(index / 3, 1) if kind == 'death' else 0
        base = np.array([22+head_shift, side*4.5, 5+bob])
        elbow = np.array([27+head_shift, side*(9+feeler), 12+bob-6*fold])
        tip = np.array([34+head_shift, side*(12+feeler*1.5), 14+bob+1.8*math.cos(feeler_phase)-8.8*fold])
        m.cylinder(base, elbow, .75, 2, 2, 6)
        m.cylinder(elbow, tip, .6, 2, 2, 6)
        jaw = np.array([24+head_shift, side*6, -6+bob])
        mid = np.array([30+head_shift, side*(7+3*jaw_open), -8+bob])
        end = np.array([34+head_shift+2*bite, side*(2+4*jaw_open), -7+bob])
        m.cylinder(jaw, mid, 1.7, 2, 2, 6)
        m.cylinder(mid, end, 1.15, 2, 2, 6)
        # Alternating tripod gait: opposite sides have opposite phases.
        for leg, x in enumerate((9, 1, -7)):
            swing = math.sin(phase + (leg % 2)*math.pi + (side == 1)*math.pi) * gait
            lift = max(0, math.cos(phase + (leg % 2)*math.pi + (side == 1)*math.pi)) * gait
            hip = np.array([x, side*6, -5+bob])
            knee = np.array([x + (4-leg*4) + swing*4, side*17, -4+bob + lift*2])
            foot = np.array([x + (7-leg*7) + swing*6, side*25, -23 + lift*4])
            toe = foot + np.array([3, side*2, 0])
            m.cylinder(hip, knee, 1.9, 1, 2, 6)
            ellipsoid(m, knee, (2.2, 2.2, 2.2), 2, 3, 6)
            m.cylinder(knee, foot, 1.25, 0, 2, 6)
            m.cylinder(foot, toe, .85, 2, 2, 6)
    if kind == 'death':
        # A quick half-turn finishes by frame 49, then holds on its back.
        t = min(index / 5, 1.0)
        angle = math.pi * t * t * (3 - 2*t)
        cs, sn = math.cos(angle), math.sin(angle)
        rot = np.array([[1,0,0],[0,cs,-sn],[0,sn,cs]])
        p = np.asarray(m.vertices); pivot = np.array([0.,0.,-15.])
        p = (p-pivot) @ rot.T + pivot
        p[:, 2] += -24 - p[:, 2].min()
        m.vertices = p.tolist()
        m.normals = (np.asarray(m.normals) @ rot.T).tolist()
    return m


def build():
    meshes = [(f'{kind}{i:02}', make_frame(kind, i, count)) for kind, count in FRAMES for i in range(count)]
    first = meshes[0][1]
    faces = np.asarray(first.faces, dtype=np.int32)[:, ::-1]
    uvs = np.asarray(first.uvs)[:, ::-1, :]
    st, indices, keys = [], [], {}
    for coords in uvs:
        ids = []
        for uv in coords:
            key = tuple(np.rint(uv * 256 - .5).astype(int))
            if key not in keys:
                keys[key] = len(st); st.append(key)
            ids.append(keys[key])
        indices.append(ids)
    timeline = []
    for name, mesh in meshes:
        assert len(mesh.vertices) == len(first.vertices) and mesh.faces == first.faces
        p = np.asarray(mesh.vertices)
        scale = (np.maximum(np.ptp(p, axis=0), .001) / 255).astype('<f4')
        trans = p.min(axis=0).astype('<f4')
        q = np.clip(np.rint((p-trans)/scale), 0, 255).astype(np.uint8)
        normals = np.argmax(np.asarray(mesh.normals) @ normal_table().T, axis=1).astype(np.uint8)
        timeline.append(struct.pack('<6f16s', *scale, *trans, name.encode()) + np.column_stack((q,normals)).astype(np.uint8).tobytes())
    parts = (SKIN.encode().ljust(64,b'\0'), np.asarray(st,dtype='<i2').tobytes(),
             np.column_stack((faces,indices)).astype('<u2').tobytes(), b''.join(timeline), gl_strips(faces,uvs))
    offsets, cursor = [], HEADER.size
    for part in parts:
        offsets.append(cursor); cursor += len(part)
    data = HEADER.pack(IDENT,8,256,256,40+len(first.vertices)*4,1,len(first.vertices),len(st),len(faces),len(parts[-1])//4,len(meshes),*offsets,cursor) + b''.join(parts)
    model = MD2.read(data)
    for frame, (p, normals) in enumerate(zip(model.positions, model.normals)):
        tris = p[model.faces]
        cross = np.cross(tris[:,1]-tris[:,0], tris[:,2]-tris[:,0])
        light = normal_table()[normals][model.faces].mean(axis=1)
        if (np.einsum('ij,ij->i',cross,light) >= 0).any():
            raise ValueError(f'Degenerate or inverted MD2 triangle: frame {frame}, faces {np.flatnonzero(np.einsum("ij,ij->i",cross,light) >= 0)[:10].tolist()}')
    return data


def review(model, png, output='ant.png', extent=48):
    decoded = MD2.read(model); image = Image.open(io.BytesIO(png))
    sheet = Image.new('RGB',(1200, 880),(23,26,30)); draw = ImageDraw.Draw(sheet)
    for row, (frame, title) in enumerate(((0,'Idle'), (14,'Walk'), (36,'Bite'), (53,'Death'))):
        one = replace(decoded, positions=decoded.positions[frame:frame+1], normals=decoded.normals[frame:frame+1])
        for col, angle in enumerate((25, 115, 205)):
            pic, _ = raster(one, image, angle, 400, (np.array([0.,0.,-3.]), extent), elevation=25, cull_front=True)
            sheet.paste(pic.resize((300,200)), (col*400,row*220+20))
            draw.text((col*400+10,row*220+5), f'{title} | {angle} degrees', fill='white')
    path = ROOT/'tools/assets/review'/output; path.parent.mkdir(parents=True, exist_ok=True); sheet.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true'); parser.add_argument('--review', action='store_true')
    args = parser.parse_args()
    model, png = build(), skin()
    for path, data in ((ROOT/'baseq2'/DIRECTORY/'tris.md2', model), (ROOT/'baseq2'/SKIN, png)):
        if args.verify:
            if path.read_bytes() != data: raise ValueError(f'Asset differs: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    if args.review: review(model,png)
    print('Ant:', MD2.read(model).stats())

if __name__ == '__main__': main()
