#!/usr/bin/env python3
"""Bake the original floor-level Plastic Platoon attic in Blender."""

import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import bake, beam, box, current_object, material, new_scene, parse_args, rod


EYE = (-0.24, -0.18, 0.09)
END = 3.2
EAVE = 2.35
EAVE_HEIGHT = 0.74
RIDGE_HEIGHT = 3.25


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def threads(name, paths, radius, mat):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    for path in paths:
        spline = curve.splines.new("POLY")
        spline.points.add(len(path) - 1)
        for point, coord in zip(spline.points, path):
            point.co = (*coord, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    curve.materials.append(mat)


def grain(name, dark, light, stretch, bump_strength):
    mat = material(name, dark, light, 1)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    stretch_grain = nodes.new("ShaderNodeVectorMath")
    stretch_grain.operation = "MULTIPLY"
    stretch_grain.inputs[1].default_value = stretch
    noise = nodes.get("Noise Texture")
    links.new(nodes.get("Texture Coordinate").outputs["Object"], stretch_grain.inputs[0])
    links.new(stretch_grain.outputs["Vector"], noise.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.002
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], nodes.get("Principled BSDF").inputs["Normal"])
    return mat


def attic_shell(m):
    box("Subfloor under plank seams", (0, 0, -0.064), (6.5, 4.8, 0.05), m["gap"])
    plank_width = 2 * EAVE / 23
    for row in range(23):
        y = -EAVE + (row + 0.5) * plank_width
        seam = (-1.27, -0.45, 0.52, 1.63, 0.02)[row % 5]
        for index, (left, right) in enumerate(((-END, seam), (seam, END))):
            board = m["floor"][(row + index * 2) % len(m["floor"])]
            box("Worn floorboard", ((left + right) / 2, y, -0.018),
                (right - left - 0.004, plank_width - 0.004, 0.036), board, 0.0015)

    for sign in (-1, 1):
        box("Low eave wall", (0, sign * EAVE, EAVE_HEIGHT / 2),
            (2 * END, 0.09, EAVE_HEIGHT), m["planks"])
        box("Eave sill", (0, sign * (EAVE - 0.06), 0.065),
            (2 * END, 0.10, 0.13), m["timber"], 0.008)
        eave = Vector((0, sign * EAVE, EAVE_HEIGHT))
        ridge = Vector((0, 0, RIDGE_HEIGHT))
        pitch = ridge - eave
        rotation = pitch.to_track_quat("Z", "Y").to_euler()
        for course in range(14):
            center = eave + pitch * ((course + 0.5) / 14)
            box("Roof sheathing board", center, (2 * END, 0.07, pitch.length / 14 - 0.008),
                m["roof"][course % len(m["roof"])], 0.003).rotation_euler = rotation
        for x in (-2.89, -2.03, -1.13, -0.26, 0.63, 1.54, 2.43, 3.10):
            beam("Exposed rafter", (x, sign * (EAVE - 0.05), EAVE_HEIGHT - 0.09),
                 (x, 0, RIDGE_HEIGHT - 0.12), 0.10, 0.16, m["timber"], 0.007)
            box("Knee wall stud", (x, sign * (EAVE - 0.08), EAVE_HEIGHT / 2),
                (0.09, 0.12, EAVE_HEIGHT), m["timber"], 0.006)
    box("Ridge beam", (0, 0, RIDGE_HEIGHT - 0.08), (2 * END, 0.14, 0.20), m["timber"], 0.009)
    for x in (-2.03, -0.26, 1.54):
        box("Collar tie", (x, 0, 2.13), (0.13, 2.18, 0.16), m["timber"], 0.009)

    for sign in (-1, 1):
        x = sign * END
        mesh_object("Gable backing", [(x, -EAVE, 0), (x, EAVE, 0), (x, EAVE, EAVE_HEIGHT),
                                      (x, 0, RIDGE_HEIGHT), (x, -EAVE, EAVE_HEIGHT)],
                    [(0, 1, 2, 3, 4)], m["gap"])
        for i in range(23):
            y = -EAVE + (i + 0.5) * plank_width
            top = RIDGE_HEIGHT - (abs(y) + plank_width / 2) / EAVE * (RIDGE_HEIGHT - EAVE_HEIGHT)
            box("Vertical gable board", (x - sign * 0.025, y, top / 2),
                (0.042, plank_width - 0.005, top), m["planks"], 0.002)
        for y in (-1.64, -0.85, 0, 0.85, 1.64):
            top = RIDGE_HEIGHT - abs(y) / EAVE * (RIDGE_HEIGHT - EAVE_HEIGHT) - 0.09
            box("Gable stud", (x - sign * 0.10, y, top / 2), (0.12, 0.09, top), m["timber"], 0.005)

    # The boarded gable window stays dark so the hanging bulb lights the room.
    box("Boarded window frame", (3.02, -0.19, 1.67), (0.15, 0.89, 0.88), m["frame"], 0.02)
    box("Dark window recess", (2.934, -0.19, 1.67), (0.031, 0.72, 0.70), m["gap"], 0.01)
    for z, angle in ((1.44, -0.09), (1.65, 0.13), (1.88, -0.12)):
        board = box("Weathered window board", (2.896, -0.19, z),
                    (0.039, 0.80, 0.18), m["planks"], 0.01)
        board.rotation_euler.x = angle


