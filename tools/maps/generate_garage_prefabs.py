#!/usr/bin/env python3
"""Make unmarked, Quake II brush props for a garage."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bathroom import BASE, disc, material, rim, rounded_rectangle
from generate_bath_prefabs import (HEADER, bevel, block, bottle_shape, cloth_surface, loft, straight_oval)
from generate_build_prefabs import prism
from generate_sandkeep_materials import write_wal
from generate_switchyard import box
from platoon_palette import load_palette

CARDBOARD = 'garage_kraft'
FLUTE = 'garage_flute'
TAPE = 'garage_tape'
STEEL = 'garage_steel'
RED = 'garage_paint'
RUBBER = 'garage_tread'
WOOD = 'kit_beech'
GRIP = 'toy_ink'


def finish(color, shade):
    image = Image.new('RGB', (128, 128))
    pixels = image.load()
    for y in range(128):
        for x in range(128):
            relief = shade(x, y) + (x * 31 ^ y * 17) % 7 - 3
            pixels[x, y] = tuple(max(0, min(255, round(c + relief))) for c in color)
    return image


def materials():
    textures = {
        CARDBOARD: finish((171, 125, 77), lambda x, y: 4 * cos(tau * x / 8) + 4 * sin(tau * (x + y) / 128)),
        FLUTE: finish((161, 112, 65), lambda x, y: 23 * cos(tau * x / 8) + 8 * cos(tau * y / 16)),
        TAPE: finish((211, 158, 95), lambda x, y: 6 * cos(tau * y / 32) + 3 * sin(tau * x / 128)),
        STEEL: finish((164, 170, 170), lambda x, y: 6 * cos(tau * y / 8) + 5 * sin(tau * (x + y) / 128)),
        RED: finish((163, 53, 47), lambda x, y: 4 * cos(tau * (x + y) / 64)),
        'garage_bristle': finish((173, 145, 100), lambda x, y: 14 * cos(tau * y / 4) + 5 * cos(tau * (x + y) / 32)),
        'garage_rag': finish((100, 109, 113), lambda x, y: 8 * cos(tau * (x + y) / 4) + 10 * cos(tau * x / 128) * sin(tau * y / 128)),
    }
    tire = finish((43, 43, 43), lambda x, y: 4 * cos(tau * x / 16))
    draw = ImageDraw.Draw(tire)
    for x in range(-32, 160, 32):
        for offset in (0, 64):
            draw.line([(x, offset), (x + 15, offset + 18), (x + 15, offset + 42), (x, offset + 63)],
                      fill=(27, 27, 27), width=6)
    textures[RUBBER] = tire
    rule = Image.new('RGB', (128, 32), (225, 183, 64))
    draw = ImageDraw.Draw(rule)
    for x in range(0, 128, 8):
        size = 11 if x % 32 == 0 else 7 if x % 16 == 0 else 4
        draw.rectangle((x, 0, x + 1, size), fill=(58, 47, 34))
        draw.rectangle((x, 31 - size, x + 1, 31), fill=(58, 47, 34))
    textures['garage_rule'] = rule
    return textures


def write_materials():
    folder = BASE / 'textures/bathroom'
    folder.mkdir(parents=True, exist_ok=True)
    palette = load_palette()
    for name, image in materials().items():
        image.save(folder / (name + '.png'))
        write_wal(folder / (name + '.wal'), material(name), image, palette)


def slab(points, z, Z, tint):
    return loft([[(x, y, height) for x, y in points] for height in (z, Z)], tint)


def capped_block(bounds, tint, cap, *, scale=1):
    return box(bounds, material(tint), detail=True, scale=scale,
               overrides={5: {'texture': material(cap)}})


def flat_ring(cx, cy, r, R, z, Z, tint, sides=12):
    return rim(disc(cx, cy, r, r, z, sides), disc(cx, cy, R, R, z, sides),
               disc(cx, cy, r, r, Z, sides), disc(cx, cy, R, R, Z, sides), tint)


def ring_band(u, v, first, last, tint, *, axis='z', sides=16):
    rings = [(disc(u, v, r, r, z, sides), disc(u, v, R, R, z, sides))
             for z, r, R in (first, last)]
    return ring_sections(rings, tint, axis=axis)


def ring_sections(rings, tint, *, axis='z'):
    sides = len(rings[0][0])
    return ''.join(loft([[inner[i-1], inner[i], outer[i], outer[i-1]] for inner, outer in rings],
                        tint, axis=axis) for i in range(sides))


def sealed_box(x, y, height):
    top = ''.join(capped_block((-x, a, height-5, x, b, height), CARDBOARD, CARDBOARD, scale=1.5)
                  for a, b in ((-y, -2), (2, y)))
    seam = block((-x, -20, height-4, x, 20, height+2), TAPE)
    ends = (block((-x-2, -20, height-61, -x, 20, height+2), TAPE)
            + block((x, -20, height-61, x+2, 20, height+2), TAPE))
    return box((-x, -y, 0, x, y, height-5), material(CARDBOARD), detail=True, scale=1.5) + top + seam + ends


def open_box():
    floor = capped_block((-168, -132, 0, 168, 132, 12), CARDBOARD, CARDBOARD)
    sides = ''.join(capped_block(bounds, CARDBOARD, FLUTE) for bounds in (
        (-168, -132, 12, -158, 132, 148), (158, -132, 12, 168, 132, 148),
        (-158, 122, 12, 158, 132, 148),
    ))
    cheeks = ''.join(prism(profile, -132, -122, CARDBOARD, axis='y') for profile in (
        [(-158, 12), (-158, 148), (-101, 101), (-93, 12)],
        [(93, 12), (102, 68), (158, 145), (158, 12)],
    ))
    walkway = prism([(-264, 0), (-132, 0), (-132, 12)], -92, 92, CARDBOARD)
    back_flap = prism([(122, 140), (221, 184), (225, 177), (130, 135)],
                      -153, 153, CARDBOARD)
    side_flap = prism([(158, 141), (253, 157), (253, 165), (158, 149)],
                      -110, 109, CARDBOARD, axis='y')
    creases = ''.join(block((-83, y, z, 83, y+2, z+2), TAPE)
                      for y, z in ((-259, .5), (-151, 10), (-124, 12)))
    return floor + sides + cheeks + walkway + back_flap + side_flap + creases


def flat_box():
    return (slab([(-167,-90),(-88,-113),(104,-115),(172,-88),(184,67),(110,112),
                  (-120,105),(-182,51)], 0, 7, CARDBOARD)
            + slab([(-133,-82),(71,-84),(110,-35),(106,58),(-127,68),(-154,-15)], 7, 13, CARDBOARD)
            + slab([(-145,-8),(109,-11),(108,16),(-148,20)], 13, 15, TAPE))


def crate():
    tray = bevel((-161, -105, 0, 161, 105, 16), 4, 'toy_navy')
    walls = ''.join(block(bounds, 'toy_blue') for bounds in (
        (-161,-105,12,161,-93,130), (-161,93,12,161,105,130),
        (-161,-93,12,-149,93,83), (149,-93,12,161,93,83),
        (-161,-93,119,-149,93,132), (149,-93,119,161,93,132),
        (-161,-93,83,-149,-42,119), (-161,42,83,-149,93,119),
        (149,-93,83,161,-42,119), (149,42,83,161,93,119),
    ))
    trim = ''.join(block(bounds, 'toy_navy') for bounds in (
        (-165,-110,130,165,-91,141), (-165,91,130,165,110,141),
        (-165,-91,132,-147,91,141), (147,-91,132,165,91,141),
    ))
    ribs = ''.join(block((x, y, 23, x+7, Y, 123), 'toy_navy')
                   for x in range(-127, 128, 40) for y,Y in ((-109,-104),(104,109)))
    return tray + walls + trim + ribs


def toolbox():
    body = bevel((-160,-74,0,160,74,96), 8, RED)
    lid = bevel((-163,-77,96,163,77,137), 5, RED)
    seam = block((-151,-79,96,151,-73,100), GRIP)
    latches = ''.join(bevel((x,-86,72,x+38,-73,115), 3, STEEL)
                      + block((x+8,-90,86,x+29,-85,98), GRIP) for x in (-111,73))
    hinge = straight_oval(75, 102, 7, 7, -128, 128, STEEL, axis='x')
    grip = (block((-65,-13,134,-46,13,169), GRIP)
            + block((46,-13,134,65,13,169), GRIP)
            + bevel((-65,-18,162,65,18,184), 4, GRIP))
    return body + lid + seam + latches + hinge + grip


def shelf():
    frame = ''.join(block((x,y,0,x+14,y+14,326), 'toy_navy')
                    + bevel((x-5,y-5,0,x+19,y+19,8), 2, GRIP)
                    for x in (-221,207) for y in (-91,77))
    decks = ''.join(
        block((-219,-92,z,219,92,z+9), STEEL)
        + block((-207,-83,z+8,207,83,z+16), WOOD)
        for z in (0,144,300))
    for x in (-218,207):
        frame += prism([(-75,145),(-72,156),(73,290),(73,278)], x, x+11, STEEL)
    return frame + decks


def hammer():
    grip = bottle_shape(18,21,8,[(-175,.78,0,21),(-158,1,0,21),
                                  (-105,1,0,21),(-84,.91,0,21)], GRIP, axis='x')
    haft = bottle_shape(14,15,6,[(-112,1,0,21),(71,.8,0,21),(105,1,0,23)], WOOD, axis='x')
    head = bevel((53,-38,0,112,40,51), 6, STEEL)
    face = straight_oval(82, 25, 30, 24, -76, -30, STEEL, axis='y')
    roots = bevel((58,27,10,109,55,47), 4, STEEL)
    claws = ''.join(prism([(46,17),(89,4),(89,14),(52,38)], x,x+17,STEEL) for x in (62,89))
    return grip + haft + head + face + roots + claws


def wrench():
    ring = flat_ring(-108,0,28,46,0,26,STEEL,sides=12)
    shaft = bevel((-82,-17,8,89,17,26), 3, STEEL)
    jaw = slab([(77,-33),(111,-45),(122,-27),(118,27),(111,45),(77,33)], 0,26,STEEL)
    jaw += slab([(104,-43),(139,-46),(153,-28),(127,-20),(112,-27)], 0,26,STEEL)
    jaw += slab([(104,43),(112,27),(127,20),(153,28),(139,46)], 0,26,STEEL)
    return ring + shaft + jaw


def screwdriver():
    handle = bottle_shape(25,28,10,[(-144,.68,0,28),(-128,1,0,28),
                                      (-64,1,0,28),(-29,.58,0,28)], 'toy_orange', axis='x')
    bands = ''.join(bottle_shape(25,28,10,[(x,1.015,0,28),(x+5,1.015,0,28)],
                                  GRIP,axis='x') for x in (-119,-105,-91,-77))
    stem = straight_oval(0,28,9,9,-36,110,STEEL,axis='x')
    tip = bevel((102,-13,23,137,13,31), 2, STEEL)
    return handle + bands + stem + tip


def pliers():
    body = ''
    for direction in (-1,1):
        def mirror(points):
            return [(x,y*direction) for x,y in points]
        body += slab(mirror([(-153,38),(-136,26),(27,0),(52,10),(34,28),(-140,65),(-153,58)]),
                     8,27,STEEL)
        body += slab(mirror([(-169,39),(-153,26),(-60,15),(-49,32),(-105,63),(-156,72)]),
                     0,35,RED)
        body += slab(mirror([(25,5),(106,9),(122,13),(118,27),(69,32),(36,29)]),
                     4,34,STEEL)
        y0, y1 = sorted((9 * direction, 6 * direction))
        body += ''.join(block((x, y0, 8, x+4, y1, 33), GRIP) for x in (63,75,87,99))
    return body + straight_oval(28,0,23,23,5,39,STEEL) + straight_oval(28,0,12,12,38,42,GRIP)


def tape_measure():
    case = bevel((-129,-53,0,6,53,112), 12, 'toy_lemon')
    belt = bevel((-115,-58,11,-20,-47,96), 3, GRIP)
    lock = bevel((-47,-26,106,-20,26,123), 3, GRIP)
    blade = box((0,-19,3,282,19,8), material('garage_rule'), detail=True,
                overrides={5: {'scale': (1,38/32), 'shift': (0,16)}})
    hook = block((279,-27,0,290,27,16), STEEL)
    return case + belt + lock + blade + hook


def paintbrush():
    handle = (bevel((-155,-18,8,-62,18,26),5,WOOD)
              + slab([(-75,-14),(6,-31),(43,-31),(43,31),(6,31),(-75,14)],8,25,WOOD))
    ferrule = bevel((19,-46,0,75,46,35), 4, STEEL)
    bristles = ''.join(block((70,y,5,145+end,y+11,28), 'garage_bristle')
                       for y,end in zip(range(-44,44,11),(1,8,15,13,17,7,9,3)))
    stains = ''.join(block((x,y,5,X,y+10,29), 'teal')
                     for x,X,y in ((139,149,-44),(145,154,-33),(148,161,-22),
                                    (143,159,-11),(149,163,0),(148,160,11),
                                    (141,153,22),(142,149,33)))
    return handle + ferrule + bristles + stains


def handsaw():
    steel = slab([(-73,-30),(148,-30),(153,3),(-73,57)],7,15,STEEL)
    tooth = ''.join(slab([(x,-30),(x+12,-37),(x+13,-30)],7,15,STEEL)
                    for x in range(-63,131,13))
    def ring(scale,z):
        return [(-122+x*scale,y*scale,z)
                for x,y,_ in rounded_rectangle(0,0,63,53,17,0)]
    grip = rim(ring(.60,0),ring(1,0),ring(.60,31),ring(1,31),'toy_orange')
    return steel + tooth + grip


def tire(*, upright=False):
    # The same exact radial directions at each section keep the seams planar.
    quadrant = [(24, 5), (20, 14), (14, 20), (5, 24)]
    outline = (quadrant + [(-x, y) for x, y in reversed(quadrant)]
               + [(-x, -y) for x, y in quadrant] + [(x, -y) for x, y in reversed(quadrant)])
    if upright:
        axis, center, offset = 'y', 144, 0
    else:
        axis, center, offset = 'z', 0, 47
    def profile(z, scale):
        return [(x * scale, y * scale + center, z + offset) for x, y in outline]

    levels = [(profile(z, r), profile(z, R)) for z, r, R in (
        (-47, 3.25, 5), (-32, 3, 6), (32, 3, 6), (47, 3.25, 5))]
    return ''.join(ring_sections([first, last], tint, axis=axis)
                   for first, last, tint in zip(levels, levels[1:], (GRIP, RUBBER, GRIP)))


def paint_can():
    body = (straight_oval(0,0,69,69,0,12,STEEL)
            + straight_oval(0,0,65,65,12,113,'teal')
            + straight_oval(0,0,69,69,113,132,STEEL)
            + straight_oval(0,0,58,58,131,136,'enamel'))
    lid = flat_ring(0,0,57,69,132,139,STEEL)
    bail = []
    for i in range(8):
        a,b = (i*pi/8,(i+1)*pi/8)
        outline = [(round(r*cos(theta),3),107+round(r*sin(theta),3))
                   for r,theta in ((77,a),(77,b),(84,b),(84,a))]
        bail.append(prism(outline,-4,4,STEEL,axis='y'))
    pivots = block((-83,-11,98,-60,11,116),STEEL) + block((60,-11,98,83,11,116),STEEL)
    return body + lid + ''.join(bail) + pivots


def oil_jug():
    jug = bottle_shape(78,53,18,[(0,.94,0,0),(12,1,0,0),(130,1,0,0),
                                  (156,.89,-5,0)], 'toy_navy')
    cap = straight_oval(-44,0,27,27,153,183,'toy_lemon')
    thumb = (bevel((7,-20,147,30,20,197),4,'toy_navy')
             + bevel((56,-20,148,76,20,197),4,'toy_navy')
             + bevel((7,-23,186,76,23,201),4,'toy_navy'))
    return jug + cap + thumb + block((-55,-55,36,53,-51,42),'toy_blue')


def bolt():
    head = loft([disc(0,34,34,34,x,6) for x in (-83,-44)],STEEL,axis='x')
    shaft = straight_oval(0,34,17,17,-46,104,STEEL,axis='x')
    ribs = ''.join(straight_oval(0,34,20,20,x,x+4,STEEL,axis='x') for x in range(40,101,10))
    return head + shaft + ribs


def hex_nut():
    low = ring_band(0,0,(0,27,49),(4,27,55),STEEL,sides=6)
    middle = ring_band(0,0,(4,27,55),(35,27,55),STEEL,sides=6)
    top = ring_band(0,0,(35,27,55),(41,30,49),STEEL,sides=6)
    return low + middle + top


def offcuts():
    plank = slab([(-142,-27),(112,-34),(126,31),(-119,33)],0,23,WOOD)
    scrap = slab([(-57,-85),(-31,-94),(94,32),(81,70),(26,67),(-77,-48)],20,39,'kit_log')
    splinter = slab([(-128,44),(-11,54),(-27,67),(-130,57)],0,11,'kit_beech_end')
    return plank + scrap + splinter


def extension_cord():
    coil = ''.join(flat_ring(0,0,r,r+10,0,12,'toy_orange',sides=16) for r in (65,80,95))
    lead = ''.join(block(bounds,'toy_orange') for bounds in (
        (74,-13,0,134,-3,12),(126,-41,0,136,-6,12),(129,-45,0,174,-35,12)))
    plug = bevel((161,-62,0,210,-22,33),4,GRIP)
    pins = ''.join(block((207,y,9,229,y+6,28),STEEL) for y in (-54,-36))
    return coil + lead + plug + pins


def rag():
    contour = [(-114,-50),(-54,-68),(13,-50),(95,-64),(108,-16),(88,47),
               (30,45),(-17,63),(-92,58),(-123,13)]
    return cloth_surface((-13,1,36),[(*p,z) for p,z in zip(contour,(8,21,11,10,16,6,23,9,14,20))],
                         ('garage_rag','garage_rag','cloth','garage_rag'))


def sockets():
    strip = bevel((-112,-26,0,112,26,12),3,GRIP)
    return strip + ''.join(flat_ring(x,0,r,R,12,Z,STEEL) for x,r,R,Z in (
        (-74,12,23,46),(-6,16,27,58),(68,20,34,72)))


PREFABS = {
    'box_taped_small': lambda: sealed_box(96,72,96),
    'box_taped_large': lambda: sealed_box(160,119,208),
    'box_open': open_box,
    'box_flattened': flat_box,
    'crate': crate,
    'toolbox': toolbox,
    'shelf': shelf,
    'hammer': hammer,
    'combination_wrench': wrench,
    'screwdriver': screwdriver,
    'pliers': pliers,
    'tape_measure': tape_measure,
    'paintbrush': paintbrush,
    'handsaw': handsaw,
    'tire_flat': tire,
    'tire_upright': lambda: tire(upright=True),
    'paint_can': paint_can,
    'oil_jug': oil_jug,
    'bolt': bolt,
    'hex_nut': hex_nut,
    'wood_offcuts': offcuts,
    'extension_cord': extension_cord,
    'shop_rag': rag,
    'socket_strip': sockets,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    for name, make in PREFABS.items():
        map_text = HEADER + '{\n"classname" "worldspawn"\n' + make() + '}\n'
        (args.output / f'garage_{name}.map').write_text(map_text, encoding='ascii')


if __name__ == '__main__':
    main()
