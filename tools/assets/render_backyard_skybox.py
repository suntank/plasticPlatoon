#!/usr/bin/env python3
"""Bake the original Plastic Platoon backyard from grass height in Blender."""

import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bake_room_skybox import bake, beam, box, current_object, linear_rgb, material, new_scene, parse_args, rod


EYE = (-0.24, -0.64, 0.088)
YARD = (-7.1, 11.65, -6.5, 6.3)


def mesh_object(name, vertices, faces, surfaces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for surface in surfaces:
        mesh.materials.append(surface)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def puff(name, center, radii, surface, *, cloud=False):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3 if cloud else 2, radius=1, location=center)
    obj = current_object(name, surface)
    obj.scale = radii
    if cloud:
        obj.visible_shadow = False
        obj.visible_diffuse = False
        for face in obj.data.polygons:
            face.use_smooth = True
    return obj


def set_colors(ramp, stops):
    ramp.elements[0].color = (*linear_rgb(stops[0][1]), 1)
    ramp.elements[1].color = (*linear_rgb(stops[-1][1]), 1)
    for position, color in stops[1:-1]:
        ramp.elements.new(position).color = (*linear_rgb(color), 1)


def cloud_surface():
    result = bpy.data.materials.new("Cumulus lit by warm daylight")
    result.use_nodes = True
    nodes = result.node_tree.nodes
    link = result.node_tree.links.new
    normal = nodes.new("ShaderNodeNewGeometry")
    sunlight = nodes.new("ShaderNodeVectorMath")
    sunlight.operation = "DOT_PRODUCT"
    sunlight.inputs[1].default_value = Vector((-.57, -.50, .76)).normalized()
    remap = nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = -1
    ramp = nodes.new("ShaderNodeValToRGB")
    set_colors(ramp.color_ramp, ((0, "c1d9eb"), (.43, "dfedf8"), (.75, "f4f7f9"), (1, "fff6df")))
    emission = nodes.new("ShaderNodeEmission")
    link(normal.outputs["Normal"], sunlight.inputs[0])
    link(sunlight.outputs["Value"], remap.inputs["Value"])
    link(remap.outputs["Result"], ramp.inputs[0])
    link(ramp.outputs["Color"], emission.inputs["Color"])
    link(emission.outputs[0], nodes.get("Material Output").inputs["Surface"])
    return result


def summer_sky(scene):
    world = bpy.data.worlds.new("Backyard afternoon")
    world.use_nodes = True
    scene.world = world
    nodes = world.node_tree.nodes
    link = world.node_tree.links.new
    ambient = nodes.get("Background")
    ambient.inputs["Color"].default_value = (*linear_rgb("cbe0f6"), 1)
    ambient.inputs["Strength"].default_value = 0.82
    camera_sky = nodes.new("ShaderNodeBackground")
    coords = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    height = nodes.new("ShaderNodeMath")
    height.operation = "MULTIPLY"
    # The world normal points back along the camera ray.
    height.inputs[1].default_value = -1
    ramp = nodes.new("ShaderNodeValToRGB")
    set_colors(ramp.color_ramp, ((0, "acdaf0"), (.30, "75b9eb"), (1, "4d92d6")))
    light_path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    link(coords.outputs["Normal"], separate.inputs[0])
    link(separate.outputs["Z"], height.inputs[0])
    link(height.outputs[0], ramp.inputs[0])
    link(ramp.outputs["Color"], camera_sky.inputs["Color"])
    link(light_path.outputs["Is Camera Ray"], mix.inputs[0])
    link(ambient.outputs[0], mix.inputs[1])
    link(camera_sky.outputs[0], mix.inputs[2])
    link(mix.outputs[0], nodes.get("World Output").inputs["Surface"])

    lamp = bpy.data.lights.new("Warm afternoon sun", "SUN")
    lamp.energy = 1.93
    lamp.color = (1, 0.94, 0.84)
    lamp.angle = math.radians(10)
    sun = bpy.data.objects.new("Warm afternoon sun", lamp)
    scene.collection.objects.link(sun)
    sun.rotation_euler = Vector((0.57, 0.50, -0.76)).to_track_quat("-Z", "Y").to_euler()

    # Each set of lobes is placed in world space, so its silhouette crosses cube faces.
    groups = (
        ((19, -17, 19), (9.0, 4.8, 2.4), 0.31),
        ((-5, -28, 17), (7.9, 4.1, 1.7), -0.19),
        ((-27, -4, 21), (4.4, 8.2, 2.0), 1.23),
        ((-15, 27, 19), (8.1, 4.6, 1.8), 0.34),
        ((21, 20, 20), (8.5, 4.5, 2.7), -0.52),
        ((-4, 8, 34), (9.2, 6.0, 2.2), 0.55),
    )
    cloud = cloud_surface()
    for center, radii, yaw in groups:
        length, width, height = radii
        long = Vector((math.cos(yaw), math.sin(yaw), 0))
        cross = Vector((-long.y, long.x, 0))
        for u, v, z, scale in ((-.48, -.13, .02, .67), (.37, -.14, -.13, .75),
                                (-.15, .14, .30, 1.0), (.19, .20, .41, .86),
                                (-.60, -.30, -.15, .46), (.61, .08, .15, .51)):
            position = Vector(center) + long * (u * length) + cross * (v * width)
            position.z += z * height
            lobe = puff("Soft cumulus lobe", position,
                        (length * scale * .57, width * scale, height * scale), cloud, cloud=True)
            lobe.rotation_euler.z = yaw


