#!/usr/bin/env python3
"""Export editable, unmarked dining-room brushes for the Quake II prefab library."""

import argparse
from math import cos, sin, tau
from pathlib import Path

from generate_bath_prefabs import HEADER, bevel, block, bottle_shape, oval, straight_oval
from generate_bathroom import BASE, disc
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, ring_band, ring_sections, slab
from generate_garden_prefabs import blade
from generate_kitchen_prefabs import bowl_shell
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette

WALNUT = 'bedroom/dining_walnut'
LINEN = 'bedroom/dining_linen'
GLAZE = 'bedroom/dining_glaze'
OCHRE = 'bedroom/dining_ochre'
CREAM = 'enamel'
INK = 'toy_ink'
STEEL = 'kitchen_steel'
BRASS = 'bedroom/attic_brass'
RUST = 'bedroom/living_rust'
SAGE = 'bedroom/living_sage'
BLUE = 'bedroom/living_blue'
WICKER = 'laundry_wicker'
GLASS = 'toy_aqua'
GREEN = 'kitchen_green'
APPLE = 'kitchen_apple'
ORANGE = 'toy_orange'


def write_materials():
    def weave(x, y):
        return 5 * cos(tau * x / 4) + 5 * sin(tau * y / 4) + 3 * cos(tau * (x + y) / 16)

    images = {
        WALNUT: finish((128, 78, 51), lambda x, y: (
            10 * sin(tau * y / 32 + sin(tau * x / 128))
            + 4 * sin(tau * y / 8 + cos(tau * x / 64)))),
        LINEN: finish((219, 204, 175), weave),
        OCHRE: finish((174, 126, 62), weave),
        GLAZE: finish((55, 96, 111), lambda x, y: (
            6 * cos(tau * (x - y) / 128) + 2 * cos(tau * y / 16))),
    }
    palette = load_palette()
    for name, image in images.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def rectangular_table():
    top = bottle_shape(312, 154, 24, [(127, 1, 0, 0), (144, 1, 0, 0)], WALNUT)
    aprons = ''.join(block(bounds, WALNUT) for bounds in (
        (-281, -128, 103, 281, -114, 129), (-281, 114, 103, 281, 128, 129),
        (-281, -128, 103, -266, 128, 129), (266, -128, 103, 281, 128, 129),
    ))
    legs = ''.join(bottle_shape(15, 15, 3, [(0, .72, x, y), (108, 1, x, y),
                                           (129, 1, x, y)], WALNUT)
                   for x in (-268, 268) for y in (-115, 115))
    return legs + aprons + top


def round_table():
    top = oval([(121, 0, 0, 192), (127, 0, 0, 203), (144, 0, 0, 203)],
               WALNUT, sides=20)
    post = oval([(13, 0, 0, 35), (34, 0, 0, 31), (95, 0, 0, 24),
                 (126, 0, 0, 43)], WALNUT)
    foot = bevel((-135, -15, 0, 135, 15, 23), 4, WALNUT)
    foot += bevel((-15, -135, 0, 15, 135, 23), 4, WALNUT)
    return foot + post + top


def chair_frame():
    seat = bevel((-68, -66, 64, 68, 59, 80), 4, WALNUT)
    legs = ''.join(bottle_shape(9, 9, 3, [(0, .82, x, y), (68, 1, x, y)], WALNUT)
                   for x in (-53, 53) for y in (-49, 45))
    rails = ''.join(block((x, -49, 28, x + 10, 45, 37), WALNUT)
                    for x in (-58, 48))
    back = ''.join(prism([(36, 74), (52, 72), (70, 170), (55, 174)],
                          x, x + 15, WALNUT)
                   for x in (-62, 47))
    return seat + legs + rails + back


def ladderback():
    slats = ''.join(bevel((-54, y, z, 54, y + 13, z + 14), 2, WALNUT)
                    for y, z in ((45, 102), (50, 128), (55, 154)))
    return chair_frame() + slats


def upholstered_chair():
    seat = bevel((-64, -63, 75, 64, 55, 93), 5, BLUE)
    back = prism([(39, 93), (54, 90), (69, 167), (54, 173)], -54, 54, BLUE)
    crest = bevel((-62, 52, 165, 62, 71, 178), 2, WALNUT)
    return chair_frame() + seat + back + crest


