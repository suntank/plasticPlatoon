"""Shared geometry and MD2 export for the ant and spider asset builders."""
from dataclasses import replace
import io
import math

import numpy as np
from PIL import Image, ImageDraw

from build_m16 import encode_md2
from md2_assets import MD2, ROOT, normal_table, raster


def unit(vector):
    return vector / np.linalg.norm(vector)


def rotation(roll=0, pitch=0, yaw=0):
    sr, sp, sy = np.sin(np.radians([roll, pitch, yaw]))
    cr, cp, cy = np.cos(np.radians([roll, pitch, yaw]))
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                     [-sp, cp*sr, cp*cr]])


def loft(mesh, sections, material, sides=8, reference=(0, 0, 1)):
    """Join elliptical rings with smooth normals and a continuous UV strip."""
    centers = np.array([center for center, _, _ in sections])
    tangents = [unit(b - a) for a, b in zip(centers, centers[1:])]
    axes = [tangents[0], *(unit(a + b) for a, b in zip(tangents, tangents[1:])), tangents[-1]]
    angles = np.arange(sides) * math.tau / sides
    rings = []
    for (center, width, height), axis in zip(sections, axes):
        across = unit(np.cross(reference, axis))
        up = np.cross(axis, across)
        rings.append(center + width * np.cos(angles)[:, None] * across
                     + height * np.sin(angles)[:, None] * up)
    start = len(mesh.vertices)
    for row, ring in enumerate(rings):
        before, after = rings[max(0, row - 1)], rings[min(row + 1, len(rings) - 1)]
        for col, point in enumerate(ring):
            across = ring[(col + 1) % sides] - ring[col - 1]
            along = after[col] - before[col]
            mesh.vertices.append(point.tolist())
            mesh.normals.append(unit(np.cross(across, along)).tolist())
    for row in range(len(rings) - 1):
        u, u_next = row / (len(rings) - 1), (row + 1) / (len(rings) - 1)
        for col in range(sides):
            v, v_next = col / sides, (col + 1) / sides
            a = start + row * sides + col
            b = start + row * sides + (col + 1) % sides
            mesh.faces.extend(([a, b, b + sides], [a, b + sides, a + sides]))
            uv_a, uv_b, uv_c, uv_d = [mesh.uv(material, x, y) for x, y in
                                     ((u, v), (u, v_next), (u_next, v_next), (u_next, v))]
            mesh.uvs.extend(([uv_a, uv_b, uv_c], [uv_a, uv_c, uv_d]))
    for ring, center, normal in ((rings[0][::-1], centers[0], -axes[0]),
                                 (rings[-1], centers[-1], axes[-1])):
        base = len(mesh.vertices)
        mesh.vertices.extend([center.tolist(), *ring.tolist()])
        mesh.normals.extend([normal.tolist()] * (sides + 1))
        hub_uv = mesh.uv(material, .5, .5)
        edge_uvs = [mesh.uv(material, .5 + .45*math.cos(angle), .5 + .45*math.sin(angle))
                    for angle in angles]
        for col in range(sides):
            next_col = (col + 1) % sides
            mesh.faces.append([base, base + col + 1, base + next_col + 1])
            mesh.uvs.append([hub_uv, edge_uvs[col], edge_uvs[next_col]])


def plate(mesh, profile, material, sides=10):
    loft(mesh, [((x, 0, z), width, height) for x, z, width, height in profile],
         material, sides=sides)


def transform(mesh, first, pivot, angles, offset=(0, 0, 0)):
    matrix = rotation(*angles)
    points = np.asarray(mesh.vertices[first:])
    mesh.vertices[first:] = ((points - pivot) @ matrix.T + pivot + offset).tolist()
    mesh.normals[first:] = (np.asarray(mesh.normals[first:]) @ matrix.T).tolist()


def stride(phase, length, height, stance=.58):
    # During stance the foot sweeps backward at constant speed. During the
    # shorter swing it lifts, arcs forward, then plants before the next stance.
    phase %= 1
    if phase < stance:
        return length * (.5 - phase / stance), 0
    swing = (phase - stance) / (1 - stance)
    return length * (swing * swing * (3 - 2 * swing) - .5), height * math.sin(math.pi * swing)


def encode_animation(frames, make_frame, skin_path):
    names, meshes = [], []
    for kind, count in frames:
        for i in range(count):
            names.append(f'{kind}{i:02}')
            meshes.append(make_frame(kind, i, count))
    first = meshes[0]
    for mesh in meshes:
        assert len(mesh.vertices) == len(first.vertices) and mesh.faces == first.faces
    data, _ = encode_md2([m.vertices for m in meshes], [m.normals for m in meshes],
                         first.faces, first.uvs, [skin_path], names)
    model = MD2.read(data)
    for frame, (p, normals) in enumerate(zip(model.positions, model.normals)):
        tris = p[model.faces]
        cross = np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0])
        light = normal_table()[normals][model.faces].mean(axis=1)
        invalid = np.flatnonzero(np.einsum('ij,ij->i', cross, light) >= 0)
        if invalid.size:
            raise ValueError(f'MD2 outward winding disagrees with normals at frame {frame}, faces {invalid.tolist()}')
    return data


def review_animation(model, png, output, poses, extent):
    decoded = MD2.read(model)
    image = Image.open(io.BytesIO(png))
    size = 260
    sheet = Image.new('RGB', (3*size, len(poses)*(size+20)), (24, 27, 32))
    draw = ImageDraw.Draw(sheet)
    for row, (frame, title) in enumerate(poses):
        one = replace(decoded, positions=decoded.positions[frame:frame+1], normals=decoded.normals[frame:frame+1])
        for col, angle in enumerate((36, 94, 151)):
            pic, mask = raster(one, image, angle, size, (np.array([0., 0., -3.]), extent),
                               elevation=24, cull_front=True)
            y = row * (size + 20)
            sheet.paste((95, 101, 107), (col*size, y+20, (col+1)*size, y+20+size))
            sheet.paste(pic, (col*size, y+20), Image.fromarray(mask))
            draw.text((col*size+8, y+4), f'{title} / {angle} deg', fill='white')
    path = ROOT/'tools/assets/review'/output
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