def fencing(m, *, front_open_at=None):
    west, east, south, north = YARD
    if front_open_at is not None:
        east = front_open_at
    rng = random.Random(221)
    # Each edge is wound so its left-hand normal faces into the yard.
    runs = (((west, south), (east, south)), ((east, south), (east, north)),
            ((east, north), (west, north)), ((west, north), (west, south)))
    for run_index, (first, last) in enumerate(runs):
        if front_open_at is not None and run_index == 1:
            continue
        start, end = Vector((*first, 0)), Vector((*last, 0))
        along = (end - start).normalized()
        inward = Vector((-along.y, along.x, 0))
        distance = (end - start).length
        vertices, faces, board_colors = [], [], []
        count = round(distance / .233)
        step = distance / count
        for index in range(count):
            x = index * step + .006
            width = step - .013
            height = 1.92 + rng.uniform(-.055, .047)
            if run_index == 0 and 2.58 < x < 4.13:
                height -= .10
            section = ((x, .026), (x + width, .026), (x + width, height - .068),
                       (x + width - .045, height), (x + .045, height), (x, height - .068))
            first_index = len(vertices)
            for thickness in (-.036, .018):
                vertices.extend(start + along * walk + inward * thickness + Vector((0, 0, z))
                                for walk, z in section)
            face = tuple(range(first_index, first_index + 6))
            back = tuple(i + 6 for i in face)
            faces.extend((face, back[::-1]))
            faces.extend((face[i], back[i], back[(i + 1) % 6], face[(i + 1) % 6]) for i in range(6))
            board_colors.extend([rng.randrange(4)] * 8)
        surface = [m[c] for c in ("fence", "fence_warm", "fence_light", "fence_gray")]
        boards = mesh_object("Dog-eared cedar planks", vertices, faces, surface)
        for poly, index in zip(boards.data.polygons, board_colors):
            poly.material_index = index

        for z in (.43, 1.48):
            offset = inward * .074 + Vector((0, 0, z))
            beam("Fence cross rail", start + offset, end + offset, .115, .135, m["rail"], .01)
        posts = math.ceil(distance / 2.46)
        # The starting post anchors this corner and the adjoining end.
        end_post = 1 if front_open_at is not None and run_index == 0 else 0
        for index in range(posts + end_post):
            point = start + along * (index * distance / posts) + inward * .103
            box("Square fence post", (*point.xy, .994), (.161, .161, 2.034), m["rail"], .017)
            box("Fence post cap", (*point.xy, 2.015), (.214, .214, .088), m["fence_light"], .021)

    # The west end of the south run includes a low gate with visible bracing.
    for dx in (2.54, 4.18):
        box("Gate jamb", (west + dx, south + .106, .988), (.163, .168, 2.027), m["rail"], .019)
    beam("Gate diagonal", (west + 2.60, south + .132, .44), (west + 4.12, south + .132, 1.51),
         .125, .078, m["rail"], .014)
    for z in (.48, 1.43):
        box("Gate hinge", (west + 2.65, south + .182, z), (.239, .035, .125), m["metal"], .012)
    box("Gate latch", (west + 4.02, south + .176, 1.12), (.19, .058, .091), m["metal"], .014)


def house_windows(m, x, y, z, width):
    box("Cream window frame", (x, y, z), (.146, width, 1.216), m["trim"], .043)
    box("Shadowed window gasket", (x - .082, y, z), (.048, width - .188, 1.044), m["metal"], .020)
    for index in (-1, 1):
        box("Cloud-blue window glass", (x - .112, y + index * (width - .2) * .249, z),
            (.033, (width - .22) * .475, .970), m["glass"], .011)
    box("Window mullion", (x - .129, y, z), (.068, .067, 1.043), m["trim"], .012)
    box("Window meeting rail", (x - .127, y, z - .135), (.063, width - .145, .073), m["trim"], .015)
    box("Projecting window sill", (x - .064, y, z - .623), (.255, width + .096, .111), m["trim"], .023)