def bench():
    seat = bottle_shape(158, 47, 12, [(66, .96, 0, 0), (70, 1, 0, 0),
                                      (80, 1, 0, 0)], WALNUT)
    legs = ''.join(bevel((x, y, 0, x + 18, y + 18, 70), 3, WALNUT)
                   for x in (-133, 115) for y in (-36, 18))
    brace = block((-126, -7, 22, 126, 7, 36), WALNUT)
    return legs + brace + seat


def sideboard():
    feet = ''.join(block((x, y, 0, x + 17, y + 17, 21), WALNUT)
                   for x in (-174, 157) for y in (-60, 57))
    body = block((-183, -68, 18, 183, 81, 117), WALNUT)
    top = block((-192, -74, 115, 192, 87, 128), WALNUT)
    doors = ''
    for x in (-174, 62):
        doors += bevel((x, -73, 25, x + 111, -66, 111), 2, WALNUT)
        doors += bevel((x + 11, -75, 35, x + 100, -72, 101), 1, SAGE)
        handle = x + (92 if x < 0 else 18)
        doors += straight_oval(handle, 66, 6, 6, -81, -74, BRASS, axis='y')
    drawers = ''.join(block((-56, -73, z, 56, -67, z + 23), WALNUT)
                      + bevel((-17, -80, z + 9, 17, -72, z + 15), 1, BRASS)
                      for z in (27, 55, 83))
    return feet + body + top + doors + drawers


def plate_at(x, y, size, z=0, *, tint=CREAM, band=GLAZE):
    floor = oval([(height, x, y, size * .72) for height in (z, z + 7)], tint, sides=16)
    rim = ring_band(x, y, (z + 7, size * .63, size * .72),
                    (z + 15, size * .91, size), tint)
    edge = ring_band(x, y, (z + 15, size * .91, size),
                     (z + 17, size * .91, size), band)
    return floor + rim + edge


def dinner_plate():
    return plate_at(0, 0, 69)


def side_plate():
    return plate_at(0, 0, 47, tint=GLAZE, band=CREAM)


def soup_bowl():
    return bowl_shell(0, 0, 0, 39, 43, 66, CREAM, GLAZE)


def goblet_at(x, y, z=0):
    foot = oval([(z, x, y, 24), (z + 5, x, y, 24),
                 (z + 10, x, y, 8), (z + 30, x, y, 7)], GLASS)
    bowl = straight_oval(x, y, 13, 13, z + 30, z + 36, GLASS)
    # Both halves share a full ring at the bowl's widest point.
    profile = [(z + 36, 9, 13), (z + 57, 22, 26), (z + 75, 19, 24)]
    rings = [(disc(x, y, inner, inner, height, 12), disc(x, y, outer, outer, height, 12))
             for height, inner, outer in profile]
    bowl += ring_sections(rings, GLASS)
    return foot + bowl


def goblet():
    return goblet_at(0, 0)


def fork_at(x, y, z):
    handle = bevel((x - 5, y - 45, z, x + 5, y + 14, z + 5), 1, STEEL)
    neck = slab([(x - 4, y + 8), (x + 4, y + 8), (x + 12, y + 27),
                 (x - 12, y + 27)], z + 1, z + 5, STEEL)
    tines = ''.join(block((x + dx, y + 24, z + 1, x + dx + 4, y + 46, z + 5), STEEL)
                    for dx in (-12, -5, 2, 9))
    return handle + neck + tines


def knife_at(x, y, z):
    grip = bevel((x - 6, y - 45, z, x + 6, y + 2, z + 6), 1, WALNUT)
    blade_outline = [(x - 7, y - 1), (x + 4, y - 1), (x + 6, y + 41),
                     (x + 1, y + 46), (x - 6, y + 37)]
    return grip + slab(blade_outline, z + 1, z + 5, STEEL)


def spoon_at(x, y, z):
    handle = bevel((x - 4, y - 45, z, x + 4, y + 20, z + 5), 1, STEEL)
    cup = straight_oval(x, y + 28, 10, 17, z, z + 3, STEEL)
    cup += oval([(z + 2, x, y + 28, 10), (z + 7, x, y + 29, 14)],
                STEEL, aspect=1.35)
    return handle + cup


def flatware():
    return fork_at(-33, 0, 0) + knife_at(2, 0, 0) + spoon_at(34, 0, 0)