def carton(m, position, size, angle, shade):
    x, y, z = position
    width, depth, height = size
    cosine, sine = math.cos(angle), math.sin(angle)

    def part(name, offset, dimensions, mat, bevel=0.004):
        dx, dy, dz = offset
        obj = box(name, (x + cosine * dx - sine * dy, y + sine * dx + cosine * dy, z + dz),
                  dimensions, mat, bevel)
        obj.rotation_euler.z = angle

    part("Cardboard moving box", (0, 0, height / 2), size, m["cardboard"][shade], 0.012)
    part("Top flap crease", (0, 0, height + 0.001), (width - 0.009, 0.009, 0.003), m["gap"])
    for dx in (-width * 0.26, width * 0.26):
        part("Packing tape across flaps", (dx, 0, height + 0.004), (0.062, depth, 0.004), m["tape"])
        part("Packing tape folded over edge", (dx, -depth / 2 - 0.001, height - 0.037),
             (0.062, 0.004, 0.075), m["tape"])
    part("Faded paper label", (-width * 0.07, -depth / 2 - 0.002, height * 0.62),
         (width * 0.34, 0.005, height * 0.20), m["paper"])
    for offset, length in ((0.026, 0.13), (-0.005, 0.093)):
        part("Faded ink on label", (-width * 0.07, -depth / 2 - 0.005, height * 0.62 + offset),
             (width * length, 0.002, 0.005), m["ink"], 0)


def dresser(m):
    wood = m["walnut"]
    y = 0.76
    for x in (2.20, 2.76):
        for dy in (-0.51, 0.51):
            rod("Turned dresser foot", (x, y + dy, 0.02), (x, y + dy, 0.22), 0.066, wood)
    box("Dresser carcass", (2.48, y, 0.68), (0.61, 1.22, 1.02), wood, 0.026)
    box("Dresser top with overhang", (2.48, y, 1.22), (0.71, 1.36, 0.092), m["frame"], 0.025)
    box("Dresser moulding", (2.48, y, 0.216), (0.66, 1.28, 0.075), m["frame"], 0.018)
    for z in (0.39, 0.69, 0.99):
        box("Drawer front", (2.143, y, z), (0.067, 1.13, 0.26), m["panel"], 0.019)
        for dy in (-0.32, 0.32):
            for side in (-1, 1):
                rod("Brass pull mount", (2.107, y + dy + side * 0.058, z + 0.024),
                    (2.068, y + dy + side * 0.058, z + 0.024), 0.018, m["brass"])
            arc = [(2.067, y + dy + 0.059 * math.cos(math.pi * i / 12),
                    z + 0.024 - 0.05 * math.sin(math.pi * i / 12)) for i in range(13)]
            threads("Bail drawer pull", [arc], 0.010, m["brass"])
    carton(m, (2.49, 0.84, 1.266), (0.44, 0.35, 0.28), -math.pi / 2, 1)


