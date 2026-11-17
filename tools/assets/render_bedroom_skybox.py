#!/usr/bin/env python3
"""Bake the original floor-level Plastic Platoon bedroom in Blender."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import area, bake, box, current_object, material, new_scene, parse_args, rod


EYE = (-0.37, -0.06, 0.082)
X_WALL = 2.78
Y_WALL = 2.42
CEILING = 2.78


def ellipsoid(name, center, radii, surface):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=center)
    obj = current_object(name, surface)
    obj.scale = radii
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def flat_shape(name, center, outline, normal, surface, thickness=0.012):
    up = Vector((0, 0, 1))
    right = up.cross(Vector(normal)).normalized()
    vertices = [Vector(center) + x * right + z * up for x, z in outline]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], [tuple(range(len(vertices)))])
    mesh.materials.append(surface)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    solid = obj.modifiers.new("Cutout thickness", "SOLIDIFY")
    solid.thickness = thickness
    return obj


def star(name, center, radius, normal, surface):
    outline = []
    for index in range(10):
        angle = math.pi / 2 + math.tau * index / 10
        r = radius if index % 2 == 0 else radius * 0.44
        outline.append((r * math.cos(angle), r * math.sin(angle)))
    return flat_shape(name, center, outline, normal, surface)


def crescent(name, center, scale, normal, surface):
    outline = [(0.55, 0.88), (0.04, 1), (-0.49, 0.87), (-0.87, 0.52), (-1, 0.02),
               (-0.85, -0.52), (-0.48, -0.88), (0.05, -1), (0.60, -0.77), (0.89, -0.38),
               (0.41, -0.51), (0.04, -0.35), (-0.14, -0.03), (-0.1, 0.36), (0.17, 0.70)]
    return flat_shape(name, center, [(x * scale, y * scale) for x, y in outline],
                      normal, surface, 0.026)


def room(m):
    box("Oatmeal carpet", (0, 0, -0.065), (5.77, 5.04, 0.13), m["carpet"])
    box("Cream ceiling", (0, 0, CEILING + 0.075), (5.77, 5.04, 0.15), m["ceiling"])
    for sign in (-1, 1):
        walls = (
            (sign * (X_WALL + 0.08), 0, 0.16, 5.04),
            (0, sign * (Y_WALL + 0.08), 5.77, 0.16),
        )
        for x, y, width, depth in walls:
            box("Powder blue wall", (x, y, CEILING / 2), (width, depth, CEILING), m["wall"])
            box("Cream wainscot", (x, y, 0.382), (width + 0.026, depth + 0.026, 0.766), m["lower"])
            box("Chair rail", (x, y, 0.777), (width + 0.054, depth + 0.054, 0.052), m["trim"], 0.011)
            box("Baseboard", (x, y, 0.061), (width + 0.061, depth + 0.061, 0.128), m["trim"], 0.012)
            box("Ceiling molding", (x, y, CEILING - 0.05),
                (width + 0.056, depth + 0.056, 0.107), m["trim"], 0.015)


def bed(m):
    wood = m["wood"]
    for x in (1.12, 2.56):
        box("Headboard post", (x, -1.96, 0.58), (0.125, 0.14, 1.16), wood, 0.027)
        box("Footboard post", (x, 0.37, 0.335), (0.125, 0.14, 0.67), wood, 0.022)
        box("Pine bed side rail", (x, -0.80, 0.314), (0.11, 2.24, 0.185), wood, 0.023)
    box("Painted headboard", (1.84, -1.96, 0.778), (1.50, 0.128, 0.64), m["teal"], 0.048)
    box("Headboard cap", (1.84, -1.96, 1.11), (1.66, 0.17, 0.095), wood, 0.026)
    star("Headboard star", (1.84, -1.883, 0.939), 0.113, (0, 1, 0), m["gold"])
    box("Painted footboard", (1.84, 0.37, 0.385), (1.50, 0.123, 0.45), m["teal"], 0.035)
    box("Footboard cap", (1.84, 0.37, 0.619), (1.65, 0.17, 0.085), wood, 0.024)
    box("Mattress", (1.84, -0.79, 0.51), (1.48, 2.16, 0.255), m["cream"], 0.077)
    box("Quilt", (1.82, -0.64, 0.647), (1.55, 1.82, 0.11), m["quilt_blue"], 0.05)
    box("Quilt hanging over the side", (1.053, -0.626, 0.524),
        (0.075, 1.83, 0.36), m["quilt_blue"], 0.027)
    patches = ("quilt_blue", "gold", "quilt_red", "cream", "teal")
    for col in range(6):
        y = -1.383 + col * 0.302
        for row in range(2):
            base = m[patches[(col + row * 2) % len(patches)]]
            box("Quilt patch on hanging side", (1.009, y, 0.437 + row * 0.169),
                (0.03, 0.296, 0.164), base, 0.014)
        for row in range(5):
            base = m[patches[(col + row * 2) % len(patches)]]
            box("Quilt patch on blanket", (1.203 + row * 0.306, y, 0.706),
                (0.300, 0.296, 0.032), base, 0.013)
    box("Quilt binding", (1.019, -0.63, 0.345), (0.056, 1.83, 0.043), m["cream"], 0.016)
    pillow = box("Pillow", (1.85, -1.59, 0.754), (1.19, 0.54, 0.225), m["cream"], 0.107)
    pillow.rotation_euler.z = 0.055
    box("Small coral cushion", (1.87, -1.735, 0.87), (0.49, 0.23, 0.38), m["quilt_red"], 0.108)
    for y, z, radius, surface in (
        (-1.34, 1.75, 0.23, "gold"), (-0.87, 1.50, 0.14, "cream"),
        (-0.60, 1.87, 0.108, "quilt_red"), (-0.33, 1.67, 0.19, "gold"),
    ):
        star("Painted wall star", (X_WALL - 0.017, y, z), radius, (-1, 0, 0), m[surface])


def curtains(m):
    for side in (-1, 1):
        vertices = []
        panels = 36
        for index in range(panels + 1):
            u = index / panels
            x = -0.58 + side * (0.65 + u * 0.55)
            fold = math.cos(u * math.tau * 4)
            y = -2.168 + 0.045 * fold
            hem = 1.02 + 0.016 * fold
            vertices.extend(((x + side * 0.044, y + 0.008, hem),
                             (x + side * 0.043, y + 0.008, hem + 0.085),
                             (x, y, 2.38)))
        faces = []
        for index in range(panels):
            a = 3 * index
            faces.extend(((a, a + 3, a + 4, a + 1), (a + 1, a + 4, a + 5, a + 2)))
        mesh = bpy.data.meshes.new("Pleated cotton curtain")
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(m["curtain"])
        mesh.materials.append(m["cream"])
        curtain = bpy.data.objects.new("Pleated cotton curtain", mesh)
        bpy.context.scene.collection.objects.link(curtain)
        for poly in mesh.polygons:
            poly.use_smooth = True
            poly.material_index = 1 if poly.index % 2 == 0 else 0


def window_and_toy_chest(m):
    x = -0.58
    box("Window casing", (x, -2.38, 1.753), (2.23, 0.12, 1.32), m["trim"], 0.028)
    for col in (-1, 1):
        for row in (-1, 1):
            box("Blue daylight pane", (x + col * 0.503, -2.303, 1.753 + row * 0.286),
                (0.94, 0.035, 0.513), m["sky"] if row == 1 else m["haze"], 0.013)
    box("Window center mullion", (x, -2.265, 1.752), (0.074, 0.085, 1.21), m["trim"], 0.013)
    box("Window meeting rail", (x, -2.264, 1.753), (2.07, 0.085, 0.081), m["trim"], 0.013)
    box("Window sill", (x, -2.31, 1.084), (2.32, 0.25, 0.101), m["trim"], 0.021)
    rod("Curtain rod", (-1.875, -2.167, 2.395), (0.715, -2.167, 2.395), 0.026, m["wood"])
    for px in (-1.88, 0.72):
        ellipsoid("Curtain rod finial", (px, -2.167, 2.395), (0.063, 0.057, 0.057), m["wood"])
    curtains(m)
    box("Toy chest", (-0.69, -2.054, 0.273), (1.38, 0.64, 0.535), m["gold"], 0.055)
    box("Rounded toy chest lid", (-0.69, -2.054, 0.556), (1.48, 0.71, 0.115), m["teal"], 0.048)
    box("Toy chest inset", (-0.69, -1.726, 0.277), (1.16, 0.047, 0.345), m["quilt_red"], 0.045)
    box("Toy chest pull", (-0.69, -1.683, 0.451), (0.25, 0.069, 0.063), m["gold"], 0.023)
    for px in (-1.03, -0.69, -0.35):
        star("Toy chest star decal", (px, -1.696, 0.265), 0.093, (0, 1, 0), m["cream"])


def teddy(m):
    x, y, z = -1.055, -1.993, 0.64
    bear, belly, eyes = m["bear"], m["cream"], m["ink"]
    ellipsoid("Teddy body", (x, y, z + 0.18), (0.167, 0.117, 0.216), bear)
    ellipsoid("Teddy belly", (x, y + 0.088, z + 0.155), (0.117, 0.041, 0.139), belly)
    ellipsoid("Teddy head", (x, y, z + 0.408), (0.158, 0.121, 0.137), bear)
    for side in (-1, 1):
        ellipsoid("Teddy ear", (x + side * 0.128, y, z + 0.513), (0.067, 0.049, 0.073), bear)
        ellipsoid("Teddy ear patch", (x + side * 0.128, y + 0.037, z + 0.513),
                  (0.04, 0.017, 0.045), belly)
        ellipsoid("Teddy leg", (x + side * 0.124, y + 0.068, z + 0.056), (0.081, 0.108, 0.075), bear)
        arm = ellipsoid("Teddy arm", (x + side * 0.152, y, z + 0.212), (0.061, 0.077, 0.12), bear)
        arm.rotation_euler.y = -side * 0.54
        ellipsoid("Teddy button eye", (x + side * 0.064, y + 0.111, z + 0.422),
                  (0.021, 0.018, 0.025), eyes)
    ellipsoid("Teddy muzzle", (x, y + 0.115, z + 0.371), (0.077, 0.042, 0.052), belly)
    ellipsoid("Teddy nose", (x, y + 0.147, z + 0.391), (0.03, 0.018, 0.02), eyes)


def books_and_desk(m):
    wood = m["wood"]
    for x in (-2.43, -1.2):
        box("Bookcase upright", (x, 2.133, 0.91), (0.082, 0.48, 1.82), wood, 0.015)
    box("Bookcase painted back", (-1.815, 2.353, 0.91), (1.21, 0.061, 1.77), m["teal"], 0.013)
    for z in (0.15, 0.61, 1.18, 1.77):
        box("Bookcase shelf", (-1.815, 2.133, z), (1.32, 0.49, 0.079), wood, 0.016)
    for z, books in (
        (0.65, ((-2.26, .33, "quilt_red"), (-2.11, .38, "gold"), (-1.96, .29, "cream"),
                (-1.65, .33, "quilt_blue"), (-1.49, .40, "quilt_red"), (-1.37, .31, "gold"))),
        (1.22, ((-2.26, .37, "cream"), (-2.1, .425, "quilt_blue"), (-1.96, .35, "teal"),
                (-1.63, .39, "gold"), (-1.49, .32, "quilt_blue"), (-1.36, .37, "quilt_red"))),
    ):
        for index, (x, height, color) in enumerate(books):
            y = 1.996 + 0.029 * (index % 3)
            box("Picture book", (x, y, z + height / 2), (0.133, 0.253, height), m[color], 0.015)
            box("Book spine band", (x, y - 0.128, z + 0.068), (0.086, 0.01, 0.019), m["cream"], 0.005)
    for x, color in ((-2.12, "teal"), (-1.536, "quilt_red")):
        box("Canvas storage basket", (x, 2.085, 0.375), (0.493, 0.39, 0.36), m[color], 0.042)
        box("Basket handle", (x, 1.883, 0.46), (0.16, 0.025, 0.057), m["cream"], 0.015)

    for x in (-0.606, 0.91):
        for y in (1.715, 2.285):
            box("Writing desk leg", (x, y, 0.366), (0.098, 0.098, 0.732), wood, 0.015)
    box("Writing desk top", (0.152, 2.002, 0.764), (1.63, 0.734, 0.13), wood, 0.031)
    box("Desk drawer", (0.588, 1.747, 0.635), (0.62, 0.47, 0.16), m["quilt_blue"], 0.026)
    box("Desk drawer pull", (0.588, 1.496, 0.626), (0.197, 0.046, 0.041), m["cream"], 0.011)
    for x in (-0.255, 0.15):
        for y in (1.02, 1.373):
            box("Small chair leg", (x, y, 0.218), (0.064, 0.064, 0.446), wood, 0.012)
        box("Small chair back post", (x, 1.017, 0.637), (0.062, 0.071, 0.43), wood, 0.012)
    box("Painted chair seat", (-0.052, 1.193, 0.468), (0.56, 0.49, 0.119), m["teal"], 0.041)
    box("Painted chair back", (-0.052, 1.013, 0.807), (0.57, 0.119, 0.23), m["teal"], 0.036)
    rod("Lamp base", (0.67, 2.049, 0.832), (0.67, 2.049, 0.878), 0.147, m["quilt_blue"])
    rod("Lamp stem", (0.67, 2.049, 0.864), (0.67, 2.049, 1.22), 0.034, m["quilt_blue"])
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.205, radius2=0.123,
                                   depth=0.24, location=(0.67, 2.049, 1.212))
    current_object("Ochre lamp shade", m["gold"])
    ellipsoid("Warm desk lamp diffuser", (0.67, 2.049, 1.086), (0.174, 0.174, 0.032), m["lamp"])
    area("Desk lamp pool", (0.67, 2.049, 1.04), (0.38, 1.68, 0.70),
         11, (1.0, 0.77, 0.56), 0.24, 0.24)

    print_x = 1.28
    box("Framed night sky print", (print_x, 2.377, 1.78), (0.87, 0.094, 0.89), wood, 0.022)
    box("Night blue print", (print_x, 2.318, 1.78), (0.756, 0.035, 0.774), m["night"], 0.009)
    crescent("Printed crescent", (print_x - 0.114, 2.297, 1.83), 0.217, (0, -1, 0), m["cream"])
    for dx, z, radius in ((0.202, 1.93, 0.077), (0.214, 1.68, 0.099), (-0.25, 1.552, 0.047)):
        star("Printed star", (print_x + dx, 2.297, z), radius, (0, -1, 0), m["gold"])


def door_and_dresser(m):
    box("Bedroom door casing", (-2.748, -1.386, 1.065), (0.137, 1.178, 2.13), m["trim"], 0.025)
    box("Cream bedroom door", (-2.655, -1.386, 1.026), (0.071, 1.006, 2.043), m["cream"], 0.021)
    for z, h in ((0.59, 0.75), (1.573, 0.79)):
        box("Raised door panel", (-2.612, -1.386, z), (0.044, 0.744, h), m["cream"], 0.036)
    ellipsoid("Door knob plate", (-2.575, -0.99, 0.994), (.022, .058, .091), m["wood"])
    ellipsoid("Round brass knob", (-2.526, -0.99, 0.994), (.063, .059, .059), m["gold"])
    box("Bedroom light switch", (-2.750, -0.566, 1.182), (0.04, 0.10, 0.153), m["trim"], 0.012)

    box("Blue dresser body", (-2.456, 0.772, 0.535), (0.60, 1.48, 0.97), m["quilt_blue"], 0.043)
    box("Dresser kickboard", (-2.474, 0.772, 0.057), (0.59, 1.36, 0.113), m["night"], 0.02)
    box("Dresser top", (-2.434, 0.772, 1.039), (0.672, 1.598, 0.121), m["wood"], 0.035)
    for z, color in ((0.274, "quilt_blue"), (0.566, "teal"), (0.858, "quilt_blue")):
        box("Wide dresser drawer", (-2.143, 0.772, z), (0.112, 1.345, 0.265), m[color], 0.029)
        for y in (0.42, 1.117):
            ellipsoid("Dresser knob", (-2.05, y, z), (0.045, 0.045, 0.045), m["wood"])
    for y, color in ((0.409, "quilt_red"), (0.829, "gold"), (1.234, "teal")):
        box("Wooden train chassis", (-2.265, y, 1.181), (0.216, 0.304, 0.09), m["wood"], 0.018)
        box("Wooden train body", (-2.265, y, 1.296), (0.204, 0.25, 0.161), m[color], 0.022)
        for dy in (-0.094, 0.094):
            rod("Train wheel axle", (-2.393, y + dy, 1.151), (-2.126, y + dy, 1.151), 0.057, m["ink"])
    rod("Locomotive chimney", (-2.266, 0.311, 1.344), (-2.266, 0.311, 1.447), 0.042, m["ink"])
    for y, z, radius, color in (
        (0.13, 1.82, .13, "gold"), (0.468, 2.011, .11, "cream"),
        (0.87, 1.795, .235, "quilt_red"), (1.338, 1.97, .153, "gold"),
    ):
        star("Wall star above train", (-2.758, y, z), radius, (1, 0, 0), m[color])


def ceiling_and_lighting(m):
    lamp = (-0.478, 0.38)
    rod("Ceiling fixture rim", (*lamp, CEILING - 0.09), (*lamp, CEILING), 0.28, m["wood"], 32)
    ellipsoid("Glowing ceiling dome", (*lamp, CEILING - 0.105), (0.251, 0.251, 0.115), m["lamp"])
    area("Ceiling lamp fill", (*lamp, 2.54), (-0.4, 0.38, 0), 68, (1.0, 0.83, 0.68), 0.47, 0.47)
    area("Window daylight", (-0.58, -2.22, 1.76), (0.4, 0.55, 0.85),
         148, (0.74, 0.86, 1.0), 1.72, 1.03)
    area("Wall bounce fill", (-0.35, 0.15, 1.64), (1.0, 0.1, 2.8),
         25, (0.94, 0.91, 1.0), 3.15, 2.4)
    area("Room fill", (0.06, 0.28, 2.24), (0.03, 0.1, 0.2),
         37, (1.0, 0.95, 0.85), 3.32, 2.92)

    x, y, z = 0.83, -0.67, 2.51
    rod("Mobile hanging thread", (x, y, CEILING), (x, y, z), 0.014, m["wood"])
    rod("Mobile crosspiece", (x - 0.47, y, z), (x + 0.47, y, z), 0.017, m["wood"])
    rod("Mobile crosspiece", (x, y - 0.34, z), (x, y + 0.34, z), 0.017, m["wood"])
    for dx, dy, height, radius, col in (
        (-0.45, 0, 2.27, .145, "quilt_red"), (0.44, 0, 2.12, .182, "gold"),
        (0, -0.32, 2.34, .116, "teal"), (0, 0.32, 2.26, .144, "cream"),
    ):
        rod("Star hanging thread", (x + dx, y + dy, z), (x + dx, y + dy, height + radius),
            0.009, m["wood"])
        star("Hanging mobile star", (x + dx, y + dy, height), radius, (-0.8, 0.56, 0), m[col])
    rod("Moon hanging thread", (x, y, z), (x, y, 2.181), 0.01, m["wood"])
    crescent("Hanging mobile crescent", (x, y, 1.995), 0.204, (-0.8, 0.56, 0), m["quilt_blue"])


def build_scene(samples):
    scene = new_scene(samples, bounces=4, exposure=0.19)
    scene.cycles.adaptive_threshold = 0.04
    coatings = {
        "wall": ("8cabc3", "96b1c5", 5),
        "lower": ("cec3a9", "dbcfb9", 6),
        "trim": ("e5dac2",),
        "ceiling": ("ded8c5",),
        "carpet": ("a39781", "b1a389", 20),
        "wood": ("bd9269", "c69c73", 4),
        "cream": ("efe0bd",),
        "quilt_blue": ("5c849b",),
        "quilt_red": ("bd705c",),
        "teal": ("589187",),
        "gold": ("cea254",),
        "curtain": ("bd776a", "c48678", 7),
        "bear": ("a57855",),
        "ink": ("404447",),
        "night": ("425870",),
    }
    m = {name: material(name, *settings) for name, settings in coatings.items()}
    m["sky"] = material("Cool upper window glass", "a8c8d9", glow=1.16)
    m["haze"] = material("Pale lower window glass", "c6dce0", glow=1.21)
    m["lamp"] = material("Warm opal diffuser", "f6deb0", glow=1.38)
    room(m)
    bed(m)
    window_and_toy_chest(m)
    teddy(m)
    books_and_desk(m)
    door_and_dresser(m)
    ceiling_and_lighting(m)
    return scene


if __name__ == "__main__":
    args = parse_args(__doc__, samples=28)
    bake(build_scene(args.samples), "pp_kids_bedroom", EYE, args.output)
