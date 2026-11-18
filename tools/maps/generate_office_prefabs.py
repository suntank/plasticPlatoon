#!/usr/bin/env python3
"""Export editable, unmarked home office brushes for the Quake II prefab library."""

import argparse
from math import cos, radians, sin, tau
from pathlib import Path

from PIL import ImageDraw

from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, label_panel, oval, straight_oval
from generate_bathroom import BASE, material
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, ring_band, slab
from generate_sandkeep_materials import write_wal
from generate_switchyard import box
from platoon_palette import load_palette

INK = 'toy_ink'
NAVY = 'toy_navy'
CREAM = 'enamel'
STEEL = 'garage_steel'
WOOD = 'kit_beech'
KRAFT = 'garage_kraft'
TEAL = 'laundry_teal'
RUST = 'bedroom/living_rust'
SAGE = 'bedroom/living_sage'
FELT = 'bedroom/living_blue'
SCREEN = 'bedroom/living_screen'
MINT = 'toy_mint'
GOLD = 'toy_lemon'
PAPER = 'bedroom/office_paper'
EDGES = 'bedroom/office_edges'
CHART = 'bedroom/office_chart'


def write_materials():
    paper = finish((228, 220, 194), lambda x, y: 2 * cos(tau * (x + y) / 128))
    edges = finish((216, 205, 177), lambda x, y: 11 * cos(tau * y / 4))
    chart = paper.copy()
    draw = ImageDraw.Draw(chart)
    draw.rectangle((14, 14, 75, 17), fill=(60, 102, 111))
    for y, length in ((26, 63), (32, 89), (38, 86), (45, 54), (105, 91), (111, 69)):
        draw.rectangle((14, y, 14 + length, y + 1), fill=(142, 145, 134))
    draw.line(((16, 54), (16, 93), (108, 93)), fill=(66, 81, 80), width=2)
    for x, height, tint in ((24, 16, (76, 133, 133)), (44, 25, (76, 133, 133)),
                            (64, 22, (155, 87, 69)), (84, 35, (76, 133, 133))):
        draw.rectangle((x, 92 - height, x + 11, 92), fill=tint)
    palette = load_palette()
    for name, image in ((PAPER, paper), (EDGES, edges), (CHART, chart)):
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def desk():
    top = block((-228, -98, 96, 228, 121, 112), WOOD)
    feet = ''.join(bevel((x, y, 0, x + 18, y + 18, 98), 3, NAVY)
                   for x in (-211, 193) for y in (-81, 83))
    back = block((-210, 84, 70, 202, 97, 96), NAVY)
    pedestal = block((104, -77, 16, 196, 90, 96), WOOD)
    drawers = ''.join(
        block((108, -83, z, 191, -76, z + 33), WOOD)
        + bevel((130, -89, z + 21, 169, -82, z + 27), 1, STEEL)
        for z in (22, 59))
    return top + feet + back + pedestal + drawers


def caster(x, y):
    return (straight_oval(x, 9, 9, 9, y - 6, y + 6, INK, axis='y')
            + straight_oval(x, 9, 4, 4, y - 7, y + 7, STEEL, axis='y')
            + block((x - 5, y - 5, 13, x + 5, y + 5, 30), NAVY))


def chair():
    base = straight_oval(0, 0, 16, 16, 21, 67, INK)
    base += straight_oval(0, 0, 8, 8, 60, 80, STEEL)
    for i in range(5):
        angle = radians(90 + i * 72)
        dx, dy = cos(angle), sin(angle)
        arm = [(r * dx - t * dy, r * dy + t * dx)
               for r, t in ((8, -8), (70, -5), (70, 5), (8, 8))]
        base += slab(arm, 21, 30, NAVY) + caster(round(68 * dx), round(68 * dy))
    seat = bevel((-59, -63, 76, 59, 49, 94), 5, FELT)
    back = prism([(28, 90), (49, 88), (70, 176), (54, 181)], -51, 51, FELT)
    frame = prism([(23, 81), (35, 79), (59, 143), (47, 147)], -16, 16, NAVY)
    arms = ''.join(block((x, 4, 89, x + 10, 20, 128), NAVY)
                   + bevel((x - 3, -31, 124, x + 14, 33, 134), 2, INK)
                   for x in (-67, 57))
    return base + seat + frame + back + arms


