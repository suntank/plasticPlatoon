#!/usr/bin/env python3
"""Render the original Plastic Platoon garage cubemap with Blender.

blender -b -t 8 --python-exit-code 1 --python tools/assets/render_garage_skybox.py
"""

import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import area, bake, beam, box, current_object, material, new_scene, parse_args, rod


EYE = (-0.42, 0.13, 0.095)


def ring(name, center, radius, thickness, mat, vertical=False, sides=24):
    bpy.ops.mesh.primitive_torus_add(
        location=center, major_radius=radius, minor_radius=thickness,
        major_segments=sides, minor_segments=8,
    )
    obj = current_object(name, mat)
    if vertical:
        obj.rotation_euler.y = math.pi / 2
    return obj


def shell(m):
    plaster, base, trim, pine, decking, slab, joint = (
        m[k] for k in ("plaster", "base", "trim", "pine", "decking", "slab", "joint")
    )
    box("Concrete slab", (0, 0, -0.1), (7.8, 6.8, 0.2), slab)
    for x in (-2.1, 2.05):
        box("Slab control joint", (x, 0, 0.0002), (0.007, 6.7, 0.0004), joint)
    box("Transverse control joint", (0, -1.61, 0.0003), (7.7, 0.007, 0.0004), joint)
    for sign in (-1, 1):
        for x, y, xy in ((sign * 3.8, 0, (0.22, 6.84)), (0, sign * 3.3, (7.8, 0.22))):
            box("Painted wall", (x, y, 1.5), (*xy, 3.0), plaster)
            box("Sage wainscot", (x, y, 0.51), (xy[0] + 0.025, xy[1] + 0.025, 1.02), base)
            box("Wall cap", (x, y, 1.025), (xy[0] + 0.048, xy[1] + 0.048, 0.044), trim, 0.01)
            box("Skirting board", (x, y, 0.064), (xy[0] + 0.052, xy[1] + 0.052, 0.128), trim, 0.008)
        # Fill the triangular gable above each end wall.
        x = sign * 3.687
        mesh = bpy.data.meshes.new("Gable")
        mesh.from_pydata([(x, -3.43, 2.78), (x, 3.43, 2.78), (x, 0, 4.10)], [], [(0, 1, 2)])
        gable = bpy.data.objects.new("Gable", mesh)
        bpy.context.scene.collection.objects.link(gable)
        mesh.materials.append(plaster)
        eave = (0, sign * 3.37, 2.89)
        direction = Vector((0, 0, 4.035)) - Vector(eave)
        panel = box("Sloped roof lining", Vector(eave) + direction / 2,
                    (7.79, 0.11, direction.length + 0.02), decking)
        panel.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    for x in (-3.48, -2.35, -1.18, 0, 1.18, 2.35, 3.48):
        box("Ceiling tie", (x, 0, 2.735), (0.145, 6.53, 0.19), pine, 0.013)
        box("King post", (x, 0, 3.25), (0.12, 0.135, 1.07), pine, 0.01)
        for sign in (-1, 1):
            beam("Rafter", (x, 0, 3.922), (x, sign * 3.24, 2.81), 0.12, 0.15, pine, 0.012)
            beam("Truss brace", (x, 0, 3.12), (x, sign * 1.48, 2.82), 0.105, 0.11, pine, 0.01)
    box("Ridge beam", (0, 0, 3.935), (7.58, 0.15, 0.18), pine, 0.011)


