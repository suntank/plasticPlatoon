#!/usr/bin/env python3
"""Build an editable pantry display and reusable, generically labeled food packages."""

import argparse
from math import cos, pi, sin, tau
from pathlib import Path

from PIL import Image, ImageDraw

from generate_bath_prefabs import HEADER, block, bottle_shape, label_panel, loft, oval, straight_oval
from generate_bathroom import BASE, rounded_rectangle
from generate_garage_prefabs import finish, ring_band
from generate_sandkeep_materials import text, write_wal
from generate_switchyard import cross, face, sub
from platoon_palette import load_palette
from verify_sandkeep import parse_entities

WOOD = 'kit_beech'
FRAME = 'bedroom/pantry_sage'
BACK = 'bedroom/pantry_linen'
TIN = 'garage_steel'
CREAM = 'enamel'
KRAFT = 'garage_kraft'
TEAL = 'laundry_teal'
RUST = 'bedroom/living_rust'
NAVY = 'toy_navy'
GOLD = 'kitchen_cheese'
OLIVE = 'kitchen_green'
AMBER = 'bedroom/pantry_amber'

# Titles name the contents. The designs use original food motifs and no product marks.
LABELS = {
    'jam': (('STRAWBERRY', 'JAM'), (155, 50, 65), 'berry'),
    'peanut_butter': (('PEANUT', 'BUTTER'), (129, 75, 42), 'seed'),
    'pickles': (('DILL', 'PICKLES'), (63, 104, 62), 'pickle'),
    'honey': (('HONEY',), (145, 88, 28), 'hex'),
    'oil': (('OLIVE', 'OIL'), (76, 96, 51), 'leaf'),
    'canned_tomatoes': (('CRUSHED', 'TOMATOES'), (167, 54, 47), 'tomato'),
    'canned_beans': (('WHITE', 'BEANS'), (71, 111, 128), 'seed'),
    'canned_corn': (('SWEET', 'CORN'), (153, 103, 22), 'grain'),
    'cocoa_tin': (('COCOA',), (112, 65, 58), 'tile'),
    'oats_box': (('ROLLED', 'OATS'), (57, 113, 110), 'grain'),
    'pasta_box': (('DRIED', 'PASTA'), (150, 65, 51), 'strand'),
    'crackers_box': (('SALTINE', 'CRACKERS'), (70, 105, 145), 'tile'),
    'tea_box': (('BLACK', 'TEA'), (117, 68, 106), 'leaf'),
    'flour_bag': (('WHEAT', 'FLOUR'), (102, 77, 121), 'grain'),
    'sugar_bag': (('CANE', 'SUGAR'), (55, 111, 131), 'tile'),
    'rice_bag': (('LONG GRAIN', 'RICE'), (63, 113, 84), 'grain'),
    'lentils_bag': (('RED', 'LENTILS'), (153, 74, 43), 'seed'),
    'coffee_bag': (('GROUND', 'COFFEE'), (112, 66, 55), 'seed'),
}

SHELF_LEVELS = (16, 168, 324, 478)
STOCK = (
    (16, (('flour_bag', -421, 38), ('sugar_bag', -253, 60), ('rice_bag', -84, 31),
          ('lentils_bag', 87, 61), ('coffee_bag', 267, 35), ('oil', 429, 47))),
    (168, (('oats_box', -412, 38), ('pasta_box', -224, 56), ('crackers_box', -40, 26),
           ('tea_box', 138, 57), ('cocoa_tin', 285, 32), ('canned_corn', 420, 52))),
    (324, (('jam', -417, 40), ('peanut_butter', -280, 42), ('pickles', -136, 27),
           ('canned_tomatoes', 9, 42), ('canned_beans', 147, 48), ('canned_corn', 279, 27),
           ('honey', 417, 37))),
    (478, (('crackers_box', -416, 42), ('flour_bag', -247, 55), ('oats_box', -80, 37),
           ('coffee_bag', 88, 44), ('rice_bag', 260, 58), ('oil', 422, 35))),
)


def label_texture(name):
    return f'bathroom/pantry_{name}'


