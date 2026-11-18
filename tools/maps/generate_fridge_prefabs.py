#!/usr/bin/env python3
"""Export an open refrigerator and unmarked food props as Quake II detail brushes."""

import argparse
from math import cos, sin, tau
from pathlib import Path

from generate_bath_prefabs import block, bottle_shape, oval, straight_oval
from generate_bathroom import BASE
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, slab
from generate_pantry_prefabs import translated_package, wrap
from generate_sandkeep_materials import write_wal
from generate_switchyard import face
from platoon_palette import load_palette
from verify_sandkeep import parse_entities

SHELL = 'bathroom/fridge_shell'
LINER = 'bathroom/fridge_liner'
ICE = 'bathroom/fridge_ice'
PULP = 'bathroom/fridge_pulp'
EGG = 'bathroom/fridge_egg'
LEAF = 'bathroom/fridge_leaf'
GRAPE = 'bathroom/fridge_grape'
WHITE = 'enamel'
STEEL = 'garage_steel'
BLUE = 'toy_blue'
NAVY = 'toy_navy'
TEAL = 'laundry_teal'
MINT = 'toy_mint'
RED = 'kitchen_apple'
GOLD = 'kitchen_cheese'
ORANGE = 'toy_orange'
GREEN = 'kitchen_green'
TAN = 'bedroom/pantry_amber'
BROWN = 'kit_beech'

DOOR_HINGE = (-229, -125)
DOOR_ANGLE = -136 / 360 * tau
SHELF_HEIGHTS = (16, 176, 344, 510)
BODY_STOCK = (
    ('milk_carton', -143, 72, 510), ('milk_carton_small', -25, 81, 510),
    ('butter', 114, 87, 510),
    ('egg_carton_open', -100, 43, 344), ('leftover_round', 104, 80, 344),
    ('lemon', -146, -65, 344), ('grapes', 132, -39, 344),
    ('leftover_open', -123, 76, 176), ('leftover_rect', 47, 102, 176),
    ('foil_tray', 134, -36, 176), ('carrots', -145, -41, 176),
    ('lettuce', -68, 108, 24), ('lemon', -151, 107, 24),
    ('apples', 51, 109, 24), ('peppers', 146, 108, 24),
)
DOOR_STOCK = (
    ('dressing', 77, 55, 107), ('ketchup', 175, 53, 107),
    ('mustard', 276, 54, 107), ('mayonnaise', 371, 53, 107),
    ('hot_sauce', 77, 50, 292), ('pickle_jar', 182, 56, 292),
    ('dressing', 292, 55, 292), ('hot_sauce', 381, 52, 292),
    ('milk_carton_small', 138, 59, 477), ('butter', 340, 54, 477),
)


def write_materials():
    textured = {
        SHELL: finish((180, 194, 192), lambda x, y: 4*cos(tau*x/128) + 2*sin(tau*y/32)),
        LINER: finish((222, 228, 214), lambda x, y: 3*cos(tau*(x+y)/128)),
        ICE: finish((142, 191, 193), lambda x, y: 8*cos(tau*(x-y)/128) + 2*cos(tau*y/16)),
        PULP: finish((143, 154, 133), lambda x, y: (x*5 ^ y*31) % 13 - 6),
        EGG: finish((198, 151, 108), lambda x, y: 4*cos(tau*(x-y)/128) - 5*((x*3 ^ y*5) % 11 == 0)),
        LEAF: finish((108, 157, 77), lambda x, y: 7*sin(tau*(x + 2*y)/32)),
        GRAPE: finish((107, 80, 129), lambda x, y: 6*cos(tau*(x-y)/128)),
    }
    palette = load_palette()
    for name, image in textured.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def crisper(cx):
    floor = block((cx-94, 35, 16, cx+94, 175, 24), ICE)
    sides = ''.join(block(bounds, LINER) for bounds in (
        (cx-94, 35, 24, cx-86, 175, 57), (cx+86, 35, 24, cx+94, 175, 57),
        (cx-86, 167, 24, cx+86, 175, 62),
    ))
    face_panel = block((cx-94, 34, 24, cx+94, 42, 68), ICE)
    handle = block((cx-38, 28, 54, cx+38, 35, 62), WHITE)
    return floor + sides + face_panel + handle


