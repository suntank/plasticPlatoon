#!/usr/bin/env python3
"""Bake a stylized Plastic Platoon kitchen from floor level in Blender."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import area, bake, box, current_object, material, new_scene, parse_args, rod


EYE = (-0.48, -0.13, 0.092)
ROOM_X = 3.05
ROOM_Y = 2.67
CEILING = 2.86


def ellipsoid(name, center, dimensions, surface):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=center)
    obj = current_object(name, surface)
    obj.scale = dimensions
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def grid(name, origin, across, up, columns, rows, spacing, gap, surfaces, material_index):
    vertices, faces = [], []
    across, up, origin = Vector(across), Vector(up), Vector(origin)
    for row in range(rows):
        for col in range(columns):
            bottom = len(vertices)
            faces.append(tuple(range(bottom, bottom + 4)))
            vertices.extend(origin + across * (col * spacing + s) + up * (row * spacing + t)
                            for s, t in ((0, 0), (spacing - gap, 0),
                                         (spacing - gap, spacing - gap), (0, spacing - gap)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for surface in surfaces:
        mesh.materials.append(surface)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for polygon in mesh.polygons:
        row, col = divmod(polygon.index, columns)
        polygon.material_index = material_index(row, col)


def north(u, d, z):
    return u, d, z


def east(u, d, z):
    return d, -u, z


def wall_box(frame, name, center, size, surface, bevel=0):
    dimensions = (size[1], size[0], size[2]) if frame is east else size
    return box(name, frame(*center), dimensions, surface, bevel)


def room(m):
    box("Warm grout between floor tiles", (0, 0, -.078), (6.40, 5.64, .15), m["grout"])
    grid("Oversized checker tiles", (-3.20, -2.80, 0), (1, 0, 0), (0, 1, 0), 16, 14, .40, .006,
         [m["tile_cream"], m["tile_honey"]], lambda row, col: (row + col) % 2)
    box("Ivory kitchen ceiling", (0, 0, CEILING + .075), (6.42, 5.66, .15), m["ceiling"])
    for sign in (-1, 1):
        for x, y, width, depth in ((sign * (ROOM_X + .075), 0, .15, 5.64),
                                    (0, sign * (ROOM_Y + .075), 6.42, .15)):
            box("Buttercream painted wall", (x, y, CEILING / 2), (width, depth, CEILING), m["wall"])
            box("Sage baseboard", (x, y, .080), (width + .065, depth + .065, .16), m["dark_green"], .008)


def base_cabinet(frame, u, depth, width, m, drawers=False):
    wall_box(frame, "Wood cabinet carcass", (u, depth + .51, .484),
             (width, .99, .776), m["dark_green"], .022)
    wall_box(frame, "Recessed toe kick", (u, depth + .54, .064),
             (width - .01, .85, .128), m["shadow"], .008)
    wall_box(frame, "Laminate counter", (u, depth + .477, .909),
             (width + .012, 1.035, .102), m["counter"], .030)
    if drawers:
        for z in (.27, .494, .718):
            wall_box(frame, "Sage drawer front", (u, depth, z),
                     (width - .032, .077, .208), m["green"], .023)
            wall_box(frame, "Drawer pull", (u, depth - .065, z + .049),
                     (min(.275, width - .15), .058, .038), m["brass"], .012)
    else:
        for sign in (-1, 1):
            x = u + sign * width / 4
            wall_box(frame, "Sage cabinet door", (x, depth, .477),
                     (width / 2 - .031, .093, .72), m["green"], .024)
            wall_box(frame, "Inset cabinet panel", (x, depth - .051, .474),
                     (width / 2 - .153, .019, .572), m["light_green"], .020)
            wall_box(frame, "Cabinet door handle", (u + sign * .10, depth - .092, .698),
                     (.045, .064, .171), m["brass"], .015)


def upper_cabinet(frame, u, d, width, m):
    wall_box(frame, "Upper cabinet body", (u, d + .26, 2.038),
             (width, .54, .993), m["cream"], .025)
    for sign in (-1, 1):
        x = u + sign * width / 4
        wall_box(frame, "Cream upper cabinet front", (x, d - .035, 2.038),
                 (width / 2 - .028, .088, .948), m["cream"], .024)
        wall_box(frame, "Upper cabinet raised panel", (x, d - .081, 2.039),
                 (width / 2 - .141, .024, .812), m["wall"], .027)
        wall_box(frame, "Upper cabinet knob", (u + sign * .088, d - .11, 1.696),
                 (.063, .054, .065), m["brass"], .024)


def backsplash(frame, u, wall, columns, m):
    grid("Glazed backsplash", frame(u, wall, .976), frame(1, 0, 0), (0, 0, 1),
         columns, 4, .155, .006, [m["splash"], m["splash_accent"]],
         lambda row, col: int(row == 2 and col % 4 == 1))


def range_wall(m):
    backsplash(east, -1.88, 3.008, 27, m)
    base_cabinet(east, -1.27, 1.98, 1.35, m)
    base_cabinet(east, 1.53, 1.98, 1.45, m, drawers=True)
    upper_cabinet(east, -1.35, 2.48, 1.22, m)
    upper_cabinet(east, 1.56, 2.48, 1.40, m)
    loc = .14
    wall_box(east, "Enamel freestanding range", (loc, 2.50, .502),
             (1.32, 1.025, .999), m["cream"], .054)
    wall_box(east, "Dark oven door rim", (loc, 1.974, .398),
             (1.145, .122, .608), m["shadow"], .052)
    wall_box(east, "Oven viewing window", (loc, 1.903, .380),
             (.942, .035, .388), m["oven_glass"], .043)
    wall_box(east, "Warm edge on oven window", (loc, 1.879, .369),
             (.762, .011, .030), m["muted_metal"], .011)
    wall_box(east, "Oven door pull", (loc, 1.844, .625),
             (1.062, .117, .068), m["muted_metal"], .022)
    wall_box(east, "Cream range control panel", (loc, 1.968, .831),
             (1.255, .117, .198), m["cream"], .023)
    for u in (-.30, -.061, .181, .424, .665):
        rod("Black range dial", east(u, 1.841, .834), east(u, 1.918, .834), .062, m["shadow"], 16)
        wall_box(east, "Range dial mark", (u + .016, 1.838, .850), (.017, .007, .035), m["cream"], .005)
    for u in (-.168, .440):
        for d in (2.241, 2.714):
            rod("Stovetop burner", east(u, d, .994), east(u, d, 1.034), .174, m["shadow"], 20)
    wall_box(east, "Kitchen hood", (loc, 2.630, 1.748), (1.38, .793, .267), m["cream"], .052)
    wall_box(east, "Range hood vent", (loc, 2.503, 1.602), (1.159, .467, .051), m["muted_metal"], .020)
    wall_box(east, "Warm hood lamp", (loc - .35, 2.322, 1.568), (.285, .15, .033), m["bulb"], .011)

    kettle = east(-.17, 2.198, 1.184)
    ellipsoid("Paprika enamel kettle", kettle, (.155, .178, .156), m["red"])
    rod("Kettle lid", (kettle[0], kettle[1], 1.294), (kettle[0], kettle[1], 1.333), .100, m["red"])
    ellipsoid("Kettle lid knob", (kettle[0], kettle[1], 1.352), (.04, .04, .032), m["shadow"])
    spout = [(kettle[0] - .05, kettle[1] + .108, 1.168), (kettle[0] - .035, kettle[1] + .229, 1.249),
             (kettle[0] - .034, kettle[1] + .270, 1.310)]
    for start, end in zip(spout, spout[1:]):
        rod("Kettle spout", start, end, .044, m["red"])
    bpy.ops.mesh.primitive_torus_add(location=(kettle[0], kettle[1], 1.265),
                                  major_radius=.142, minor_radius=.024, major_segments=24, minor_segments=8)
    current_object("Arched kettle handle", m["shadow"]).rotation_euler.y = math.pi / 2
    for u, color in ((1.88, "cream"), (1.64, "red"), (1.39, "light_green")):
        rod("Breakfast canister", east(u, 2.21, .954), east(u, 2.21, 1.134), .087, m[color], 16)
        rod("Breakfast canister lid", east(u, 2.21, 1.13), east(u, 2.21, 1.165), .091, m["wood"], 16)


def sink_wall(m):
    backsplash(north, -2.99, 2.625, 31, m)
    for u, width in ((-2.22, 1.49), (-.567, 1.80), (1.128, 1.57)):
        base_cabinet(north, u, 1.597, width, m)
    upper_cabinet(north, -2.27, 2.091, 1.28, m)
    upper_cabinet(north, 1.47, 2.091, .93, m)
    window_x = -.411
    box("Kitchen window frame", (window_x, 2.628, 1.78), (2.32, .127, 1.29), m["cream"], .032)
    for dx in (-.497, .497):
        for dz, tint in ((-.269, "window_haze"), (.269, "window_blue")):
            box("Frosted window pane", (window_x + dx, 2.548, 1.78 + dz),
                (.953, .034, .51), m[tint], .011)
    box("Kitchen window mullion", (window_x, 2.515, 1.78), (.068, .09, 1.173), m["cream"], .010)
    box("Kitchen window sash", (window_x, 2.515, 1.78), (2.164, .09, .064), m["cream"], .010)
    box("Deep kitchen windowsill", (window_x, 2.546, 1.126), (2.43, .285, .115), m["cream"], .024)
    box("Enamel sink lip", (-.554, 1.981, .964), (1.285, .625, .052), m["muted_metal"], .030)
    box("Recessed sink bowl", (-.554, 1.980, .994), (1.094, .438, .016), m["shadow"], .027)
    faucet = [(-.55, 2.259, .990), (-.55, 2.259, 1.252), (-.55, 2.232, 1.349),
              (-.55, 2.157, 1.390), (-.55, 2.070, 1.365), (-.55, 2.021, 1.303)]
    for start, end in zip(faucet, faucet[1:]):
        rod("Gooseneck faucet", start, end, .040, m["muted_metal"], 16)
    for u in (-.77, -.33):
        rod("Faucet knob", (u, 2.234, .988), (u, 2.234, 1.059), .059, m["muted_metal"], 14)
    for i, shade in enumerate(("cream", "light_green", "cream", "splash_accent")):
        plate = ellipsoid("Plate in dish rack", (.751 + .102 * i, 1.929, 1.139),
                          (.028, .188, .168), m[shade])
        plate.rotation_euler.y = -.15
    box("Dish draining tray", (.904, 1.924, .984), (.554, .437, .069), m["dark_green"], .022)
    for x in (-.984, -.85, -.716):
        box("Folded tea towel", (x, 1.459, .600), (.132, .057, .341),
            m["cream"] if x != -.85 else m["splash_accent"], .017)
    box("Tea towel hanging bar", (-.851, 1.405, .754), (.546, .063, .052), m["brass"], .014)


def fridge_wall(m):
    box("Retro refrigerator body", (-2.588, .685, 1.039), (.898, 1.242, 2.078), m["fridge"], .118)
    box("Refrigerator grating", (-2.122, .685, .121), (.111, 1.028, .145), m["shadow"], .031)
    box("Rounded refrigerator door", (-2.092, .686, .787), (.192, 1.150, 1.148), m["fridge"], .085)
    box("Rounded upper freezer door", (-2.092, .686, 1.691), (.190, 1.150, .596), m["fridge"], .081)
    for z in (1.198, 1.452):
        box("Chrome fridge door pull", (-1.962, .352, z), (.122, .414, .061), m["muted_metal"], .027)
    note = box("Paper shopping list", (-1.987, .946, 1.697), (.022, .217, .278), m["paper"], .009)
    note.rotation_euler.x = -.081
    for z, width in ((1.766, .120), (1.728, .147), (1.69, .102), (1.652, .130)):
        box("List pencil stroke", (-1.973, .945, z), (.003, width, .009), m["shadow"], .002)
    for y, z, shade in ((.963, 1.81, "red"), (.65, 1.87, "light_green"),
                        (.592, 1.631, "red"), (.998, 1.109, "blue"), (.817, 1.030, "red")):
        rod("Round refrigerator magnet", (-1.996, y, z), (-1.957, y, z), .044, m[shade], 14)

    box("Doorway casing", (-2.978, -1.482, 1.105), (.158, 1.096, 2.214), m["cream"], .026)
    box("Back hall door", (-2.872, -1.482, 1.052), (.084, .91, 2.085), m["light_green"], .033)
    for z, h in ((.586, .791), (1.52, .812)):
        box("Door raised panel", (-2.821, -1.482, z), (.039, .687, h), m["green"], .039)
    ellipsoid("Back hall doorknob", (-2.736, -1.792, 1.042), (.052, .059, .059), m["brass"])


def chair(x, y, side, m):
    for dx in (-.195, .195):
        for dy in (-.171, .171):
            box("Breakfast chair leg", (x + dx, y + dy, .246), (.069, .069, .491), m["wood"], .012)
    box("Pressed wood chair seat", (x, y, .481), (.536, .484, .102), m["wood"], .035)
    for dy in (-.173, .173):
        box("Painted chair back post", (x + side * .218, y + dy, .699),
            (.065, .07, .463), m["red"], .016)
    for z in (.714, .897):
        box("Painted chair back slat", (x + side * .219, y, z), (.093, .514, .110), m["red"], .028)


def breakfast_nook(m):
    x, y = -.13, -1.922
    for dx in (-.728, .728):
        for dy in (-.356, .356):
            box("Oak table leg", (x + dx, y + dy, .395), (.113, .113, .785), m["wood"], .016)
    box("Table apron", (x, y, .690), (1.619, .821, .17), m["wood"], .025)
    box("Rounded breakfast table", (x, y, .805), (1.967, 1.134, .147), m["wood"], .053)
    chair(-1.350, -1.896, -1, m)
    chair(1.183, -1.698, 1, m)
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=.134, radius2=.254,
                                   depth=.145, location=(x + .173, y + .394, .952))
    current_object("Porcelain breakfast bowl", m["blue"])
    for dx, dy, z, shade in ((-.100, .014, 1.084, "red"), (.019, -.113, 1.075, "light_green"),
                             (.102, .045, 1.102, "fridge"), (-.007, .092, 1.145, "red")):
        center = (x + .173 + dx, y + .394 + dy, z)
        ellipsoid("Fruit in breakfast bowl", center, (.075, .072, .077), m[shade])
        rod("Apple stem", (center[0], center[1], z + .055),
            (center[0] + .012, center[1] - .008, z + .089), .008, m["wood"], 8)
    box("Kitchen shelf", (.654, -2.477, 1.803), (2.313, .358, .086), m["wood"], .021)
    box("Hanging utensil rail", (.654, -2.528, 1.610), (1.91, .058, .056), m["muted_metal"], .014)
    for x in (-.01, .267, .557):
        rod("Wooden utensil handle", (x, -2.46, 1.609), (x, -2.46, 1.289), .022, m["wood"])
    ellipsoid("Wooden stirring spoon", (-.01, -2.46, 1.275), (.069, .028, .104), m["wood"])
    box("Broad kitchen turner", (.267, -2.46, 1.222), (.132, .029, .179), m["wood"], .021)
    ellipsoid("Deep metal ladle", (.557, -2.46, 1.239), (.071, .054, .093), m["muted_metal"])
    for x, shade in ((.945, "splash_accent"), (1.261, "cream"), (1.520, "light_green")):
        rod("Kitchen shelf crock", (x, -2.444, 1.843), (x, -2.444, 2.074), .107, m[shade], 16)
        rod("Kitchen shelf crock lid", (x, -2.444, 2.071), (x, -2.444, 2.101), .113, m["wood"], 16)


def lighting(m):
    p = (-.17, -1.508)
    rod("Pendant canopy", (*p, CEILING - .06), (*p, CEILING), .15, m["muted_metal"], 24)
    rod("Pendant stem", (*p, 2.241), (*p, CEILING - .045), .020, m["muted_metal"], 16)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=.416, radius2=.121,
                                   depth=.268, location=(*p, 2.134))
    current_object("Sage enamel pendant shade", m["dark_green"])
    ellipsoid("Warm pendant diffuser", (*p, 1.991), (.373, .373, .060), m["bulb"])
    area("Soft breakfast pendant", (*p, 1.914), (*p, .2), 35, (1, .83, .66), .54, .54)
    ellipsoid("Kitchen ceiling opal dome", (.416, .761, CEILING - .068), (.247, .247, .091), m["bulb"])
    area("Kitchen ceiling fixture", (.416, .761, 2.683), (.416, .761, .1), 71, (1, .89, .73), .48, .48)
    area("Daylight from kitchen window", (-.42, 2.463, 1.785), (-.28, -.6, .61),
         120, (.76, .89, 1), 2.009, 1.090)
    area("Soft room fill", (-1.27, -.294, 2.085), (1.51, .33, .55),
         51, (.96, .93, 1), 3.1, 2.13)
    area("Ceiling and cabinet bounce", (.0, .0, 1.222), (.0, .24, 2.55),
         21, (.90, .94, 1), 2.8, 2.4)


def build_scene(samples):
    scene = new_scene(samples, bounces=4, exposure=.22)
    scene.cycles.adaptive_threshold = .038
    coatings = {
        "wall": ("c9c2a9", "d0c8b2", 7),
        "ceiling": ("e2dbc6",),
        "tile_cream": ("b8b29f", "c9beaa", 17),
        "tile_honey": ("a79477", "b6a284", 17),
        "grout": ("9b8f7a",),
        "dark_green": ("648071",),
        "green": ("7c9785",),
        "light_green": ("94ac97",),
        "cream": ("e0d4b4",),
        "fridge": ("ded1a2",),
        "counter": ("ad9c7f", "bbab8e", 16),
        "splash": ("c9c4ad",),
        "splash_accent": ("b68765",),
        "red": ("ac5140",),
        "blue": ("668b98",),
        "wood": ("ad8159", "bc9467", 4),
        "paper": ("efe2be",),
        "shadow": ("44494a",),
        "brass": ("b6a17a",),
        "muted_metal": ("85928e",),
        "oven_glass": ("4e6267",),
    }
    m = {name: material(name, *parameters) for name, parameters in coatings.items()}
    m["window_blue"] = material("Cool daylight glass", "aacad3", glow=1.15)
    m["window_haze"] = material("Pale daylight glass", "c9dbdd", glow=1.14)
    m["bulb"] = material("Warm opal light diffusers", "f0dfb5", glow=1.35)
    room(m)
    range_wall(m)
    sink_wall(m)
    fridge_wall(m)
    breakfast_nook(m)
    lighting(m)
    return scene


if __name__ == "__main__":
    args = parse_args(__doc__, samples=24)
    bake(build_scene(args.samples), "pp_kitchen", EYE, args.output)
