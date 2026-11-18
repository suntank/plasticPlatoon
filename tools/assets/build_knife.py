#!/usr/bin/env python3
"""Build Plastic Platoon's knife models, HUD icon, and melee sounds."""

from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import wave

import numpy as np
from PIL import Image, ImageDraw

from asset_sources import source_bytes
from build_m16 import MATERIALS, atlas_uvs, encode_md2, rigid_transforms, texture_bytes
from build_pistol import placement
from m16_geometry import Mesh, _triangulate
from md2_assets import MD2
from pistol_geometry import GRIP

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "baseq2"
VIEW = "models/weapons/v_knife"
PICKUP = "models/weapons/g_knife"
HELD = "players/soldier/w_knife.md2"

# X runs toward the tip, Y is left and Z is up. The two outlines share the
# same vertices around the blade so the beveled edge can taper into the tip.
BLADE_OUTLINE = [
    (3.7, -2.05), (9.3, -2.14), (12.5, -1.78), (15.0, -0.74),
    (17.1, 0.38), (14.2, 1.56), (12.5, 2.13), (3.7, 2.18),
]
BLADE_FACE = [
    (3.7, -1.20), (9.2, -1.24), (12.2, -0.99), (14.0, -0.29),
    (15.4, 0.43), (13.9, 1.26), (12.45, 1.79), (3.7, 1.82),
]
WRIST = np.array((-2.5, -1.65, -1.10))
HAND_ROLL = -112
# Camera-space rest pose: the hand sits low on the right and the spine
# rises inward. Roll the grip around the blade axis to show its narrow edge.
GRIP_ORIGIN = np.array((14.0, -7.5, -8.8))
GRIP_ANGLES = (74, 57, -70)
ELBOW = np.array((5.0, -3.0, -18.0))
SHOULDER = np.array((-9.0, -5.0, -16.0))
READY = ((0, 0, 0), 0)

# Each pose pairs a whole-arm rotation with lateral shoulder travel. Pose
# three crosses the reticle. The follow-through slows outside the viewport.
SWINGS = {
    "down": [((10, 4, -6), 0), ((17, 4, -9), 0), ((-5, 0, -16), 0),
             ((-56, 2, -15), 0), ((-50, 1, -12), 0), READY],
    # The hands lead the side cuts. The blade points back along the sweep.
    "left": [((20, 4, 52), -5), ((40, 7, 103), -10),
             ((37, 12, 104), 15), ((37, 24, 102), 52),
             ((35, 21, 99), 51), READY],
    "right": [((15, -3, -42), 8), ((30, -5, -83), 15),
              ((30, -18, -94), -4), ((30, -26, -87), -42),
              ((27, -24, -84), -41), READY],
}


def blade(mesh):
    mesh.part("beveled_blade")
    for side in (-1, 1):
        face = [(x, side * .51, z) for x, z in BLADE_FACE]
        edge = [(x, side * .12, z) for x, z in BLADE_OUTLINE]
        for indices in _triangulate(BLADE_FACE):
            mesh.poly([face[i] for i in indices], "plastic", (0, side, 0),
                      [((face[i][0] - 3.7) / 13.4, (2.2 - face[i][2]) / 4.4)
                       for i in indices], group=f"face{side}")
        for i, (x, z) in enumerate(BLADE_OUTLINE):
            j = (i + 1) % len(edge)
            next_x, next_z = BLADE_OUTLINE[j]
            outward = (next_z - z, side, x - next_x)
            mesh.poly([edge[i], edge[j], face[j], face[i]], "edge", outward,
                      group=f"bevel{side}")
    for i, (x, z) in enumerate(BLADE_OUTLINE):
        next_x, next_z = BLADE_OUTLINE[(i + 1) % len(BLADE_OUTLINE)]
        mesh.poly([(x, -.12, z), (next_x, -.12, next_z),
                   (next_x, .12, next_z), (x, .12, z)], "edge",
                  (next_z - z, 0, x - next_x), group="rim")