def cabinet():
    skin = ''.join(block(bounds, SHELL) for bounds in (
        (-246, -135, 0, -216, 205, 690), (216, -135, 0, 246, 205, 690),
        (-216, 178, 0, 216, 205, 690), (-216, -131, 664, 216, 178, 690),
    ))
    liner = ''.join(block(bounds, LINER) for bounds in (
        (-232, -119, 16, -207, 178, 664), (207, -119, 16, 232, 178, 664),
        (-207, 173, 16, 207, 182, 664), (-207, -119, 652, 207, 179, 664),
        (-216, -126, 0, 216, 179, 16),
    ))
    decks = ''.join(block((-207, -108, z-11, 207, 173, z), ICE)
                    + block((-207, -111, z-11, 207, -101, z), LINER)
                    for z in SHELF_HEIGHTS[1:])
    jamb = ''.join(block((x, -137, 17, x+8, -131, 666), NAVY) for x in (-218, 210))
    jamb += block((-218, -137, 664, 218, -131, 672), NAVY)
    hinges = ''.join(block((-247, -140, z, -213, -121, z+17), STEEL)
                      for z in (21, 333, 638))
    vent = block((-81, 166, 593, 81, 174, 628), ICE)
    vent += ''.join(block((-71, 163, z, 71, 169, z+3), STEEL) for z in (600, 609, 618))
    lamp = block((-88, -91, 643, 88, -46, 652), WHITE)
    return skin + liner + decks + jamb + hinges + vent + lamp + crisper(-104) + crisper(104)


def door_bin(z):
    deck = block((32, 18, z-11, 434, 101, z), LINER)
    cheeks = ''.join(block((x, 21, z, x+11, 101, z+44), LINER) for x in (32, 423))
    rail = block((32, 96, z, 434, 105, z+37), ICE)
    trim = block((29, 93, z+37, 437, 108, z+45), LINER)
    return deck + cheeks + rail + trim


def door():
    slab_brush = block((1, -26, 1, 462, 17, 680), SHELL)
    inset = block((14, 16, 13, 449, 24, 668), LINER)
    gasket = ''.join(block(bounds, NAVY) for bounds in (
        (5, 17, 7, 13, 22, 674), (448, 17, 7, 456, 22, 674),
        (13, 17, 7, 448, 22, 14), (13, 17, 667, 448, 22, 674),
    ))
    grip = block((411, -48, 272, 430, -43, 456), STEEL)
    grip += ''.join(block((412, -48, z, 429, -24, z+14), STEEL) for z in (271, 444))
    return slab_brush + inset + gasket + grip + ''.join(door_bin(z) for z in (107, 292, 477))


def milk(width, depth, height, tint):
    base = block((-width, -depth, 0, width, depth, 23), tint)
    sidewall = block((-width, -depth, 23, width, depth, height-35), WHITE)
    fold = prism([(-depth, height-35), (depth, height-35), (4, height-10),
                  (-4, height-10)], -width, width, WHITE)
    seam = block((-width, -5, height-10, width, 5, height-5), tint)
    stamp = block((-width+8, -depth-1, 31, width-8, -depth+1, 35), tint)
    cap = straight_oval(width*.54, 0, 9, 9, height-5, height, tint)
    return base + sidewall + fold + seam + stamp + cap


def egg_at(x, y, z, tint=EGG):
    levels = ((0, 7), (8, 14), (20, 17), (34, 13), (45, 8), (49, 3))
    return oval([(z+h, x, y, radius) for h, radius in levels], tint, sides=8)


def egg_carton(*, opened):
    base = bottle_shape(104, 49, 13, [(0, .93, 0, 0), (9, 1, 0, 0),
                                        (17, 1, 0, 0)], PULP)
    rim = ''.join(block(bounds, PULP) for bounds in (
        (-101, -49, 17, 101, -43, 24), (-101, 43, 17, 101, 49, 24),
        (-104, -43, 17, -97, 43, 22), (97, -43, 17, 104, 43, 22),
    ))
    if opened:
        lid = prism([(44, 17), (67, 87), (58, 91), (38, 23)], -101, 101, PULP)
        eggs = ''.join(egg_at(x, y, 16, EGG if (x+y)%3 else WHITE)
                       for x in (-72, -24, 24, 72) for y in (-21, 22))
        dividers = ''.join(block((x-3, -35, 17, x+3, 35, 26), PULP) for x in (-47, 0, 47))
        return base + rim + lid + dividers + eggs
    lid = bottle_shape(104, 49, 13, [(24, 1, 0, 0), (48, .88, 0, 0)], PULP)
    catch = block((-28, -50, 18, 28, -44, 27), WHITE)
    return base + rim + lid + catch


