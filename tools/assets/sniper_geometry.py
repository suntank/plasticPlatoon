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
SCOPE_RINGS = ((28., 5.03), (29.65, 5.33), (36.5, 4.78), (48., 5.62))


def add_scope(m, detail):
    """Outer casing, inward-facing channel and annular end lips; no glass cap."""
    sides = 12 if detail == 'view' else 8
    def loop(x, radius):
        return [(x, radius * math.cos(math.pi / sides + i * math.tau / sides),
                 12. + radius * math.sin(math.pi / sides + i * math.tau / sides))
                for i in range(sides)]
    outer = [loop(x, radius) for x, radius in SCOPE_RINGS]
    rear = loop(REAR_SIGHT[0], 4.20)
    front = loop(FRONT_SIGHT[0], 4.70)
    length = FRONT_SIGHT[0] - REAR_SIGHT[0]
    first = len(m.faces)
    m.tube('scope', [(x, 0., 12., radius, radius) for x, radius in SCOPE_RINGS],
           sides, 'magazine', phase=math.pi / sides)
    for face in range(first, len(m.faces)):
        m.uvs[face] = [[(m.vertices[index][0] - REAR_SIGHT[0]) / length, v]
                       for index, (_, v) in zip(m.faces[face], m.uvs[face])]
    for i in range(sides):
        j = (i + 1) % sides
        normal = (0., -rear[i][1] - rear[j][1], 24. - rear[i][2] - rear[j][2])
        m.poly([rear[i], rear[j], front[j], front[i]], 'bore', normal, group='inner_wall')
    for exterior, interior, direction in ((outer[0], rear, -1), (outer[-1], front, 1)):
        for i in range(sides):
            j = (i + 1) % sides
            m.poly([exterior[i], exterior[j], interior[j], interior[i]],
                   'edge', (direction, 0., 0.), group='rim')
    # A small central gap leaves the exact sight ray clear. Each post is a
    # solid prism, wide enough to survive every MD2 byte-quantized held pose.
    half_post = .18 if detail == 'view' else .35
    for side, name in ((-1, 'right'), (1, 'left')):
        low, high = sorted((side * .55, side * 4.73))
        m.box('reticle_' + name, (43., low, 12. - half_post), (44.5, high, 12. + half_post), 'bore')
    for side, name in ((-1, 'lower'), (1, 'upper')):
        low, high = sorted((12. + side * .55, 12. + side * 4.73))
        m.box('reticle_' + name, (43., -half_post, low), (44.5, half_post, high), 'bore')


def build_sniper(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('Expected world or view')
    m = Mesh()
    stock = [(0., 2.24, -3.1, 6.10), (2., 2.90, -2.85, 7.5),
             (8., 2.73, -2.42, 6.85), (30., 1.45, -.6, 2.45)]
    m.loft('stock', [[(x, w * math.cos(i * math.tau / 6), mid + h * math.sin(i * math.tau / 6))
                      for i in range(6)] for x, w, mid, h in stock], 'plastic', uv_axes=(0, 2))
    section = [(-.64, -1.), (.64, -1.), (1., -.55), (1., .57),
               (.60, 1.), (-.60, 1.), (-1., .57), (-1., -.55)]
    receiver = [(26., 1.64, -.12, 3.43), (32., 2.74, .08, 5.08),
                (53.8, 2.30, -.15, 4.11)]
    rings = [[(x + .13 * h * z, w * y, mid + h * z) for y, z in section]
             for x, w, mid, h in receiver]
    first = len(m.faces)
    m.loft('receiver', rings, 'plastic', uv_axes=(0, 2))
    for band in range(len(rings) - 1):
        for side in (2, 6):
            face = first + 2 * (band * len(section) + side)
            m.materials[face:face + 2] = ['receiver'] * 2
    m.profile('grip', [(29, -15.1), (25.8, -13.8), (31, -4.3), (36, -4.7),
                       (34, -7.2), (32.8, -15.3)], 1.85, 'grip', 'edge')
    m.ring_profile('trigger_guard', [(33.9, -4.2), (43.3, -4.2), (43, -8.5), (33.3, -8.2)],
                   [(35.4, -5.3), (42, -5.3), (41.8, -7.2), (34.7, -7.1)], .72)
    m.profile('magazine', [(43.8, -3.8), (50.9, -3.7), (51.8, -9.05),
                           (50.6, -10.35), (45.4, -10.6), (44.4, -9.8)],
              2.02, 'grip', 'edge')
    m.tube('handguard', [(51.7, 0, .1, 2.65, 2.95), (55.7, 0, 0, 3.7, 3.65),
                         (76, 0, .6, 2.47, 2.60)], 8, 'handguard', caps=(True, True))
    m.tube('barrel', [(72, 0, 1.8, 1.46, 1.46), (108, 0, 1.8, 1.05, 1.05)],
           8, 'dark', caps=(True, True))
    # Recessed muzzle is a cup-shaped closed solid, rather than a flat decal.
    m.tube('muzzle_brake', [(106, 0, 1.8, 1.55, 1.55), (112, 0, 1.8, 1.8, 1.8)],
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
    for x, name, top in ((33, 'rear', 7.63), (44, 'front', 7.29)):
        m.profile('scope_mount_' + name,
                  [(x - .65, 3.8), (x + 2.9, 3.8), (x + 2.35, top), (x + .45, top)],
                  1.52, 'dark', 'edge')
    add_scope(m, detail)
    m.loft('scope_turret', [[(x + rx * math.cos(i * math.tau / 8), ry * math.sin(i * math.tau / 8), z)
                             for i in range(8)]
                            for z, x, rx, ry in ((16.56, 39.5, 2.6, 2.20), (18.5, 39.5, 2.02, 1.72))],
           'grip')
    m.limb('bolt_handle', (39, -2.5, 2.0), (38, -6., -.5), .8, 1.05, 'dark', 4)
    m.limb('bolt_knob', (38.15, -5.35, -.14), (37.78, -7.12, -.93), 1.15, .86, 'grip')
    if detail == 'view':
        add_hands(m)
    result = m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             support=[62., 0., -2.])
    return result
