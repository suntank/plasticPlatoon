#!/usr/bin/env python3
"""Generate unmarked, Quake II construction toy prefabs."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image

from generate_bathroom import BASE, disc, material, rim, rounded_rectangle
from generate_bath_prefabs import HEADER, bevel, block, loft, straight_oval
from generate_sandkeep_materials import write_wal
from generate_switchyard import box
from platoon_palette import load_palette

PITCH = 64
STUD_HEIGHT = 8


def timber_texture(color, *, end=False):
    image = Image.new('RGB', (128, 128))
    pixels = image.load()
    for y in range(128):
        for x in range(128):
            if end:
                u = (x + 64) % 128 - 64
                v = (y + 64) % 128 - 64
                radius = (u * u + v * v * .84) ** .5
                grain = 9 * cos(radius * 1.14 + 1.6 * sin(u / 12) * cos(v / 11))
                grain += 4 * sin(radius * .47)
            else:
                wave = sin(tau * x / 128) + .4 * cos(tau * x / 64)
                grain = 10 * sin(tau * y / 16 + wave) + 5 * cos(tau * y / 4 + wave)
                grain += 4 * sin(tau * y / 64)
            grain += (x * 31 ^ y * 17) % 5 - 2
            pixels[x, y] = tuple(max(0, min(255, round(channel + grain))) for channel in color)
    return image


def write_materials():
    folder = BASE / 'textures/bathroom'
    palette = load_palette()
    finishes = {
        'kit_beech': ((184, 139, 95), False),
        'kit_beech_end': ((198, 152, 102), True),
        'kit_log': ((130, 79, 51), False),
        'kit_log_end': ((161, 103, 62), True),
    }
    for name, (rgb, end) in finishes.items():
        image = timber_texture(rgb, end=end)
        image.save(folder / (name + '.png'))
        write_wal(folder / (name + '.wal'), material(name), image, palette)


def outline(cx, cy, columns, rows, z, scale=1):
    rx, ry = columns * PITCH / 2, rows * PITCH / 2
    return [(cx + x * scale, cy + y * scale, z)
            for x, y, _ in rounded_rectangle(0, 0, rx, ry, 3, 0)]


def stud(x, y, base, tint):
    return loft([disc(x, y, r, r, z) for z, r in (
        (base, 18), (base + STUD_HEIGHT - 2, 18), (base + STUD_HEIGHT, 16))], tint)


def brick(columns, rows, height, tint, *, has_studs=True, x=0, z=0):
    def outer(level):
        return outline(x, 0, columns, rows, level)

    def inner(level):
        return rounded_rectangle(x, 0, columns * PITCH / 2 - 6, rows * PITCH / 2 - 6, 1, level)

    recess = rim(inner(z), outer(z), inner(z + STUD_HEIGHT), outer(z + STUD_HEIGHT), tint)
    crown = z + height
    body = loft([outer(z + STUD_HEIGHT), outer(crown - 2),
                 outline(x, 0, columns, rows, crown, .985)], tint)
    if not has_studs:
        return recess + body
    studs = ''.join(stud(x + (i + .5 - columns / 2) * PITCH, (j + .5 - rows / 2) * PITCH,
                         crown, tint)
                    for i in range(columns) for j in range(rows))
    return recess + body + studs


def prism(points, low, high, tint, *, axis='x', end=None):
    """Extrude a 2D profile and optionally texture its exposed end cuts."""
    cut = loft([[(u, v, limit) for u, v in points] for limit in (low, high)],
               tint, axis=axis)
    if end:
        return cut.replace(material(tint), material(end), 2)
    return cut


def ramp_brick():
    # Wide face runs up to one row of studs at the high end.
    low = prism([(-128, 0), (64, 0), (64, 48), (-128, 8)], -64, 64, 'toy_lilac', axis='y')
    high = block((64, -64, 0, 128, 64, 48), 'toy_lilac')
    return low + high + ''.join(stud(96, y, 48, 'toy_lilac') for y in (-32, 32))


def tile_steps():
    return ''.join(brick(4 - tier, 2, 16, tint, has_studs=False, x=32 * tier, z=16 * tier)
                   for tier, tint in enumerate(('toy_navy', 'toy_blue', 'toy_aqua', 'toy_lemon')))


LOG_BODY = [(-14, 0), (14, 0), (29, 16), (32, 23), (32, 41), (29, 48),
            (14, 64), (-14, 64), (-29, 48), (-32, 41), (-32, 23), (-29, 16)]
LOG_NOTCH = LOG_BODY[2:6] + LOG_BODY[8:]
SILL_BODY = [(-32, 0), (32, 0), (32, 25), (29, 32), (14, 48), (-14, 48), (-29, 32), (-32, 25)]
SILL_NOTCH = SILL_BODY[:4] + SILL_BODY[6:]


def notched_log(center, *, sill=False):
    # 68-unit seats accept the perpendicular 64-unit body with 2 units per side.
    left, right = -center, center
    edges = (left - 48, left - 34, left + 34, right - 34, right + 34, right + 48)
    full, seat = (SILL_BODY, SILL_NOTCH) if sill else (LOG_BODY, LOG_NOTCH)
    return ''.join(prism(profile, low, high, 'kit_log', end='kit_log_end')
                   for low, high, profile in zip(edges, edges[1:], (full, seat, full, seat, full)))


def bevel_wood(bounds):
    x, y, z, X, Y, Z = bounds
    inset = 2
    core = box((x, y, z + inset, X, Y, Z - inset), material('kit_beech'), detail=True,
               overrides={axis: {'texture': material('kit_beech_end')} for axis in (0, 1)})
    u, v, rx, ry = (x + X) / 2, (y + Y) / 2, (X - x) / 2, (Y - y) / 2
    # A light break on the horizontal edges, as on a sanded wooden toy.
    rings = [rounded_rectangle(u, v, rx, ry, .4, level) for level in (z + inset, Z - inset)]
    edge_rings = [rounded_rectangle(u, v, rx - inset, ry - inset, .4, level) for level in (z, Z)]
    return core + loft([edge_rings[0], rings[0]], 'kit_beech') + loft([rings[1], edge_rings[1]], 'kit_beech')


def wood_arch():
    height, inner, outer = 70, 65, 119
    # Cabinet arch with a real opening and flat faces that meet the posts.
    posts = ''.join(block((x, -48, 0, X, 48, height), 'kit_beech')
                    for x, X in ((-outer, -inner), (inner, outer)))
    def ring(radius):
        return [(round(radius * cos(i * pi / 8), 3), height + round(radius * sin(i * pi / 8), 3))
                for i in range(9)]

    opening, crown = ring(inner), ring(outer)
    return posts + ''.join(prism([opening[i], opening[i+1], crown[i+1], crown[i]],
                                 -48, 48, 'kit_beech', axis='y') for i in range(8))


def wood_wedge():
    return prism([(-128, 0), (128, 0), (128, 64)], -56, 56, 'kit_beech', axis='y')


def wood_column():
    return loft([disc(0, 0, radius, radius, z)
                 for z, radius in ((0, 43), (4, 48), (92, 48), (96, 44))],
                'kit_beech', top='kit_beech_end')


def pinbeam():
    # Each octagon is a clear through-bore. Neighboring sections touch at the web.
    perimeter = [(24, 0), (24, 28), (0, 28), (-24, 28), (-24, 0),
                 (-24, -28), (0, -28), (24, -28)]
    hole = [(round(14 * cos(i * tau / 8), 3), round(14 * sin(i * tau / 8), 3))
            for i in range(8)]
    result = []
    for x in range(-144, 145, 48):
        for i in range(8):
            section = [hole[i-1], hole[i], perimeter[i], perimeter[i-1]]
            result.append(prism([(u + x, z + 28) for u, z in section],
                                -16, 16, 'toy_blue', axis='y'))
    return ''.join(result)


def dowel():
    center = 15 * cos(pi / 12)
    return (straight_oval(0, center, 10, 10, -48, 48, 'toy_lemon', axis='x')
            + straight_oval(0, center, 15, 15, -49, -41, 'toy_orange', axis='x')
            + straight_oval(0, center, 15, 15, 41, 49, 'toy_orange', axis='x'))


def square_frame():
    return (bevel((-80, -12, 0, 80, 12, 22), 2, 'toy_aqua')
            + bevel((-80, -12, 137, 80, 12, 159), 2, 'toy_aqua')
            + block((-80, -12, 20, -58, 12, 139), 'toy_aqua')
            + block((58, -12, 20, 80, 12, 139), 'toy_aqua'))


def triangle_frame():
    outer, inner = [(-88, 0), (88, 0), (0, 154)], [(-53, 20), (53, 20), (0, 114)]
    return ''.join(prism([inner[i-1], inner[i], outer[i], outer[i-1]],
                         -12, 12, 'toy_coral', axis='y') for i in range(3))


PREFABS = {
    'brick_1x1': lambda: brick(1, 1, 48, 'toy_coral'),
    'brick_1x2': lambda: brick(2, 1, 48, 'toy_blue'),
    'brick_2x2': lambda: brick(2, 2, 48, 'toy_lemon'),
    'brick_2x4': lambda: brick(4, 2, 48, 'toy_aqua'),
    'plate_2x4': lambda: brick(4, 2, 16, 'toy_coral'),
    'tile_2x4': lambda: brick(4, 2, 16, 'enamel', has_studs=False),
    'ramp_2x4': ramp_brick,
    'steps_2x4': tile_steps,
    'log_short': lambda: notched_log(64),
    'log_medium': lambda: notched_log(128),
    'log_long': lambda: notched_log(192),
    'log_sill': lambda: notched_log(128, sill=True),
    'wood_cube': lambda: bevel_wood((-48, -48, 0, 48, 48, 96)),
    'wood_beam': lambda: bevel_wood((-128, -32, 0, 128, 32, 64)),
    'wood_arch': wood_arch,
    'wood_wedge': wood_wedge,
    'wood_column': wood_column,
    'pinbeam': pinbeam,
    'dowel': dowel,
    'frame_square': square_frame,
    'frame_triangle': triangle_frame,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, make in PREFABS.items():
        map_text = HEADER + '{\n"classname" "worldspawn"\n' + make() + '}\n'
        (args.output / f'build_{name}.map').write_text(map_text, encoding='ascii')


if __name__ == '__main__':
    main()