def product_icon(draw, motif, ink, paper):
    if motif == 'grain':
        draw.line((64, 104, 64, 65), fill=ink, width=3)
        for y in (71, 82, 93):
            draw.ellipse((43, y - 5, 63, y + 3), fill=ink)
            draw.ellipse((65, y - 5, 85, y + 3), fill=ink)
    elif motif in ('tomato', 'berry'):
        for x, y in ((46, 83), (66, 76), (78, 90)):
            draw.ellipse((x - 11, y - 8, x + 11, y + 12), fill=ink)
            draw.polygon(((x-7, y-6), (x-1, y-12), (x+7, y-6), (x+1, y-4)), fill=(71, 112, 68))
            if motif == 'berry':
                for dx, dy in ((-4, 0), (4, 1), (0, 6)):
                    draw.point((x + dx, y + dy), fill=paper)
    elif motif == 'seed':
        for x, y in ((46, 90), (62, 74), (78, 88), (64, 98)):
            draw.ellipse((x-9, y-6, x+9, y+6), fill=ink)
            draw.arc((x-7, y-5, x+7, y+5), 54, 174, fill=paper, width=2)
    elif motif == 'pickle':
        for x, y in ((54, 80), (74, 88)):
            draw.rounded_rectangle((x - 7, y - 16, x + 7, y + 16), radius=6, fill=ink)
            for dy in (-10, 0, 10):
                draw.point((x, y + dy), fill=paper)
    elif motif == 'hex':
        for x, y in ((56, 78), (73, 78), (64, 94)):
            points = [(x+round(9*cos(pi*i/3)), y+round(9*sin(pi*i/3))) for i in range(6)]
            draw.polygon(points, outline=ink, width=2)
    elif motif == 'leaf':
        draw.line((42, 99, 86, 69), fill=ink, width=3)
        draw.ellipse((46, 70, 62, 88), fill=ink)
        draw.ellipse((61, 83, 81, 93), fill=ink)
        draw.ellipse((70, 66, 84, 78), fill=ink)
    elif motif == 'strand':
        for x in (53, 60, 67, 74):
            draw.line((x - 5, 102, x + 6, 67), fill=ink, width=3)
        draw.line((48, 89, 76, 94), fill=ink, width=5)
    else:
        for x, y in ((39, 76), (71, 70), (64, 91)):
            draw.rounded_rectangle((x, y, x+21, y+13), radius=2, fill=ink)
            for dx in (5, 10, 15):
                draw.point((x+dx, y+6), fill=paper)


