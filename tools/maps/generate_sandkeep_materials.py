#!/usr/bin/env python3
"""Generate original, deterministic Sandkeep game materials and a seamless sky.

Requires Python 3, Pillow, and NumPy. WAL files carry all four indexed mipmaps;
PNG files retain the original colors for renderers that support replacements.
Terrain and fortress artwork is procedural. The six alphabet block faces are
copied from this repository's Sandbox artwork, preserved in material_sources.
Indexed WAL mipmaps use the original project palette defined in build_bootstrap.py.
Truecolor artwork is independent of palette indexing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
from platoon_palette import load_palette, quantize_opaque

SAND_COLORS = ((235, 211, 199), (199, 171, 155), (167, 139, 119), (135, 107, 87))
TERRAIN_NAMES = ("soil", "grass")
SOIL_COLORS = ((122, 92, 66), (111, 83, 60), (101, 76, 55), (91, 67, 49),
               (81, 59, 44), (71, 52, 40), (62, 46, 35), (52, 39, 30), (43, 33, 27))
GRASS_COLORS = ((67, 101, 43), (73, 111, 47), (79, 121, 51), (87, 131, 56),
                (94, 141, 60), (102, 149, 65), (111, 157, 70), (121, 166, 77))
# Preserved originals: release/baseq2/textures/sandbox/abc_block_[a-f].png.
ALPHABET_SOURCES = {"abc_" + letter: ROOT / "tools/maps/material_sources" / ("abc_block_" + letter + ".png")
                    for letter in "abcdef"}
# func_button uses EF_ANIM01 while idle, and EF_ANIM23 after activation.
# Each WAL chain therefore contains two idle and two active frames. Quake II
# reads the explicit WAL animname chain; Quake I's +0/+a names do not apply.
BUTTON_ANIMATIONS = {
    "switch_armory": ("switch_armory", "switch_armory_idle", "switch_armory_on", "switch_armory_on_alt"),
    "switch_radio": ("switch_radio", "switch_radio_idle", "switch_radio_on", "switch_radio_on_alt"),
}
# An intentionally tiny, original block alphabet avoids font dependencies and
# remains legible with nearest-neighbor filtering at low display resolutions.
FONT = {
    "A": ["01110", "11011", "11011", "11111", "11011", "11011", "11011"],
    "B": ["11110", "11011", "11011", "11110", "11011", "11011", "11110"],
    "C": ["01111", "11000", "11000", "11000", "11000", "11000", "01111"],
    "D": ["11110", "11011", "11011", "11011", "11011", "11011", "11110"],
    "E": ["11111", "11000", "11000", "11110", "11000", "11000", "11111"],
    "F": ["11111", "11000", "11000", "11110", "11000", "11000", "11000"],
    "G": ["01111", "11000", "11000", "11011", "11011", "11011", "01111"],
    "H": ["11011", "11011", "11011", "11111", "11011", "11011", "11011"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00011", "00011", "00011", "11011", "11011", "01110"],
    "K": ["11011", "11011", "11110", "11100", "11110", "11011", "11011"],
    "L": ["11000", "11000", "11000", "11000", "11000", "11000", "11111"],
    "M": ["11011", "11111", "11111", "11011", "11011", "11011", "11011"],
    "N": ["11011", "11011", "11111", "11111", "11011", "11011", "11011"],
    "O": ["01110", "11011", "11011", "11011", "11011", "11011", "01110"],
    "P": ["11110", "11011", "11011", "11110", "11000", "11000", "11000"],
    "Q": ["01110", "11011", "11011", "11011", "11011", "01110", "00011"],
    "R": ["11110", "11011", "11011", "11110", "11110", "11011", "11011"],
    "S": ["01111", "11000", "11000", "01110", "00011", "00011", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["11011", "11011", "11011", "11011", "11011", "11011", "01110"],
    "V": ["11011", "11011", "11011", "11011", "11011", "01010", "00100"],
    "W": ["11011", "11011", "11011", "11011", "11111", "11111", "11011"],
    "X": ["11011", "11011", "01010", "00100", "01010", "11011", "11011"],
    "Y": ["11011", "11011", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00011", "00010", "00100", "01000", "11000", "11111"],
    "0": ["01110", "11011", "11011", "11011", "11011", "11011", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "11011", "00011", "00110", "01100", "11000", "11111"],
    "3": ["11110", "00011", "00011", "01110", "00011", "00011", "11110"],
    "4": ["11011", "11011", "11011", "11111", "00011", "00011", "00011"],
    "5": ["11111", "11000", "11000", "11110", "00011", "00011", "11110"],
    "6": ["01110", "11000", "11000", "11110", "11011", "11011", "01110"],
    "7": ["11111", "00011", "00010", "00100", "00100", "00100", "00100"],
    "8": ["01110", "11011", "11011", "01110", "11011", "11011", "01110"],
    "9": ["01110", "11011", "11011", "01111", "00011", "00011", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00011", "00010", "00100", "01000", "11000", "10000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    " ": ["00000"] * 7,
}


def rgb(values: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(values, 0, 255).astype(np.uint8), "RGB")


def field(seed: int, size: int = 128) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y, x = np.indices((size, size))
    return x, y, rng.normal(0, 1, (size, size))


def paint(base, shade):
    return rgb(np.array(base)[None, None, :] + shade[:, :, None])


def sand_ramp(im):
    """Posterize original sand artwork to four authored warm RGB colors."""
    colors = np.array(SAND_COLORS, dtype=np.int32)
    pixels = np.array(im, dtype=np.int32)
    indices = ((pixels[:, :, None, :] - colors[None, None, :, :]) ** 2).sum(axis=3).argmin(axis=2)
    return rgb(colors[indices])


def text(draw, center_x, y, value, scale, color):
    width = (6 * len(value) - 1) * scale
    left = int(center_x - width / 2)
    for index, char in enumerate(value.upper()):
        for row, pattern in enumerate(FONT[char]):
            for col, bit in enumerate(pattern):
                if bit == "1":
                    x0 = left + (index * 6 + col) * scale
                    y0 = y + row * scale
                    draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=color)


def bolt(draw, x, y, color=(171, 181, 167)):
    draw.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(31, 40, 32))
    draw.rectangle((x - 2, y - 2, x + 2, y + 2), fill=color)
    draw.line((x - 1, y, x + 1, y), fill=(66, 74, 63))


def panel(color=(40, 65, 50), accent=(228, 200, 104)):
    im = Image.new("RGB", (256, 128), color)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 255, 127), fill=(31, 40, 32))
    d.rectangle((3, 3, 252, 124), fill=accent)
    d.rectangle((7, 7, 248, 120), fill=color)
    for x in (13, 242):
        for y in (13, 114):
            bolt(d, x, y)
    return im, d


def terrain_materials() -> dict[str, Image.Image]:
    """Periodic garden loam and rooted lawn at the scale of a toy soldier.

    Every noise lattice wraps and every pebble, root and blade is drawn across
    the tile boundary. The textures have no rectangular edges or panel seams.
    A 256-unit tile at scale 1 makes individual blades roughly 6--18 units long.
    """
    size = 256
    rng = np.random.default_rng(7312)
    y, x = np.indices((size, size))

    def noise(cells):
        lattice = rng.uniform(-1, 1, (cells, cells))
        u, v = x * cells / size, y * cells / size
        ix, iy = u.astype(int), v.astype(int)
        fx, fy = u - ix, v - iy
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        top = lattice[iy, ix] * (1 - fx) + lattice[iy, (ix + 1) % cells] * fx
        bottom = lattice[(iy + 1) % cells, ix] * (1 - fx) + lattice[(iy + 1) % cells, (ix + 1) % cells] * fx
        return top * (1 - fy) + bottom * fy

    def wrapped_line(draw, points, fill, width=1):
        for dy in (-size, 0, size):
            for dx in (-size, 0, size):
                draw.line([(px + dx, py + dy) for px, py in points], fill=fill, width=width)

    def wrapped_polygon(draw, points, fill):
        for dy in (-size, 0, size):
            for dx in (-size, 0, size):
                draw.polygon([(px + dx, py + dy) for px, py in points], fill=fill)

    shade = noise(4) * 11 + noise(17) * 12 + noise(43) * 4 + rng.normal(0, 2.4, (size, size))
    soil = rgb(np.array((103, 79, 59)) + shade[:, :, None] * np.array((1., .85, .65)))
    d = ImageDraw.Draw(soil)
    for _ in range(230):
        px, py = rng.integers(0, size, 2)
        rx, ry = rng.integers(1, 4, 2)
        tone = SOIL_COLORS[int(rng.integers(len(SOIL_COLORS)))]
        for dy in (-size, 0, size):
            for dx in (-size, 0, size):
                d.ellipse((px - rx + dx, py - ry + dy, px + rx + dx, py + ry + dy), fill=(37, 29, 24))
                d.ellipse((px - rx + dx, py - ry + dy, px + rx - 1 + dx, py + ry - 1 + dy), fill=tone)
    # Sparse exposed rootlets add garden character to the loam and vertical
    # banks, with restrained contrast so the surface does not become gravel.
    for _ in range(17):
        px, py = rng.integers(0, size, 2)
        direction = rng.uniform(0, math.tau)
        points = [(int(px), int(py))]
        for _ in range(int(rng.integers(3, 6))):
            direction += rng.uniform(-.55, .55)
            step = rng.uniform(5, 10)
            points.append((points[-1][0] + int(math.cos(direction) * step),
                           points[-1][1] + int(math.sin(direction) * step)))
        wrapped_line(d, [(px + 1, py + 1) for px, py in points], (32, 25, 21), 2)
        wrapped_line(d, points, (128, 97, 67))
        tip = points[len(points) // 2]
        wrapped_line(d, (tip, (tip[0] + int(rng.integers(-7, 8)), tip[1] + int(rng.integers(-7, 8)))), (111, 82, 57))

    coverage = np.clip((noise(5) + .85) * 2, .12, 1)
    shade = noise(11) * 10 + noise(31) * 6 + rng.normal(0, 2, (size, size))
    turf = np.array((91, 107, 51)) + shade[:, :, None] * np.array((.8, 1., .6))
    ground = np.array(soil) * (1 - coverage[:, :, None]) + turf * coverage[:, :, None]
    grass = rgb(ground)
    d = ImageDraw.Draw(grass)
    for _ in range(1150):
        px, py = rng.integers(0, size, 2)
        if coverage[py, px] < .6 and rng.random() > coverage[py, px]:
            continue
        orientation = rng.uniform(0, math.tau)
        for _ in range(int(rng.integers(2, 5))):
            direction = orientation + rng.uniform(-1.2, 1.2)
            length = rng.uniform(6, 17)
            tx = int(px + math.cos(direction) * length)
            ty = int(py + math.sin(direction) * length)
            side_x, side_y = -math.sin(direction) * 1.3, math.cos(direction) * 1.3
            blade = [(int(px + side_x), int(py + side_y)), (tx, ty), (int(px - side_x), int(py - side_y))]
            wrapped_line(d, [(int(px) + 1, int(py) + 1), (tx + 1, ty + 1)], (42, 60, 31), 2)
            tone = GRASS_COLORS[int(rng.integers(len(GRASS_COLORS)))]
            if rng.random() < .045:
                tone = ((144, 122, 73), (124, 103, 62), (137, 139, 80), (110, 117, 62))[int(rng.integers(4))]
            wrapped_polygon(d, blade, tone)
    return {"soil": soil, "grass": grass}


def switch_face(label: str, active: bool, alternate: bool) -> Image.Image:
    """A compact, readable press plate, designed to fit an 80 by 48 unit face.

    The housing, bevel and finger ridges stay fixed while the indicator and pad
    change state. Both idle frames remain visibly idle, and both active frames
    remain green, so legacy button animation never flashes the wrong state.
    """
    radio = label == "RADIO"
    im = Image.new("RGB", (128, 64), (31, 40, 32))
    d = ImageDraw.Draw(im)
    d.rectangle((1, 1, 126, 62), fill=(106, 119, 103))
    d.rectangle((3, 3, 124, 60), fill=(37, 59, 65) if radio else (52, 65, 42))
    d.line((4, 4, 123, 4), fill=(140, 155, 133))
    d.line((4, 59, 123, 59), fill=(15, 26, 23))
    for bx in (7, 120):
        for by in (7, 56):
            bolt(d, bx, by, (128, 141, 120))
    cream = (235, 223, 173)
    text(d, 62, 7, label, 1, cream)
    d.ellipse((105, 7, 111, 13), fill=(14, 26, 21))
    indicator = (99, 191, 75) if active else ((183, 91, 36) if alternate else (223, 135, 47))
    d.ellipse((107, 9, 109, 11), fill=indicator)
    # A deep socket surrounds the raised pad; it remains easy to distinguish
    # from decorative louvers and colored crates elsewhere in the map.
    d.rectangle((13, 18, 114, 48), fill=(10, 20, 17))
    d.rectangle((16, 20, 111, 46), fill=(84, 98, 82))
    pad = ((53, 125, 54) if alternate else (47, 113, 48)) if active else ((48, 109, 125) if radio else (167, 113, 35))
    d.rectangle((18, 21, 109, 44), fill=pad)
    d.line((18, 21, 109, 21), fill=(157, 192, 129) if active else ((124, 177, 188) if radio else (225, 179, 89)))
    d.line((18, 44, 109, 44), fill=(24, 53, 29) if active else (52, 47, 25))
    for px in (23, 27, 100, 104):
        d.line((px, 27, px, 38), fill=(27, 50, 36) if active else (24, 51, 57) if radio else (83, 59, 24))
        d.line((px + 1, 27, px + 1, 38), fill=(129, 160, 105) if active else (118, 163, 172) if radio else (207, 158, 77))
    text(d, 64, 26, "LINK" if radio else "OPEN", 2, cream)
    text(d, 64, 53, ("OFFLINE" if radio else "UNLOCKED") if active else "PRESS", 1, cream)
    return im


def materials(palette: bytes | None = None):
    # Truecolor source artwork is independent of indexed export colors.
    out = {}
    x, y, n = field(300)
    grains = 2.2 * n + 1.5 * np.sin(x * math.tau / 128) * np.sin(y * math.tau / 64)
    grains += np.where(n > 1.95, 9, 0) - np.where(n < -2.05, 10, 0)
    out["sand"] = sand_ramp(paint((199, 171, 155), grains))
    layers = 4 * np.sin(y * math.tau / 32 + .6 * np.sin(x * math.tau / 128))
    layers += 1.5 * np.sin(y * math.tau / 8 + np.sin(x * math.tau / 64))
    out["sand_wall"] = sand_ramp(paint((167, 139, 119), layers + grains * .9))
    # Match the intact sand wall right up to every border. Restrained fissures
    # hint at a brittle section without outlining or advertising a secret door.
    fissures = [
        [(67, 22), (62, 34), (66, 43), (59, 54), (63, 65), (58, 76), (61, 87), (55, 105)],
        [(65, 43), (77, 47), (83, 58), (93, 62)],
        [(60, 55), (49, 60), (44, 72), (35, 77)],
        [(60, 86), (74, 90), (80, 101)],
    ]
    for name, offset in (("sand_cracked", 0), ("sand_cracked_offset", -64)):
        # Offset only the fissure overlay, never the sand grain. The wrapped
        # version centers a crack on world S=0 without breaking wall UVs.
        im = out["sand_wall"].copy()
        d = ImageDraw.Draw(im)
        for wrap in (-128, 0, 128):
            for points in fissures:
                shifted = [(px + offset + wrap, py) for px, py in points]
                d.line([(px + 1, py) for px, py in shifted], fill=(199, 171, 155), width=1)
                d.line(shifted, fill=(135, 107, 87), width=1)
        out[name] = im

    out.update(terrain_materials())
    for name, source in ALPHABET_SOURCES.items():
        with Image.open(source) as im:
            out[name] = im.convert("RGB")

    x, y, n = field(417)
    grain = np.sin(y * math.tau / 16 + 1.7 * np.sin(x * math.tau / 128))
    grain += .8 * np.sin(y * math.tau / 8 + 2 * np.sin(x * math.tau / 128 + .8))
    shade = 4 * grain + 2 * n + (y // 64) * 8
    shade[(y % 64) < 2] -= 28
    shade[(y % 64) == 2] += 10
    out["wood"] = paint((138, 97, 56), shade)
    r = np.sqrt(((x - 64) * .94) ** 2 + ((y - 64) * 1.07) ** 2)
    out["wood_end"] = paint((146, 106, 65), 6 * np.sin(r * .6 + .1 * n) + 2 * n)

    # One complete gate face. Planks run vertically; forged straps and studs
    # are solid moving map geometry, avoiding a second painted strap beneath.
    x, y, n = field(418, 256)
    grain = 4 * np.sin(x * math.tau / 16 + 1.1 * np.sin(y * math.tau / 256))
    grain += 2.5 * np.sin(x * math.tau / 7 + .4 * np.sin(y * math.tau / 128))
    shade = grain + 1.5 * n + ((x // 32) % 3 - 1) * 7
    shade[(x % 32) < 2] -= 31
    shade[(x % 32) == 2] += 16
    # A subdued knot breaks up the machine-perfect grain without disrupting
    # plank edges or introducing a prominent repeating knot grid.
    knot = np.sqrt(((x - 79) * 1.6) ** 2 + ((y - 139) * .45) ** 2)
    shade += np.sin(knot * .55) * np.clip((25 - knot) / 25, 0, 1) * 8
    out["gate_wood"] = paint((126, 88, 49), shade)

    for label, frames in BUTTON_ANIMATIONS.items():
        for index, name in enumerate(frames):
            out[name] = switch_face("RADIO" if label == "switch_radio" else "ARMORY", index >= 2, bool(index & 1))

    # A physical recessed lens for small ceiling/corridor fixtures. Emission is
    # supplied only by the map's selected face (LIGHT, value 180), so fixture
    # sides and incidental uses never become unintended light sources.
    im = Image.new("RGB", (32, 32), (45, 48, 37))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 31, 31), outline=(132, 141, 116))
    d.rectangle((2, 2, 29, 29), fill=(95, 100, 78))
    d.rectangle((4, 4, 27, 27), fill=(255, 255, 211))
    d.rectangle((5, 5, 26, 26), outline=(255, 255, 255))
    # The shallow cage reads as a lens grid at either native size or stretched
    # over a narrow rectangular bar; avoid busy high-contrast checker patterns.
    for k in (11, 20):
        d.line((k, 4, k, 27), fill=(151, 159, 123))
        d.line((4, k, 27, k), fill=(151, 159, 123))
        d.line((k + 1, 5, k + 1, 26), fill=(255, 255, 211))
        d.line((5, k + 1, 26, k + 1), fill=(255, 255, 211))
    for bx in (2, 29):
        for by in (2, 29):
            d.point((bx, by), fill=(195, 199, 173))
    out["lamp"] = im

    for name, color, seed in [
        ("plastic_green", (77, 117, 69), 81),
        ("plastic_red", (178, 61, 43), 82),
        ("plastic_blue", (52, 114, 151), 83),
    ]:
        x, y, n = field(seed)
        out[name] = paint(color, .9 * n + 1.3 * np.cos(x * math.tau / 128))
        if name in ("plastic_blue", "plastic_green"):
            # Curved garden toys use seamless molded plastic. Keep the same
            # resin color and fine grain, without crate/panel edge highlights.
            out[name + "_smooth"] = out[name].copy()
        d = ImageDraw.Draw(out[name])
        d.line((0, 0, 127, 0), fill=tuple(min(255, c + 13) for c in color))
        d.line((0, 0, 0, 127), fill=tuple(min(255, c + 9) for c in color))
        d.line((127, 0, 127, 127), fill=tuple(max(0, c - 14) for c in color))
        d.line((0, 127, 127, 127), fill=tuple(max(0, c - 14) for c in color))

    x, y, n = field(91)
    out["trim"] = paint((52, 63, 42), n + np.cos(y * math.tau / 128) * 2)
    d = ImageDraw.Draw(out["trim"])
    d.line((0, 0, 127, 0), fill=(79, 89, 59))
    d.line((0, 127, 127, 127), fill=(29, 38, 26))

    # Seamless stock for rails, gate straps and brackets. The separate metal
    # material below is a vent panel and should never wrap around narrow trim.
    # Keep brushed variation restrained, and use the same period on both edges.
    brush = 1.2 * np.sin(y * math.tau / 8) + .6 * np.sin(y * math.tau / 4)
    brush += .5 * np.sin(x * math.tau / 128 + y * math.tau / 16)
    out["iron"] = paint((67, 67, 51), brush)

    out["metal"] = paint((83, 96, 91), 1.5 * n)
    d = ImageDraw.Draw(out["metal"])
    d.rectangle((1, 1, 126, 126), outline=(120, 135, 124), width=2)
    d.rectangle((5, 5, 122, 122), outline=(39, 52, 47), width=2)
    for row in range(18, 111, 10):
        d.rectangle((20, row, 107, row + 4), fill=(33, 45, 40))
        d.line((21, row + 5, 106, row + 5), fill=(116, 129, 116))
    for bx in (12, 115):
        for by in (12, 115):
            bolt(d, bx, by)

    cream = (242, 230, 180)
    yellow = (239, 197, 74)
    im, d = panel()
    text(d, 128, 19, "OPERATION", 2, yellow)
    text(d, 128, 45, "SANDKEEP", 4, cream)
    d.line((35, 87, 220, 87), fill=yellow, width=2)
    text(d, 128, 100, "PLASTIC PLATOON", 1, cream)
    out["sign_start"] = im

    im, d = panel((43, 66, 45))
    text(d, 128, 22, "SUPPLY DEPOT", 2, yellow)
    text(d, 128, 53, "ARMORY", 4, cream)
    text(d, 128, 99, "RESUPPLY HERE", 1, cream)
    out["sign_armory"] = im

    im, d = panel((40, 66, 84), (123, 187, 195))
    text(d, 128, 23, "UPLINK CONTROL", 2, (157, 213, 216))
    text(d, 128, 53, "RADIO", 4, cream)
    text(d, 128, 99, "AUTHORIZED TROOPS", 1, cream)
    out["sign_radio"] = im

    im, d = panel((100, 37, 26), yellow)
    for k in range(-10, 29):
        ox = k * 16
        d.polygon([(ox, 7), (ox + 8, 7), (ox - 3, 18), (ox - 11, 18)], fill=(28, 33, 25))
        d.polygon([(ox, 109), (ox + 8, 109), (ox - 3, 120), (ox - 11, 120)], fill=(28, 33, 25))
    text(d, 128, 35, "DANGER", 4, cream)
    text(d, 128, 80, "HOSTILE AIRSPACE", 2, yellow)
    out["sign_boss"] = im

    im, d = panel((42, 85, 60), (169, 205, 128))
    text(d, 128, 20, "RALLY POINT", 2, yellow)
    text(d, 128, 48, "EXTRACT", 4, cream)
    # Upward arrow: it can sit over a door without implying a lateral route.
    d.polygon([(128, 88), (114, 102), (122, 102), (122, 113), (134, 113), (134, 102), (142, 102)], fill=cream)
    out["sign_exit"] = im

    im = out["trim"].copy()
    d = ImageDraw.Draw(im)
    d.rectangle((6, 6, 121, 121), outline=(230, 194, 74), width=4)
    d.polygon([(39, 29), (69, 29), (99, 64), (69, 99), (39, 99), (68, 64)], fill=(239, 202, 79))
    out["marker"] = im

    im = out["plastic_green"].resize((256, 256), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(im)
    d.rectangle((5, 5, 250, 250), outline=yellow, width=6)
    d.rectangle((20, 20, 235, 235), outline=(169, 188, 127), width=2)
    d.ellipse((43, 43, 212, 212), outline=cream, width=6)
    d.rectangle((82, 78, 103, 177), fill=cream)
    d.rectangle((152, 78, 173, 177), fill=cream)
    d.rectangle((104, 116, 151, 137), fill=cream)
    for bx in (16, 239):
        for by in (16, 239):
            bolt(d, bx, by)
    out["helipad"] = im
    # Sky faces render the separate environment cube. This invisible material
    # supplies RAD emission, which must remain neutral daylight rather than
    # tinting all outdoor bounced light blue/green.
    out["sky"] = Image.new("RGB", (64, 64), (235, 235, 235))
    return out


def write_wal(path: Path, name: str, image: Image.Image, palette: bytes, flags=0, animation_next=""):
    w, h = image.size
    if w & (w - 1) or h & (h - 1) or min(w, h) < 8:
        raise ValueError("WAL dimensions must be powers of two and at least 8")
    levels = []
    for mip in range(4):
        sized = image.resize((w >> mip, h >> mip), Image.Resampling.BOX)
        indices = quantize_opaque(sized, palette)
        levels.append(indices.tobytes())
    offsets, pos = [], 100
    for data in levels:
        offsets.append(pos)
        pos += len(data)
    encoded = name.encode("ascii")
    encoded_next = animation_next.encode("ascii")
    if len(encoded) >= 32 or len(encoded_next) >= 32:
        raise ValueError("WAL name too long")
    header = struct.pack("<32sII4I32siii", encoded, w, h, *offsets, encoded_next, flags, 0, 0)
    path.write_bytes(header + b"".join(levels))


def skyboxes(directory: Path):
    # Inverse of gl1_warp.c's R_MakeSkyVec, including its vertical texture flip.
    # Sampling one world-direction function makes all six cube faces seamless.
    axes = ((3, -1, 2), (-3, 1, 2), (1, 3, 2), (-1, -3, 2), (-2, -1, 3), (2, -1, -3))
    suffixes = ("rt", "lf", "bk", "ft", "up", "dn")
    size = 256
    yy, xx = np.indices((size, size))
    s = 2 * (xx + .5) / size - 1
    t = 1 - 2 * (yy + .5) / size
    bases = (s, t, np.ones_like(s))
    sun = np.array((.36, -.36, .86))
    sun /= np.linalg.norm(sun)
    results = []
    for axis, suffix in zip(axes, suffixes):
        vec = np.stack([bases[abs(k) - 1] * (1 if k > 0 else -1) for k in axis], axis=-1)
        vec /= np.linalg.norm(vec, axis=2, keepdims=True)
        x, y, z = vec[:, :, 0], vec[:, :, 1], vec[:, :, 2]
        up = np.clip(z, 0, 1) ** .55
        # Original blue-gray daylight endpoints remain stable in truecolor.
        horizon = np.array((179, 199, 211))
        zenith = np.array((91, 135, 155))
        colors = horizon[None, None, :] * (1 - up[:, :, None]) + zenith[None, None, :] * up[:, :, None]
        # Soft, stylized cloud banks. All frequencies depend on world direction.
        cloud = np.sin(9 * x + 2.5 * y + 1.7 * z) + .6 * np.cos(14 * y - 5 * x + 2 * z)
        cloud += .3 * np.sin(27 * x + 9 * y - 3 * z)
        cloud = np.clip((cloud - .6) * .8, 0, 1) * np.clip(z * 4, 0, 1) * np.clip((.9 - z) * 3, 0, 1)
        colors = colors * (1 - cloud[:, :, None] * .66) + np.array((203, 215, 223)) * cloud[:, :, None] * .66
        sun_dot = np.sum(vec * sun, axis=2)
        halo = np.clip((sun_dot - .97) / .03, 0, 1) ** 3 * .4
        sun_disc = np.clip((sun_dot - .9987) / .0007, 0, 1)
        sun_amount = np.maximum(halo, sun_disc)
        colors = colors * (1 - sun_amount[:, :, None]) + np.array((235, 235, 235)) * sun_amount[:, :, None]
        path = directory / ("sandkeep" + suffix + ".tga")
        rgb(colors).save(path, compression="tga_rle")
        results.append(path)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--basedir", type=Path, default=ROOT / "baseq2")
    p.add_argument("--palette", type=Path, help="optional copy of the generated project colormap PCX")
    p.add_argument("--compile-colormap-dir", type=Path)
    p.add_argument("--preview", type=Path)
    a = p.parse_args()
    palette = load_palette(a.palette)
    dest = a.basedir / "textures/sandkeep"
    dest.mkdir(parents=True, exist_ok=True)
    env = a.basedir / "env"
    env.mkdir(parents=True, exist_ok=True)
    generated = materials(palette)
    animation_next = {frame: frames[(index + 1) % len(frames)]
                      for frames in BUTTON_ANIMATIONS.values()
                      for index, frame in enumerate(frames)}
    manifest = {"generator": "tools/maps/generate_sandkeep_materials.py", "palette_sha256": hashlib.sha256(palette).hexdigest(),
                "artwork": "Procedural Sandkeep artwork and reused repository Sandbox alphabet blocks", "materials": {}}
    for name, im in generated.items():
        if name in ALPHABET_SOURCES:
            (dest / (name + ".png")).write_bytes(ALPHABET_SOURCES[name].read_bytes())
        else:
            im.save(dest / (name + ".png"), optimize=True)
        next_name = "sandkeep/" + animation_next[name] if name in animation_next else ""
        write_wal(dest / (name + ".wal"), "sandkeep/" + name, im, palette, flags=4 if name == "sky" else 0,
                  animation_next=next_name)
        manifest["materials"]["sandkeep/" + name] = {"width": im.width, "height": im.height, "surface_flags": 4 if name == "sky" else 0,
            "wal_sha256": hashlib.sha256((dest / (name + ".wal")).read_bytes()).hexdigest(),
            "png_sha256": hashlib.sha256((dest / (name + ".png")).read_bytes()).hexdigest()}
        if next_name:
            manifest["materials"]["sandkeep/" + name]["animation_next"] = next_name
        if name in ALPHABET_SOURCES:
            manifest["materials"]["sandkeep/" + name].update(
                source=ALPHABET_SOURCES[name].relative_to(ROOT).as_posix(),
                source_sha256=hashlib.sha256(ALPHABET_SOURCES[name].read_bytes()).hexdigest(),
                indexed_fallback="Nearest opaque project-palette color; original PNG preserved")
        if name in TERRAIN_NAMES:
            manifest["materials"]["sandkeep/" + name].update(
                tileable=True, indexed_fallback="Nearest opaque project-palette color")
    manifest["skybox"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in skyboxes(env)}
    (dest / "materials.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if a.compile_colormap_dir:
        a.compile_colormap_dir.mkdir(parents=True, exist_ok=True)
        palette_image = Image.new("P", (16, 16))
        palette_image.putpalette(palette)
        palette_image.putdata(list(range(256)))
        palette_image.save(a.compile_colormap_dir / "colormap.pcx")
    if a.preview:
        rows = math.ceil(len(generated) / 5)
        canvas = Image.new("RGB", (5 * 270, rows * 168), (24, 32, 32))
        draw = ImageDraw.Draw(canvas)
        for index, (name, im) in enumerate(generated.items()):
            thumb = im.copy()
            thumb.thumbnail((256, 128), Image.Resampling.NEAREST)
            x, y = (index % 5) * 270 + 7, (index // 5) * 168 + 7
            canvas.paste(thumb, (x + (256 - thumb.width) // 2, y))
            draw.text((x + 3, y + 137), name, fill=(224, 225, 206))
        a.preview.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(a.preview)
    print(f"Generated {len(generated)} WAL/PNG pairs and six skybox faces under {a.basedir}")


if __name__ == "__main__":
    main()
