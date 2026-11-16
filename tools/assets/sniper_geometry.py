#!/usr/bin/env python3
"""Original low-poly sniper rifle, open optic and existing molded rifle hands.

Artistic coordinates only: X forward, Y left, Z up. The scope is a closed
annular solid with an empty optical channel and four physical reticle posts.
"""
import math
from m16_geometry import Mesh, add_hands

MUZZLE = (112., 0., 1.8)
REAR_SIGHT = (28., 0., 12.)
FRONT_SIGHT = (48., 0., 12.)
GRIP = (34., 0., -8.)
SCOPE_RINGS = ((28., 5.4, 4.5), (32., 5.0, 4.1),
               (39., 5.0, 4.1), (48., 6.0, 5.1))


def add_scope(m, detail):
    """Outer casing, inward-facing channel and annular end lips; no glass cap."""
    sides = 8
    def loop(x, radius):
        return [(x, radius * math.cos(math.pi / 8 + i * math.tau / sides),
                 12. + radius * math.sin(math.pi / 8 + i * math.tau / sides))
                for i in range(sides)]
    outer = [loop(x, r) for x, r, _ in SCOPE_RINGS]
    inner = [loop(x, r) for x, _, r in SCOPE_RINGS]
    m.part('scope')
    for loops, inward in ((outer, False), (inner, True)):
        for a, b in zip(loops, loops[1:]):
            for i in range(sides):
                j = (i + 1) % sides
                normal = (0., a[i][1] + a[j][1], a[i][2] + a[j][2] - 24.)
                if inward:
                    normal = tuple(-v for v in normal)
                m.poly([a[i], a[j], b[j], b[i]],
                       'dark' if inward else 'receiver', normal)
    for k, direction in ((0, -1), (-1, 1)):
        for i in range(sides):
            j = (i + 1) % sides
            m.poly([outer[k][i], outer[k][j], inner[k][j], inner[k][i]],
                   'edge', (direction, 0., 0.))
    # A small central gap leaves the exact sight ray clear. Each post is a
    # solid prism, wide enough to survive every MD2 byte-quantized held pose.
    half_post = .18 if detail == 'view' else .35
    for side, name in ((-1, 'right'), (1, 'left')):
        low, high = sorted((side * .55, side * 4.25))
        m.box('reticle_' + name, (43., low, 12. - half_post), (44.5, high, 12. + half_post), 'bore')
    for side, name in ((-1, 'lower'), (1, 'upper')):
        low, high = sorted((12. + side * .55, 12. + side * 4.25))
        m.box('reticle_' + name, (43., -half_post, low), (44.5, half_post, high), 'bore')


def build_sniper(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('Expected world or view')
    m = Mesh()
    m.profile('stock', [(0, -9.8), (0, 3.8), (5, 4.6), (24, 2.5),
                        (30, .8), (29, -3.4), (22, -4.8)], 2.8, 'plastic', 'edge')
    m.profile('butt_plate', [(0, -9.8), (1.4, -9.5), (1.4, 3.8), (0, 3.8)],
              2.95, 'dark', 'edge')
    m.profile('receiver', [(26, -4.5), (26, 3.5), (30, 5.2), (50, 5.2),
                           (54, 2.6), (53, -3.8), (45, -4.8)], 2.65, 'receiver', 'edge')
    m.profile('grip', [(29, -15.1), (25.8, -13.8), (31, -4.3), (36, -4.7),
                       (34, -7.2), (32.8, -15.3)], 1.85, 'grip', 'edge')
    m.ring_profile('trigger_guard', [(33.9, -4.2), (43.3, -4.2), (43, -8.5), (33.3, -8.2)],
                   [(35.4, -5.3), (42, -5.3), (41.8, -7.2), (34.7, -7.1)], .72)
    m.profile('magazine', [(44, -4.), (51, -3.8), (51.5, -10.2), (44.5, -10.6)],
              2.1, 'magazine', 'edge')
    m.tube('handguard', [(52, 0, 0, 3.6, 3.6), (55, 0, 0, 3.6, 3.6),
                         (76, 0, .6, 2.6, 2.8)], 8, 'handguard', caps=(True, True))
    m.tube('barrel', [(72, 0, 1.8, 1.35, 1.35), (108, 0, 1.8, 1.1, 1.1)],
           8, 'dark', caps=(True, True))
    # Recessed muzzle is a cup-shaped closed solid, rather than a flat decal.
    m.tube('muzzle_brake', [(106, 0, 1.8, 1.8, 1.8), (112, 0, 1.8, 1.8, 1.8)],
           8, 'edge', caps=(True, False))
    def rim(x, r):
        return [(x, r * math.cos(math.pi / 8 + i * math.tau / 8),
                 1.8 + r * math.sin(math.pi / 8 + i * math.tau / 8)) for i in range(8)]
    outer, inner, floor = rim(112, 1.8), rim(112, .95), rim(109, .95)
    for i in range(8):
        j = (i + 1) % 8
        m.poly([outer[i], outer[j], inner[j], inner[i]], 'edge', (1, 0, 0))
        m.poly([inner[i], inner[j], floor[j], floor[i]], 'dark',
               (0, -inner[i][1] - inner[j][1], 3.6 - inner[i][2] - inner[j][2]))
    m.poly(floor, 'bore', (1, 0, 0), group='bore_floor')
    for x, name in ((33, 'rear'), (44, 'front')):
        m.box('scope_mount_' + name, (x, -1.6, 4.6), (x + 2.4, 1.6, 7.6), 'dark')
    add_scope(m, detail)
    m.box('scope_turret', (38, -1.7, 16.4), (43, 1.7, 19.), 'dark', 'edge')
    m.limb('bolt_handle', (39, -2.5, 2.0), (38, -6., -.5), .8, 1.05, 'dark', 4)
    m.box('bolt_knob', (36.8, -7., -1.5), (39.2, -5., .7), 'grip', 'edge')
    if detail == 'view':
        add_hands(m)
    result = m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             support=[62., 0., -2.])
    return result