def squeeze(width, depth, height, tint, cap):
    body = bottle_shape(width, depth, 10, [(0, .91, 0, 0), (8, 1, 0, 0),
                                            (height-33, 1, 0, 0), (height-21, .62, 0, 0)],
                        tint)
    collar = straight_oval(0, 0, width*.52, depth*.57, height-21, height-13, cap)
    nozzle = oval([(height-13, 0, 0, 9), (height-5, 0, 0, 6),
                  (height, 0, 0, 4)], cap, sides=8)
    return body + collar + nozzle


def jar(width, depth, height, tint, cap):
    body = bottle_shape(width, depth, 9, [(0, .93, 0, 0), (8, 1, 0, 0),
                                         (height-23, 1, 0, 0), (height-13, .81, 0, 0)], tint)
    lid = straight_oval(0, 0, width*.79, depth*.84, height-13, height, cap)
    return body + lid


def dressing():
    vessel = bottle_shape(34, 26, 11, [(0, .87, 0, 0), (12, 1, 0, 0),
                                         (97, .94, 0, 0), (125, .43, 0, 0)], TAN)
    cap = straight_oval(0, 0, 15, 15, 125, 142, NAVY)
    return vessel + cap


def apples():
    fruits = ''
    for x,y,z,tint in ((-26,-13,0,RED),(26,-3,1,RED),(1,25,4,GREEN)):
        fruits += oval([(z, x, y, 17), (z+15, x, y, 29), (z+37, x, y, 27),
                         (z+48, x, y, 16)], tint, sides=10)
        fruits += straight_oval(x, y, 3, 3, z+46, z+55, BROWN)
    return fruits


def carrots():
    roots = ''
    for x,y,z in ((-16,-9,10),(12,4,12)):
        roots += oval([(y-43, x, z-3, 3), (y-24, x, z, 7),
                        (y+19, x, z+3, 12), (y+29, x, z+5, 9)],
                       ORANGE, aspect=.75, axis='y', sides=10)
        for offset in (-1, 1):
            outline = [(x-4,y+22), (x+6,y+23), (x+offset*12+4,y+49),
                       (x+offset*12-5,y+51)]
            roots += slab(outline, z+5, z+10, LEAF)
    return roots + block((-20,-28,0,-12,-15,8), ORANGE)


def lettuce():
    base = oval([(0,0,0,29),(13,0,0,46),(36,0,0,43),(56,0,0,29)], GREEN, sides=12)
    for x,y,top,tint in ((-23,-17,62,LEAF),(25,-16,67,GREEN),(0,24,76,LEAF),(-2,-4,83,MINT)):
        base += oval([(16,x,y,16),(37,x,y,25),(top-9,x,y,23),(top,x,y,15)], tint, sides=8)
    return base


def peppers():
    brush = ''
    for cx,cy,tint in ((-24,-6,RED),(23,12,ORANGE)):
        for dx,dy in ((-8,-4),(7,-4),(0,10)):
            brush += oval([(0,cx+dx,cy+dy,11),(11,cx+dx,cy+dy,17),
                           (36,cx+dx,cy+dy,18),(45,cx+dx,cy+dy,12)], tint, sides=8)
        brush += straight_oval(cx, cy, 5, 5, 44, 57, GREEN)
    return brush


def grapes():
    brush = ''
    for x,y,z in ((-25,-9,0),(0,-20,0),(22,-8,3),(-19,13,3),(4,10,1),(14,27,0),
                  (-11,-5,15),(12,-8,14),(3,14,16),(-4,2,29)):
        brush += oval([(z,x,y,7),(z+6,x,y,13),(z+17,x,y,12),(z+22,x,y,7)],
                      GRAPE, sides=8)
    return brush + slab([(-7,-1),(2,-4),(18,8),(7,12)],47,53,GREEN)


def lemon():
    return oval([(0,0,0,12),(9,0,0,22),(23,0,0,26),(37,0,0,18),
                 (42,0,0,7)], 'toy_lemon', aspect=.76, sides=12)


def butter():
    wrapper = bottle_shape(48, 26, 6, [(0,.95,0,0),(4,1,0,0),(30,1,0,0)], GOLD)
    fold = block((-43,-25,30,43,25,33), WHITE)
    return wrapper + fold


def leftover_rect():
    bin_base = bottle_shape(74, 51, 14, [(0,.88,0,0),(46,1,0,0)], ICE)
    lid = bottle_shape(78, 54, 13, [(46,1,0,0),(53,1,0,0)], TEAL)
    clips = ''.join(block((x,-55,37,x+21,-51,48), WHITE) for x in (-55, 34))
    return bin_base + lid + clips


