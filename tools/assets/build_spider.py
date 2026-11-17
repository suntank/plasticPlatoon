#!/usr/bin/env python3
"""Build the original animated eight-legged spider MD2 and skin."""
import argparse
import io
import math

import numpy as np
from PIL import Image

from build_heavy_tank import Mesh
from insect_mesh import encode_animation, loft, plate, review_animation, rotation, stride, transform
from md2_assets import MD2, ROOT

DIRECTORY = 'models/monsters/spider'
SKIN = DIRECTORY + '/skin.png'
FRAMES = [('idle', 8), ('walk', 12), ('run', 12), ('attack', 8), ('pain', 4), ('death', 10)]
ABDOMEN, CARAPACE, FANG, EYE, FEMUR, TIBIA, JOINT = range(7)
# Front to back. Each row describes the leg's root, arch and resting foot.
LEGS = ((18, 10, 35, 25, 8, 51, 36),
        (10, 14, 21, 35, 12, 27, 53),
        (0, 14, -10, 36, 11, -15, 56),
        (-10, 10, -31, 27, 8, -48, 42))


def skin():
    image = Image.new('RGB', (256, 256), (26, 26, 29))
    colors = ((38, 38, 43), (43, 43, 48), (41, 40, 43), (49, 14, 22),
              (37, 37, 41), (33, 33, 38), (26, 26, 30))
    for material, color in enumerate(colors):
        tile_x, tile_y = material % 4 * 64, material // 4 * 64
        for y in range(64):
            for x in range(64):
                u, v = (x - 6) / 52, (y - 6) / 52
                grain = ((19*x + 13*y + 7*x*y) % 17 - 8) * .38
                sheen = math.exp(-((v - .24) / .14) ** 2)
                light = grain + (24 if material in (ABDOMEN, CARAPACE) else 16) * sheen
                if material == ABDOMEN:
                    # Fine mottling on the abdomen, with soft chevrons across its back.
                    ripple = math.sin(10 * math.pi * (u + .46 * abs(v - .25)))
                    light += 4 * ripple * sheen
                if material == EYE:
                    glint = math.exp(-((u - .59) / .26) ** 2 - ((v - .21) / .14) ** 2)
                    pixel = (round(49 + 66*glint), round(14 + 34*glint), round(22 + 41*glint))
                else:
                    pixel = tuple(round(c + light) for c in color)
                image.putpixel((tile_x + x, tile_y + y), pixel)
    out = io.BytesIO()
    image.save(out, format='PNG', compress_level=9)
    return out.getvalue()


def face(mesh, side, gape, feel):
    # Large forward eyes and three progressively smaller lateral eyes per side.
    for x, y, z, radius in ((26, 3.6, 4.8, 3.15), (23, 9.1, 5.9, 2.4),
                            (19, 13.0, 4.9, 1.9), (14.2, 15.5, 2.2, 1.55)):
        y *= side
        loft(mesh, [((x-1.5, y, z-.6), .68*radius, .66*radius),
                    ((x+.3, y, z+.25), radius, .92*radius),
                    ((x+1.9, y, z+.35), .57*radius, .55*radius)],
             EYE, sides=6)
    jaw = len(mesh.vertices)
    loft(mesh, [((22, side*5.5, -4.3), 3.15, 3.45),
                ((27.5, side*5.8, -6.3), 3.05, 3.25),
                ((31.5, side*5.9, -7.3), 1.85, 1.9),
                ((35, side*5.0, -10.5), 1.24, 1.2),
                ((34, side*3.4, -14.3), .68, .67)], FANG, sides=7, reference=(0, 1, 0))
    transform(mesh, jaw, (22, side*5.5, -4.3), (0, 10*gape, side*28*gape))
    # The pedipalps frame the fangs and probe forward at rest.
    loft(mesh, [((20, side*10.7, -5.0), 2.3, 2.2),
                ((26 + feel, side*(13.7 + 2*gape), -7.0), 2.05, 2.0),
                ((32 + feel, side*(12.9 + 4*gape), -9.5 + 1.3*feel), 1.2, 1.28)],
         JOINT, sides=7)


def leg(mesh, hip, knee, foot, side):
    # An arched, thick femur meets a thinner, pointed lower leg.
    femur = .55*hip + .45*knee + np.array([0, 0, 1.8])
    loft(mesh, [(hip, 3.0, 2.9), (femur, 3.35, 2.85), (knee, 2.0, 2.1)],
         FEMUR, sides=8, reference=(1, 0, 0))
    shin = .58*knee + .42*foot + np.array([0, side*2, 1])
    loft(mesh, [(knee, 2.32, 2.35), (shin, 1.83, 1.69), (foot, .98, .9)],
         TIBIA, sides=7, reference=(1, 0, 0))
    toe = foot + np.array([2.3, side*2.3, -.29])
    loft(mesh, [(foot, 1.08, .78), (toe, .94, .66)], JOINT, sides=6)