def garage_door(m):
    steel, blue, seam, glass = (m[k] for k in ("steel", "blue", "shadow", "glass"))
    box("Overhead door jamb", (3.648, 0, 1.223), (0.15, 5.24, 2.46), steel, 0.035)
    for index in range(5):
        z = 0.27 + index * 0.456
        box("Sectional door panel", (3.54, 0, z), (0.09, 4.97, 0.445), blue, 0.023)
        for y in (-1.86, -0.62, 0.62, 1.86):
            if index == 4:
                box("Window gasket", (3.48, y, z), (0.056, 1.02, 0.28), seam, 0.038)
                box("Frosted door window", (3.445, y, z), (0.031, 0.934, 0.211), glass, 0.027)
                area("Door window fill", (3.403, y, z), (0, y * 0.35, 0.45),
                     22, (0.57, 0.77, 1.0), 0.88, 0.18)
            else:
                box("Raised door stamping", (3.487, y, z), (0.04, 1.072, 0.292), blue, 0.031)
    box("Rubber threshold", (3.485, 0, 0.034), (0.075, 4.99, 0.062), seam, 0.012)
    for y in (-2.52, 2.52):
        path = [(3.49, y, 0.08), (3.49, y, 1.99), (3.45, y, 2.14),
                (3.34, y, 2.27), (3.16, y, 2.36), (-0.62, y, 2.36)]
        for start, end in zip(path, path[1:]):
            beam("Sectional door track", start, end, 0.065, 0.11, steel, 0.009)
        for x in (-0.02, 2.32):
            beam("Door track hanger", (x, y, 2.35), (x, y, 2.77), 0.04, 0.027, steel, 0.005)
    box("Opener rail", (1.18, 0, 2.54), (4.55, 0.085, 0.078), steel, 0.01)
    box("Opener motor", (-1.05, 0, 2.49), (0.58, 0.42, 0.22), m["sage"], 0.045)
    box("Opener lens", (-1.07, 0, 2.367), (0.35, 0.27, 0.048), m["diffuser"], 0.02)
    rod("Emergency release cord", (1.4, 0, 2.5), (1.4, 0, 1.9), 0.012, m["rope"])
    box("Emergency release grip", (1.4, 0, 1.86), (0.16, 0.068, 0.063), m["red"], 0.019)


def workbench(m):
    wood, steel, red, shadow = (m[k] for k in ("pine", "steel", "red", "shadow"))
    for x in (-2.4, 0.96):
        for y in (-3.06, -2.45):
            box("Workbench leg", (x, y, 0.49), (0.14, 0.14, 0.98), wood, 0.016)
    box("Workbench stretcher", (-0.72, -2.48, 0.27), (3.4, 0.12, 0.13), wood, 0.012)
    box("Workbench top", (-0.72, -2.76, 1.01), (3.84, 0.9, 0.17), wood, 0.035)
    box("Pegboard", (-0.71, -3.14, 1.73), (3.56, 0.13, 1.18), m["pegboard"], 0.025)
    # The board's pin holes are one mesh so the pattern stays cheap to render.
    vertices, quads = [], []
    for i in range(31):
        for j in range(10):
            x, z = -2.355 + i * 0.109, 1.243 + j * 0.105
            quads.append(tuple(range(len(vertices), len(vertices) + 4)))
            vertices.extend((x + dx, -3.074, z + dz) for dx, dz in
                            ((-0.011, -0.011), (0.011, -0.011), (0.011, 0.011), (-0.011, 0.011)))
    mesh = bpy.data.meshes.new("Pegboard holes")
    mesh.from_pydata(vertices, [], quads)
    dots = bpy.data.objects.new("Pegboard holes", mesh)
    bpy.context.scene.collection.objects.link(dots)
    mesh.materials.append(m["holes"])

    for x, length in ((-2.08, 0.36), (-1.84, 0.30), (-1.62, 0.26)):
        rod("Combination wrench shaft", (x, -3.032, 1.88 - length), (x, -3.032, 1.88), 0.027, steel)
        head = ring("Wrench ring", (x, -3.029, 1.92), 0.044, 0.017, steel, sides=12)
        head.rotation_euler.x = math.pi / 2
    rod("Hammer handle", (-1.11, -3.02, 1.57), (-0.98, -3.02, 1.96), 0.038, wood)
    box("Hammer head", (-0.99, -3.011, 2.005), (0.32, 0.091, 0.115), steel, 0.016)
    for x, grip in ((-0.51, m["red"]), (-0.31, m["sage"])):
        rod("Screwdriver", (x, -3.015, 1.59), (x, -3.015, 1.87), 0.018, steel)
        rod("Screwdriver grip", (x, -3.015, 1.81), (x, -3.015, 1.995), 0.041, grip, 8)
    box("Tool chest body", (0.52, -2.84, 1.36), (0.85, 0.53, 0.54), red, 0.04)
    box("Tool chest top", (0.52, -2.84, 1.64), (0.9, 0.57, 0.09), red, 0.022)
    for z in (1.22, 1.34, 1.46, 1.56):
        box("Drawer gap", (0.52, -2.575, z), (0.77, 0.018, 0.024), shadow, 0.006)
        box("Drawer pull", (0.52, -2.551, z + 0.028), (0.42, 0.029, 0.027), steel, 0.007)
    box("Vise base", (-2.13, -2.39, 1.126), (0.36, 0.27, 0.072), steel, 0.022)
    box("Vise body", (-2.13, -2.39, 1.253), (0.24, 0.23, 0.23), m["blue"], 0.035)
    for y in (-2.51, -2.32):
        box("Vise jaw", (-2.13, y, 1.385), (0.28, 0.086, 0.083), steel, 0.009)
    rod("Vise handle", (-2.26, -2.247, 1.13), (-1.96, -2.247, 1.22), 0.018, steel)
    box("Under-bench utility crate", (-0.53, -2.84, 0.255), (0.98, 0.62, 0.51), m["sage"], 0.024)
    box("Crate grip", (-0.53, -2.523, 0.417), (0.31, 0.025, 0.069), shadow, 0.012)