def knife_mesh(view=False):
    mesh = Mesh()
    blade(mesh)
    handle = [
        (-4.7, 0, 0, 1.15, 1.35), (-4.3, 0, 0, 1.50, 1.66),
        (-3.1, 0, 0, 1.48, 1.60), (2.8, 0, 0, 1.10, 1.22),
        (4.0, 0, 0, 1.24, 1.45),
    ]
    if view:
        # Continue the grip through the open web between the thumb and fingers.
        handle = [
            (-2.28, 0, 0, .72, .80), (2.02, 0, 0, .77, .85),
            (3.65, 0, 0, .82, .91), (4.0, 0, 0, 1.24, 1.45),
        ]
    mesh.tube("molded_handle", handle, sides=8, material="grip", caps=(True, True))
    mesh.tube("crossguard", [
        (3.59, 0, 0, 1.29, 2.06), (3.78, 0, 0, 1.48, 2.36),
        (4.14, 0, 0, 1.48, 2.36), (4.32, 0, 0, 1.29, 2.06),
    ], sides=8, material="dark", caps=(True, True))
    if view:
        hand_start = len(mesh.vertices)
        # Seat the knife along its own axis, just above the finger curl.
        for point in mesh.vertices:
            point[0] -= 1.22
        # Keep the heel against the wrist and the upper palm behind the curl.
        # Stop on the palm side of the handle to leave the thumb web open.
        mesh.tube("palm", [
            (-2.87, -1.58, -.94, .92, .80),
            (-2.33, -1.35, -.67, 1.08, .93),
            (-1.42, -1.06, -.36, 1.25, 1.12),
            (.65, -1.15, -.12, .99, 1.02),
            (1.28, -1.18, .20, .67, .71),
            (1.60, -1.12, .45, .42, .44),
        ], sides=10, material="hand", caps=(True, True))

        finger_band = []
        for angle, center_x, half_width, thickness in (
            (152, -.34, 2.12, .47), (117, -.35, 2.35, .67),
            (76, -.43, 2.41, .65), (35, -.53, 2.31, .57),
            (-7, -.64, 2.11, .52), (-38, -.68, 1.86, .38),
        ):
            y, z = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            ring = []
            for side in range(8):
                section = side * math.tau / 8
                radial = thickness * math.sin(section)
                ring.append((center_x + half_width * math.cos(section),
                             y * (1.63 + radial), z * (1.71 + radial)))
            finger_band.append(ring)
        mesh.loft("finger_band", finger_band)

        mesh.finger("thumb", [
            (-.53, -2.05, -1.10), (.72, -2.75, -.58),
            (1.63, -2.51, .30), (1.95, -1.83, 1.12),
        ], (.98, .91, .71, .43))
        # Turn the knuckles around the handle so the glove's back faces
        # the player and only the curled finger silhouette peeks around it.
        hand_basis = rotation((0, 0, HAND_ROLL))
        mesh.vertices[hand_start:] = (np.asarray(mesh.vertices[hand_start:]) @ hand_basis).tolist()
    return mesh.finish("view" if view else "world")


def arm_mesh():
    mesh = Mesh()
    mesh.tube("sleeved_forearm", [
        (0, 0, 0, 2.82, 2.61), (.57, 0, 0, 2.46, 2.23),
        (.65, 0, 0, 2.45, 2.18), (.75, 0, 0, 2.12, 1.95),
        (.80, 0, 0, 1.21, 1.07), (1, 0, 0, 1.17, 1.03),
    ], sides=8, material="plastic", caps=(True, True))
    mesh.materials[32:64] = ["cuff"] * 32
    mesh.materials[64:80] = ["hand"] * 16
    mesh.materials[-6:] = ["hand"] * 6
    return mesh.finish("forearm")


