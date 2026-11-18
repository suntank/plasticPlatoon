#!/usr/bin/env python3
"""Export unmarked, toy-scale basement brushes and modular utility fittings."""

import argparse
from math import cos, radians, sin, tau
from pathlib import Path

from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, loft, oval, straight_oval
from generate_bathroom import BASE, disc
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, ring_band, slab
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

COPPER = 'bathroom/basement_copper'
ZINC = 'bathroom/basement_zinc'
IRON = 'bathroom/basement_iron'
CONCRETE = 'bathroom/basement_concrete'
KRAFT = 'garage_kraft'
FLUTE = 'garage_flute'
TAPE = 'garage_tape'
INK = 'toy_ink'
RED = 'garage_paint'
CREAM = 'enamel'
WOOD = 'bedroom/attic_wood'
PAPER = 'bedroom/attic_paper'
GRAY = 'garage_steel'
TEAL = 'laundry_teal'
NAVY = 'toy_navy'
BRASS = 'bedroom/attic_brass'


def write_materials():
    images = {
        COPPER: finish((150, 92, 58), lambda x, y:
                       8 * cos(tau * y / 32) + 6 * sin(tau * (x - y) / 128)),
        ZINC: finish((142, 155, 153), lambda x, y:
                     6 * cos(tau * x / 16) + 7 * sin(tau * (x + y) / 128)),
        IRON: finish((62, 79, 76), lambda x, y:
                     5 * cos(tau * x / 32) + 6 * sin(tau * (x + y) / 128)),
        CONCRETE: finish((124, 122, 110), lambda x, y:
                         (x * 19 ^ y * 28 ^ ((x + y) * 31)) % 17 - 8
                         + 4 * sin(tau * x / 64) * cos(tau * y / 64)),
    }
    palette = load_palette()
    for name, image in images.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def storage_shelf():
    frame = ''.join(block((x, y, 0, x + 15, y + 16, 232), IRON)
                    for x in (-154, 139) for y in (-68, 51))
    decks = ''.join(block((-154, -72, z - 12, 154, 72, z - 4), IRON)
                    + block((-154, -72, z - 4, 154, 72, z), WOOD)
                    for z in (64, 144, 224))
    braces = ''.join(prism([(-59, z), (55, z + 57), (55, z + 65), (-59, z + 8)],
                           x, x + 7, RED)
                     for x in (-153, 147) for z in (65, 145))
    bolts = ''.join(block((x, -70, z, x + 7, -67, z + 6), ZINC)
                    for x in (-149, 143) for z in (44, 123, 204))
    return frame + decks + braces + bolts


def workbench():
    legs = ''.join(block((x, y, 0, x + 18, y + 18, 115), IRON)
                   for x in (-152, 134) for y in (-63, 49))
    rails = block((-149, 52, 26, 149, 65, 38), RED)
    rails += block((-148, -61, 99, 148, 67, 114), IRON)
    top = bevel((-165, -74, 110, 165, 76, 129), 3, WOOD)
    drawers = ''.join(block((x, -64, 68, x + 51, 52, 113), IRON)
                      + block((x + 3, -69, 71, x + 47, -62, 95), RED)
                      + block((x + 12, -71, 82, x + 38, -67, 88), ZINC)
                      for x in (36, 91))
    return legs + rails + top + drawers


def furnace():
    base = block((-108, -80, 0, 108, 86, 12), INK)
    shell = bottle_shape(120, 87, 9, [(8, 1, 0, 0), (149, 1, 0, 0)], IRON)
    roof = block((-120, -88, 147, 120, 88, 160), ZINC)
    panels = ''.join(bevel((-109, -91, z, 109, -85, Z), 2, IRON)
                     for z, Z in ((17, 81), (88, 142)))
    intake = block((-97, -93, 22, 97, -90, 73), INK)
    louvers = ''.join(block((-92, -97, z, 92, -91, z + 3), ZINC) for z in range(28, 72, 8))
    latch = bevel((54, -99, 113, 91, -89, 122), 2, ZINC)
    light = block((-87, -93, 120, -74, -90, 126), RED)
    duct = prism([(32, 159), (83, 159), (82, 207), (51, 224), (32, 224)], -53, 53, ZINC)
    seam = block((-55, 30, 214, 55, 84, 220), GRAY)
    return base + shell + roof + panels + intake + louvers + latch + light + duct + seam