def house(m):
    facade = 6.61
    y0 = -.46
    box("Raised house foundation", (8.77, y0, .277), (4.35, 8.44, .555), m["foundation"], .042)
    box("House volume", (8.79, y0, 1.80), (4.35, 8.42, 2.63), m["siding"])
    for row in range(12):
        z = .648 + .207 * row
        box("Clapboard course", (facade - .015, y0, z), (.076, 8.414, .197),
            m["siding_light"] if row % 4 == 2 else m["siding"], .011)
    for y in (y0 - 4.174, y0 + 4.174):
        box("Painted corner board", (facade - .075, y, 1.83), (.121, .173, 2.59), m["trim"], .013)
    box("Horizontal eave trim", (facade - .066, y0, 3.112), (.155, 8.55, .153), m["trim"], .019)

    ridge = (y0, 4.92)
    for x in (facade, 10.99):
        mesh_object("Rear gable", [(x, y0 - 4.21, 3.105), (x, y0 + 4.21, 3.105), (x, *ridge)],
                    [(0, 1, 2)], [m["siding"]])
    for side in (-1, 1):
        eave_y = y0 + side * 4.51
        beam("Slate shingle roof", (8.72, *ridge), (8.72, eave_y, 3.104),
             5.20, .162, m["roof"], .025)
        beam("White rake board", (6.11, y0, 4.92), (6.11, eave_y, 3.104),
             .215, .158, m["trim"], .016)
        box("Shaded roof gutter", (8.72, eave_y, 3.057), (5.061, .141, .139), m["trim"], .016)
    box("Roof ridge", (8.72, y0, 4.963), (5.27, .195, .102), m["roof"], .034)
    box("Brick chimney", (8.43, y0 + 1.29, 4.927), (.64, .732, 1.327), m["brick"], .031)
    for z in (4.72, 4.914, 5.108, 5.302, 5.496):
        box("Chimney mortar line", (8.43, y0 + 1.29, z), (.649, .742, .022), m["foundation"])
    box("Chimney cap", (8.43, y0 + 1.29, 5.605), (.794, .886, .122), m["foundation"], .032)

    house_windows(m, facade - .073, -2.83, 1.925, 1.49)
    house_windows(m, facade - .073, 1.93, 2.007, 2.02)
    for dx in (-1, 1):
        y = -2.83 + dx * .94
        box("Painted window shutter", (facade - .142, y, 1.932), (.115, .321, 1.155), m["door"], .021)
        for z in (1.51, 2.31):
            box("Shutter batten", (facade - .21, y, z), (.045, .316, .064), m["trim"], .008)
    box("Back door casing", (facade - .17, -.29, 1.596), (.246, 1.35, 2.165), m["trim"], .038)
    box("Terracotta back door", (facade - .302, -.29, 1.583), (.102, 1.111, 2.039), m["door"], .025)
    box("Door glass inset", (facade - .363, -.29, 2.024), (.049, .773, .879), m["glass"], .022)
    box("Door bottom panel", (facade - .366, -.29, 1.123), (.057, .792, .615), m["door"], .035)
    rod("Back door knob", (facade - .409, .130, 1.49), (facade - .358, .13, 1.49), .057, m["metal"])
    for x, z, height in ((6.19, .295, .59), (5.72, .199, .397), (5.365, .099, .198)):
        box("Back porch step", (x, -.29, z), (.51, 1.84, height), m["deck"], .04)
        box("Back porch tread edge", (x - .243, -.29, height - .028), (.099, 1.95, .082), m["trim"], .018)
    box("Porch light backplate", (facade - .103, .771, 2.284), (.154, .234, .297), m["metal"], .036)
    box("Porch lantern", (facade - .23, .771, 2.228), (.253, .207, .235), m["glass"], .031)
    box("Porch lantern cap", (facade - .23, .771, 2.374), (.313, .26, .078), m["metal"], .022)


def tapered_limb(name, start, end, radius, tip, surface):
    vector = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cone_add(vertices=11, radius1=radius, radius2=tip,
                                   depth=vector.length, location=Vector(start) + vector / 2)
    obj = current_object(name, surface)
    obj.rotation_euler = vector.to_track_quat("Z", "Y").to_euler()