def leftover_round():
    bin_base = oval([(0,0,0,52),(8,0,0,58),(51,0,0,67)], ICE)
    lid = straight_oval(0,0,71,71,51,61,BLUE)
    tab = block((59,-12,52,78,12,60), BLUE)
    return bin_base + lid + tab


def open_container(width, depth, height, wall, rim):
    floor = block((-width,-depth,0,width,depth,8), wall)
    rails = ''.join(block(bounds, wall) for bounds in (
        (-width,-depth,8,width,-depth+6,height),
        (-width,depth-6,8,width,depth,height),
        (-width,-depth+6,8,-width+6,depth-6,height),
        (width-6,-depth+6,8,width,depth-6,height),
    ))
    trim = ''.join(block(bounds, rim) for bounds in (
        (-width-2,-depth-2,height,width+2,-depth+8,height+4),
        (-width-2,depth-8,height,width+2,depth+2,height+4),
        (-width-2,-depth+8,height,-width+8,depth-8,height+4),
        (width-8,-depth+8,height,width+2,depth-8,height+4),
    ))
    return floor + rails + trim


def leftover_open():
    bin_shape = open_container(68,49,43,ICE,TEAL)
    food = ''.join(block((x,y,8,x+21,y+17,z), tint)
                   for x,y,z,tint in ((-46,-26,47,ORANGE),(-20,-12,51,GREEN),
                                      (17,-22,45,GOLD),(-37,18,43,GOLD),
                                      (3,15,47,ORANGE),(33,13,46,GREEN)))
    return bin_shape + food


def foil_tray():
    pan = open_container(62,41,28,STEEL,WHITE)
    foil = bottle_shape(55,35,10,[(8,1,0,0),(28,1,0,0),(37,.87,0,0)], STEEL)
    fold = block((-38,-5,37,40,6,39), WHITE)
    return pan + foil + fold


def packages():
    return {
        'milk_carton': milk(47,36,137,BLUE), 'milk_carton_small': milk(38,29,104,TEAL),
        'egg': egg_at(0,0,0), 'egg_carton_open': egg_carton(opened=True),
        'egg_carton_closed': egg_carton(opened=False),
        'ketchup': squeeze(29,25,137,RED,WHITE),
        'mustard': squeeze(28,23,122,GOLD,NAVY),
        'hot_sauce': squeeze(20,18,102,RED,NAVY),
        'mayonnaise': jar(38,30,93,WHITE,TEAL),
        'pickle_jar': jar(39,32,112,GREEN,STEEL),
        'dressing': dressing(), 'apples': apples(), 'carrots': carrots(),
        'lettuce': lettuce(), 'peppers': peppers(), 'grapes': grapes(), 'lemon': lemon(),
        'butter': butter(), 'leftover_rect': leftover_rect(), 'leftover_round': leftover_round(),
        'leftover_open': leftover_open(), 'foil_tray': foil_tray(),
    }


def unpack(brush_data):
    return parse_entities(wrap(brush_data))[0]['brushes']


def open_door(brush_data):
    c, s = cos(DOOR_ANGLE), sin(DOOR_ANGLE)
    hx, hy = DOOR_HINGE
    brushes = []
    for brush in unpack(brush_data):
        lines = []
        for side in brush:
            points = [(round(hx+x*c-y*s, 4), round(hy+x*s+y*c, 4), z)
                      for x, y, z in side['points']]
            lines.append(face(points, side['texture'], detail=True))
        brushes.append('{\n' + ''.join(lines) + '}\n')
    return ''.join(brushes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    food = packages()
    parsed = {name: unpack(brushes) for name, brushes in food.items()}
    core, leaf = cabinet(), door()
    stocked_core = core + ''.join(translated_package(parsed[name], x, y, z)
                                   for name, x, y, z in BODY_STOCK)
    stocked_leaf = leaf + ''.join(translated_package(parsed[name], x, y, z)
                                   for name, x, y, z in DOOR_STOCK)
    prefabs = {
        'open_empty': core + open_door(leaf),
        'open_stocked': stocked_core + open_door(stocked_leaf),
        **food,
    }
    for name, brush_data in prefabs.items():
        (args.output / f'fridge_{name}.map').write_text(wrap(brush_data), encoding='ascii')


if __name__ == '__main__':
    main()
