#!/usr/bin/env python3
"""Lay out the Tile Tide blockout and paint its original bathroom materials."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from build_endline import BASE, ROOT
from generate_sandkeep_materials import write_wal
from generate_switchyard import box, convex, entity
from platoon_palette import load_palette

MAP = ROOT / 'maps/source/pp_tile_tide.map'


def material(name):
    return name if '/' in name else 'bathroom/' + name


def bathroom_materials():
    def finish(color, surface):
        image = Image.new('RGB', (128, 128))
        pixels = image.load()
        for y in range(128):
            for x in range(128):
                shift = round(surface(x, y))
                pixels[x, y] = tuple(max(0, min(255, channel + shift)) for channel in color)
        return image

    def tile(color, grout):
        image = Image.new('RGB', (128, 128), grout)
        enamel = finish(color, lambda x, y: 4 * cos(tau * (x + y) / 128)
                        + 3 * sin(tau * y / 128) + ((x * 13 ^ y * 17) % 5) - 2)
        image.paste(enamel.crop((3, 3, 125, 125)), (3, 3))
        draw = ImageDraw.Draw(image)
        draw.line([(3, 123), (3, 3), (123, 3)], fill=tuple(v + 12 for v in color), width=2)
        draw.line([(4, 124), (124, 124), (124, 4)], fill=tuple(v - 20 for v in color), width=2)
        return image

    def painted(color):
        return finish(color, lambda x, y: 2 * cos(tau * (x + y) / 128)
                      + 2 * ((x * 11 ^ y * 13) % 3 - 1))

    return {
        'floor': tile((187, 171, 150), (116, 107, 101)),
        'wall_tile': tile((116, 158, 156), (72, 109, 111)),
        'paint': painted((226, 213, 188)),
        'enamel': painted((236, 229, 213)),
        'teal': painted((62, 114, 118)),
        'rose': painted((169, 86, 82)),
        'wood': finish((135, 83, 57), lambda x, y: 8 * sin(tau * (x / 128 + y / 32))
                       + 5 * cos(tau * y / 8 + sin(tau * x / 128))),
        'chrome': finish((153, 178, 184), lambda x, y: 26 * cos(tau * y / 128)
                         + 7 * cos(tau * y / 32)),
        'rubber': finish((52, 67, 67), lambda x, y: 5 * ((x // 4 + y // 4) % 2)),
        'cloth': finish((72, 116, 149), lambda x, y: 8 * cos(tau * (x + y) / 8)
                        + 3 * sin(tau * y / 128)),
        'yellow': finish((222, 171, 75), lambda x, y: 8 * cos(tau * x / 8)
                         + 6 * ((x // 4 + y // 4) % 2)),
        'window': finish((166, 199, 224), lambda x, y: 8 * cos(tau * (x - y) / 128)
                         + 5 * sin(tau * y / 128)),
        'lamp': painted((242, 226, 185)),
    }


def write_materials():
    folder = BASE / 'textures/bathroom'
    folder.mkdir(parents=True, exist_ok=True)
    palette = load_palette()
    for name, image in bathroom_materials().items():
        image.save(folder / (name + '.png'))
        write_wal(folder / (name + '.wal'), material(name), image, palette)


def rounded_rectangle(x, y, radius_x, radius_y, corner, z):
    return [(x + dx, y + dy, z) for dx, dy in (
        (-radius_x + corner, -radius_y), (radius_x - corner, -radius_y),
        (radius_x, -radius_y + corner), (radius_x, radius_y - corner),
        (radius_x - corner, radius_y), (-radius_x + corner, radius_y),
        (-radius_x, radius_y - corner), (-radius_x, -radius_y + corner),
    )]


def disc(x, y, rx, ry, z, sides=12):
    return [(x + rx * cos(tau * i / sides + pi / sides),
             y + ry * sin(tau * i / sides + pi / sides), z) for i in range(sides)]


def join_rings(bottom, top, texture):
    sides = [[bottom[i - 1], bottom[i], top[i], top[i - 1]] for i in range(len(bottom))]
    return convex([bottom, top, *sides], material(texture), detail=True)


def rim(inner_bottom, outer_bottom, inner_top, outer_top, texture):
    return ''.join(join_rings(
        [inner_bottom[i - 1], inner_bottom[i], outer_bottom[i], outer_bottom[i - 1]],
        [inner_top[i - 1], inner_top[i], outer_top[i], outer_top[i - 1]], texture)
        for i in range(len(inner_bottom)))


def generate():
    brushes = []

    def section(name):
        brushes.append(f'// {name}\n')

    def block(bounds, texture, *, structural=False, scale=1, emitter=None):
        overrides = None
        if emitter:
            face, intensity = emitter
            overrides = {face: {'flags': 1, 'value': intensity}}
        brushes.append(box(bounds, material(texture), detail=not structural,
                           scale=scale, overrides=overrides))

    def slope(bounds, axis, start, end, texture):
        x, y, X, Y = bounds
        outline = [(x, y), (X, y), (X, Y), (x, Y)]
        top = [(a, b, end if (a, b)[axis] == (X, Y)[axis] else start) for a, b in outline]
        bottom = [(a, b, -8) for a, b in outline]
        brushes.append(join_rings(bottom, top, texture))

    def rounded_box(bounds, corner, texture):
        x, y, z, X, Y, Z = bounds
        profile = ((x + X) // 2, (y + Y) // 2, (X - x) // 2, (Y - y) // 2, corner)
        brushes.append(join_rings(rounded_rectangle(*profile, z), rounded_rectangle(*profile, Z), texture))

    def cylinder(x, y, rx, ry, z, Z, texture, *, taper=1):
        brushes.append(join_rings(disc(x, y, rx, ry, z),
                                  disc(x, y, rx * taper, ry * taper, Z), texture))

    section('Sealed bathroom shell and ceramic wainscot')
    block((-1216, -896, -64, 1216, 896, 0), 'floor', structural=True, scale=2)
    block((-1216, -896, 0, -1152, 896, 1248), 'paint', structural=True)
    block((1152, -896, 0, 1216, 896, 1248), 'paint', structural=True)
    block((-1152, -896, 0, 1152, -832, 1248), 'paint', structural=True)
    block((-1152, 832, 0, 1152, 896, 1248), 'paint', structural=True)
    block((-1216, -896, 1248, 1216, 896, 1312), 'paint', structural=True)
    wainscot = [(-1152, -832, -1136, 832), (1136, -832, 1152, 832),
                (-1136, -832, 1136, -816), (-1136, 816, 1136, 832)]
    for x, y, X, Y in wainscot:
        block((x, y, 0, X, Y, 512), 'wall_tile', scale=2)
        block((x, y, 512, X, Y, 536), 'teal')
    block((224, -814, 0, 640, -778, 944), 'wood')
    for x in (204, 640):
        block((x, -814, 0, x + 20, -754, 964), 'enamel')
    block((224, -814, 944, 640, -754, 964), 'enamel')
    for z, Z in ((100, 360), (432, 844)):
        block((272, -781, z, 592, -766, Z), 'wood')
    block((521, -766, 435, 550, -728, 468), 'chrome')

    section('Walk-in bath with an open side and end')
    block((-1088, 254, 0, 320, 816, 48), 'enamel', structural=True)
    block((-1088, 752, 48, 320, 816, 320), 'enamel')
    block((-1088, 254, 48, -1008, 752, 320), 'enamel')
    for x, X in ((-1008, -920), (-736, 240)):
        block((x, 254, 48, X, 330, 294), 'teal', scale=2)
        block((x, 250, 294, X, 334, 320), 'enamel')
    for y, Y in ((254, 488), (648, 752)):
        block((240, y, 48, 320, Y, 294), 'teal')
        block((240, y, 294, 324, Y, 320), 'enamel')
    block((-1092, 250, 294, -1088, 752, 314), 'chrome')
    slope((-920, 78, -736, 254), 1, 0, 48, 'enamel')
    slope((320, 488, 504, 648), 0, 48, 0, 'enamel')
    # The rubber inlay is low enough to walk over in every direction.
    rounded_box((-898, 404, 48, 110, 698, 51), 22, 'wall_tile')
    for y in (442, 486, 530, 574, 618, 662):
        block((-836, y, 51, 62, y + 5, 53), 'teal')
    cylinder(-956, 540, 25, 25, 48, 52, 'chrome')
    for y in (526, 538, 550):
        block((-968, y, 52, -944, y + 4, 53), 'rubber')
    block((-1032, 618, 318, -990, 676, 374), 'chrome')
    block((-1028, 612, 368, -920, 672, 394), 'chrome')
    block((-936, 612, 348, -914, 672, 381), 'chrome')
    cylinder(-1037, 555, 33, 25, 320, 340, 'chrome')
    block((-1136, 548, 743, -1098, 598, 801), 'chrome')
    block((-1104, 557, 762, -1008, 588, 792), 'chrome')
    cylinder(-1013, 572, 45, 39, 742, 773, 'chrome', taper=.65)

    section('Shower curtain, rod and frosted window')
    block((-1128, 280, 904, 336, 292, 922), 'chrome')
    block((320, 284, 910, 334, 816, 922), 'chrome')
    for i in range(12):
        x = -1096 + 25 * i
        y = 277 + (i % 2) * 8
        block((x, y, 898, x + 9, y + 17, 913), 'chrome')
        block((x, y, 368 + (i % 3) * 3, x + 25, y + 13, 899), 'cloth')
    block((-558, 802, 650, 102, 816, 1038), 'chrome')
    block((-534, 790, 676, 78, 802, 1014), 'window', emitter=(2, 55))
    block((-239, 782, 676, -217, 796, 1014), 'enamel')
    block((-566, 770, 645, 110, 816, 671), 'enamel')
    rounded_box((-628, 764, 320, -487, 812, 343), 12, 'enamel')
    rounded_box((-608, 769, 343, -505, 804, 373), 12, 'yellow')

    section('Floating vanity, apron and recessed washbasin')
    block((744, -670, 170, 1136, 216, 480), 'teal', structural=True)
    for y, Y in ((-642, -390), (-382, -113), (-105, 187)):
        block((729, y, 204, 745, Y, 449), 'teal')
        block((704, y + 54, 389, 731, Y - 54, 408), 'chrome')
    block((688, -704, 467, 1136, 248, 493), 'enamel')
    block((688, -704, 493, 772, 248, 520), 'enamel')
    block((1012, -704, 493, 1136, 248, 520), 'enamel')
    block((772, -704, 493, 1012, -498, 520), 'enamel')
    block((772, -110, 493, 1012, 248, 520), 'enamel')
    profile = (892, -304, 120, 194)
    brushes.append(rim(
        rounded_rectangle(892, -304, 108, 182, 42, 493),
        rounded_rectangle(*profile, 1, 493),
        rounded_rectangle(892, -304, 108, 182, 42, 520),
        rounded_rectangle(*profile, 1, 520), 'enamel'))
    cylinder(894, -320, 24, 24, 493, 496, 'chrome')
    cylinder(1070, -308, 36, 36, 520, 647, 'chrome')
    block((957, -336, 624, 1089, -280, 656), 'chrome')
    block((949, -335, 601, 978, -281, 645), 'chrome')
    for y in (-388, -226):
        cylinder(1066, y, 25, 32, 520, 546, 'chrome')
    block((1112, -498, 688, 1137, -96, 1094), 'chrome')
    block((1104, -478, 709, 1114, -116, 1073), 'window')
    for y in (-574, -36):
        block((1102, y - 24, 745, 1135, y + 24, 1008), 'chrome')
        block((1090, y - 18, 760, 1106, y + 18, 993), 'lamp', emitter=(0, 44))
    cylinder(993, 98, 74, 65, 520, 653, 'rose', taper=.9)
    cylinder(993, 98, 38, 38, 653, 683, 'enamel')
    block((920, 72, 678, 1010, 124, 701), 'enamel')
    rounded_box((734, -671, 520, 900, -560, 549), 16, 'yellow')

    section('Commode and wall-mounted paper roll')
    def bowl_profile(scale, z):
        # Integer multiples of one outline keep the annular brush seams planar.
        quadrant = [(15, 4), (11, 12), (4, 16)]
        outline = (quadrant + [(-x, y) for x, y in reversed(quadrant)]
                   + [(-x, -y) for x, y in quadrant] + [(x, -y) for x, y in reversed(quadrant)])
        return [(-881 + x * scale, -573 + y * scale, z) for x, y in outline]

    brushes.append(join_rings(bowl_profile(6, 0), bowl_profile(7, 95), 'enamel'))
    brushes.append(join_rings(bowl_profile(7, 95), bowl_profile(10, 244), 'enamel'))
    brushes.append(join_rings(bowl_profile(7, 244), bowl_profile(7, 250), 'window'))
    brushes.append(rim(bowl_profile(6, 244), bowl_profile(10, 244),
                       bowl_profile(8, 279), bowl_profile(11, 279), 'enamel'))
    brushes.append(rim(bowl_profile(8, 279), bowl_profile(11, 279),
                       bowl_profile(8, 308), bowl_profile(11, 308), 'paint'))
    rounded_box((-1088, -816, 153, -674, -668, 479), 24, 'enamel')
    rounded_box((-1094, -816, 479, -668, -661, 513), 24, 'enamel')
    block((-760, -677, 426, -704, -652, 447), 'chrome')
    block((-1108, -326, 432, -1024, -204, 462), 'chrome')
    cylinder(-1066, -259, 56, 58, 335, 437, 'enamel')
    block((-1017, -299, 253, -1009, -219, 426), 'paint')

    section('Floor cover, hamper and folded bath linens')
    rounded_box((-698, -364, 0, -398, -100, 7), 20, 'cloth')
    rounded_box((40, -140, 0, 574, 234, 7), 24, 'cloth')
    rounded_box((44, -96, 0, 265, 62, 56), 22, 'teal')
    rounded_box((62, -90, 56, 264, 61, 104), 18, 'cloth')
    rounded_box((82, -85, 104, 248, 64, 140), 17, 'paint')
    rounded_box((362, 12, 7, 540, 150, 98), 18, 'yellow')
    rounded_box((-415, -746, 0, -75, -477, 198), 46, 'wood')
    for z in (27, 59, 91, 123, 155):
        rounded_box((-417, -748, z, -73, -475, z + 7), 48, 'paint')
    rounded_box((-429, -756, 198, -61, -465, 228), 50, 'wood')
    rounded_box((-385, -722, 228, -122, -484, 258), 37, 'rose')
    block((-1152, -72, 501, -1104, 143, 518), 'chrome')
    block((-1112, -54, 256, -1093, 124, 525), 'cloth')
    block((-1110, -64, 259, -1091, 134, 282), 'teal')
    for x in (-668, 332, 868):
        rounded_box((x - 143, -104, 1221, x + 143, 104, 1248), 25, 'paint')
        rounded_box((x - 130, -87, 1208, x + 130, 87, 1221), 20, 'lamp')

    entities = ['// Deathmatch starts and an editor preview start\n']
    starts = [
        (-1014, 30, 0, 0), (-570, 53, 0, 270), (-72, 500, 53, 180),
        (603, 705, 0, 240), (1020, 482, 0, 225), (1004, -554, 0, 180),
        (318, -671, 0, 85), (-509, -672, 0, 55), (-581, -195, 7, 5),
        (596, -447, 0, 140), (670, 264, 0, 160), (-683, 597, 53, 0),
    ]
    for x, y, z, yaw in starts:
        entities.append(entity('info_player_deathmatch', (x, y, z + 32), angle=yaw))
    entities.append(entity('info_player_start', (455, -581, 32), angle=158))
    entities.append(entity('info_player_intermission', (674, -706, 720), angles='23 136 0'))

    entities.append('// Arena pickups stay on the floor and in the accessible bath\n')
    for kind, x, y, z in (
        ('weapon_shotgun', -1036, -148, 0), ('ammo_shells', -677, -105, 7),
        ('weapon_supershotgun', 993, 96, 0), ('ammo_shells', 803, -617, 0),
        ('weapon_machinegun', -226, -410, 0), ('ammo_bullets', -540, -531, 0),
        ('weapon_machinegun', 861, 584, 0), ('ammo_bullets', 529, 764, 0),
        ('weapon_grenadelauncher', -418, 633, 53), ('ammo_grenades', 152, 392, 48),
        ('weapon_shotgun', 121, -508, 0), ('ammo_shells', 550, -523, 0),
        ('item_armor_combat', 294, -69, 7), ('item_armor_jacket', -573, 409, 51),
        ('item_health', -1080, 119, 0), ('item_health', 1073, -323, 0),
        ('item_health', 469, -658, 0), ('item_health', -700, -774, 0),
        ('item_health', 579, 212, 0), ('item_health', 189, 710, 48),
        ('ammo_bullets', -455, -19, 0),
    ):
        entities.append(entity(kind, (x, y, z + 25)))

    entities.append('// Baked daylight and warm ceiling fill\n')
    for x, y, z, strength, color in (
        (-668, -90, 1116, 720, '1 .89 .76'), (332, -40, 1116, 710, '1 .90 .77'),
        (868, 46, 1116, 670, '1 .91 .81'), (-260, 727, 829, 490, '.72 .84 1'),
        (22, 726, 829, 430, '.72 .85 1'), (-833, 255, 593, 400, '.87 .94 1'),
        (814, -296, 795, 260, '.96 .92 .83'), (916, -250, 105, 170, '.94 .89 .78'),
        (482, 417, 514, 360, '.88 .94 1'), (-825, -435, 516, 330, '1 .88 .73'),
        (-520, 468, 485, 400, '.86 .93 1'), (-490, -553, 200, 155, '1 .88 .76'),
        (74, -589, 580, 340, '1 .9 .77'),
    ):
        entities.append(entity('light', (x, y, z), light=strength, _color=color))

    return ('// Tile Tide - Plastic Platoon deathmatch\n'
            '{\n"classname" "worldspawn"\n"message" "Tile Tide"\n"sky" "unit1_"\n'
            + ''.join(brushes) + '}\n' + ''.join(entities))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=MAP)
    parser.add_argument('--materials-only', action='store_true')
    args = parser.parse_args()
    write_materials()
    if not args.materials_only:
        args.output.write_text(generate(), encoding='ascii', errors='strict')


if __name__ == '__main__':
    main()
