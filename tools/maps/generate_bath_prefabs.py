#!/usr/bin/env python3
"""Generate the detail-brush bathroom kit and its Plastic Platoon materials."""

import argparse
from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bathroom import BASE, ROOT, disc, material, rim, rounded_rectangle
from generate_sandkeep_materials import text, write_wal
from generate_switchyard import box, convex
from platoon_palette import load_palette

HEADER = '// Game: Quake 2\n// Format: Quake2\n'
PALETTE = {
    'toy_lemon': (250, 205, 48),
    'toy_orange': (234, 111, 46),
    'toy_coral': (216, 87, 79),
    'toy_aqua': (79, 183, 177),
    'toy_blue': (67, 123, 187),
    'toy_navy': (40, 66, 92),
    'toy_mint': (154, 205, 161),
    'toy_lilac': (147, 113, 171),
    'toy_ink': (40, 42, 47),
}
LABELS = {
    'label_shampoo': ('SHAMPOO', 'SEA GLASS', (83, 176, 171), 'wave'),
    'label_conditioner': ('CONDITION', 'ROSE MILK', (218, 124, 135), 'flower'),
    'label_bodywash': ('BODY WASH', 'SUN PEEL', (245, 159, 66), 'flower'),
    'label_pump': ('HAND SOAP', 'FRESH RAIN', (159, 130, 191), 'wave'),
    'label_toothpaste': ('TOOTHPASTE', 'COOL MINT', (110, 183, 150), 'wave'),
}


def label_image(title, subtitle, color, motif):
    paper, ink = (249, 236, 212), (31, 55, 61)
    image = Image.new('RGB', (128, 128), color)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, 121, 121), radius=14, fill=paper, outline=ink, width=2)
    draw.rounded_rectangle((12, 13, 115, 31), radius=6, fill=color)
    text(draw, 64, 18, 'TIDEPOOL', 1, ink)
    if motif == 'wave':
        for y in (44, 52):
            draw.line([(x, y + round(4 * sin((x - 40) / 6))) for x in range(40, 89)],
                      fill=color, width=3)
    else:
        for x, y in ((59, 42), (70, 44), (70, 55), (58, 56)):
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
        draw.ellipse((60, 46, 68, 53), fill=ink)
    text(draw, 64, 70, title, 1, ink)
    draw.line((23, 88, 104, 88), fill=color, width=2)
    text(draw, 64, 99, subtitle, 1, ink)
    return image


def write_materials():
    folder = BASE / 'textures/bathroom'
    palette = load_palette()
    images = {}
    for name, color in PALETTE.items():
        image = Image.new('RGB', (64, 64))
        image.putdata([tuple(max(0, min(255, value + (x * 11 ^ y * 7) % 3 - 1))
                             for value in color) for y in range(64) for x in range(64)])
        images[name] = image
    images.update({name: label_image(*label) for name, label in LABELS.items()})
    for name, image in images.items():
        image.save(folder / (name + '.png'))
        write_wal(folder / (name + '.wal'), material(name), image, palette)


def block(bounds, texture):
    return box(bounds, material(texture), detail=True)


def loft(rings, texture, *, axis='z', top=None):
    # All joins use the same outline and uniform scale per cross-section.
    def orient(p):
        x, y, z = p
        if axis == 'x':
            return (z, x, y)
        if axis == 'y':
            return (x, z, y)
        return p

    brushes = []
    for first, last in zip(rings, rings[1:]):
        sides = [[first[i - 1], first[i], last[i], last[i - 1]] for i in range(len(first))]
        faces = [[orient(p) for p in polygon] for polygon in [first, last, *sides]]
        brushes.append(convex(faces, material(texture), detail=True,
                              top_texture=material(top) if top else None))
    return ''.join(brushes)


def bottle_shape(rx, ry, corner, layers, texture, *, axis='z'):
    outline = rounded_rectangle(0, 0, rx, ry, corner, 0)
    return loft([[(x * scale + u, y * scale + v, z) for x, y, _ in outline]
                 for z, scale, u, v in layers], texture, axis=axis)


def oval(layers, texture, *, aspect=1, axis='z', sides=12):
    return loft([disc(x, y, radius, radius * aspect, z, sides) for z, x, y, radius in layers],
                texture, axis=axis)


def straight_oval(x, y, rx, ry, z0, z1, texture, *, axis='z'):
    return oval([(z, x, y, rx) for z in (z0, z1)], texture, aspect=ry / rx, axis=axis)