def make_frame(kind, index, count):
    mesh = Mesh()
    running = kind == 'run'
    moving = running or kind == 'walk'
    cycle = (2 if running else 1) * index / count
    wave = math.tau * cycle
    alive_phase = 0 if kind == 'death' else wave
    roll = pitch = shift = sway = gape = recoil = 0
    bob = .9 * math.sin(alive_phase)
    if moving:
        bob = (2.6 if running else 1.4) * math.sin(2*wave - .6)
        roll = (7 if running else 3) * math.sin(wave)
        pitch = (5 if running else 2) * math.cos(2*wave)
        sway = (2.7 if running else 1.6) * math.sin(wave)
    if kind == 'attack':
        # Front pair rears up in the threat pose, then plants as the fangs
        # snap in on attack04, the one frame that deals damage.
        shift = (0, -1, -3.5, -5, 8, 4, 1, 0)[index]
        bob = (0, 1, 2.5, 4, -2, -1, .25, 0)[index]
        pitch = (0, -5, -11, -16, 11, 7, -2, 0)[index]
        gape = (0, .42, .78, 1, 0, .16, .08, 0)[index]
    if kind == 'pain':
        recoil = (0, 1, -.45, 0)[index]
        shift = -5 * abs(recoil)
        sway, roll, pitch, bob = 3*recoil, 14*recoil, -8*recoil, -3.5*abs(recoil)

    plate(mesh, [(-46, -4, 2.6, 2.3), (-43, -3, 9.7, 6.2), (-38, -1, 15.1, 11.5),
                 (-30, 1, 18.2, 14.6), (-21, 1, 16.2, 13.2), (-14, -1, 11.1, 9.0),
                 (-8, -4, 4.6, 4.5)], ABDOMEN, sides=14)
    transform(mesh, 0, (-9, 0, -3),
              (-.4*roll, -.32*pitch - 4*gape, -6*math.sin(alive_phase) + 9*recoil))
    plate(mesh, [(-13, -4, 4.8, 4.4), (-7, -4, 5.2, 4.2), (-2, -4, 6.8, 5.4)], JOINT)
    plate(mesh, [(-13, -4, 6.2, 5.9), (-8, -3, 11.9, 7.9), (1, -1, 15.8, 9.8),
                 (11, -1, 17.0, 9.75), (20, -2, 14.2, 8.5), (26, -3, 10.3, 6.4),
                 (29, -4, 5.8, 4.4)], CARAPACE, sides=12)
    for side in (-1, 1):
        feel = (.6 if moving else 1.2) * math.sin(2 * alive_phase + side * .8)
        face(mesh, side, gape, feel)

    offset = np.array([shift, sway, bob])
    body_rotation = rotation(roll, pitch)
    transform(mesh, 0, (0, 0, 0), (roll, pitch, 0), offset)
    for side in (-1, 1):
        for i, (x, y, knee_x, knee_y, knee_z, foot_x, foot_y) in enumerate(LEGS):
            swing = lift = splay = 0
            if moving:
                # Alternating quartets with a front-to-back phase offset,
                # giving each side a ripple before the next quartet lands.
                phase = cycle + .5 * ((i + (side == 1)) % 2) - .055*i
                swing, lift = stride(phase, 39 if running else 25,
                                     (12 if running else 7.5) - .9*i, stance=.63)
            if i == 0:
                lift += 17*gape
                swing += .86*shift
                splay += 7*gape
            if i == 1:
                splay += 3*gape
            if kind == 'pain':
                lift += 5 * max(0, side * recoil) * (1 - i / 4)
                splay += 3 * abs(recoil)
            hip = body_rotation @ np.array([x, side*y, -4]) + offset
            knee = np.array([knee_x + .63*swing + .23*shift,
                             side*(knee_y + .6*splay) + .55*sway,
                             knee_z + .55*bob + .46*lift + side*1.2*recoil])
            foot = np.array([foot_x + swing, side*(foot_y + splay), -23 + lift])
            leg(mesh, hip, knee, foot, side)
    if kind == 'death':
        # Preserve the old frame range for corpses in pre-gib saves.
        progress = min(index / 5, 1.0)
        transform(mesh, 0, (0, 0, 0), (180 * progress**2 * (3 - 2*progress), 0, 0))
        points = np.asarray(mesh.vertices)
        points[:, 2] += -24 - points[:, 2].min()
        mesh.vertices = points.tolist()
    return mesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--review', action='store_true')
    args = parser.parse_args()
    model, png = encode_animation(FRAMES, make_frame, SKIN), skin()
    for path, data in ((ROOT/'baseq2'/DIRECTORY/'tris.md2', model), (ROOT/'baseq2'/SKIN, png)):
        if args.verify:
            if path.read_bytes() != data:
                raise ValueError(f'Asset differs: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if args.review:
        poses = ((0, 'Idle'), (11, 'Walk'), (22, 'Run'), (35, 'Threat'), (36, 'Bite'), (41, 'Flinch'))
        review_animation(model, png, 'spider.png', poses, extent=66)
    print('Spider:', MD2.read(model).stats())


if __name__ == '__main__':
    main()
