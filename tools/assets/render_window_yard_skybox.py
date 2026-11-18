#!/usr/bin/env python3
"""Bake the Plastic Platoon neighborhood from human-height windowsill level."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import (bake, beam, box, current_object, match_edge_texels, material,
                             new_scene, parse_args, rod)
from render_backyard_skybox import (fencing, grass, house_windows, mesh_object, puff,
                                      summer_sky, tree_and_swing, yard_materials)


EYE = (6.21, -1.34, 1.62)
DRIVEWAY = (4.4, 16.57, -6.23, -3.04)


def bordered_bed(name, x, y, width, depth, crest, edge, fill):
    for side in (-1, 1):
        box(name + " long rail", (x, y + side * depth / 2, crest * .5),
            (width + .154, .155, crest), edge, .019)
        box(name + " end rail", (x + side * width / 2, y, crest * .5),
            (.154, depth - .147, crest), edge, .019)
    box(name + " fill", (x, y, (crest - .044) * .5),
        (width - .106, depth - .110, crest - .044), fill, .007)
    return crest - .044


def castle_tower(name, x, y, bottom, height, radius, m):
    top = bottom + height
    rod(name, (x, y, bottom), (x, y, top), radius, m["castle"], 12)
    rod("Sand tower rim", (x, y, top - .071), (x, y, top), radius + .027, m["castle_lit"], 12)
    for direction in range(8):
        angle = math.tau * direction / 8
        cap = box("Molded sand battlement",
                  (x + math.cos(angle) * radius * .85, y + math.sin(angle) * radius * .85, top + .046),
                  (.113, .092, .092), m["castle_lit"], .008)
        cap.rotation_euler.z = angle


def castle_arch(x, y, z, m):
    for sign in (-1, 1):
        box("Sandcastle gate pier", (x, y + sign * .298, z + .093),
            (.177, .159, .188), m["castle"], .015)
    for section in range(8):
        low = math.pi * section / 8
        high = math.pi * (section + 1) / 8
        profile = [(radius * math.cos(angle), radius * math.sin(angle) + .176)
                   for radius, angle in ((.375, low), (.375, high), (.219, high), (.219, low))]
        vertices = [(x + offset, y + col, z + row) for offset in (-.084, .084) for col, row in profile]
        mesh_object("Packed sand arch", vertices,
                    [(3,2,1,0), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)],
                    [m["castle_lit"] if section % 3 else m["castle"]])


def sandbox(m):
    x, y = .08, -2.19
    top = bordered_bed("Timber sandbox", x, y, 3.22, 2.74, .33, m["sandbox_wood"], m["sand"])
    for dx in (-1.61, 1.61):
        for dy in (-1.37, 1.37):
            box("Square sandbox corner cap", (x + dx, y + dy, .332),
                (.241, .237, .077), m["fence_light"], .014)
    cx, cy = x - .24, y + .01
    for dx in (-.628, .612):
        for dy in (-.68, .68):
            castle_tower("Corner sand tower", cx + dx, cy + dy, top, .53, .196, m)
    for dy in (-.68, .68):
        box("Sandcastle side wall", (cx, cy + dy, top + .153),
            (1.21, .155, .306), m["castle"], .017)
        for dx in (-.442, -.147, .15, .445):
            box("Sandcastle wall crenel", (cx + dx, cy + dy, top + .349),
                (.148, .156, .086), m["castle_lit"], .007)
    box("Rear sandcastle wall", (cx - .619, cy, top + .154), (.15, 1.32, .309), m["castle"], .016)
    castle_arch(cx + .612, cy, top, m)
    castle_tower("Tall central sand keep", cx - .22, cy + .073, top, .81, .249, m)
    flag = (cx - .22, cy + .073)
    rod("Small sandcastle pennant pole", (*flag, top + .806), (*flag, top + 1.136), .013, m["rail"], 10)
    mesh_object("Red sandbox pennant",
                [(*flag, top + 1.121), (flag[0] - .03, flag[1] + .293, top + 1.044),
                 (*flag, top + .990)], [(0,1,2)], [m["flower_red"]])
    bpy.ops.mesh.primitive_cone_add(vertices=18, radius1=.139, radius2=.183,
                                   depth=.254, location=(x + 1.13, y - .886, top + .122))
    current_object("Upside-down bucket mold", m["flower_red"])
    rod("Sandbox shovel shaft", (x + 1.07, y + .859, top + .047),
        (x + .721, y + 1.067, top + .079), .02, m["sand_blue"])
    shovel = box("Blue plastic shovel blade", (x + 1.157, y + .808, top + .051),
                 (.205, .159, .056), m["sand_blue"], .032)
    shovel.rotation_euler.z = -.55


def garden(m):
    for x, y, crop in ((-4.45, .13, "lettuce"), (-4.46, 2.04, "tomato")):
        top = bordered_bed("Cedar vegetable bed", x, y, 2.52, 1.37, .398, m["rail"], m["soil"])
        for row in (-.33, .32):
            for col in (-.83, -.276, .279, .827):
                px, py = x + col, y + row
                if crop == "lettuce":
                    puff("Outer lettuce leaves", (px, py, top + .135), (.190,.183,.175), m["leaf"])
                    puff("Lettuce heart", (px + .058, py - .031, top + .192),
                         (.128,.122,.130), m["leaf_lit"])
                else:
                    rod("Tomato stake", (px, py, top), (px, py, top + .754), .019, m["rail"], 8)
                    puff("Staked tomato vine", (px - .05, py, top + .375), (.158,.151,.323), m["leaf_mid"])
                    for dx, dy, h in ((.072,.106,.264),(.072,-.104,.397),(.024,.096,.497)):
                        puff("Tomatoes on the vine", (px+dx, py+dy, top+h), (.049,.048,.052), m["flower_red"])
    top = bordered_bed("Cottage flower bed", -.89, -5.53, 4.54, .83, .242, m["sandbox_wood"], m["soil"])
    for index in range(12):
        x = -2.85 + index * .355 + .04 * math.sin(index)
        y = -5.53 + .113 * math.cos(index * 2)
        height = .22 + .17 * ((index * 3) % 7) / 6
        puff("Flower border foliage", (x, y, top + .11), (.212,.161,.183), m["leaf_mid"])
        rod("Flower stems", (x, y, top + .088), (x + .04, y - .036, top + height),
            .012, m["leaf"], 8)
        shade = ("flower_yellow", "flower_cream", "flower_red")[index % 3]
        puff("Garden flower head", (x + .04, y - .036, top + height), (.10,.097,.059), m[shade])
        puff("Flower center", (x + .04, y - .036, top + height + .050),
             (.040,.038,.023), m["flower_yellow"])
    for index, x in enumerate((5.02,4.36,3.67,2.97,2.29,1.57,.89,.18,-.53,-1.21,-1.89)):
        tile = box("Stepping stone across lawn", (x, -.518 + .25 * math.sin(index * .45), .022),
                   (.524,.524,.057), m["walk"], .046)
        tile.rotation_euler.z = .127 * math.sin(index + 1)


def concrete_run(name, x1, x2, y1, y2, repeat, axis, surface):
    start, end = (x1, x2) if axis == "x" else (y1, y2)
    count = max(1, round((end - start) / repeat))
    length = (end - start) / count
    for index in range(count):
        position = start + length * (index + .5)
        z = .017
        if axis == "x":
            center, bounds = (position, (y1 + y2) / 2, z), (length - .023, y2 - y1, .055)
        else:
            center, bounds = ((x1 + x2) / 2, position, z), (x2 - x1, length - .023, .055)
        box(name, center, bounds, surface, .009)


def street(m):
    x1, x2, y1, y2 = DRIVEWAY
    near_start, near_end = 14.22, 15.93
    far_start, far_end = 25.29, 26.86
    concrete_run("Driveway expansion slabs", x1, near_start, y1, y2, 2.22, "x", m["drive"])
    concrete_run("Driveway apron", near_end, x2, y1, y2, .75, "x", m["drive"])
    concrete_run("Continuous near sidewalk", near_start, near_end, -52, 52, 2.03, "y", m["walk"])
    concrete_run("Across-street sidewalk", far_start, far_end, -52, 52, 2.09, "y", m["walk"])
    box("Unmarked neighborhood asphalt", (20.804, 0, .010), (8.61, 116.0, .09), m["asphalt"])
    for x in (16.49, 25.12):
        box("Rounded residential curb", (x, 0, .056), (.152, 109.6, .127), m["curb"], .017)
    for y in (-16.2, -.78, 12.8):
        concrete_run("Neighbor driveway apron", 25.05, far_start, y - 1.52, y + 1.52, .5, "x", m["drive"])
        concrete_run("Neighbor driveway", far_end, 30.23, y - 1.52, y + 1.52, 1.83, "x", m["drive"])
        rod("Mailbox post", (26.11, y + 1.87, .0), (26.11, y + 1.87, 1.06), .063, m["rail"])
        box("Rounded roadside mailbox", (26.10, y + 1.86, 1.082),
            (.405,.259,.232), m["metal"], .085)
        box("Mailbox side flag", (26.12, y + 1.701, 1.144), (.049,.032,.138), m["flower_red"], .012)


def neighbor_house(x, y, width, height, siding, roof, m):
    gable_base = height + .16
    ridge = gable_base + width * .237
    box("Neighbor's shallow masonry plinth", (x + 2.55, y, .174),
        (5.2,width,.348), m["foundation"], .025)
    box("Neighbor's painted clapboard walls", (x + 2.59, y, (height + .34) * .5),
        (5.2,width,height - .34), siding, .015)
    for row in range(round((height - .34) / .239)):
        z = .453 + row * .239
        box("Simple horizontal siding course", (x - .041, y, z), (.064,width - .017,.226), siding, .004)
    for xx in (x, x + 5.17):
        mesh_object("Suburban gable", [(xx,y-width/2,height),(xx,y+width/2,height),(xx,y,ridge)],
                    [(0,1,2)], [siding])
    for side in (-1, 1):
        edge = y + side * (width / 2 + .24)
        beam("Neighbor's shingled roof", (x+2.585,y,ridge),(x+2.585,edge,height),
             5.76,.165,roof,.025)
        beam("Pale fascia on gabled roof", (x-.289,y,ridge),(x-.289,edge,height),
             .119,.152,m["trim"],.012)
    box("Neighbor's pale eave band", (x-.112,y,height),(.109,width+.15,.128),m["trim"],.014)
    box("Side brick chimney", (x + 2.10, y + width*.24, ridge - .336),
        (.55,.615,1.307),m["brick"],.026)
    box("Chimney coping", (x + 2.10, y + width*.24, ridge + .329),
        (.66,.71,.099),m["foundation"],.019)
    for sign in (-1, 1):
        house_windows(m,x-.045,y+sign*width*.285,1.76,1.44)
    box("Pale neighbor door frame", (x-.102,y+.14,1.313),(.175,1.10,2.094),m["trim"],.026)
    box("Painted neighbor front door", (x-.207,y+.14,1.313),(.082,.876,1.894),m["door"],.021)
    box("Neighbor entrance platform", (x-.36,y+.14,.184),(.756,1.65,.366),m["foundation"],.023)


def neighborhood(m):
    homes = (
        (31.4, -16.09, 7.82, 2.85, "neighbor_yellow", "roof"),
        (30.9, -.55, 7.43, 3.06, "neighbor_blue", "neighbor_gray_roof"),
        (31.82, 12.77, 8.06, 2.79, "neighbor_rose", "roof"),
        (-6.6, 12.4, 6.17, 3.05, "neighbor_rose", "neighbor_gray_roof"),
        (-1.49, -13.21, 6.16, 2.89, "neighbor_yellow", "roof"),
    )
    for x, y, width, height, siding, roof in homes:
        neighbor_house(x, y, width, height, m[siding], m[roof], m)
    for x, y, h, width in ((-10.3,6.14,4.33,1.64),(-10.5,-4.83,3.68,1.76),
                            (10.03,10.55,4.28,1.76),(9.84,-10.45,3.91,1.54),
                            (28.56,-9.52,4.21,1.48),(29.9,6.37,3.85,1.67),
                            (36.5,19.13,4.5,1.83),(27.55,-23.44,4.2,1.68)):
        rod("Neighbor shade tree trunk", (x,y,.0),(x+.11,y+.04,h),.104,m["bark"],10)
        puff("Crowns beyond the yard", (x+.11,y,h), (width,width*.83,width*.87), m["distant"])
        puff("Warm crown side", (x-.67,y-.42,h-.36), (width*.73,width*.73,width*.70), m["leaf_mid"])
    for x, y, height in ((-.4,8.6,1.12),(3.73,7.75,1.07),(1.15,-8.1,1.2),(11.56,-7.9,.91),
                         (12.43,6.64,1.05),(27.9,-14.5,.89),(28.4,1.42,1.02),(28.68,14.13,.91)):
        puff("Trimmed border shrubs", (x,y,height*.40), (1.31,.63,height*.66), m["leaf_mid"])


def build_scene(samples):
    scene = new_scene(samples, bounces=3, exposure=-.14)
    scene.view_settings.view_transform = "Standard"
    scene.cycles.adaptive_threshold = .049
    m = yard_materials()
    swatches = {
        "sandbox_wood": ("ad8354","be9466",4),
        "sand": ("cbad74","d2b680",10),
        "castle": ("cba864","d1ab68",15),
        "castle_lit": ("d8b779",),
        "sand_blue": ("4d86a5",),
        "soil": ("6a4d36","805a3e",8),
        "flower_red": ("bb5a40",),
        "flower_yellow": ("d39d47",),
        "flower_cream": ("ece3c5",),
        "walk": ("bdbaae","c8c3b5",17),
        "drive": ("a9a59b","b7b1a5",13),
        "curb": ("b0aaa0",),
        "asphalt": ("63676a","737677",6),
        "neighbor_yellow": ("bcad83",),
        "neighbor_blue": ("78959f",),
        "neighbor_rose": ("ad8c7d",),
        "neighbor_gray_roof": ("626967",),
    }
    m.update({name: material(name, *values) for name, values in swatches.items()})
    summer_sky(scene)
    grass(m, paving=DRIVEWAY)
    fencing(m, front_open_at=5.79)
    tree_and_swing(m, swing_yaw=math.radians(23))
    sandbox(m)
    garden(m)
    street(m)
    neighborhood(m)
    return scene


if __name__ == "__main__":
    args = parse_args(__doc__, samples=20)
    bake(build_scene(args.samples), "pp_window_yard", EYE, args.output)
    match_edge_texels(args.output, "pp_window_yard")