def covered_chair(m):
    x, y = 0.54, -1.78
    for dx in (-0.24, 0.24):
        for dy in (-0.23, 0.23):
            rod("Spare chair leg", (x + dx * 1.15, y + dy, 0.01),
                (x + dx, y + dy, 0.50), 0.036, m["walnut"])
    box("Spare chair seat", (x, y, 0.47), (0.53, 0.51, 0.10), m["walnut"], 0.032)

    # Run the sheet over the high back, across the seat, and down in front.
    vertices, faces = [], []
    for row in range(21):
        t = row / 20
        for col in range(25):
            u = col / 24
            dx = (u - 0.5) * 0.71
            fold = math.cos(u * math.tau * 5) * 0.023 + math.sin(u * math.tau * 8) * 0.008
            if t <= 0.32:
                v = t / 0.32
                dy = -0.30 + 0.11 * v
                z = 0.15 + 0.99 * math.sin(v * math.pi / 2)
            elif t <= 0.67:
                v = (t - 0.32) / 0.35
                dy = -0.19 + 0.48 * v
                z = 1.14 - 0.59 * math.sin(v * math.pi / 2) ** 0.8
            else:
                v = (t - 0.67) / 0.33
                dy = 0.29 + 0.07 * v
                z = 0.55 - (0.39 + 0.11 * math.sin(u * math.pi)) * v
            edge_drop = abs(2 * u - 1) ** 8 * (0.16 + 0.18 * math.sin(t * math.pi))
            vertices.append((x + dx, y + dy + fold * abs(2 * t - 1), max(0.035, z + fold - edge_drop)))
            if row and col:
                i = row * 25 + col
                faces.append((i - 26, i - 25, i, i - 1))
    sheet = mesh_object("Dust sheet over spare chair", vertices, faces, m["linen"])
    for polygon in sheet.data.polygons:
        polygon.use_smooth = True
    sheet.modifiers.new("Relaxed folds", "SUBSURF").levels = 2
    sheet.modifiers.new("Sheet thickness", "SOLIDIFY").thickness = 0.004


def steamer_trunk(m):
    x, y = -1.29, -1.60
    width, depth = 1.10, 0.61
    box("Faded steamer trunk body", (x, y, 0.245), (width, depth, 0.44), m["leather"], 0.036)
    vertices, faces = [], []
    for sx in (-1, 1):
        for i in range(17):
            angle = math.pi * i / 16
            vertices.append((x + sx * width / 2, y + depth / 2 * math.cos(angle),
                             0.44 + 0.18 * math.sin(angle)))
    faces.extend((i, i + 1, i + 18, i + 17) for i in range(16))
    faces.extend((tuple(reversed(range(17))), tuple(range(17, 34))))
    lid = mesh_object("Domed trunk lid", vertices, faces, m["leather"])
    for polygon in list(lid.data.polygons)[:16]:
        polygon.use_smooth = True

    for dx in (-0.39, 0.39):
        box("Trunk edge band", (x + dx, y + 0.30, 0.25), (0.069, 0.04, 0.44), m["frame"], 0.009)
        path = [(x + dx, y + 0.311 * math.cos(math.pi * i / 20),
                 0.44 + 0.187 * math.sin(math.pi * i / 20)) for i in range(21)]
        threads("Trunk lid strap", [path], 0.025, m["frame"])
        for z in (0.11, 0.35, 0.45):
            rod("Brass trunk rivet", (x + dx, y + 0.314, z), (x + dx, y + 0.328, z), 0.018, m["brass"])
    box("Trunk lock plate", (x, y + 0.312, 0.433), (0.13, 0.039, 0.15), m["brass"], 0.014)
    box("Trunk keyhole", (x, y + 0.333, 0.416), (0.018, 0.005, 0.035), m["gap"], 0.004)
    box("Old luggage sticker", (x + 0.20, y + 0.308, 0.27), (0.20, 0.006, 0.10),
        m["paper"], 0.009).rotation_euler.y = -0.17