def bevel(bounds, edge, texture):
    x, y, z, X, Y, Z = bounds
    rx, ry = (X - x) / 2, (Y - y) / 2
    u, v = (X + x) / 2, (Y + y) / 2
    inset = 1 - edge / min(rx, ry)
    return bottle_shape(rx, ry, min(rx, ry) / 3,
                        [(z, inset, u, v), (z + edge, 1, u, v),
                         (Z - edge, 1, u, v), (Z, inset, u, v)], texture)


def label_panel(bounds, label, background, *, top=False):
    x, y, z, X, Y, Z = bounds
    sx = (X - x) / 128
    if top:
        sy = (Y - y) / 128
        face, shift_y = 5, Y / sy
    else:
        sy = (Z - z) / 128
        face, shift_y = 2, Z / sy
    return box(bounds, material(background), detail=True,
               overrides={face: {'texture': material(label), 'scale': (sx, sy),
                                 'shift': (-x / sx, shift_y)}})


def shampoo():
    return (bottle_shape(60, 35, 16, [(0, .91, 0, 0), (12, 1, 0, 0), (145, 1, 0, 0),
                                     (173, .58, 3, 0)], 'toy_aqua')
            + bevel((-32, -24, 173, 37, 24, 207), 4, 'toy_navy')
            + block((-20, -25, 194, 25, -22, 198), 'toy_blue')
            + label_panel((-36, -36, 38, 36, -35, 135), 'label_shampoo', 'toy_aqua'))


def conditioner():
    return (bevel((-36, -23, 0, 36, 23, 29), 4, 'toy_coral')
            + block((-24, -24, 12, 24, -21, 16), 'rose')
            + bottle_shape(55, 32, 15, [(29, .65, 0, 0), (59, 1, 0, 0),
                                       (162, 1, 0, 0), (187, .79, 0, 0)], 'rose')
            + label_panel((-34, -33, 69, 34, -32, 156), 'label_conditioner', 'rose'))


def bodywash():
    return (bottle_shape(55, 32, 15, [(0, .85, 0, 0), (16, 1, 0, 0), (48, 1, 0, 0),
                                      (63, .81, 0, 0), (151, .81, 0, 0), (175, .6, 0, 0)],
                         'toy_orange')
            + bevel((-31, -21, 175, 31, 21, 207), 4, 'toy_lemon')
            + block((-18, -22, 194, 18, -19, 198), 'toy_orange')
            + label_panel((-29, -27, 66, 29, -25, 146), 'label_bodywash', 'toy_orange'))


def pumpbottle():
    return (bottle_shape(63, 43, 16, [(0, .9, 0, 0), (9, 1, 0, 0), (118, 1, 0, 0),
                                      (141, .48, 2, 0)], 'toy_lilac')
            + straight_oval(2, 0, 28, 25, 138, 159, 'toy_navy')
            + straight_oval(2, 0, 14, 14, 157, 186, 'enamel')
            + bevel((-58, -19, 184, 31, 19, 205), 4, 'enamel')
            + bevel((-59, -15, 176, -44, 15, 190), 2, 'enamel')
            + label_panel((-38, -44, 17, 38, -42, 109), 'label_pump', 'toy_lilac'))


def toothpaste():
    # Cross-sections lie on the YZ plane, so the crimp and cap run along X.
    tube = bottle_shape(44, 21, 10, [(-110, .86, 0, 21), (-98, 1, 0, 21),
                                    (50, 1, 0, 21), (92, .51, 0, 21)], 'enamel', axis='x')
    return (tube + bevel((-123, -39, 13, -106, 39, 28), 2, 'toy_mint')
            + straight_oval(0, 21, 17, 17, 89, 123, 'toy_mint', axis='x')
            + straight_oval(0, 21, 18, 18, 112, 121, 'teal', axis='x')
            + label_panel((-91, -27, 41, 36, 27, 43), 'label_toothpaste', 'enamel', top=True)
            + bevel((-17, -13, 0, 16, 13, 7), 2, 'enamel'))


def soapbar():
    return (bevel((-67, -39, 0, 67, 39, 33), 7, 'toy_mint')
            + oval([(33, 0, 0, 21), (36, 0, 0, 17)], 'enamel', aspect=.62, sides=8))


def soapdish():
    def outline(z, scale):
        return [(x * scale, y * scale, z) for x, y, _ in rounded_rectangle(0, 0, 96, 60, 19, 0)]

    tray = loft([outline(4, .9), outline(12, 1)], 'toy_blue')
    tray += rim(outline(12, .86), outline(12, 1), outline(27, .89), outline(27, 1.04), 'toy_aqua')
    for x in (-66, 50):
        for y in (-43, 32):
            tray += block((x, y, 0, x + 16, y + 11, 8), 'rubber')
    for y in (-25, -8, 9, 26):
        tray += bevel((-68, y, 12, 68, y + 4, 16), 1, 'toy_blue')
    return tray