def tower():
    case = bevel((-51, -86, 0, 51, 86, 165), 6, INK)
    feet = ''.join(block((x, y, 0, x + 12, y + 15, 9), NAVY)
                   for x in (-44, 32) for y in (-79, 64))
    front = bevel((-43, -92, 11, 43, -84, 151), 2, NAVY)
    tray = block((-31, -94, 122, 29, -91, 126), INK)
    switch = straight_oval(0, 140, 6, 6, -95, -91, STEEL, axis='y')
    ports = ''.join(block((x, -94, 101, x + 12, -91, 105), INK) for x in (-26, -8, 12))
    grille = ''.join(block((-31, -95, z, 31, -91, z + 3), INK) for z in range(23, 80, 8))
    return case + feet + front + tray + switch + ports + grille


def monitor():
    foot = bevel((-63, -30, 0, 63, 39, 12), 3, NAVY)
    stand = bevel((-12, 6, 9, 12, 31, 77), 3, NAVY)
    case = bevel((-108, -16, 48, 108, 12, 176), 5, INK)
    panel = label_panel((-99, -18, 59, 99, -15, 168), SCREEN, INK)
    chin = block((-99, -19, 53, 99, -16, 58), NAVY)
    power = block((84, -20, 54, 91, -18, 57), MINT)
    return foot + stand + case + panel + chin + power


def key(x, y, z=14, width=11, tint=CREAM):
    return block((x, y, z, x + width, y + 9, z + 3), tint)


def keyboard():
    base = bevel((-131, -46, 0, 131, 46, 14), 3, INK)
    rows = ''.join(key(x, y) for x in range(-120, 22, 13) for y in (-19, -6, 7, 20))
    modifiers = ''.join(key(x, -32, width=w, tint=STEEL)
                        for x, w in ((-120, 16), (-101, 16), (-82, 69), (-10, 26)))
    function_keys = ''.join(key(x, 33, width=10, tint=STEEL)
                            for x in (-120, -96, -83, -70, -57, -36, -23, -10, 3))
    arrows = ''.join(key(x, y, width=9, tint=STEEL)
                     for x, y in ((28, -32), (39, -32), (50, -32), (39, -21), (29, 20), (42, 20)))
    numpad = ''.join(key(x, y, tint=STEEL) for x in (75, 90, 105) for y in (-32, -19, -6, 7, 20))
    lights = ''.join(block((x, 35, 13, x + 5, 38, 15), MINT) for x in (80, 92, 104))
    return base + rows + modifiers + function_keys + arrows + numpad + lights


def mouse():
    body = bottle_shape(35, 58, 23, [(0, .93, 0, 0), (7, 1, 0, 0),
                                    (21, .99, 0, -2), (29, .78, 0, -7),
                                    (33, .44, 0, -12)], INK)
    buttons = ''.join(bevel((x, 9, 18, x + 24, 50, 25), 2, NAVY) for x in (-27, 3))
    wheel = straight_oval(20, 25, 10, 10, -4, 4, STEEL, axis='x')
    cord = slab([(-3, 51), (3, 51), (4, 79), (-3, 81)], 1, 6, INK)
    return body + buttons + wheel + cord


def mouse_pad():
    return bottle_shape(59, 72, 12, [(0, 1, 0, 0), (4, 1, 0, 0)], FELT)


def laptop():
    shell = bevel((-93, -68, 0, 93, 57, 11), 2, STEEL)
    screen = prism([(39, 8), (53, 7), (87, 119), (75, 123)], -91, 91, INK)
    panel = prism([(42, 22), (45, 22), (73, 111), (70, 111)], -81, 81, SCREEN)
    keys = ''.join(key(x, y, z=11, tint=NAVY) for x in range(-78, 74, 13)
                   for y in (-13, 0, 13, 26))
    trackpad = bevel((-31, -56, 10, 31, -26, 13), 1, NAVY)
    return shell + screen + panel + keys + trackpad


def printer():
    body = bevel((-132, -71, 0, 132, 87, 40), 4, CREAM)
    deck = bevel((-132, -71, 66, 132, 87, 102), 4, CREAM)
    supports = ''.join(block((x, -70, 28, X, 85, 77), CREAM)
                       for x, X in ((-130, -99), (99, 130)))
    rear = block((-100, 33, 33, 100, 86, 71), INK)
    tray = (bevel((-87, -133, 26, 87, -20, 39), 3, NAVY)
            + block((-87, -133, 36, 87, -125, 45), NAVY))
    output = label_panel((-62, -119, 38, 62, -28, 41), CHART, PAPER, top=True)
    lid = bevel((-104, -57, 99, 78, 73, 111), 3, STEEL)
    controls = bevel((84, -56, 99, 121, 2, 104), 1, NAVY)
    buttons = ''.join(straight_oval(102, y, 4, 4, 103, 107, tint)
                      for y, tint in ((-46, MINT), (-34, STEEL), (-22, STEEL)))
    return body + deck + supports + rear + tray + output + lid + controls + buttons


