#!/usr/bin/env python3
"""Export a loaded open dishwasher and loose unmarked dishes as Quake II brushes."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from generate_bath_prefabs import block, bottle_shape, oval, straight_oval
from generate_bathroom import BASE, disc
from generate_dining_prefabs import fork_at, knife_at, spoon_at
from generate_garage_prefabs import finish, ring_band, ring_sections
from generate_pantry_prefabs import translated_package, wrap
from generate_sandkeep_materials import write_wal
from generate_switchyard import face
from platoon_palette import load_palette
from verify_sandkeep import parse_entities

STEEL = 'bathroom/dishwasher_steel'
WIRE = 'bathroom/dishwasher_wire'
LINER = 'bathroom/freezer_liner'
CREAM = 'enamel'
GLAZE = 'bedroom/dining_glaze'
RUST = 'bedroom/living_rust'
MINT = 'toy_mint'
AQUA = 'toy_aqua'
TEAL = 'laundry_teal'
NAVY = 'toy_navy'
INK = 'toy_ink'

# Two lower plate rows stand on edge. Cups and several bowls drain upside down.
LOWER_LOAD = (
    ('plate_upright', -178, -321, 52), ('plate_upright_blue', -126, -313, 52),
    ('plate_upright', -75, -305, 52), ('bowl_tilted', 15, -318, 52),
    ('plate_upright_small', -146, -184, 52), ('plate_upright_small', -91, -169, 52),
    ('bowl_inverted', 71, -183, 52), ('silverware_basket_loaded', 145, -328, 52),
)
UPPER_LOAD = (
    ('mug_inverted', -143, -204, 197), ('mug_inverted_rust', -25, -204, 197),
    ('tumbler_inverted', 84, -208, 197), ('tumbler_inverted', 159, -188, 197),
    ('bowl_inverted', -132, -62, 197), ('bowl_inverted', -7, -61, 197),
    ('mug_inverted', 125, -61, 197),
)


def write_materials():
    images = {
        STEEL: finish((157, 171, 174), lambda x, y: (
            5*cos(tau*y/8) + 8*sin(tau*(x+y)/128))),
        WIRE: finish((100, 135, 142), lambda x, y: 5*cos(tau*(x-y)/32)),
    }
    palette = load_palette()
    for name, image in images.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def cabinet():
    kick = block((-249, -112, 0, 249, 158, 22), INK)
    shell = ''.join(block(bounds, STEEL) for bounds in (
        (-260, -137, 22, -232, 163, 365), (232, -137, 22, 260, 163, 365),
        (-232, 143, 22, 232, 163, 365), (-232, -137, 343, 232, 143, 365),
    ))
    tub = ''.join(block(bounds, LINER) for bounds in (
        (-232, -132, 22, 232, 146, 33),
        (-232, -126, 33, -219, 143, 343), (219, -126, 33, 232, 143, 343),
        (-219, 133, 33, 219, 147, 343), (-219, -132, 331, 219, 143, 343),
    ))
    seal = ''.join(block(bounds, INK) for bounds in (
        (-232, -140, 25, -221, -134, 346), (221, -140, 25, 232, -134, 346),
        (-221, -140, 333, 221, -134, 346),
    ))
    filter_plate = straight_oval(0, 74, 45, 45, 33, 37, INK)
    filter_plate += ring_band(0, 74, (37, 35, 45), (41, 35, 45), STEEL, sides=12)
    spray = block((-108, 62, 39, 108, 79, 47), WIRE)
    spray += straight_oval(0, 72, 13, 13, 37, 49, STEEL)
    return kick + shell + tub + seal + filter_plate + spray


def lowered_door():
    panel = bottle_shape(250, 151, 12, [(0, .99, 0, -280), (5, 1, 0, -280),
                                        (16, 1, 0, -280)], STEEL)
    inside = block((-219, -414, 16, 219, -134, 19), LINER)
    hinges = ''.join(block((x, -160, 0, x+26, -111, 29), STEEL) for x in (-225, 199))
    grooves = ''.join(block((x, -406, 19, x+9, -148, 24), INK) for x in (-222, 213))
    control = block((83, -426, 16, 197, -413, 20), INK)
    buttons = ''.join(block((x, -423, 20, x+10, -416, 23), tint)
                      for x, tint in ((96, MINT), (123, STEEL), (145, STEEL), (167, STEEL)))
    dispenser = block((97, -278, 19, 173, -232, 26), STEEL)
    dispenser += block((103, -271, 26, 142, -241, 31), WIRE)
    latch = block((149, -262, 26, 167, -249, 31), NAVY)
    return panel + inside + hinges + grooves + control + buttons + dispenser + latch


def rack(front_y, rear_y, height, *, upper=False):
    rim_z = height + (55 if upper else 42)
    rods = ''.join(block((x, front_y, height-5, x+5, rear_y, height), WIRE)
                   for x in range(-204, 206, 19))
    rods += ''.join(block((-209, y, height-10, 209, y+5, height-5), WIRE)
                    for y in range(front_y+6, rear_y-4, 23))
    frame = ''.join(block(bounds, WIRE) for bounds in (
        (-211, front_y-3, rim_z-5, 211, front_y+3, rim_z),
        (-211, rear_y-3, rim_z-5, 211, rear_y+3, rim_z),
        (-211, front_y+3, rim_z-5, -205, rear_y-3, rim_z),
        (205, front_y+3, rim_z-5, 211, rear_y-3, rim_z),
        (-211, front_y-3, height-7, 211, front_y+3, height),
        (-211, rear_y-3, height-7, 211, rear_y+3, height),
        (-211, front_y+3, height-7, -205, rear_y-3, height),
        (205, front_y+3, height-7, 211, rear_y-3, height),
    ))
    uprights = ''.join(block((x, y, height-4, x+5, y+5, rim_z-2), WIRE)
                       for x in range(-203, 206, 21) for y in (front_y-2, rear_y-2))
    uprights += ''.join(block((x, y, height-4, x+5, y+5, rim_z-2), WIRE)
                        for x in (-209, 204) for y in range(front_y+16, rear_y-4, 23))
    grip = block((-48, front_y-11, rim_z-10, 48, front_y+3, rim_z+3), NAVY)
    grip += block((-35, front_y-12, rim_z-7, 35, front_y-10, rim_z-2), STEEL)
    return rods + frame + uprights + grip


def rack_rails():
    upper = ''.join(block((x, -115, 170, x+10, 119, 188), STEEL)
                    + block((x+1, -270, 179, x+8, 56, 191), WIRE)
                    for x in (-223, 213))
    lower = ''.join(block((x, -413, 30, x+10, -103, 40), STEEL)
                    for x in (-221, 211))
    rollers = ''.join(straight_oval(y, 37, 10, 10, x, x+10, NAVY, axis='x')
                      for y in (-376,-149) for x in (-220,210))
    return upper + lower + rollers


def tines():
    lower = ''.join(block((x, y, 49, x+5, y+5, 78+(x%3)), WIRE)
                    for x in (-200,-157,-107,-53)
                    for y in (-366,-319,-267,-209,-163))
    upper = ''.join(block((x, y, 194, x+5, y+5, 216), WIRE)
                    for x in (-170,-113,-56,2,60,118,175)
                    for y in (-257,-140,12))
    return lower + upper


def appliance():
    return (cabinet() + lowered_door() + rack(-401, -96, 52)
            + rack(-270, 39, 197, upper=True) + rack_rails() + tines())


def vessel(profile, tint, lip, *, sides=12):
    """Make a dish with a real cavity and shared, coplanar ring seams."""
    z, _, outer = profile[0]
    floor = oval([(0, 0, 0, outer), (z, 0, 0, outer)], tint, sides=sides)
    rings = [(disc(0, 0, inside, inside, h, sides), disc(0, 0, out, out, h, sides))
             for h, inside, out in profile]
    return floor + ring_sections(rings[:-1], tint) + ring_sections(rings[-2:], lip)


def plate(radius, center, rim):
    floor_radius = .74 * radius
    floor = oval([(0,0,0,floor_radius),(7,0,0,floor_radius)], center, sides=12)
    edge = ring_band(0, 0, (7,.64*radius,floor_radius), (17,.91*radius,radius),
                     rim, sides=12)
    return floor + edge


def cereal_bowl():
    return vessel(((8,36,42),(26,49,56),(44,52,59),(49,52,59)), CREAM, GLAZE)


def mug(tint, rim):
    cup = vessel(((8,30,37),(72,30,37),(81,30,37)), tint, rim)
    handle = ring_band(44,43,(-8,21,29),(8,21,29),tint,axis='y',sides=12)
    return cup + handle


def tumbler():
    return vessel(((8,24,30),(78,29,36),(86,29,36)), AQUA, TEAL)


def unpack(data):
    return parse_entities(wrap(data))[0]['brushes']


def orient(data, transform):
    """Reorient plain materials and set the lowest point on local Z 0."""
    brushes = [[(side['texture'], [transform(x, y, z) for x, y, z in side['points']])
                for side in brush] for brush in unpack(data)]
    datum = min(z for brush in brushes for _, points in brush for _, _, z in points)
    result = []
    for brush in brushes:
        lines = [face([(round(x, 5), round(y, 5), round(z-datum, 5)) for x, y, z in points],
                      texture, detail=True) for texture, points in brush]
        result.append('{\n' + ''.join(lines) + '}\n')
    return ''.join(result)


def place(assembly, parts):
    return ''.join(translated_package(parts[name], x, y, z) for name, x, y, z in assembly)


def silverware_basket():
    floor = block((-55,-61,0,55,61,8), NAVY)
    rims = ''.join(block(bounds, NAVY) for bounds in (
        (-57,-63,49,57,-53,57),(-57,53,49,57,63,57),
        (-57,-53,49,-48,53,57),(48,-53,49,57,53,57),
    ))
    sides = ''.join(block((x,y,7,x+6,y+7,51), WIRE)
                    for x in range(-53,54,13) for y in (-59,52))
    sides += ''.join(block((x,y,7,x+7,y+6,51), WIRE)
                     for x in (-54,47) for y in range(-47,49,13))
    partition = block((-50,-3,8,50,3,39), NAVY)
    grip = ''.join(block((x,-6,37,x+9,6,82), NAVY) for x in (-46,37))
    grip += block((-46,-8,78,46,8,88), NAVY)
    return floor + rims + sides + partition + grip


def food_props():
    dinner = plate(72, CREAM, GLAZE)
    salad = plate(50, GLAZE, CREAM)
    blue_plate = plate(68, GLAZE, TEAL)
    bowl = cereal_bowl()
    plain_mug, rust_mug, glass = mug(CREAM, MINT), mug(RUST, CREAM), tumbler()
    # Rotate a horizontal dish onto its rim or invert it for draining.
    def on_edge(x,y,z):
        return z,y,-x
    def inverted(x,y,z):
        return x,-y,-z
    def tilted(x,y,z):
        angle = pi*32/180
        return x,y*cos(angle)-z*sin(angle),y*sin(angle)+z*cos(angle)

    props = {
        'dinner_plate': dinner, 'salad_plate': salad,
        'plate_upright': orient(dinner, on_edge),
        'plate_upright_blue': orient(blue_plate, on_edge),
        'plate_upright_small': orient(salad, on_edge),
        'cereal_bowl': bowl, 'bowl_inverted': orient(bowl, inverted),
        'bowl_tilted': orient(bowl, tilted),
        'mug': plain_mug, 'mug_inverted': orient(plain_mug, inverted),
        'mug_inverted_rust': orient(rust_mug, inverted),
        'tumbler': glass, 'tumbler_inverted': orient(glass, inverted),
        'fork': fork_at(0,0,0), 'spoon': spoon_at(0,0,0), 'table_knife': knife_at(0,0,0),
        'silverware_basket_empty': silverware_basket(),
    }
    utensils = {name: unpack(orient(props[name], lambda x,y,z: (x,-z,y)))
                for name in ('fork','spoon','table_knife')}
    props['silverware_basket_loaded'] = props['silverware_basket_empty'] + place((
        ('fork',-34,-29,8),('spoon',-3,-24,8),('table_knife',28,-24,8),
        ('spoon',-30,30,8),('fork',1,28,8),('table_knife',28,37,8),
    ), utensils)
    return props


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    dishes = food_props()
    parts = {name: unpack(data) for name, data in dishes.items()}
    empty = appliance()
    stocked = empty + place(LOWER_LOAD + UPPER_LOAD, parts)
    prefabs = {'open_empty': empty, 'open_stocked': stocked, **dishes}
    for name, data in prefabs.items():
        (args.output / f'dishwasher_{name}.map').write_text(wrap(data), encoding='ascii')


if __name__ == '__main__':
    main()