def tree_and_swing(m, *, swing_yaw=0):
    # Continuous tapered trunk and a long exposed limb toward the middle of the yard.
    base = ((.95, 3.43, -.08), (.91, 3.48, .57), (1.01, 3.42, 1.77),
            (.94, 3.50, 2.68), (1.12, 3.59, 3.72), (.89, 3.60, 4.87))
    widths = (.65, .47, .34, .31, .224, .073)
    vertices = []
    sides = 11
    for (x, y, z), width in zip(base, widths):
        for index in range(sides):
            angle = math.tau * index / sides
            r = width * (1 + .08 * math.cos(angle * 3))
            vertices.append((x + r * math.cos(angle), y + r * math.sin(angle), z))
    faces = [
        (row*sides + i, row*sides + (i+1) % sides,
         (row+1)*sides + (i+1) % sides, (row+1)*sides + i)
        for row in range(len(base)-1) for i in range(sides)
    ]
    mesh_object("Bending tree trunk", vertices, faces, [m["bark"]])
    limbs = (
        ((.92, 3.51, 2.48), (.02, 3.34, 3.27), .289, .19),
        ((.05, 3.34, 3.24), (-1.55, 3.10, 3.69), .193, .097),
        ((-1.49, 3.1, 3.67), (-2.05, 3.11, 4.36), .102, .045),
        ((.0, 3.34, 3.28), (-.86, 3.86, 4.48), .152, .052),
        ((1.04, 3.55, 3.05), (2.72, 3.88, 4.26), .235, .059),
        ((.94, 3.6, 3.51), (1.40, 4.78, 4.51), .175, .042),
        ((.96, 3.57, 3.69), (.49, 2.64, 4.60), .156, .05),
    )
    for start, end, root, tip in limbs:
        tapered_limb("Crooked oak limb", start, end, root, tip, m["bark"])
    for dx, dy in ((.95, .37), (-.9, .6), (-.68, -.65), (.66, -.69)):
        tapered_limb("Shallow oak root", (.93, 3.46, .24), (.93 + dx, 3.46 + dy, .028), .24, .044, m["bark"])

    crown = (
        ((-.95, 3.02, 4.63), (1.29, 1.12, .84), "leaf"),
        ((-1.81, 3.35, 4.57), (.90, .84, .68), "leaf_lit"),
        ((-.82, 4.27, 4.90), (1.31, 1.22, .83), "leaf"),
        ((.34, 2.90, 5.02), (1.36, 1.22, .96), "leaf_mid"),
        ((1.35, 3.67, 5.49), (1.67, 1.50, 1.08), "leaf_lit"),
        ((2.46, 3.93, 4.94), (1.19, 1.01, .85), "leaf_mid"),
        ((1.22, 4.91, 5.26), (1.44, 1.07, .91), "leaf"),
        ((.10, 4.00, 5.75), (1.34, 1.17, .83), "leaf_lit"),
        ((2.32, 2.92, 5.33), (1.02, .82, .69), "leaf_mid"),
    )
    for center, radii, color in crown:
        puff("Rounded oak leaf cluster", center, radii, m[color])

    center = (-.98, 3.19, .965)
    bpy.ops.mesh.primitive_torus_add(location=center, major_segments=40, minor_segments=12,
                                  major_radius=.315, minor_radius=.115)
    tire = current_object("Tire swing", m["rubber"])
    tire.rotation_euler.x = math.pi / 2
    tire.rotation_euler.z = swing_yaw
    for polygon in tire.data.polygons:
        polygon.use_smooth = True
    swing_turn = Matrix.Rotation(swing_yaw, 3, "Z")
    for index in range(26):
        angle = math.tau * index / 26
        offset = swing_turn @ Vector((.397 * math.cos(angle), -.065, .397 * math.sin(angle)))
        tread = box("Short tire tread", Vector(center) + offset,
                    (.054, .071, .044), m["metal"], .008)
        tread.rotation_euler.y = -angle
        tread.rotation_euler.z = swing_yaw
    rod("Tire swing rope", (center[0], center[1], 1.306),
        (center[0] + .04, center[1] + .035, 3.616), .031, m["rope"], 12)
    rod("Rope knot above tire", (center[0], center[1], 1.369),
        (center[0], center[1], 1.472), .061, m["rope"])