def cloth_surface(center, outline, colors):
    """Make one connected fabric surface from solid triangular wedges."""
    result = []
    for i, p in enumerate(outline):
        top = [center, outline[i - 1], p]
        bottom = [(x, y, 0) for x, y, _ in top]
        result.append(loft([bottom, top], colors[i % len(colors)]))
    return ''.join(result)


def towelpile():
    upper = cloth_surface((-33, 8, 63), [
        (-105, -36, 9), (-45, -68, 24), (3, -59, 16), (48, -17, 28),
        (34, 45, 17), (-34, 63, 33), (-87, 43, 20), (-111, 2, 47),
    ], ('cloth',))
    tail = cloth_surface((48, -9, 28), [
        (8, -49, 7), (73, -60, 11), (111, -22, 5), (117, 15, 11),
        (78, 47, 9), (23, 42, 17), (5, -2, 19),
    ], ('toy_lilac',))
    return tail + upper


def washcloth():
    return cloth_surface((1, 3, 11), [
        (-69, -57, 4), (-4, -53, 6), (58, -62, 3), (69, -14, 7),
        (59, 55, 5), (2, 47, 13), (-68, 57, 6), (-58, 7, 8),
    ], ('cloth', 'cloth', 'teal', 'cloth'))


def sock():
    return cloth_surface((19, 2, 29), [
        (-77, -15, 10), (-5, -20, 17), (26, -47, 15), (55, -63, 10),
        (85, -50, 11), (94, -29, 8), (60, 4, 15), (37, 25, 18),
        (6, 44, 11), (-73, 43, 18),
    ], ('cloth', 'paint', 'paint', 'paint', 'cloth',
        'cloth', 'paint', 'paint', 'paint', 'paint'))


def rubberducky():
    body = oval([
        (0, -22, 0, 64), (21, -20, 0, 86),
        (50, -18, 0, 91), (76, -9, 0, 76), (90, 5, 0, 53),
    ], 'toy_lemon', aspect=.61)
    body += oval([(53, -78, 0, 29), (75, -83, 0, 31),
                  (104, -95, 0, 14)], 'toy_lemon', aspect=.61, sides=8)
    head = oval([
        (64, 39, 0, 31), (93, 47, 0, 48), (130, 50, 0, 53),
        (156, 48, 0, 43), (171, 46, 0, 27),
    ], 'toy_lemon', aspect=.8)
    bill = bevel((85, -29, 94, 133, 29, 118), 5, 'toy_orange')
    bill += bevel((98, -22, 88, 132, 22, 97), 3, 'toy_orange')
    eyes = ''.join(
        straight_oval(69, 132, 8, 10, y, Y, 'toy_ink', axis='y')
        + straight_oval(71, 135, 2.5, 2.5, a, b, 'enamel', axis='y')
        for y, Y, a, b in ((-42, -31, -43, -41), (31, 42, 41, 43))
    )
    wings = ''.join(oval([
        (start, -30, 48, 44), (end, -35, 51, 32),
    ], 'toy_lemon', aspect=.39, axis='y', sides=8) for start, end in ((-32, -56), (32, 56)))
    return body + head + bill + eyes + wings


def stackcups():
    result = []
    for z, height, radius, tint in ((0, 48, 71, 'toy_blue'),
                                    (27, 50, 65, 'toy_mint'),
                                    (58, 47, 58, 'toy_coral')):
        base_r = radius - 9
        result.append(straight_oval(0, 0, base_r, base_r, z, z + 6, tint))
        result.append(rim(disc(0, 0, base_r - 8, base_r - 8, z + 6),
                          disc(0, 0, base_r, base_r, z + 6),
                          disc(0, 0, radius - 8, radius - 8, z + height),
                          disc(0, 0, radius, radius, z + height), tint))
    return ''.join(result)


def starfish():
    contour = []
    for ray in range(5):
        for offset, radius, height in ((-36, 40, 12), (-15, 73, 13),
                                       (-4, 90, 8), (4, 90, 8), (15, 73, 13)):
            theta = radians(18 + ray * 72 + offset)
            contour.append((round(radius * cos(theta), 2), round(radius * sin(theta), 2), height))
    return (cloth_surface((0, 0, 32), contour, ('toy_coral',))
            + straight_oval(-12, -8, 5, 5, 26, 34, 'toy_orange')
            + straight_oval(10, -8, 5, 5, 26, 34, 'toy_orange')
            + straight_oval(1, 12, 6, 6, 25, 35, 'toy_orange'))