def rotation(angles):
    pitch, yaw, roll = map(math.radians, angles)
    cp, cy, cr = map(math.cos, (pitch, yaw, roll))
    sp, sy, sr = map(math.sin, (pitch, yaw, roll))
    bank = np.array(((1, 0, 0), (0, cr, sr), (0, -sr, cr)))
    lift = np.array(((cp, 0, sp), (0, 1, 0), (-sp, 0, cp)))
    turn = np.array(((cy, sy, 0), (-sy, cy, 0), (0, 0, 1)))
    return bank @ lift @ turn


def model_bytes(positions, normals, mesh, skin, names):
    result, _ = encode_md2(positions, normals, mesh["faces"], atlas_uvs(mesh),
                           [skin], names)
    return result


def view_model(skin):
    knife = knife_mesh(view=True)
    arm = arm_mesh()
    knife_vertices = np.asarray(knife["vertices"])
    knife_normals = np.asarray(knife["normals"])
    arm_vertices = np.asarray(arm["vertices"])
    arm_normals = np.asarray(arm["normals"])
    faces = knife["faces"] + (np.asarray(arm["faces"]) + len(knife_vertices)).tolist()
    mesh = {"faces": faces, "uvs": knife["uvs"] + arm["uvs"],
            "materials": knife["materials"] + arm["materials"]}
    poses = {"ready": READY}
    for name, frames in SWINGS.items():
        poses.update({f"{name}{number}": pose for number, pose in enumerate(frames, 1)})
    grip_basis = rotation(GRIP_ANGLES)
    wrist = WRIST @ rotation((0, 0, HAND_ROLL))
    reach = wrist @ grip_basis + GRIP_ORIGIN - ELBOW
    length = np.linalg.norm(reach)
    axis = reach / length
    across = np.cross((0, 0, 1), axis)
    across /= np.linalg.norm(across)
    arm_basis = np.array((axis, across, np.cross(axis, across)))
    scale = np.array((length, 1, 1))
    arm_directions = (arm_normals / scale) @ arm_basis
    arm_directions /= np.linalg.norm(arm_directions, axis=1, keepdims=True)

    rest_positions = np.vstack((knife_vertices @ grip_basis + GRIP_ORIGIN,
                                (arm_vertices * scale) @ arm_basis + ELBOW))
    rest_normals = np.vstack((knife_normals @ grip_basis, arm_directions))
    positions, normals = [], []
    for angles, travel in poses.values():
        swing = rotation(angles)
        positions.append((rest_positions - SHOULDER) @ swing + SHOULDER + (0, travel, 0))
        normals.append(rest_normals @ swing)
    return model_bytes(positions, normals, mesh, skin, list(poses))


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, "PNG", compress_level=9)
    return output.getvalue()


def hud_icon():
    image = Image.new("RGB", (128, 128))
    pixels = image.load()
    for y in range(128):
        for x in range(128):
            distance = ((x - 64) / 74) ** 2 + ((y - 63) / 76) ** 2
            glow = max(0, 1 - distance)
            pixels[x, y] = (round(16 + 35 * glow), round(18 + 39 * glow),
                            round(48 + 96 * glow))
    draw = ImageDraw.Draw(image)
    draw.line((0, 0, 127, 0, 127, 3, 0, 3), fill=(56, 62, 145))
    draw.line((0, 124, 127, 124, 127, 127, 0, 127), fill=(17, 19, 52))
    draw.polygon([(38, 79), (75, 42), (98, 24), (115, 15), (110, 41),
                  (92, 66), (57, 96)], fill=(29, 54, 20))
    draw.polygon([(43, 79), (78, 44), (102, 25), (111, 21), (105, 40),
                  (89, 63), (56, 91)], fill=(104, 144, 58))
    draw.polygon([(48, 81), (84, 45), (109, 23), (102, 42), (83, 62),
                  (56, 86)], fill=(79, 117, 41))
    draw.polygon([(14, 107), (19, 96), (41, 73), (57, 90), (34, 114),
                  (24, 118)], fill=(27, 69, 18))
    draw.line((22, 105, 45, 82), fill=(108, 169, 59), width=6)
    for x, y in ((24, 97), (31, 90), (38, 83)):
        draw.line((x, y, x + 9, y + 10), fill=(47, 103, 23), width=3)
    draw.polygon([(36, 72), (42, 66), (63, 88), (58, 95)],
                 fill=(66, 123, 41))
    return png_bytes(image.resize((32, 32), Image.Resampling.LANCZOS))


