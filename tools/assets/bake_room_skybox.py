"""Shared Blender primitives and cubemap baking for Plastic Platoon environments."""

import argparse
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
# The software renderer reads the sky with a fixed 256-pixel stride.
FACE_SIZE = 256
# GL1/GL3 st_to_vec and skytexorder, with image rows starting at the top.
# Each tuple gives the center direction and the direction of the top edge.
FACES = {
    "rt": ((1, 0, 0), (0, 0, 1)),
    "lf": ((-1, 0, 0), (0, 0, 1)),
    "bk": ((0, 1, 0), (0, 0, 1)),
    "ft": ((0, -1, 0), (0, 0, 1)),
    "up": ((0, 0, 1), (-1, 0, 0)),
    "dn": ((0, 0, -1), (1, 0, 0)),
}


def linear_rgb(hex_color):
    srgb = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def material(name, color, variation=None, scale=5, glow=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    rgba = (*linear_rgb(color), 1)
    mat.diffuse_color = rgba
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = 0.83
    shader.inputs["Specular IOR Level"].default_value = 0.24
    shader.inputs["Emission Color"].default_value = rgba
    shader.inputs["Emission Strength"].default_value = glow
    if variation:
        coords = nodes.new("ShaderNodeTexCoord")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = scale
        noise.inputs["Detail"].default_value = 2.0
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = rgba
        ramp.color_ramp.elements[1].color = (*linear_rgb(variation), 1)
        links.new(coords.outputs["Object"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    return mat


def current_object(name, mat):
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def box(name, center, size, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = current_object(name, mat)
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        edges = obj.modifiers.new("Soft edges", "BEVEL")
        edges.width = bevel
        edges.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def beam(name, start, end, width, depth, mat, bevel=0):
    direction = Vector(end) - Vector(start)
    center = Vector(start) + direction * 0.5
    obj = box(name, center, (width, depth, direction.length), mat, bevel)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def rod(name, start, end, radius, mat, sides=12):
    direction = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=sides, radius=radius, depth=direction.length,
        location=Vector(start) + direction * 0.5,
    )
    obj = current_object(name, mat)
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def area(name, location, target, energy, color, width, height):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = energy
    light.color = color
    light.shape = "RECTANGLE"
    light.size = width
    light.size_y = height
    obj = bpy.data.objects.new(name, light)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()


def new_scene(samples, *, bounces=6, exposure=0.15):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = bounces
    scene.render.resolution_x = FACE_SIZE * 2
    scene.render.resolution_y = FACE_SIZE * 2
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 60
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = exposure
    return scene


def save_face(rendered, destination):
    image = bpy.data.images.load(str(rendered))
    try:
        image.scale(FACE_SIZE, FACE_SIZE)
        image.save(filepath=str(destination))
    finally:
        bpy.data.images.remove(image)


def bake(scene, basename, eye, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lens = bpy.data.cameras.new("Cubemap 90 degree lens")
    lens.lens_unit = "FOV"
    lens.angle = math.pi / 2
    lens.clip_start = 0.008
    camera = bpy.data.objects.new("Floor-level cubemap camera", lens)
    scene.collection.objects.link(camera)
    camera.location = eye
    scene.camera = camera

    with TemporaryDirectory(prefix="pp-skybox-bake-") as temporary:
        for face, (direction, top) in FACES.items():
            forward, up = Vector(direction), Vector(top)
            right = forward.cross(up)
            camera.rotation_euler = Matrix((right, up, -forward)).transposed().to_euler()
            filename = f"{basename}{face}.png"
            rendered = Path(temporary) / filename
            scene.render.filepath = str(rendered)
            bpy.ops.render.render(write_still=True)
            save_face(rendered, output / filename)


def parse_args(description, samples):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--output", type=Path, default=ROOT / "baseq2" / "env")
    parser.add_argument("--samples", type=int, default=samples, help="Cycles samples per pixel")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