def mat_at(x, y, rx, ry, tint):
    edge = bottle_shape(rx, ry, 9, [(0, 1, x, y), (4, 1, x, y)], tint)
    inset = block((x - rx + 13, y - ry + 10, 3, x + rx - 13, y + ry - 10, 5), LINEN)
    return edge + inset


def placemat():
    return mat_at(0, 0, 122, 78, GLAZE)


def place_setting():
    return (placemat() + plate_at(0, -2, 60, 5)
            + fork_at(-78, -11, 5) + knife_at(76, -11, 5)
            + spoon_at(100, -11, 5) + goblet_at(83, 49, 5))


def folded_napkin():
    lower = slab([(-61, -43), (63, -38), (54, 40), (-50, 46)], 0, 5, GLAZE)
    fold = slab([(-57, -40), (61, -37), (49, 15)], 4, 10, BLUE)
    corner = slab([(-56, -39), (48, 15), (-49, 43)], 5, 12, GLAZE)
    return lower + fold + corner


def napkin_ring():
    cloth = oval([(-68, 0, 17, 14), (-41, 0, 17, 24), (18, 0, 17, 21),
                  (67, 0, 17, 26)], LINEN, aspect=.62, axis='y')
    clasp = ring_sections([(disc(0, 16, 18, 12, y, 12), disc(0, 16, 26, 16, y, 12))
                           for y in (-22, 17)], BRASS, axis='y')
    return cloth + clasp + block((-11, -38, 0, 11, 34, 4), LINEN)


def runner():
    textile = mat_at(0, 0, 270, 39, RUST)
    fringe = ''.join(block((x, y, 0, x + 12, y + 3, 3), LINEN)
                     for y in range(-28, 29, 7) for x in (-280, 268))
    return textile + fringe


def platter():
    foot = straight_oval(0, 0, 107, 48, 0, 8, GLAZE)
    lip = oval([(6, 0, 0, 107), (12, 0, 0, 126)], CREAM, aspect=.47, sides=16)
    accents = ''.join(bevel((x, -19, 3, x + 26, 19, 14), 2, GLAZE)
                       for x in (-142, 116))
    return foot + lip + accents


def bread_basket():
    basket = bowl_shell(0, 0, 0, 43, 49, 72, WICKER, OCHRE)
    bread = ''.join(oval([(20, x, y, 15), (33, x, y, 23), (49, x, y, 23),
                          (58, x, y, 15)], 'kitchen_crust', aspect=.80, sides=10)
                    for x, y in ((-28, -20), (23, -16), (0, 26)))
    cuts = ''.join(block((x - 10, y - 2, 56, x + 10, y + 2, 59), 'kitchen_crumb')
                    for x, y in ((-28, -20), (23, -16), (0, 26)))
    return basket + bread + cuts


def fruit_bowl():
    bowl = bowl_shell(0, 0, 0, 43, 47, 69, GLAZE, CREAM)
    for x, y, base, rx, tint in ((-26, -13, 20, 25, APPLE), (22, -12, 21, 24, ORANGE),
                                  (0, 24, 19, 27, 'kitchen_green'), (-4, 2, 39, 21, APPLE)):
        bowl += oval([(base, x, y, .62 * rx), (base + 12, x, y, rx),
                       (base + 32, x, y, .93 * rx), (base + 39, x, y, .51 * rx)],
                      tint, sides=10)
        bowl += block((x - 2, y - 2, base + 37, x + 2, y + 2, base + 45), WALNUT)
    return bowl


def flower_vase():
    vase = straight_oval(0, 0, 32, 32, 0, 9, GLAZE)
    for lower, upper in (
        ((8, 27, 32), (28, 44, 50)), ((28, 44, 50), (61, 32, 37)),
        ((61, 32, 37), (82, 23, 28)), ((82, 23, 28), (89, 27, 33)),
    ):
        vase += ring_band(0, 0, lower, upper, GLAZE, sides=12)
    for x, y, top, tint in ((-38, -13, 130, CREAM), (32, -11, 154, 'toy_coral'),
                             (-1, 23, 171, OCHRE), (13, 23, 125, CREAM)):
        vase += oval([(7, 0, 0, 3), (top + 1, x, y, 3)], GREEN, sides=8)
        vase += blade(x * .76, y * .76, top * .76, x / 22, 26, 10, 7, GREEN)
        for i in range(6):
            theta = tau * i / 6
            vase += straight_oval(x + 11 * cos(theta), y + 11 * sin(theta),
                                   8, 8, top - 1, top + 5, tint)
        vase += straight_oval(x, y, 6, 6, top, top + 8, 'toy_lemon')
    return vase


