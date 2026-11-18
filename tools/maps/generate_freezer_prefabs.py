#!/usr/bin/env python3
"""Export a lift-lid chest freezer and unbranded frozen food brushes for Quake II."""

import argparse
from math import cos, sin, tau
from pathlib import Path

from PIL import ImageDraw

from generate_bath_prefabs import block, bottle_shape, label_panel, oval, straight_oval
from generate_bathroom import BASE
from generate_build_prefabs import prism
from generate_garage_prefabs import finish, ring_band
from generate_pantry_prefabs import translated_package, wrap
from generate_sandkeep_materials import write_wal
from platoon_palette import load_palette
from verify_sandkeep import parse_entities

SHELL = 'bathroom/fridge_shell'
LINER = 'bathroom/freezer_liner'
FROST = 'bathroom/freezer_frost'
ICE = 'bathroom/freezer_cube'
STEEL = 'garage_steel'
WHITE = 'enamel'
NAVY = 'toy_navy'
BLUE = 'toy_blue'
TEAL = 'laundry_teal'
MINT = 'toy_mint'
RED = 'kitchen_apple'
KRAFT = 'garage_kraft'
GOLD = 'kitchen_cheese'
CRUST = 'kitchen_crust'
GREEN = 'kitchen_green'
BROWN = 'bedroom/pantry_amber'
PINK = 'toy_coral'
PURPLE = 'toy_lilac'

PIZZA_COLORS = {
    'pizza_cheese_box': ((99, 143, 131), (237, 182, 93), 'cheese'),
    'pizza_pepperoni_box': ((165, 86, 71), (234, 176, 81), 'pepperoni'),
    'pizza_flatbread_box': ((117, 106, 153), (234, 183, 97), 'flatbread'),
}
VEGETABLE_COLORS = {
    'vegetable_mixed_bag': ((72, 124, 114), (109, 147, 70), 'mixed'),
    'vegetable_peas_bag': ((69, 110, 158), (117, 153, 81), 'peas'),
    'vegetable_corn_bag': ((182, 117, 63), (229, 179, 56), 'corn'),
    'vegetable_broccoli_bag': ((117, 92, 147), (68, 117, 71), 'broccoli'),
}

# All stock coordinates are relative to the same chest origin.
PIZZA_STACK = (
    ('pizza_cheese_box', 0, 0, 0),
    ('pizza_pepperoni_box', -5, 2, 16),
    ('pizza_flatbread_box', 7, -4, 32),
)
STOCK = (
    ('pizza_box_stack', -181, -9, 168),
    ('ice_cream_vanilla', -10, -68, 146), ('ice_cream_berry', 99, -51, 146),
    ('ice_cream_chocolate', -8, 58, 146), ('ice_cream_open', 101, 58, 146),
    ('vegetable_mixed_bag', 229, -72, 146), ('vegetable_peas_bag', 238, -72, 182),
    ('ice_tray_empty', 231, 81, 176), ('ice_tray_full', 231, 81, 194),
)


def print_texture(name):
    return f"bathroom/fz_{name.removesuffix('_box').removesuffix('_bag')}"


def pizza_art(base, cheese, style):
    image = finish(base, lambda x, y: 3*cos(tau*(x+y)/128))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((7, 7, 120, 120), radius=8, outline=(228, 215, 177), width=3)
    if style == 'flatbread':
        draw.rounded_rectangle((22, 28, 105, 101), radius=15, fill=(153, 98, 49))
        draw.rounded_rectangle((29, 35, 98, 94), radius=11, fill=cheese)
    else:
        draw.ellipse((24, 24, 104, 104), fill=(163, 106, 55))
        draw.ellipse((30, 30, 98, 98), fill=(165, 66, 49))
        draw.ellipse((33, 33, 95, 95), fill=cheese)
    for x, y in ((49, 51),(70, 46),(83, 62),(53, 74),(72, 82)):
        if style == 'pepperoni':
            draw.ellipse((x-5,y-5,x+5,y+5), fill=(159, 59, 48))
        elif style == 'flatbread':
            draw.ellipse((x-6,y-4,x+6,y+4), fill=(79, 111, 58))
            draw.rectangle((x+1,y+7,x+5,y+10), fill=(171, 66, 50))
        else:
            draw.arc((x-5,y-4,x+5,y+4), 18, 210, fill=(181, 115, 60), width=2)
    return image