def storage(m):
    steel, wood, carton, tape = (m[k] for k in ("steel", "pine", "carton", "tape"))
    for x in (-2.84, -1.14, 0.55):
        for y in (2.54, 3.14):
            box("Storage rack upright", (x, y, 1.26), (0.085, 0.085, 2.52), steel, 0.009)
    for z in (0.22, 0.9, 1.56, 2.25):
        box("Storage rack shelf", (-1.145, 2.84, z), (3.51, 0.74, 0.085), wood, 0.012)
    rng = random.Random(12)
    for x, z, w, h in ((-2.38, 1.56, 0.65, 0.43), (-1.6, 1.56, 0.61, 0.48),
                       (-0.67, 0.9, 0.66, 0.52), (0.02, 2.25, 0.79, 0.42),
                       (-2.32, 2.25, 0.75, 0.31), (-1.95, 0.22, 0.54, 0.43)):
        depth = rng.uniform(0.42, 0.52)
        center = (x, 2.85, z + 0.043 + h / 2)
        angle = rng.uniform(-0.09, 0.09)
        box("Cardboard carton", center, (w, depth, h), carton, 0.017).rotation_euler.z = angle
        box("Packing tape", (x, 2.85, z + h + 0.045),
            (0.11, depth - 0.01, 0.006), tape).rotation_euler.z = angle
        stamp = box("Paper label", (0, 0, 0), (w * 0.37, 0.006, 0.1), m["paper"], 0.006)
        label_offset = Vector((-w * 0.17, -depth / 2 - 0.004, 0.02))
        stamp.location = Vector(center) + Matrix.Rotation(angle, 3, "Z") @ label_offset
        stamp.rotation_euler.z = angle
    for x, z, w, h, mat in ((-2.27, 0.90, 0.96, 0.40, m["sage"]),
                             (-0.22, 1.56, 0.94, 0.42, m["blue"]),
                             (-0.42, 0.22, 1.13, 0.48, m["sage"])):
        box("Storage tote", (x, 2.84, z + 0.041 + h / 2), (w, 0.56, h), mat, 0.043)
        box("Tote lid", (x, 2.84, z + h + 0.049), (w + 0.05, 0.60, 0.079), mat, 0.024)
        box("Tote latch", (x, 2.535, z + h - 0.006), (0.18, 0.055, 0.091), steel, 0.013)
    x = 2.13
    for dx in (-0.293, 0.293):
        beam("Ladder rail", (x + dx, 2.57, 0.03), (x + dx, 3.11, 2.48),
             0.086, 0.10, m["ladder"], 0.014)
        box("Ladder foot", (x + dx, 2.58, 0.055), (0.119, 0.13, 0.102), steel, 0.014)
    for z in (0.3, 0.61, 0.92, 1.23, 1.54, 1.85, 2.16):
        box("Ladder rung", (x, 2.57 + z * 0.22, z), (0.59, 0.105, 0.066), steel, 0.011)
    box("Ladder top cap", (x, 3.101, 2.483), (0.73, 0.17, 0.10), steel, 0.025)