def candlesticks():
    pieces = ''
    for x, y, height, wax in ((-27, 3, 115, LINEN), (29, -5, 84, RUST)):
        pieces += oval([(0, x, y, 24), (5, x, y, 25), (12, x, y, 14),
                        (25, x, y, 7), (height - 53, x, y, 7),
                        (height - 43, x, y, 15)], BRASS)
        pieces += straight_oval(x, y, 9, 9, height - 43, height, wax)
        pieces += block((x - 1, y - 1, height - 1, x + 1, y + 1, height + 4), INK)
    return pieces


def salt_pepper():
    pieces = ''
    for x, y, tint in ((-24, -6, CREAM), (25, 9, GLAZE)):
        pieces += oval([(0, x, y, 15), (7, x, y, 20), (39, x, y, 20),
                        (49, x, y, 15)], tint)
        pieces += straight_oval(x, y, 16, 16, 48, 56, STEEL)
        for dx, dy in ((-6, 0), (6, 0), (0, 6), (0, -6)):
            pieces += block((x+dx-1, y+dy-1, 55, x+dx+1, y+dy+1, 57), INK)
    return pieces


def pitcher():
    body = bowl_shell(0, 0, 0, 90, 33, 41, CREAM, GLAZE)
    handle = ring_band(44, 53, (-5, 22, 29), (5, 22, 29), GLAZE, axis='y', sides=12)
    spout = prism([(-52, 91), (-21, 75), (-20, 84), (-51, 98)], -10, 10,
                  GLAZE, axis='y')
    return body + handle + spout


def linen_steps():
    stairs = ''
    colors = (OCHRE, LINEN, RUST, BLUE, LINEN, OCHRE, RUST, LINEN, BLUE)
    for i, tint in enumerate(colors):
        y, z = -420 + 46 * i, i * 16
        width = 90 - 2 * i
        stairs += block((-width, y, z, width, 28, z + 16), tint)
        for x in (-width - 1, width - 2):
            stairs += block((x, y + 7, z + 4, x + 3, 19, z + 9), LINEN if tint != LINEN else RUST)
    return stairs


def serving_crate_steps():
    stairs = ''
    for i in range(8):
        x, height = -250 + 56 * i, (i + 1) * 16
        end = x + 56 if i < 7 else 222
        stairs += block((x, -66, 0, end, 66, height - 5), WALNUT)
        stairs += block((x, -66, height - 5, end, 66, height), OCHRE)
        for y in (-68, 66):
            stairs += block((x + 12, y, height - 12, end - 12, y + 2, height - 8), INK)
    return stairs


def table_leaf_ramp():
    board = prism([(-169, 0), (-137, 0), (132, 48), (132, 64)], -63, 63, WALNUT, axis='y')
    landing = block((132, -63, 49, 207, 63, 64), WALNUT)
    prop = bevel((129, -54, 0, 195, 54, 51), 4, OCHRE)
    braces = ''.join(block((164, y, 48, 188, y + 2, 58), BRASS) for y in (-64, 62))
    return board + landing + prop + braces


PREFABS = {
    'table_rect': rectangular_table, 'table_round': round_table,
    'chair_ladderback': ladderback, 'chair_upholstered': upholstered_chair,
    'bench': bench, 'sideboard': sideboard, 'place_setting': place_setting,
    'dinner_plate': dinner_plate, 'side_plate': side_plate, 'soup_bowl': soup_bowl,
    'goblet': goblet, 'flatware': flatware, 'napkin_folded': folded_napkin,
    'napkin_ring': napkin_ring, 'placemat': placemat, 'runner': runner,
    'serving_platter': platter, 'bread_basket': bread_basket, 'fruit_bowl': fruit_bowl,
    'flower_vase': flower_vase, 'candlesticks': candlesticks, 'salt_pepper': salt_pepper,
    'pitcher': pitcher, 'linen_steps': linen_steps, 'serving_crate_steps': serving_crate_steps,
    'table_leaf_ramp': table_leaf_ramp,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, make in PREFABS.items():
        data = HEADER + '{\n"classname" "worldspawn"\n' + make() + '}\n'
        (args.output / f'dining_{name}.map').write_text(data, encoding='ascii')


if __name__ == '__main__':
    main()