def vegetable_art(base, accent, style):
    image = finish(base, lambda x, y: 2*sin(tau*x/64))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 110, 110), radius=18, fill=(221, 224, 201))
    for x, y in ((42, 49), (67, 39), (83, 54), (57, 66), (81, 78), (45, 86), (65, 93)):
        if style == 'broccoli':
            draw.rectangle((x-2,y,x+2,y+11), fill=accent)
            draw.ellipse((x-7,y-6,x+7,y+5), fill=(52, 108, 62))
        else:
            draw.ellipse((x-7,y-6,x+7,y+6), fill=accent)
            if style == 'mixed':
                draw.rounded_rectangle((x-1,y+5,x+9,y+12), radius=2, fill=(203, 112, 47))
    return image


def write_materials():
    images = {
        LINER: finish((188, 213, 219), lambda x, y: 3*cos(tau*(x+y)/128)),
        FROST: finish((189, 220, 224), lambda x, y:
                      7*cos(tau*x/32)*sin(tau*y/64) + 11*((x*29 ^ y*11) % 17 < 3)),
        ICE: finish((124, 189, 207), lambda x, y:
                    14*cos(tau*(x+y)/128) + 4*cos(tau*(x-2*y)/32)),
    }
    images.update({print_texture(name): pizza_art(*colors) for name, colors in PIZZA_COLORS.items()})
    images.update({print_texture(name): vegetable_art(*colors) for name, colors in VEGETABLE_COLORS.items()})
    palette = load_palette()
    for name, image in images.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def lid_piece(x, X, a, b, front, back, tint):
    # The lid rises just past vertical on its rear hinge.
    profile = [(153+.23*d+.973*t, 237+.973*d-.23*t)
               for d, t in ((a,front),(b,front),(b,back),(a,back))]
    return prism(profile, x, X, tint)


def raised_lid():
    shell = lid_piece(-341, 341, 0, 318, -4, 19, SHELL)
    inset = lid_piece(-313, 313, 17, 301, -10, -4, LINER)
    seal = ''.join(lid_piece(x, X, a, b, -10, -4, NAVY) for x, X, a, b in (
        (-325,-314,11,307),(314,325,11,307),(-314,314,8,17),(-314,314,301,310),
    ))
    cold_panel = lid_piece(-275, 275, 52, 265, -14, -10, FROST)
    seams = ''.join(lid_piece(x, x+5, 70, 246, -16, -14, LINER)
                    for x in (-219,-111,-2,107,215))
    outer_handle = lid_piece(-86, 86, 280, 298, 30, 42, STEEL)
    outer_handle += ''.join(lid_piece(x,x+12,280,297,17,32,STEEL) for x in (-86,74))
    brackets = ''.join(block((x,133,218,x+59,172,252),STEEL) for x in (-263,204))
    return shell + inset + seal + cold_panel + seams + outer_handle + brackets


def wire_basket():
    floor = block((-54,-131,136,152,130,146), LINER)
    posts = ''.join(block((x,y,144,x+6,y+6,209),STEEL)
                     for x in (-53,146) for y in (-131,124))
    rails = ''.join(block(bounds,STEEL) for bounds in (
        (-54,-132,202,152,-125,211),(-54,124,202,152,131,211),
        (-54,-125,202,-48,124,211),(146,-125,202,152,124,211),
    ))
    rods = ''.join(block((x,y,146,x+4,y+5,204),STEEL)
                    for x in range(-38,144,15) for y in (-130,125))
    rods += ''.join(block((x,y,146,x+5,y+4,205),STEEL)
                     for x in (-53,146) for y in range(-112,118,18))
    lift = ''.join(block((x,-140,208,x+30,-131,219),WHITE) for x in (-45,113))
    return floor + posts + rails + rods + lift