def paper_block(bounds):
    return box(bounds, material(EDGES), detail=True, overrides={5: {'texture': material(PAPER)}})


def ream():
    return (block((-88, -62, 0, 88, 62, 5), RUST)
            + paper_block((-86, -60, 5, 86, 60, 27))
            + block((-90, -61, 0, -58, 61, 27), RUST)
            + block((56, -61, 0, 87, 61, 5), RUST))


def report():
    return (paper_block((-78, -59, 0, 80, 57, 9))
            + label_panel((-76, -58, 8, 79, 57, 11), CHART, PAPER, top=True)
            + block((-71, 45, 10, -62, 54, 13), STEEL))


def scattered_papers():
    pages = [
        [(-128, -28), (-52, -94), (43, -4), (-28, 62)],
        [(-35, -35), (100, -55), (116, 46), (-18, 68)],
        [(-112, 66), (-7, 24), (40, 117), (-71, 141)],
    ]
    return (''.join(slab(outline, 2 * i, 2 * i + 3, PAPER)
                    for i, outline in enumerate(pages))
            + block((47, 13, 5, 91, 42, 7), GOLD))


def folder():
    outline = [(-84, -58), (84, -58), (84, 52), (18, 68), (-84, 68)]
    return (slab(outline, 0, 3, SAGE)
            + paper_block((-74, -50, 2, 77, 59, 11))
            + slab(outline, 9, 13, SAGE)
            + block((-72, 67, 9, -18, 77, 13), SAGE))


def binders():
    brushes = ''
    for x, depth, height, tint in ((-63, 49, 137, TEAL), (-18, 59, 151, RUST), (25, 52, 127, NAVY)):
        brushes += block((x, -depth, 0, x + 42, depth, height), tint)
        brushes += block((x + 4, -depth + 8, height - 2, x + 38, depth - 4, height + 1), PAPER)
        brushes += straight_oval(x + 21, 27, 11, 11, -depth - 2, -depth + 1, INK, axis='y')
        brushes += block((x + 9, -depth - 1, 63, x + 33, -depth + 1, 101), STEEL)
    return brushes


def notebook():
    pages = paper_block((-69, -53, 4, 76, 53, 18))
    cover = block((-76, -56, 0, 79, 56, 4), TEAL) + block((-76, -56, 17, 79, 56, 22), TEAL)
    rings = ''.join(ring_band(-72, 11, (y, 9, 13), (y + 4, 9, 13), STEEL, axis='y', sides=8)
                    for y in range(-48, 48, 13))
    tag = block((22, 9, 21, 68, 38, 23), PAPER)
    return pages + cover + rings + tag


def sticky_notes():
    return (paper_block((-60, -53, 0, 38, 44, 9))
            + block((-62, -52, 7, 40, 44, 13), GOLD)
            + slab([(38, -31), (104, -19), (92, 39), (28, 26)], 0, 3, MINT)
            + slab([(-98, 36), (-41, 18), (-18, 63), (-71, 88)], 1, 3, 'toy_coral'))


def stapler():
    base = bevel((-29, -81, 0, 29, 82, 12), 3, INK)
    anvil = block((-19, -76, 11, 19, -55, 15), STEEL)
    hinge = straight_oval(61, 25, 18, 15, -24, 24, STEEL, axis='x')
    jaw = prism([(-73, 21), (-70, 32), (70, 46), (75, 32)], -20, 20, STEEL)
    grip = prism([(-80, 31), (-73, 49), (60, 62), (77, 52), (78, 33)], -27, 27, RUST)
    return base + anvil + hinge + jaw + grip


def pen_cup():
    cup = (straight_oval(0, 0, 38, 38, 0, 7, TEAL)
           + ring_band(0, 0, (6, 34, 38), (90, 39, 44), TEAL)
           + ring_band(0, 0, (88, 38, 46), (95, 38, 46), NAVY))
    for x, y, height, tilt, tint in ((-16, 11, 139, -14, GOLD), (12, 7, 131, 9, RUST),
                                      (6, -17, 154, 13, NAVY)):
        cup += oval([(5, x, y, 5), (height - 16, x + tilt, y, 5)], tint, sides=8)
        cup += straight_oval(x + tilt, y, 5, 5, height - 17, height, STEEL)
    return cup


