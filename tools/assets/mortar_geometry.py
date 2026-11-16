#!/usr/bin/env python3
"""Original low-poly mortar with a deep bore, circular plate and splayed bipod.

X is forward, Y left, Z up in artistic rifle-hand coordinates. Carried models
keep the baseplate low and support legs below the tube; the pickup stands on
its plate with the tube elevated and the bipod deployed.
"""
import math
import numpy as np
from m16_geometry import Mesh, add_hands

MUZZLE = (86., 0., 2.8)
REAR_SIGHT = (32., 0., 10.2)
FRONT_SIGHT = (80., 0., 10.2)
GRIP = (34., 0., -8.)
BORE_RADIUS = 3.5
PICKUP_ELEVATION = math.radians(55.)
PICKUP_ROTATION = np.array([[math.cos(PICKUP_ELEVATION), 0., math.sin(PICKUP_ELEVATION)],
                            [0., 1., 0.],
                            [-math.sin(PICKUP_ELEVATION), 0., math.cos(PICKUP_ELEVATION)]])


def deployed_point(point):
    return (np.asarray(point) - [18., 0., 2.8]) @ PICKUP_ROTATION + [0., 0., 4.]


def add_barrel(m):
    m.tube('mortar_tube', [(18., 0., 2.8, 4.3, 4.3), (81., 0., 2.8, 4.3, 4.3),
                          (86., 0., 2.8, 5.3, 5.3)], 8, 'plastic', caps=(True, False))
    def ring(x, radius):
        return [(x, radius * math.cos(math.pi/8 + i*math.tau/8),
                 2.8 + radius * math.sin(math.pi/8 + i*math.tau/8)) for i in range(8)]
    outer, inner, floor = ring(86., 5.3), ring(86., BORE_RADIUS), ring(23., BORE_RADIUS)
    for i in range(8):
        j = (i+1) % 8
        m.poly([outer[i], outer[j], inner[j], inner[i]], 'edge', (1., 0., 0.))
        m.poly([inner[i], inner[j], floor[j], floor[i]], 'dark',
               (0., -inner[i][1]-inner[j][1], 5.6-inner[i][2]-inner[j][2]))
    m.poly(floor, 'bore', (1., 0., 0.), group='bore_floor')


def build_mortar(detail='world'):
    if detail not in ('world', 'view', 'pickup'):
        raise ValueError('Expected world, view or pickup')
    m = Mesh()
    add_barrel(m)
    m.profile('receiver', [(27., -5.5), (27., -1.4), (49., -1.4),
                           (52., -3.0), (51., -5.5)], 2.5, 'receiver', 'edge')
    m.profile('grip', [(29., -15.1), (25.8, -13.8), (31., -4.3), (36., -4.7),
                       (34., -7.2), (32.8, -15.3)], 1.85, 'grip', 'edge')
    m.ring_profile('trigger_guard', [(33.9, -4.2), (43.3, -4.2), (43., -8.5), (33.3, -8.2)],
                   [(35.4, -5.3), (42., -5.3), (41.8, -7.2), (34.7, -7.1)], .8)
    m.profile('fore_grip', [(54., -1.5), (70., -1.5), (70., -4.9), (55., -4.9)],
              2.3, 'handguard', 'edge')
    m.box('bipod_mount', (64., -5., -3.1), (68., 5., -1.), 'dark', 'edge')
    for side, name in ((-1, 'right'), (1, 'left')):
        y = side * 1.1
        m.box('rear_sight_' + name, (31., y-.45, 6.5), (33., y+.45, 10.8), 'dark')
    m.box('front_sight', (79.3, -.5, 6.8), (80.7, .5, 10.2), 'edge')
    if detail == 'view':
        add_hands(m)
    core = m.finish(detail)
    core.pop('rifle_bounds')
    core['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                           support=[62., 0., -2.])
    support = Mesh()
    if detail == 'pickup':
        core['vertices'] = np.asarray(core['vertices']) @ PICKUP_ROTATION - np.array([18., 0., 2.8]) @ PICKUP_ROTATION + [0., 0., 4.]
        core['normals'] = np.asarray(core['normals']) @ PICKUP_ROTATION
        core['anchors'] = {name: deployed_point(point).tolist() for name,point in core['anchors'].items()}
        loops = [[(radius*math.cos(math.pi/8 + i*math.tau/8),
                   radius*math.sin(math.pi/8 + i*math.tau/8), z) for i in range(8)]
                 for z,radius in ((0.,21.), (2.,21.), (3.,18.8))]
        support.loft('baseplate', loops, 'plastic', uv_axes=(0, 1))
        support.limb('baseplate_socket', (0.,0.,2.), (0.,0.,5.5), 2.6, 2.6, 'dark', 6)
    else:
        support.tube('baseplate', [(18.,0.,-10.,14.,14.), (21.,0.,-10.,14.,14.)],
                     8, 'plastic', caps=(True, True))
        support.limb('baseplate_hinge', (20.,0.,-5.), (19.,0.,2.8),
                     2., 2.4, 'dark', 6)
    for side, name in ((-1, 'right'), (1, 'left')):
        if detail == 'pickup':
            start = deployed_point((66., side*4.5, -2.))
            end = np.array([47., side*18., 1.6])
        else:
            start = np.array([66., side*4.5, -2.])
            end = np.array([74., side*14., -24.])
        support.limb('bipod_' + name, start, end, 1.25, 1.05, 'dark', 4)
        support.box('bipod_foot_' + name, end + [-2.,-2.,-1.], end + [2.,2.,.5], 'edge')
    if detail == 'pickup':
        brace_center = deployed_point((66.,0.,-2.)) * .5 + [23.5,0.,.8]
        half_width = 11.25
    else:
        brace_center = np.array([70.,0.,-13.])
        half_width = 9.25
    support.limb('bipod_crossbrace', brace_center+[0.,-half_width,0.],
                 brace_center+[0.,half_width,0.], .8, .8, 'dark', 4)
    extra = support.finish(detail)
    vertex_base, face_base = len(core['vertices']), len(core['faces'])
    for key in ('vertices', 'normals', 'uvs', 'materials'):
        core[key] = list(core[key]) + list(extra[key])
    core['faces'] += [[i+vertex_base for i in face] for face in extra['faces']]
    core['parts'] += [dict(part, first_triangle=part['first_triangle']+face_base) for part in extra['parts']]
    return core