def service_wall(m):
    dark, teal, trim = (m[k] for k in ("shadow", "sage", "paper"))
    box("Service door casing", (-3.597, 1.63, 1.098), (0.19, 1.29, 2.20), trim, 0.024)
    box("Service door", (-3.484, 1.63, 1.06), (0.076, 1.08, 2.105), teal, 0.019)
    for z, h in ((0.57, 0.77), (1.49, 0.83)):
        box("Service door panel", (-3.436, 1.63, z), (0.038, 0.81, h), teal, 0.039)
    rod("Door handle spindle", (-3.448, 1.23, 1.025), (-3.366, 1.23, 1.025), 0.037, m["steel"])
    rod("Door lever", (-3.365, 1.23, 1.025), (-3.365, 1.43, 1.025), 0.023, m["steel"])
    box("Switch plate", (-3.55, 0.73, 1.24), (0.049, 0.111, 0.16), trim, 0.012)
    box("Light switch", (-3.517, 0.73, 1.24), (0.026, 0.043, 0.086), dark, 0.008)

    x = -3.366
    for y in (-2.35, -0.98):
        ring("Bicycle tire", (x, y, 1.50), 0.355, 0.046, dark, vertical=True)
        ring("Bicycle rim", (x, y, 1.50), 0.302, 0.019, m["steel"], vertical=True)
        for i in range(12):
            angle = math.tau * i / 12
            edge = (x, y + 0.3 * math.cos(angle), 1.50 + 0.3 * math.sin(angle))
            rod("Bicycle spoke", (x, y, 1.50), edge, 0.005, m["steel"], 6)
    rear, front = (x, -2.35, 1.50), (x, -0.98, 1.50)
    seat, crank, head = (x, -1.97, 2.01), (x, -1.73, 1.54), (x, -1.22, 2.03)
    for start, end in ((rear, seat), (seat, crank), (crank, rear), (seat, head), (head, crank), (head, front)):
        rod("Bicycle frame", start, end, 0.028, m["bicycle"])
    rod("Bicycle seat post", seat, (x, -2.034, 2.16), 0.022, m["steel"])
    box("Bicycle saddle", (x, -2.056, 2.17), (0.17, 0.23, 0.071), dark, 0.027)
    rod("Bicycle stem", head, (x, -1.275, 2.227), 0.023, m["steel"])
    rod("Bicycle handlebar", (x - 0.21, -1.278, 2.224), (x + 0.24, -1.278, 2.224), 0.026, dark)
    rod("Bicycle crank axle", (x - 0.135, -1.73, 1.54), (x + 0.16, -1.73, 1.54), 0.072, dark)
    beam("Wall hanger", (-3.684, -1.74, 2.038), (x + 0.071, -1.74, 2.038), 0.064, 0.056, dark, 0.009)


def lighting(m):
    for x, y in ((-1.78, -1.17), (1.77, 1.16)):
        for dx in (-0.57, 0.57):
            rod("Pendant mounting stem", (x + dx, y, 2.76), (x + dx, y, 2.65), 0.023, m["steel"])
        box("Shop light housing", (x, y, 2.635), (1.56, 0.35, 0.138), m["steel"], 0.032)
        for dy in (-0.083, 0.083):
            box("Shop light diffuser", (x, y + dy, 2.554),
                (1.43, 0.112, 0.059), m["diffuser"], 0.023)
        area("Shop light", (x, y, 2.517), (x, y, 0), 125, (1.0, 0.86, 0.68), 1.43, 0.29)
    area("Ceiling bounce", (0, 0.4, 1.37), (0, 0, 3.44), 30, (0.85, 0.89, 1.0), 4.5, 3.2)
    area("Workbench fill", (-0.8, -1.37, 2.45), (-0.8, -3.24, 1.3),
         27, (1.0, 0.88, 0.71), 2.1, 0.6)
    area("Overhead ambient fill", (0.69, 0.1, 2.22), (0.69, 0.1, 0),
         43, (0.82, 0.9, 1.0), 4.2, 2.2)


def build_scene(samples):
    scene = new_scene(samples)
    surfaces = {
        "plaster": ("c1b8a3", "c9c1ad", 7),
        "base": ("79877e", "839286", 8),
        "trim": ("727970",),
        "pine": ("ae855a", "bc9569", 4),
        "decking": ("9c7854", "ad8961", 8),
        "slab": ("777b76", "8e8f83", 4),
        "joint": ("707570",),
        "blue": ("8a9da3",),
        "steel": ("59666a",),
        "shadow": ("343e3c",),
        "sage": ("617d73",),
        "red": ("a85039",),
        "rope": ("b89d6f",),
        "pegboard": ("a88967", "b79a76", 8),
        "holes": ("705940",),
        "carton": ("aa8b62", "b79c75", 9),
        "tape": ("d0ad78",),
        "paper": ("c8c2ad",),
        "ladder": ("af8240",),
        "bicycle": ("477c79",),
    }
    m = {name: material(name, *settings) for name, settings in surfaces.items()}
    m["glass"] = material("Frosted blue window", "b0cbd0", glow=1.25)
    m["diffuser"] = material("Warm fluorescent diffuser", "efe1b8", glow=2.0)
    shell(m)
    garage_door(m)
    workbench(m)
    storage(m)
    service_wall(m)
    lighting(m)
    return scene


def main():
    args = parse_args(__doc__, samples=64)
    bake(build_scene(args.samples), "pp_garage", EYE, args.output)


if __name__ == "__main__":
    main()