def write_materials():
    sage = finish((110, 143, 128), lambda x, y: 3 * cos(tau * (x + y) / 128))
    linen = finish((209, 199, 175), lambda x, y: 3 * sin(tau * y / 64))
    amber = finish((158, 96, 42), lambda x, y: 12 * cos(tau * (x - 2 * y) / 128))
    images = {FRAME: sage, BACK: linen, AMBER: amber}
    paper = (243, 226, 190)
    for name, (title, color, motif) in LABELS.items():
        image = finish(paper, lambda x, y: 2 * cos(tau * (x + y) / 128))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 127, 8), fill=color)
        draw.rounded_rectangle((5, 13, 122, 106), radius=6, outline=color, width=2)
        draw.rectangle((0, 114, 127, 127), fill=color)
        title_y = 26 if len(title) == 2 else 36
        for line in title:
            if len(line) <= 9:
                text(draw, 64, title_y, line, 2, color)
            else:
                width = (6 * len(line) - 1) * 2
                mask = Image.new('L', (width, 14))
                text(ImageDraw.Draw(mask), width // 2, 0, line, 2, 255)
                image.paste(color, (10, title_y), mask.resize((108, 14), Image.Resampling.NEAREST))
            title_y += 18
        product_icon(draw, motif, color, paper)
        images[label_texture(name)] = image

    palette = load_palette()
    for name, image in images.items():
        image.save(BASE / 'textures' / (name + '.png'))
        write_wal(BASE / 'textures' / (name + '.wal'), name, image, palette)


def shelf():
    posts = ''.join(block((x, y, 0, x+20, y+20, 526), FRAME)
                    for x in (-528, 508) for y in (-147, 127))
    backing = block((-508, 133, 0, 508, 145, 515), BACK)
    joints = ''.join(block((x-1, -151, z-6, x+7, -146, z+1), WOOD)
                     for x in (-520, 514) for z in SHELF_LEVELS)
    decks = ''.join(
        block((-528, -148, z-12, 528, 147, z-4), FRAME)
        + block((-518, -148, z-4, 518, 144, z), WOOD)
        for z in SHELF_LEVELS
    )
    rail = block((-517, 109, 497, 517, 146, 525), FRAME)
    return posts + backing + decks + joints + rail


def box_package(name, width, depth, height, tint):
    label = label_texture(name)
    body = label_panel((-width, -depth, 0, width, depth, height-7), label, tint)
    flap = block((-width, -depth, height-7, width, depth, height), tint)
    seam = block((-width+3, -2, height, width-3, 1, height+1), CREAM)
    return body + flap + seam


def bag(name, width, depth, height, tint):
    profiles = ((0, .90, .80), (9, 1, 1), (height-25, 1, 1),
                (height-8, .90, .47), (height-3, .88, .36))
    body = loft([rounded_rectangle(0, 0, width*u, depth*v, 5, z)
                 for z,u,v in profiles], tint)
    seal = block((-width*.86, -depth*.29, height-3, width*.86, depth*.29, height), tint)
    label = label_panel((-width+9, -depth-1, 12, width-9, -depth+1, height-27),
                        label_texture(name), tint)
    fold = block((-width*.8, -depth*.30, height-4, width*.8, -depth*.22, height-2), BACK)
    return body + seal + label + fold


def jar(name, width, depth, height, tint, cap_color):
    body = bottle_shape(width, depth, 9, [(0, .96, 0, 0), (8, 1, 0, 0),
                                         (height-24, 1, 0, 0), (height-16, .79, 0, 0)], tint)
    neck = straight_oval(0, 0, width*.66, depth*.87, height-17, height-9, tint)
    lid = straight_oval(0, 0, width*.82, depth*.97, height-10, height, cap_color)
    label = label_panel((-width+10, -depth-1, 12, width-10, -depth+1, height-27),
                        label_texture(name), tint)
    return body + neck + lid + label


def bottle(name, width, depth, height, tint, cap_color):
    body = bottle_shape(width, depth, 8, [(0, .92, 0, 0), (8, 1, 0, 0),
                                         (height-37, 1, 0, 0), (height-22, .53, 0, 0),
                                         (height-12, .44, 0, 0)], tint)
    lid = straight_oval(0, 0, width*.49, depth*.60, height-14, height, cap_color)
    label = label_panel((-width+9, -depth-1, 14, width-9, -depth+1, height-40),
                        label_texture(name), tint)
    return body + lid + label


def can(name, radius, height, tint=TIN):
    bottom, top = 5, height-5
    cylinder = straight_oval(0, 0, radius, radius, bottom, top, tint)
    faces = cylinder.splitlines()
    sx = radius * 2**.5 / 128
    sy = (top - bottom) / 128
    # These three side faces share the X/Z projection on the front of a 12-sided can.
    for side in (8, 9, 10):
        index = 3 + side
        vertices, _, _ = faces[index].rpartition(' ) ')
        faces[index] = f'{vertices} ) {label_texture(name)} 64 {top/sy:g} 0 {sx:g} {sy:g} 134217728 0 0'
    caps = straight_oval(0, 0, radius+2, radius+2, 0, bottom, TIN)
    caps += straight_oval(0, 0, radius+2, radius+2, top, height, TIN)
    tab = ring_band(7, 0, (height, 6, 11), (height+2, 6, 11), tint, sides=8)
    return '\n'.join(faces) + '\n' + caps + tab


def package_brushes():
    return {
        'jam': jar('jam', 44, 35, 87, 'kitchen_apple', RUST),
        'peanut_butter': jar('peanut_butter', 48, 39, 103, AMBER, NAVY),
        'pickles': jar('pickles', 49, 41, 120, OLIVE, TIN),
        'honey': bottle('honey', 41, 32, 121, AMBER, GOLD),
        'oil': bottle('oil', 38, 35, 131, OLIVE, NAVY),
        'canned_tomatoes': can('canned_tomatoes', 42, 96),
        'canned_beans': can('canned_beans', 39, 88),
        'canned_corn': can('canned_corn', 39, 83),
        'cocoa_tin': can('cocoa_tin', 44, 106, RUST),
        'oats_box': box_package('oats_box', 64, 35, 127, TEAL),
        'pasta_box': box_package('pasta_box', 55, 31, 132, RUST),
        'crackers_box': box_package('crackers_box', 70, 29, 116, NAVY),
        'tea_box': box_package('tea_box', 54, 35, 79, 'toy_lilac'),
        'flour_bag': bag('flour_bag', 62, 38, 125, CREAM),
        'sugar_bag': bag('sugar_bag', 57, 38, 117, BACK),
        'rice_bag': bag('rice_bag', 65, 36, 120, FRAME),
        'lentils_bag': bag('lentils_bag', 59, 34, 114, KRAFT),
        'coffee_bag': bag('coffee_bag', 54, 36, 115, AMBER),
    }


def translated_package(brushes, dx, dy, dz):
    """Translate the package and keep its label texture locked to the surface."""
    result = []
    for brush in brushes:
        lines = []
        for side in brush:
            a, b, c = side['points']
            nx, ny, nz = cross(sub(a,b),sub(c,b))
            axis = max(range(3), key=lambda i: abs((nx,ny,nz)[i]))
            u,v,rot,sx,sy = side['mapping']
            assert rot == 0
            vertices = [(x+dx,y+dy,z+dz) for x,y,z in (a,b,c)]
            shift = u - (dy if axis == 0 else dx)/sx, v + (dy if axis == 2 else dz)/sy
            lines.append(face(vertices, side['texture'], detail=True, scale=(sx,sy), shift=shift))
        result.append('{\n' + ''.join(lines) + '}\n')
    return ''.join(result)


def stocked_shelf(frame, packages):
    brushes = {name: parse_entities(wrap(data))[0]['brushes'] for name, data in packages.items()}
    return frame + ''.join(translated_package(brushes[name], x, y, z)
                           for z,row in STOCK for name, x, y in row)


def wrap(brushes):
    return HEADER + '{\n"classname" "worldspawn"\n' + brushes + '}\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_materials()
    frame, packages = shelf(), package_brushes()
    prefabs = {'shelf_empty': frame, 'shelf_stocked': stocked_shelf(frame, packages), **packages}
    for name, brushes in prefabs.items():
        (args.output / f'pantry_{name}.map').write_text(wrap(brushes), encoding='ascii')


if __name__ == '__main__':
    main()