def water_heater():
    shell = oval([(0, 0, 0, 69), (12, 0, 0, 81), (217, 0, 0, 81),
                  (231, 0, 0, 71), (237, 0, 0, 49)], CREAM, sides=12)
    skirt = straight_oval(0, 0, 83, 83, 13, 29, IRON)
    access = bevel((-45, -81, 34, 45, -71, 89), 3, IRON)
    fasteners = ''.join(block((x, -83, 78, x+5, -80, 83), ZINC) for x in (-36, 31))
    drain = straight_oval(35, 40, 9, 9, -100, -79, COPPER, axis='y')
    drain += straight_oval(35, -95, 11, 11, 42, 49, RED)
    inlets = ''.join(straight_oval(x, 18, 10, 10, 232, 264, COPPER)
                     + straight_oval(x, 18, 13, 13, 249, 256, ZINC)
                     for x in (-27, 27))
    vent = straight_oval(0, -22, 20, 20, 231, 260, ZINC)
    vent += straight_oval(0, -22, 25, 25, 260, 266, IRON)
    return shell + skirt + access + fasteners + drain + inlets + vent


def dehumidifier():
    case = bevel((-72, -48, 0, 72, 53, 131), 6, CREAM)
    grille = block((-59, -50, 24, 59, -47, 102), INK)
    slots = ''.join(block((-54, -53, z, 54, -49, z + 3), ZINC) for z in range(29, 103, 8))
    pan = block((-61, -53, 6, 61, -45, 23), TEAL)
    pan += block((-29, -56, 13, 29, -52, 17), IRON)
    controls = bevel((-46, -11, 128, 46, 28, 133), 1, IRON)
    buttons = ''.join(block((x, 0, 132, x + 9, 13, 135), tint)
                      for x, tint in ((-32, RED), (-13, CREAM), (14, CREAM)))
    return case + grille + slots + pan + controls + buttons


def sump_cover():
    rim = oval([(0, 0, 0, 72), (9, 0, 0, 82), (14, 0, 0, 82)], IRON)
    inset = straight_oval(0, 0, 64, 64, 14, 17, INK)
    grates = ''.join(block((-42, y, 17, 42, y + 5, 19), ZINC) for y in range(-42, 43, 14))
    drain = straight_oval(48, 0, 9, 9, 16, 74, ZINC)
    drain += straight_oval(48, 74, 10, 10, 0, 28, ZINC, axis='y')
    return rim + inset + grates + drain


def tube_x(first, last, radius=14, tint=COPPER, *, y=0, z=24):
    return straight_oval(y, z, radius, radius, first, last, tint, axis='x')


def tube_y(first, last, radius=14, tint=COPPER, *, x=0, z=24):
    return straight_oval(x, z, radius, radius, first, last, tint, axis='y')


def straight_pipe(half_length):
    collars = ''.join(tube_x(x - 5, x + 5, 18, ZINC)
                      for x in (-half_length + 15, half_length - 15))
    return tube_x(-half_length, half_length) + collars


def swept_elbow(*, vertical=False):
    profile = disc(0, 0, 14, 14, 0, 12)
    rings = []
    for angle in (-90, -60, -30, 0):
        c, s = cos(radians(angle)), sin(radians(angle))
        section = [(-64 + (64 + radial) * c, 64 + (64 + radial) * s, 24 + lift)
                   for radial, lift, _ in profile]
        if vertical:
            section = [(x, z - 24, y + 24) for x, y, z in section]
        rings.append(section)
    return loft(rings, COPPER)


def pipe_elbow():
    return swept_elbow()


def pipe_riser():
    return swept_elbow(vertical=True)


def pipe_tee():
    body = tube_x(-64, 64) + tube_y(0, 64)
    coupling = block((-18, -18, 7, 18, 20, 41), COPPER)
    rings = tube_y(18, 27, 17, ZINC)
    rings += tube_x(-25, -17, 17, ZINC) + tube_x(17, 25, 17, ZINC)
    return body + coupling + rings


