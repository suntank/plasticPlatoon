#!/usr/bin/env python3
"""Build the original animated ant MD2 and its skin without external assets.

Coordinates are Quake units, +X forward. Run with --review to inspect decoded
frames; --verify checks that the checked-in assets match this generator.
"""
import argparse
import io
import math

import numpy as np
from PIL import Image

from build_heavy_tank import Mesh
from insect_mesh import encode_animation, loft, plate, review_animation, rotation, stride, transform
from md2_assets import MD2, ROOT

DIRECTORY = 'models/monsters/ant'
SKIN = DIRECTORY + '/skin.png'
# The last six indices are reserved for saves from before instant gibbing.
FRAMES = [('idle', 8), ('walk', 12), ('run', 12), ('attack', 8), ('pain', 4), ('death', 6)]
GASTER, THORAX, JOINT, EYE, HEAD, MANDIBLE, LEG, FEELER = range(8)


def skin():
    image = Image.new('RGB', (256, 256), (27, 28, 30))
    colors = [(39, 41, 44), (43, 44, 47), (25, 26, 27), (24, 25, 28),
              (46, 48, 51), (36, 37, 39), (38, 40, 42), (33, 34, 36)]
    for i, color in enumerate(colors):
        x, y = i % 4 * 64, i // 4 * 64
        for py in range(64):
            for px in range(64):
                u, v = (px - 6) / 52, (py - 6) / 52
                grain = ((px * 13 + py * 7 + px * py * 3) % 11 - 5) * .5
                # A broad satin highlight follows the upper curve of each plate.
                shine = math.exp(-((v - .23) / .17) ** 2)
                value = grain + (24 if i in (GASTER, THORAX, HEAD) else 13) * shine
                if i == GASTER:
                    # Subtle shading along the abdominal sutures.
                    for seam in (.25, .42, .60):
                        value += (7 * math.exp(-((u - seam + .018) / .014) ** 2)
                                  - 10 * math.exp(-((u - seam) / .013) ** 2))
                if i == EYE:
                    lens = math.exp(-((u - .46) / .22) ** 2 - ((v - .24) / .12) ** 2)
                    value = 41 * lens + (4 if (px + py // 3) % 5 < 2 else 0)
                image.putpixel((x + px, y + py), tuple(round(c + value) for c in color))
    out = io.BytesIO()
    image.save(out, format='PNG', compress_level=9)
    return out.getvalue()


def make_frame(kind, index, count):
    m = Mesh()
    phase = 0 if kind == 'death' else math.tau * index / count
    moving = kind in ('walk', 'run')
    running = kind == 'run'
    cycle = (2 if running else 1) * phase
    sway = math.sin(cycle)
    bob = 1.15 * math.sin(phase)
    roll = lateral = pitch = 0
    if moving:
        bob = -(2.5 if running else 1.45) * math.cos(2 * cycle)
        roll = (9 if running else 5) * sway
        lateral = (2.7 if running else 1.45) * sway
        pitch = (-3 if running else 0) + (5 if running else 3) * math.sin(2 * cycle)

    # The mandibles lock shut on attack04, the game's single damage frame.
    lunge = (0, -2, -5, -6, 7, 3.5, 1, 0)[index] if kind == 'attack' else 0
    gape = (0, .45, .9, 1, 0, .16, .12, 0)[index] if kind == 'attack' else 0
    flinch = (0, 1, -.48, 0)[index] if kind == 'pain' else 0
    if kind == 'attack':
        bob = (0, -.7, -2.5, -3, 2.4, .7, -.6, 0)[index]
        pitch = (0, -4, -9, -12, 13, 7, -1, 0)[index]
    if kind == 'pain':
        bob, roll, lateral, pitch = -3 * abs(flinch), 14 * flinch, 3.2 * flinch, -9 * flinch

    # Taper the gaster into a raised petiole. Its weight trails the thorax.
    plate(m, [(-38,-4,1.8,1.9), (-36,-3,6.4,5.6), (-32,-2,10.6,9.8),
              (-25,-1,12.6,12.3), (-18,-1,11.1,10.6), (-12,-2,7.3,7.3),
              (-8,-3,3.4,3.6)], GASTER, sides=12)
    transform(m, 0, (-9, 0, -3),
              (-roll * .5, 9 * sway + 1.2 * lunge, -10 * sway + 17 * flinch))
    plate(m, [(-12,-3,3.4,3.2), (-8,-1,4.1,5.4), (-5,-2,3.3,3.4),
              (-1,-3,4.4,3.8)], JOINT, sides=8)
    plate(m, [(-6,-2,4.3,4.3), (-3,-1,6.4,6.2), (2,0,7.9,8.0),
              (7,0,8.5,7.4), (12,-1,6.1,5.5), (14,-1,4.2,3.9)], THORAX)

    # Stretch the neck into the bite. The rest of the head moves as one piece.
    scan = 11 * math.sin(phase) if kind == 'idle' else -4 * sway
    head_angles = (-roll * .45, -2.0 * lunge + 8 * abs(flinch), scan - 22 * flinch)
    head_offset = (lunge + (1.5 if running else 0) - 4.5 * abs(flinch), 0, 0)
    head_start = len(m.vertices)
    plate(m, [(10,-1,3.8,3.8), (13,-.5,5.3,4.7), (16,-.2,7.8,7.2),
              (20,0,9.0,8.3), (24,-.6,8.1,7.0), (27,-2,5.1,4.5),
              (28,-2.5,3.8,3.5)], HEAD, sides=12)
    for side in (-1, 1):
        loft(m, [((17,side*7.2,1.8),1.25,1.4), ((19.2,side*8.2,2.25),2.05,2.75),
                 ((22.3,side*8.05,2.0),1.7,2.25), ((23.6,side*7.5,1.6),.65,.85)], EYE)
        jaw_start = len(m.vertices)
        loft(m, [((24,side*5.3,-4.2),2.3,1.85), ((28.5,side*7.7,-5.2),2.65,1.7),
                 ((33,side*7.0,-5.8),1.85,1.32), ((36.3,side*4.4,-5.5),1.15,.85),
                 ((37,side*1.15,-5),.62,.58)], MANDIBLE, sides=6)
        transform(m, jaw_start, (24, side*5.3, -4.2), (0, -4*gape, side*38*gape))

        # The long flagellum sweeps with a slight lag behind the shorter scape.
        twitch = math.sin(cycle + side * 1.15)
        flick = math.sin(phase * 2 - .8 + side * 1.4)
        elbow = (27.9, side*(8.5 + 2.8*twitch + 2*gape), 11 + 2*flick)
        loft(m, [((22,side*4.6,5.6),1.15,1.05), ((25.5,side*6.3,8.6),.9,.88),
                 (elbow,.86,.82)], FEELER, sides=6)
        loft(m, [(elbow,.87,.84),
                 ((32,side*(11+4*twitch+2.5*gape),14+2.5*flick),.75,.74),
                 ((37.5-2.5*gape,side*(13+5*twitch+3*gape),15+3.4*flick-2.8*lunge/7),.66,.65),
                 ((42-3*gape,side*(14+5*twitch+4*gape),13.5+4*flick-3.5*lunge/7),.57,.57)],
             FEELER, sides=6)
    transform(m, head_start, (12, 0, -1), head_angles, head_offset)
    # A flexible neck spans the full windup/reach without exposing a mesh gap.
    neck = rotation(*head_angles) @ np.array([4, 0, 2]) + np.array([12, 0, -1]) + head_offset
    loft(m, [((7,0,-1),4.6,4.5), (neck,4.4,4.2)], JOINT)

    offset = np.array([0, lateral, bob])
    body_rotation = rotation(roll, pitch)
    transform(m, 0, (0, 0, 0), (roll, pitch, 0), offset)
    for side in (-1, 1):
        for leg, (x, knee_x, foot_x, spread) in enumerate(((8,17,23,23), (1,0,1,29), (-5,-17,-24,24))):
            swing, rise = stride(cycle/math.tau + .5*((leg + (side == 1)) % 2),
                                 31 if running else 22, 11 if running else 6.5) if moving else (0, 0)
            if leg == 0:
                swing += .7*lunge
                rise += 5*gape
            hip = body_rotation @ np.array([x, side*6.4, -3]) + offset
            knee = np.array([knee_x + .57*swing, side*(.65*spread + 1.9*abs(flinch)) + lateral*.65,
                             1 + .65*bob + .48*rise - 3*abs(flinch)])
            foot = np.array([foot_x+swing, side*(spread + 2.1*abs(flinch)), -23+rise])
            # Broad femur, narrow tibia, and a low, hooked tarsus.
            upper = (hip+knee)*.5 + np.array([0, 0, 1.5])
            loft(m, [(hip,2.15,1.9), (upper,2.35,1.9), (knee,1.4,1.35)],
                 LEG, sides=7, reference=(1,0,0))
            shin = .55*knee + .45*foot + np.array([0, side*.8, 0])
            loft(m, [(knee,1.56,1.6), (shin,1.24,1.09), (foot,.59,.65)],
                 LEG, sides=7, reference=(1,0,0))
            toe = foot + np.array([2.8, side*2.05, -.42])
            loft(m, [(foot,.74,.68), ((foot+toe)*.5,.68,.62), (toe,.55,.52)], JOINT, sides=6)
    if kind == 'death':
        # Legacy corpse roll for older saves. Live deaths switch straight to gibs.
        progress = index / (count - 1)
        transform(m, 0, (0, 0, 0), (180 * progress**2 * (3 - 2*progress), 0, 0))
        points = np.asarray(m.vertices)
        points[:, 2] += -24 - points[:, 2].min()
        m.vertices = points.tolist()
    return m


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
        poses = ((0, 'Idle'), (11, 'Walk'), (22, 'Run'), (35, 'Windup'), (36, 'Bite'), (41, 'Flinch'))
        review_animation(model, png, 'ant.png', poses, extent=47)
    print('Ant:', MD2.read(model).stats())


if __name__ == '__main__':
    main()