def submarine():
    hull = oval([
        (-126, 0, 44, 23), (-94, 0, 44, 44),
        (67, 0, 44, 44), (114, 0, 44, 26), (126, 0, 44, 15),
    ], 'toy_blue', aspect=.864, axis='x')
    stand = bevel((-65, -29, 0, 57, 29, 12), 3, 'toy_navy')
    bridge = (bevel((-38, -29, 71, 25, 29, 119), 6, 'toy_coral')
              + straight_oval(-12, 0, 9, 9, 111, 144, 'toy_navy')
              + bevel((-20, -9, 135, 10, 9, 150), 3, 'toy_navy'))
    fins = (bevel((-117, -64, 38, -73, 64, 50), 4, 'toy_coral')
            + bevel((-119, -9, 61, -80, 9, 96), 3, 'toy_coral'))
    windows = ''
    for x in (-54, 0, 54):
        for y, Y, a, b in ((-46, -38, -48, -45), (38, 46, 45, 48)):
            windows += straight_oval(x, 46, 16, 16, y, Y, 'toy_navy', axis='y')
            windows += straight_oval(x, 46, 11, 11, a, b, 'window', axis='y')
    return hull + stand + bridge + fins + windows


def plasticboat():
    """Open toy launch with a 24-unit deck and a ramp through its transom."""
    hull = [(-216, -93), (-164, -114), (110, -114), (161, -94),
            (218, -54), (247, -17), (247, 17), (218, 54),
            (161, 94), (110, 114), (-164, 114), (-216, 93)]

    def outline(points, z, scale=1):
        return [(x * scale, y * scale, z) for x, y in points]

    deck = loft([outline(hull, 0, .94), outline(hull, 24)], 'toy_blue', top='paint')
    ramp_side = [(-277, -54, 0), (-216, -54, 0), (-216, -54, 24)]
    ramp_back = [(x, 54, z) for x, _, z in ramp_side]
    ramp_faces = [[ramp_side[i - 1], ramp_side[i], ramp_back[i], ramp_back[i - 1]]
                  for i in range(3)]
    ramp = convex([ramp_side, ramp_back, *ramp_faces], material('toy_blue'),
                  detail=True, top_texture=material('paint'))

    # Keep a 108-unit opening at the stern. The open center of the ring is deck.
    wall = hull + [(-216, 61), (-216, -61)]
    rails = []
    for i, end in enumerate(wall):
        if i == len(wall) - 1:
            continue
        edge = [wall[i - 1], end]

        def section(z, inner):
            return list(reversed(outline(edge, z, inner))) + outline(edge, z)

        rails.append(loft([section(24, .87), section(54, .87)], 'toy_blue'))
        rails.append(loft([section(54, .87), section(62, .87)], 'toy_coral'))
    helm = (bevel((34, -31, 24, 86, 31, 95), 4, 'toy_aqua')
            + bevel((30, -26, 83, 37, 26, 99), 1, 'toy_navy')
            + straight_oval(0, 93, 17, 15, 26, 33, 'rubber', axis='x')
            + straight_oval(0, 93, 7, 6, 24, 30, 'toy_coral', axis='x'))
    cleats = ''.join(bevel((91, y, 62, 117, y + 10, 69), 2, 'enamel') for y in (-109, 99))
    stripes = ''.join(block((x, -68, 24, x + 3, 68, 25), 'toy_navy')
                      for x in (-149, -94, -39, 16))
    return deck + ramp + ''.join(rails) + helm + cleats + stripes


PREFABS = {
    'shampoo': shampoo,
    'conditioner': conditioner,
    'bodywash': bodywash,
    'pumpbottle': pumpbottle,
    'toothpastetube': toothpaste,
    'soapbar': soapbar,
    'soapdish': soapdish,
    'towelpile': towelpile,
    'washcloth': washcloth,
    'sock': sock,
    'rubberducky': rubberducky,
    'stackcups': stackcups,
    'starfish': starfish,
    'submarine': submarine,
    'plasticboat': plasticboat,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, maker in PREFABS.items():
        prefab = HEADER + '{\n"classname" "worldspawn"\n' + maker() + '}\n'
        (args.output / f'bath_{name}.map').write_text(prefab, encoding='ascii')


if __name__ == '__main__':
    main()