def pipe_valve():
    body = tube_x(-64, 64) + tube_x(-19, 19, 20, BRASS)
    gland = straight_oval(0, 0, 11, 11, 36, 64, BRASS)
    wheel = ring_band(0, 0, (62, 17, 23), (69, 17, 23), RED, sides=12)
    spokes = block((-20, -3, 62, 20, 3, 68), RED)
    spokes += block((-3, -20, 62, 3, 20, 68), RED)
    cap = straight_oval(0, 0, 5, 5, 68, 72, ZINC)
    return body + gland + wheel + spokes + cap


def pipe_hanger():
    tube = tube_x(-64, 64)
    clamp = tube_x(-6, 6, 18, ZINC)
    shank = block((-4, -4, 40, 4, 4, 75), IRON)
    plate = bevel((-17, -15, 73, 17, 15, 80), 1, ZINC)
    return tube + clamp + shank + plate


def duct_straight():
    panel = block((-120, -46, 16, 120, 46, 84), ZINC)
    return panel + ''.join(block((x - 4, -49, 13, x + 4, 49, 87), IRON) for x in (-92, 0, 92))


def duct_elbow():
    panel = block((-120, -46, 16, 46, 46, 84), ZINC)
    panel += block((-46, 46, 16, 46, 120, 84), ZINC)
    band = block((-99, -49, 13, -91, 49, 87), IRON)
    band += block((-49, 91, 13, 49, 99, 87), IRON)
    return panel + band


def taped_box():
    box = bevel((-107, -73, 0, 107, 73, 93), 4, KRAFT)
    tape = block((-97, -12, 92, 98, 13, 95), TAPE)
    tape += block((-109, -12, 49, -105, 13, 93), TAPE)
    tape += block((105, -12, 61, 109, 13, 93), TAPE)
    fold = block((-97, -75, 70, 92, -72, 73), FLUTE)
    patch = block((-83, -76, 34, -42, -74, 57), PAPER)
    return box + tape + fold + patch


def open_box():
    floor = block((-99, -77, 0, 99, 79, 10), KRAFT)
    walls = ''.join(block(b, KRAFT) for b in (
        (-99, -77, 9, -90, 79, 104), (90, -77, 9, 99, 79, 104),
        (-90, 71, 9, 90, 79, 104),
        (-90, -77, 9, -64, -69, 101), (64, -77, 9, 90, -69, 101)))
    flap = prism([(71, 101), (143, 127), (142, 134), (74, 109)], -93, 93, FLUTE)
    flap += prism([(92, 101), (147, 114), (146, 121), (91, 109)], -70, 67, KRAFT, axis='y')
    flap += prism([(-152, 127), (-146, 132), (-90, 108), (-92, 102)], -70, 65, KRAFT, axis='y')
    return floor + walls + flap


def crushed_box():
    base = slab([(-112, -44), (-78, -78), (48, -77), (104, -48), (108, 42),
                 (67, 78), (-97, 66)], 0, 8, KRAFT)
    crease = prism([(-97, 7), (89, 7), (72, 18), (-38, 34)], -49, 56, FLUTE, axis='y')
    fold = slab([(-108, -55), (-70, -77), (-18, -58), (5, 16), (-94, 45)], 7, 16, KRAFT)
    tape = slab([(-82, -29), (-56, -45), (60, 3), (63, 24), (-17, 16)], 13, 17, TAPE)
    return base + crease + fold + tape


def archive_box():
    body = bevel((-81, -56, 0, 81, 56, 79), 3, 'bedroom/attic_tan')
    lid = bevel((-87, -61, 72, 87, 61, 92), 3, KRAFT)
    slot = bevel((-26, -59, 50, 26, -55, 61), 1, INK)
    label = block((-49, -58, 31, 49, -55, 40), PAPER)
    return body + lid + slot + label


def milk_crate():
    bottom = block((-80, -74, 0, 80, 74, 11), NAVY)
    perimeter = ''.join(block(b, NAVY) for b in (
        (-82, -76, 75, 82, -67, 88), (-82, 67, 75, 82, 76, 88),
        (-82, -67, 75, -73, 67, 88), (73, -67, 75, 82, 67, 88)))
    uprights = ''.join(block((x, y, 10, x + 8, y + 8, 76), NAVY)
                       for x in (-80, 72) for y in (-74, 66))
    slats = ''.join(block((x, y, 10, x + 9, y + 7, 76), TEAL)
                    for x in (-54, -31, -8, 15, 38, 61) for y in (-74, 67))
    slats += ''.join(block((x, y, 10, x + 7, y + 8, 76), TEAL)
                     for x in (-80, 73) for y in (-49, -25, -1, 23, 47))
    return bottom + perimeter + uprights + slats