def storage(m):
    for position, size, angle, shade in (
        ((-0.93, 1.21, 0), (0.92, 0.73, 0.66), -0.10, 0),
        ((-0.96, 1.24, 0.66), (0.69, 0.55, 0.46), 0.12, 1),
        ((0.09, 1.57, 0), (0.87, 0.62, 0.54), 0.09, 2),
        ((0.96, 1.54, 0), (0.57, 0.48, 0.44), -0.19, 0),
        ((1.18, 0.87, 0), (0.50, 0.41, 0.34), -0.71, 1),
        ((-2.39, -1.34, 0), (0.69, 0.59, 0.47), 1.72, 2),
    ):
        carton(m, position, size, angle, shade)

    for x in (-3.02, -2.50):
        for y in (-0.71, 0.64):
            box("Rough shelving upright", (x, y, 0.94), (0.085, 0.091, 1.88), m["timber"], 0.009)
    for z in (0.15, 0.69, 1.26, 1.83):
        box("Rough shelf board", (-2.77, -0.035, z), (0.61, 1.45, 0.065), m["planks"], 0.01)
    carton(m, (-2.74, 0.27, 0.183), (0.51, 0.42, 0.37), math.pi / 2, 1)
    carton(m, (-2.75, -0.28, 0.723), (0.57, 0.41, 0.36), math.pi / 2, 0)
    rng = random.Random(19)
    for i in range(10):
        height = rng.uniform(0.20, 0.36)
        y = -0.50 + i * 0.073
        z = 1.293 + height / 2
        box("Book spine", (-2.61, y, z), (0.075, 0.056, height), m["books"][i % 3], 0.008)
        box("Yellowed book pages", (-2.74, y, z), (0.23, 0.05, height - 0.022), m["paper"], 0.004)
        for height_offset in (-0.06, 0.057):
            box("Faded gilt spine rule", (-2.572, y, z + height_offset),
                (0.003, 0.041, 0.008), m["brass"], 0.001)


def cobweb(m, center, anchors, seed):
    rng = random.Random(seed)
    hub = Vector(center)
    anchors = [Vector(anchor) for anchor in anchors]
    lines = [[hub, anchor] for anchor in anchors]
    for fraction in (0.19, 0.32, 0.47, 0.64, 0.81):
        ring = [hub.lerp(anchor, fraction + rng.uniform(-0.045, 0.045)) for anchor in anchors]
        for start, end in zip(ring, ring[1:]):
            midpoint = start.lerp(end, 0.5) - Vector((0, 0, 0.019 * fraction))
            lines.append([start, midpoint, end])
    threads("Cobweb anchor threads", lines[:len(anchors)], 0.0028, m["web"])
    threads("Sagging cobweb spiral", lines[len(anchors):], 0.0017, m["web"])


def details(m):
    cobweb(m, (1.55, -0.87, 1.72),
           [(1.55, -1.49, 1.57), (1.55, -1.23, 1.83), (1.55, -0.94, 2.09),
            (1.55, -0.60, 2.08), (1.55, -0.29, 2.07), (1.50, -0.32, 1.53)], 14)
    cobweb(m, (-1.37, -1.26, 0.56),
           [(-1.79, -1.33, 0.45), (-1.66, -1.42, 0.55), (-1.48, -1.42, 0.62),
            (-1.26, -1.45, 0.61), (-1.06, -1.37, 0.57), (-0.77, -1.30, 0.44)], 27)
    cobweb(m, (-1.36, 0.78, 0.46),
           [(-1.60, 0.54, 0.025), (-1.47, 0.89, 0.21), (-1.37, 0.88, 0.47),
            (-1.37, 0.90, 0.65), (-1.05, 0.86, 0.65), (-0.82, 0.82, 0.66)], 3)

    for cx, cy, angle in ((0.59, -0.77, 0.23), (-1.40, 0.41, -0.30), (-1.34, 0.48, 0.16)):
        box("Discarded sheet of paper", (cx, cy, 0.004), (0.23, 0.17, 0.005),
            m["paper"], 0.002).rotation_euler.z = angle