def desk_lamp():
    base = bevel((-48, -43, 0, 48, 43, 12), 3, NAVY)
    foot = straight_oval(0, 8, 12, 12, 10, 33, STEEL)
    lower = prism([(-1, 24), (12, 22), (41, 98), (29, 102)], -6, 6, STEEL)
    upper = prism([(-40, 135), (-34, 146), (38, 104), (32, 94)], -6, 6, STEEL)
    hinge = straight_oval(34, 99, 12, 12, -10, 10, NAVY, axis='x')
    shade = ring_band(0, -46, (115, 36, 42), (151, 12, 17), TEAL)
    cap = straight_oval(0, -46, 17, 17, 150, 157, TEAL)
    bulb = oval([(121, 0, -46, 8), (128, 0, -46, 13), (139, 0, -46, 9)], CREAM)
    return base + foot + lower + upper + hinge + shade + cap + bulb


def wastebasket():
    return (straight_oval(0, 0, 59, 59, 0, 10, NAVY)
            + ring_band(0, 0, (9, 52, 58), (110, 71, 76), NAVY)
            + ring_band(0, 0, (107, 70, 80), (115, 70, 80), STEEL))


def filing_cabinet():
    body = block((-74, -68, 0, 74, 69, 96), STEEL)
    drawers = ''
    for z in (14, 54):
        drawers += block((-68, -73, z, 68, -67, z + 34), NAVY)
        drawers += block((-19, -76, z + 18, 19, -72, z + 23), STEEL)
        drawers += block((-46, -75, z + 11, -26, -72, z + 23), PAPER)
    return body + drawers


def paper_tray():
    tray = block((-99, -85, 0, 99, 91, 9), NAVY)
    return (tray + block((-99, 81, 8, 99, 91, 40), NAVY)
            + block((-99, -85, 8, -89, 82, 39), NAVY)
            + block((89, -85, 8, 99, 82, 39), NAVY)
            + paper_block((-77, -79, 8, 78, 56, 14))
            + label_panel((-73, -72, 13, 76, 51, 16), CHART, PAPER, top=True))


def paper_steps():
    stairs = ''
    for i in range(6):
        x, z = -210 + 58 * i, 16 * i
        width = 84 - 2 * i
        stairs += paper_block((x, -width, z, 197, width, z + 16))
        for y in (-width - 1, width - 3):
            stairs += block((x + 12, y, z + 3, 187, y + 4, z + 8),
                            TEAL if i % 2 else RUST)
    return stairs


def file_box_steps():
    stairs = ''
    for i in range(7):
        y, height = -298 + 62 * i, 16 * (i + 1)
        end = y + 62 if i < 6 else 147
        stairs += block((-77, y, 0, 77, end, height - 5), KRAFT)
        stairs += block((-77, y, height - 5, 77, end, height), WOOD)
        for x in (-78, 76):
            stairs += block((x, y + 9, height - 12, x + 2, end - 9, height - 7), TEAL)
    return stairs


def binder_ramp():
    pages = prism([(-142, 0), (146, 0), (146, 45)], -68, 68, EDGES, axis='y')
    cover = prism([(-142, 0), (146, 45), (146, 48), (-124, 3)], -72, 72, TEAL, axis='y')
    spine = block((146, -72, 0, 211, 72, 48), TEAL)
    ring = straight_oval(178, 25, 10, 10, -73, -71, INK, axis='y')
    return pages + cover + spine + ring


PREFABS = {
    'desk': desk, 'chair': chair, 'computer_tower': tower, 'monitor': monitor,
    'keyboard': keyboard, 'mouse': mouse, 'mouse_pad': mouse_pad, 'laptop': laptop,
    'printer': printer, 'paper_tray': paper_tray, 'paper_ream': ream, 'report': report,
    'scattered_papers': scattered_papers, 'folder': folder, 'binders': binders,
    'notebook': notebook, 'sticky_notes': sticky_notes, 'stapler': stapler,
    'pen_cup': pen_cup, 'desk_lamp': desk_lamp, 'wastebasket': wastebasket,
    'filing_cabinet': filing_cabinet, 'paper_steps': paper_steps,
    'file_box_steps': file_box_steps, 'binder_ramp': binder_ramp,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, make in PREFABS.items():
        data = HEADER + '{\n"classname" "worldspawn"\n' + make() + '}\n'
        (args.output / f'office_{name}.map').write_text(data, encoding='ascii')


if __name__ == '__main__':
    main()
