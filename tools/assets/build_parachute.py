#!/usr/bin/env python3
"""Build the soldier's original canvas parachute and suspension lines."""

import argparse
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from build_m16 import encode_md2, vertex_normals


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path("models/objects/parachute")
SKIN = DIRECTORY / "canvas.png"
MODEL = DIRECTORY / "tris.md2"
PANEL_COUNT = 12
COLORS = [(176, 159, 107), (158, 142, 94), (125, 110, 75), (82, 67, 43)]


def build_assets():
    vertices, faces, materials = [], [], []
    angles = np.arange(PANEL_COUNT) * (2 * np.pi / PANEL_COUNT)

    def ring(radius, height):
        indices = list(range(len(vertices), len(vertices) + PANEL_COUNT))
        vertices.extend(zip(radius * np.cos(angles), radius * np.sin(angles), [height] * PANEL_COUNT))
        return indices

    def triangle(a, b, c, material):
        faces.append((a, b, c))
        materials.append(material)

    # A closed shell keeps the canopy visible from the ground.
    for underside in (False, True):
        center = len(vertices)
        vertices.append((0, 0, 116 - 2 * underside))
        inner = ring(20, 113 - 2 * underside)
        middle = ring(35, 102 - 2 * underside)
        outer = ring(43, 84 - 2 * underside)
        for panel in range(PANEL_COUNT):
            following = (panel + 1) % PANEL_COUNT
            material = 2 if underside else panel % 2
            panel_faces = [(center, inner[panel], inner[following])]
            for inside, outside in ((inner, middle), (middle, outer)):
                panel_faces.extend(((inside[panel], outside[panel], outside[following]),
                                    (inside[panel], outside[following], inside[following])))
            for a, b, c in panel_faces:
                triangle(a, c if underside else b, b if underside else c, material)
        if underside:
            for panel in range(PANEL_COUNT):
                following = (panel + 1) % PANEL_COUNT
                triangle(rim[panel], outer[panel], outer[following], 2)
                triangle(rim[panel], outer[following], rim[following], 2)
        else:
            rim = outer

    for panel in (1, 5, 7, 11):
        top = np.asarray(vertices[rim[panel]])
        shoulder = np.array([-3, 8 if top[1] > 0 else -8, 23])
        axis = top - shoulder
        across = np.cross(axis, [0, 0, 1])
        across *= 0.85 / np.linalg.norm(across)
        perpendicular = np.cross(axis, across) / np.linalg.norm(axis)
        start = len(vertices)
        for end in (shoulder, top):
            vertices.extend(end + offset for offset in (across, perpendicular, -across, -perpendicular))
        for edge in range(4):
            a = start + edge
            b = start + (edge + 1) % 4
            triangle(a, b, b + 4, 3)
            triangle(a, b + 4, a + 4, 3)

    skin = Image.new("RGB", (256, 256))
    pixels = skin.load()
    for index, color in enumerate(COLORS):
        for y in range(256):
            for x in range(64):
                grain = ((x * 13 + y * 7) % 11) - 5
                pixels[index * 64 + x, y] = tuple(channel + grain for channel in color)
    texture = BytesIO()
    skin.save(texture, format="PNG")

    points = np.asarray(vertices)
    faces = np.asarray(faces)
    normals = vertex_normals(points, faces)
    uvs = [[((64 * material + x) / 256, y / 256) for x, y in ((6, 6), (58, 6), (32, 246))]
           for material in materials]
    # Quake renders linked models at the body frame, including stand01 (146).
    frames = 147
    model, _ = encode_md2(np.repeat(points[None], frames, axis=0),
                          np.repeat(normals[None], frames, axis=0),
                          faces, uvs, [SKIN.as_posix()], ["canopy"] * frames)
    return {SKIN: texture.getvalue(), MODEL: model}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="check that shipped media match the generator")
    args = parser.parse_args()
    for relative, data in build_assets().items():
        path = ROOT / "baseq2" / relative
        if args.verify:
            if path.read_bytes() != data:
                raise SystemExit(f"Stale parachute asset: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