def chest():
    floor = block((-335,-163,0,335,163,24),SHELL)
    walls = ''.join(block(b,SHELL) for b in (
        (-339,-167,12,339,-144,225),(-339,144,12,339,167,225),
        (-339,-144,12,-316,144,225),(316,-144,12,339,144,225),
    ))
    inner = ''.join(block(b,LINER) for b in (
        (-319,-145,24,319,-137,224),(-319,137,24,319,145,224),
        (-319,-137,24,-309,137,224),(309,-137,24,319,137,224),
        (-309,-137,24,309,137,32),
    ))
    rim = ''.join(block(b,FROST) for b in (
        (-343,-171,224,343,-134,240),(-343,134,224,343,171,240),
        (-343,-134,224,-307,134,240),(307,-134,224,343,134,240),
    ))
    left_rack = block((-308,-131,157,-60,134,168),LINER)
    left_rack += ''.join(block((x,-131,82,x+6,134,157),STEEL) for x in (-306,-67))
    right_step = block((153,-134,32,309,137,146),LINER)
    right_step += block((153,31,146,309,137,176),LINER)
    exterior = block((218,-169,29,306,-165,78),NAVY)
    exterior += ''.join(block((227,-174,z,296,-168,z+4),STEEL) for z in (35,46,57,68))
    exterior += straight_oval(-273,60,12,12,-174,-166,STEEL,axis='y')
    exterior += block((-252,-170,56,-239,-166,63),TEAL)
    return floor + walls + inner + rim + left_rack + right_step + wire_basket() + exterior + raised_lid()


def pizza_box(name, width, depth, tint):
    bottom = block((-width,-depth,0,width,depth,10),KRAFT)
    cover = label_panel((-width-2,-depth-2,10,width+2,depth+2,16),
                        print_texture(name),tint,top=True)
    tab = block((-19,-depth-4,7,19,-depth-1,12),tint)
    return bottom + cover + tab


def pizza_box_open():
    tray = block((-111,-95,0,111,95,7),KRAFT)
    tray += ''.join(block(b,KRAFT) for b in (
        (-111,-95,7,-105,95,21),(105,-95,7,111,95,21),
        (-105,-95,7,105,-89,21),(-105,89,7,105,95,21),
    ))
    lid = prism([(89,13),(102,17),(177,134),(169,138)],-111,111,KRAFT)
    crust = oval([(7,0,0,72),(13,0,0,82),(21,0,0,80)],CRUST)
    cheese = straight_oval(0,0,73,73,21,25,GOLD)
    toppings = ''.join(straight_oval(x,y,9,9,25,28,RED)
                       for x,y in ((-42,19),(-24,-33),(-6,35),(23,-12),(44,24),(29,-43)))
    return tray + lid + crust + cheese + toppings


def tub(radius, height, tint, lid):
    body = oval([(0,0,0,radius*.87),(7,0,0,radius*.95),
                 (height-17,0,0,radius),(height-9,0,0,radius)],tint)
    lid_plate = straight_oval(0,0,radius+3,radius+3,height-9,height,lid)
    cap = straight_oval(0,0,radius-4,radius-4,height,height+2,WHITE)
    return body + lid_plate + cap


def tub_open():
    floor = straight_oval(0,0,40,40,0,9,TEAL)
    sides = ring_band(0,0,(9,35,40),(56,44,49),TEAL,sides=12)
    lip = ring_band(0,0,(56,44,49),(62,44,49),WHITE,sides=12)
    ice_cream = straight_oval(0,0,41,41,12,34,WHITE)
    scoops = ''.join(oval([(27,x,y,r),(40,x,y,r),(46,x,y,r*.76)],WHITE,sides=8)
                     for x,y,r in ((-17,14,19),(15,15,16),(5,-18,18)))
    return floor + sides + lip + ice_cream + scoops