def sound_bytes(hit):
    rate = 22050
    time = np.arange(round(rate * (.12 if hit else .22))) / rate
    rng = np.random.default_rng(108 if hit else 55)
    noise = rng.standard_normal(len(time))
    low = np.convolve(noise, np.full(11, 1 / 11), mode="same")
    if hit:
        body = np.sin(math.tau * (165 * time - 270 * time ** 2))
        envelope = np.minimum(time / .003, 1) * np.exp(-time * 48)
        signal = (body * .7 + low + (noise - low) * .12) * envelope
    else:
        mid = np.convolve(noise, np.full(3, 1 / 3), mode="same")
        envelope = np.sin(math.pi * time / .22) ** 3
        signal = ((mid - low) * .65 + (noise - mid) * time * 1.15) * envelope
    amplitude = .55 if hit else .40
    fade_out = np.clip((time[-1] - time) / .01, 0, 1)
    pcm = np.rint(signal * fade_out * amplitude * 32767 / np.max(np.abs(signal))).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as sound:
        sound.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        sound.writeframes(pcm.tobytes())
    return output.getvalue()


def build_assets():
    atlas_image = Image.open(io.BytesIO(texture_bytes()))
    # Lift the glove pigment a little above the handle in dim rooms.
    tile = MATERIALS.index("hand")
    x, y = tile % 4 * 64, tile // 4 * 64
    glove = atlas_image.crop((x, y, x + 64, y + 64))
    glove = glove.point(lambda value: min(255, round(value * 1.18)))
    atlas_image.paste(glove, (x, y))
    atlas = png_bytes(atlas_image)
    mesh = knife_mesh()
    points = np.asarray(mesh["vertices"])
    normals = np.asarray(mesh["normals"])

    # Match the scale of other pickups and center the knife on its spin axis.
    pickup_points = points * .88 + (-5.45, 0, 9)
    pickup = model_bytes(pickup_points[None], normals[None], mesh,
                         f"{PICKUP}/skin.png", ["pickup"])

    # Reuse the player's one-handed attachment motion. The stock poses share
    # their indices with the body so locomotion and death still move in sync.
    originals = json.loads((ROOT / "tools/assets/platoon-originals.json").read_text())
    source = MD2.read(source_bytes(originals, "baseq2/players/soldier/w_blaster.md2"),
                      source_compat=True)
    movements, translations, _ = rigid_transforms(source)
    matrix, offset, _ = placement("player")
    grip = np.asarray(GRIP) @ matrix + offset
    turn = rotation((65, 8, 12))
    held_points = points @ turn * .68 + grip
    held_normals = normals @ turn
    held = model_bytes(held_points @ movements + translations[:, None],
                       held_normals @ movements, mesh, f"{VIEW}/skin.png", source.names)
    return {
        f"{VIEW}/tris.md2": view_model(f"{VIEW}/skin.png"),
        f"{VIEW}/skin.png": atlas,
        f"{PICKUP}/tris.md2": pickup,
        f"{PICKUP}/skin.png": atlas,
        HELD: held,
        "pics/w_knife.png": hud_icon(),
        "sound/weapons/knife_swing.wav": sound_bytes(hit=False),
        "sound/weapons/knife_hit.wav": sound_bytes(hit=True),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    for name, content in build_assets().items():
        path = BASE / name
        current = path.read_bytes() if path.is_file() else None
        if current == content:
            continue
        if args.verify:
            raise ValueError(f"Stale knife asset: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("Verified knife assets" if args.verify else "Built knife assets")


if __name__ == "__main__":
    main()