def tote():
    body = bottle_shape(110, 70, 16, [(0, .86, 0, 0), (76, 1, 0, 0)], TEAL)
    lid = bevel((-117, -76, 72, 117, 76, 91), 4, NAVY)
    clasps = ''.join(block((x, -77, 65, x + 31, -72, 83), ZINC) for x in (-76, 45))
    return body + lid + clasps


def pallet():
    skids = ''.join(block((x, -82, 0, x + 15, 82, 19), WOOD) for x in (-97, -8, 82))
    deck = ''.join(block((-99, y, 19, 99, y + 25, 28), WOOD)
                   for y in (-84, -53, -21, 11, 43, 65))
    return skids + deck


def paint_cans():
    cans = ''
    for x, y, radius, height, tint in ((-47, -10, 34, 77, IRON), (31, 24, 27, 60, RED),
                                       (47, -44, 23, 42, ZINC)):
        cans += straight_oval(x, y, radius, radius, 0, height, tint)
        cans += straight_oval(x, y, radius + 2, radius + 2, height, height + 5, ZINC)
        cans += straight_oval(x, y, radius + 1, radius + 1, 0, 5, GRAY)
    return cans


def carton_steps():
    stairs = ''
    for i, tint in enumerate((KRAFT, 'bedroom/attic_tan', KRAFT, FLUTE)):
        y, height = -203 + 53 * i, 16 * (i + 1)
        end = y + 53
        stairs += block((-74, y, 0, 74, end, height - 4), tint)
        stairs += block((-74, y, height - 4, 74, end, height), KRAFT)
        for x in (-75, 73):
            stairs += block((x, y + 13, height - 14, x + 2, end - 13, height - 5), TAPE)
    return stairs


def cinderblock_steps():
    stairs = ''
    for i in range(3):
        x, top = -118 + 65 * i, (i + 1) * 16
        stairs += block((x, -47, 0, x + 65, 47, top), CONCRETE)
        for y in (-48, 47):
            for dx in (9, 35):
                stairs += block((x + dx, y, top - 12, x + dx + 19, y + 1, top - 5), IRON)
    return stairs


def duct_ramp():
    deck = prism([(-340, 0), (-297, 0), (188, 136), (188, 160)], -69, 69, ZINC, axis='y')
    landing = block((188, -69, 136, 268, 69, 160), ZINC)
    supports = ''.join(block((x, -49, 0, x + 29, 49, h), IRON)
                       for x, h in ((-109, 58), (64, 102), (201, 137)))
    rim = ''.join(prism([(-315, 4), (188, 149), (188, 160), (-315, 8)], y, y + 4,
                        IRON, axis='y') for y in (-70, 67))
    bolts = ''.join(block((x, y, 148, x + 5, y + 3, 154), GRAY)
                    for x in (207, 240) for y in (-70, 68))
    return deck + landing + supports + rim + bolts


PREFABS = {
    'storage_shelf': storage_shelf, 'workbench': workbench, 'furnace': furnace,
    'water_heater': water_heater, 'dehumidifier': dehumidifier, 'sump_cover': sump_cover,
    'pipe_straight': lambda: straight_pipe(64), 'pipe_long': lambda: straight_pipe(128),
    'pipe_elbow': pipe_elbow, 'pipe_riser': pipe_riser, 'pipe_tee': pipe_tee,
    'pipe_valve': pipe_valve, 'pipe_hanger': pipe_hanger, 'duct_straight': duct_straight,
    'duct_elbow': duct_elbow, 'box_sealed': taped_box, 'box_open': open_box,
    'box_crushed': crushed_box, 'box_archive': archive_box, 'milk_crate': milk_crate,
    'tote': tote, 'pallet': pallet, 'paint_cans': paint_cans, 'carton_steps': carton_steps,
    'cinderblock_steps': cinderblock_steps, 'duct_ramp': duct_ramp,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, make in PREFABS.items():
        data = HEADER + '{\n"classname" "worldspawn"\n' + make() + '}\n'
        (args.output / f'basement_{name}.map').write_text(data, encoding='ascii')


if __name__ == '__main__':
    main()