def frozen_bag(name, width, depth, height, tint):
    body = bottle_shape(width,depth,13,[(0,.91,0,0),(6,1,0,0),
                                         (height-9,1,0,0),(height-2,.90,0,0)],tint)
    decorated = label_panel((-width+9,-depth+12,height-2,width-9,depth-12,height),
                            print_texture(name),tint,top=True)
    crimps = ''.join(block((-width+6,y,8,width-6,y+10,15),tint)
                     for y in (-depth-6,depth-4))
    return body + decorated + crimps


def ice_cube(x, y, z, height):
    return bottle_shape(9,11,3,[(z,.91,x,y),(z+3,1,x,y),
                               (z+height-3,1,x,y),(z+height,.84,x,y)],ICE)


def ice_tray(fill):
    floor = block((-72,-37,0,72,37,5),BLUE)
    rim = ''.join(block(b,BLUE) for b in (
        (-72,-37,5,72,-31,18),(-72,31,5,72,37,18),
        (-72,-31,5,-66,31,18),(66,-31,5,72,31,18),
    ))
    divider = block((-66,-2,5,66,2,18),TEAL)
    for x in (-44,-22,0,22,44):
        divider += block((x-2,-31,5,x+2,31,18),TEAL)
    handles = ''.join(block((x,-17,9,x+7,17,17),BLUE) for x in (-77,70))
    positions = [(x,y) for x in (-55,-33,-11,11,33,55) for y in (-16,16)]
    if fill == 'half':
        positions = positions[::2]
    if fill == 'empty':
        positions = []
    cubes = ''.join(ice_cube(x,y,5,16+(i%3)) for i,(x,y) in enumerate(positions))
    return floor + rim + divider + handles + cubes


def loose_ice():
    return ''.join(ice_cube(x,y,z,h) for x,y,z,h in (
        (-21,-6,0,21),(2,16,0,18),(18,-7,0,24),(-1,-9,9,16),
    ))


def unpack(data):
    return parse_entities(wrap(data))[0]['brushes']


def assemble(placed, parts):
    return ''.join(translated_package(parts[name],x,y,z) for name,x,y,z in placed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    write_materials()
    food = {
        'pizza_cheese_box': pizza_box('pizza_cheese_box',102,96,TEAL),
        'pizza_pepperoni_box': pizza_box('pizza_pepperoni_box',108,93,RED),
        'pizza_flatbread_box': pizza_box('pizza_flatbread_box',109,71,PURPLE),
        'pizza_box_open': pizza_box_open(),
        'ice_cream_vanilla': tub(45,68,WHITE,BLUE),
        'ice_cream_berry': tub(43,65,PINK,WHITE),
        'ice_cream_chocolate': tub(45,64,BROWN,WHITE),
        'ice_cream_open': tub_open(),
        'vegetable_mixed_bag': frozen_bag('vegetable_mixed_bag',64,57,36,TEAL),
        'vegetable_peas_bag': frozen_bag('vegetable_peas_bag',55,54,34,BLUE),
        'vegetable_corn_bag': frozen_bag('vegetable_corn_bag',60,57,31,GOLD),
        'vegetable_broccoli_bag': frozen_bag('vegetable_broccoli_bag',64,59,38,PURPLE),
        'ice_tray_empty': ice_tray('empty'), 'ice_tray_full': ice_tray('full'),
        'ice_tray_half': ice_tray('half'), 'loose_ice': loose_ice(),
    }
    parts = {name: unpack(data) for name,data in food.items()}
    stack = assemble(PIZZA_STACK,parts)
    food['pizza_box_stack'] = stack
    parts['pizza_box_stack'] = unpack(stack)
    shell = chest()
    prefabs = {'open_empty': shell, 'open_stocked': shell + assemble(STOCK,parts), **food}
    for name,data in prefabs.items():
        (args.output / f'freezer_{name}.map').write_text(wrap(data),encoding='ascii')


if __name__ == '__main__':
    main()