def hanging_bulb(scene, m):
    x, y, z = (-0.26, -0.64, 1.81)
    rod("Cloth-covered electrical cord", (x, y, 2.11), (x, y, z + 0.11), 0.009, m["gap"])
    rod("Bakelite light socket", (x, y, z + 0.041), (x, y, z + 0.121), 0.030, m["gap"])
    neck = rod("Frosted bulb neck", (x, y, z + 0.015), (x, y, z + 0.048), 0.025, m["bulb"])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=(x, y, z))
    globe = current_object("Bare incandescent bulb", m["bulb"])
    globe.scale = (0.039, 0.039, 0.050)
    for polygon in globe.data.polygons:
        polygon.use_smooth = True
    # The point represents the light from the same visible bulb.
    for part in (globe, neck):
        part.visible_diffuse = False
        part.visible_shadow = False
    light = bpy.data.lights.new("Incandescent bulb light", "POINT")
    light.energy = 120
    light.color = (1.0, 0.76, 0.48)
    light.shadow_soft_size = 0.045
    obj = bpy.data.objects.new("Incandescent bulb light", light)
    scene.collection.objects.link(obj)
    obj.location = (x, y, z)


def build_scene(samples):
    scene = new_scene(samples, exposure=0.28)
    surfaces = {
        "gap": ("28201a",),
        "paper": ("b8a280", "d2bc94", 18),
        "ink": ("655649",),
        "tape": ("a17a47", "b99256", 21),
        "brass": ("997143", "b5915e", 27),
        "linen": ("a8a197", "c8bca4", 22),
        "leather": ("2e4039", "52675b", 17),
        "web": ("b4afa1",),
        "timber": ("75533a", "aa8055", 10),
    }
    m = {name: material(name, *settings) for name, settings in surfaces.items()}
    m["bulb"] = material("Incandescent glass", "ffe1a8", glow=11)
    m["floor"] = [grain(f"Floorboard tone {i}", dark, light, (2.5, 74, 25), 0.28)
                  for i, (dark, light) in enumerate((("6d5038", "a68157"), ("674a34", "98754d"),
                                                    ("77563a", "ad875d"), ("654832", "906b49")))]
    m["roof"] = [grain(f"Roof board tone {i}", dark, light, (3, 42, 56), 0.23)
                 for i, (dark, light) in enumerate((("654a34", "9e754f"), ("523a2a", "886440"),
                                                   ("745237", "a77d53")))]
    m["planks"] = grain("Old pine boards", "604530", "9e7550", (25, 49, 3), 0.20)
    m["walnut"] = grain("Worn walnut veneer", "38231c", "77503a", (14, 3, 51), 0.16)
    m["panel"] = grain("Drawer veneer", "4b2c20", "905f40", (47, 3, 44), 0.18)
    m["frame"] = material("Dark stained hardwood", "553528", "82563a", 12)
    m["cardboard"] = [material(f"Cardboard tone {i}", dark, light, 16)
                      for i, (dark, light) in enumerate((("91714b", "b79061"), ("a48158", "c39c69"),
                                                        ("7e6247", "ab885e")))]
    m["books"] = [material(f"Worn bookcloth {i}", color)
                  for i, color in enumerate(("7a4637", "525b4a", "485664"))]
    attic_shell(m)
    dresser(m)
    covered_chair(m)
    steamer_trunk(m)
    storage(m)
    details(m)
    hanging_bulb(scene, m)
    return scene


def main():
    args = parse_args(__doc__, samples=64)
    bake(build_scene(args.samples), "pp_attic", EYE, args.output)


if __name__ == "__main__":
    main()