def grass(m, *, paving=None, eye=EYE):
    box("Grassy yard", (0.0, 0.0, -.102), (200, 200, .2), m["ground"])
    visible = [m[c] for c in ("grass_dark", "grass", "grass_lit", "grass_young")]
    rng = random.Random(421)
    vertices, faces, shades = [], [], []
    tufts = []
    for index in range(120):
        angle = math.tau * rng.random()
        radius = .69 + 3.37 * rng.random() ** 1.32
        tufts.append((eye[0] + radius * math.cos(angle), eye[1] + radius * math.sin(angle),
                      rng.uniform(.071, .193)))
    for index in range(265):
        x, y = rng.uniform(-7.15, 6.5), rng.uniform(-6.32, 6.19)
        if math.hypot(x - eye[0], y - eye[1]) > 2.6:
            tufts.append((x, y, rng.uniform(.072, .23)))
    for x, y, height in tufts:
        if paving is not None and paving[0] <= x <= paving[1] and paving[2] <= y <= paving[3]:
            continue
        for index in range(rng.randint(3, 6)):
            angle = rng.uniform(0, math.tau)
            dx, dy = math.cos(angle), math.sin(angle)
            cx, cy = x + rng.uniform(-.057, .057), y + rng.uniform(-.057, .057)
            h = height * rng.uniform(.48, 1.13)
            width = rng.uniform(.013, .031)
            lean = h * rng.uniform(.17, .61)
            start = len(vertices)
            vertices.extend((
                (cx + dy*width, cy - dx*width, .002),
                (cx - dy*width, cy + dx*width, .002),
                (cx + dx*lean*.29, cy + dy*lean*.29, h*.58),
                (cx + dx*lean, cy + dy*lean, h),
            ))
            faces.extend(((start, start+1, start+2), (start+1, start+3, start+2), (start+3, start, start+2)))
            tone = rng.randrange(len(visible))
            shades.extend((tone, tone, min(len(visible)-1, tone+1)))
    blades = mesh_object("Folded grass blades", vertices, faces, visible)
    for polygon, shade in zip(blades.data.polygons, shades):
        polygon.material_index = shade

    bushes = ((-6.72, 3.12, .48, .86), (-6.71, 2.0, .48, .73), (-6.6, -4.7, .6, .92),
              (-5.62, 5.94, .43, .75), (-4.77, 5.95, .46, .83), (3.31, 5.97, .42, .82),
              (5.99, -3.98, .34, .54), (5.96, 3.24, .36, .66))
    for index, (x, y, z, size) in enumerate(bushes):
        puff("Border shrub", (x, y, z), (size, size*.78, z*1.24), m["leaf_mid" if index % 2 else "leaf"])
    for x, y, z, radius in ((-9, 8, 2.24, 2.3), (3.8, 8.6, 2.02, 2.4),
                            (-8.34, -5.88, 2.10, 1.91), (7.5, -8.2, 2.07, 2.51)):
        puff("Distant blurred hedge shape", (x, y, z), (radius, radius*.59, radius*.60), m["distant"])


def yard_materials():
    coatings = {
        "ground": ("627d3b", "759646", 2.1),
        "grass_dark": ("576d32",),
        "grass": ("72863b",),
        "grass_lit": ("8f9d4b",),
        "grass_young": ("a2ad5b",),
        "fence": ("ad8c61", "bc9c70", 1.4),
        "fence_warm": ("b59972", "c3a676", 1.2),
        "fence_light": ("c5a577", "ccae80", 1.2),
        "fence_gray": ("a18a6a", "ab9576", 1.2),
        "rail": ("a1815b",),
        "bark": ("725338", "8b6946", 2.4),
        "leaf": ("557338",),
        "leaf_mid": ("6c883c",),
        "leaf_lit": ("829847",),
        "distant": ("728c54",),
        "siding": ("799da4",),
        "siding_light": ("80a3aa",),
        "trim": ("e6dac0",),
        "foundation": ("a6a294", "b7ac96", 6.0),
        "roof": ("51616f",),
        "door": ("a76548",),
        "brick": ("a7775f",),
        "deck": ("917546",),
        "rope": ("a99565",),
        "rubber": ("353a38",),
        "metal": ("515956",),
    }
    m = {name: material(name, *params) for name, params in coatings.items()}
    m["glass"] = material("Pale reflected sky in glass", "97b3bf", glow=.17)
    return m


def build_scene(samples):
    scene = new_scene(samples, bounces=3, exposure=-.14)
    scene.view_settings.view_transform = "Standard"
    scene.cycles.adaptive_threshold = .045
    m = yard_materials()
    summer_sky(scene)
    fencing(m)
    house(m)
    tree_and_swing(m)
    grass(m)
    return scene


if __name__ == "__main__":
    args = parse_args(__doc__, samples=24)
    bake(build_scene(args.samples), "pp_backyard", EYE, args.output)
