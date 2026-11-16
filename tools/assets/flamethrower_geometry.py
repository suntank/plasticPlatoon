#!/usr/bin/env python3
"""Original molded-plastic flame wand, twin fuel tanks and flexible hose.

The wand uses the shared rifle-hand coordinates (X forward, Y left, Z up).
The backpack is authored in the soldier's local frame-zero space, so its
independent torso animation never inherits the gun's aiming motion.
"""
import math
import numpy as np
from m16_geometry import Mesh, add_hands

MUZZLE = (92., 0., 0.)
REAR_SIGHT = (32., 0., 8.6)
FRONT_SIGHT = (82., 0., 8.6)
GRIP = (34., 0., -8.)
INLET = (28., -2.6, -2.5)
PACK_OUTLET = (-10., -7.4, 10.)
HOSE_CONTROLS = (PACK_OUTLET, (-10., -11.5, 4.8),
                 (1.8, -11., 7.2), (8.4, -5.53, 14.45))


def hose_mesh(controls, radius=.65, name='fuel_hose', detail='world', seed=None):
    """Closed six-sided hose with transported rings along a cubic curve."""
    controls = np.asarray(controls, dtype=float)
    times = np.linspace(0., 1., 8)
    points = np.asarray([(1-t)**3 * controls[0] + 3*(1-t)**2*t*controls[1] +
                         3*(1-t)*t*t*controls[2] + t**3*controls[3] for t in times])
    loops = []
    previous = None
    for i, point in enumerate(points):
        tangent = points[min(i+1, len(points)-1)] - points[max(0, i-1)]
        tangent /= np.linalg.norm(tangent)
        if previous is None:
            helper = np.eye(3)[np.argmin(np.abs(tangent))]
            radial = (np.cross(tangent, helper) if seed is None else
                      np.asarray(seed) - np.dot(seed, tangent) * tangent)
        else:
            radial = previous - np.dot(previous, tangent) * tangent
        radial /= np.linalg.norm(radial)
        previous = radial
        other = np.cross(tangent, radial)
        loops.append([point + radius * (radial * math.cos(j*math.tau/6) +
                                        other * math.sin(j*math.tau/6)) for j in range(6)])
    m = Mesh()
    m.loft(name, loops, 'dark')
    result = m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors'] = {'pack_end': points[0].tolist(), 'gun_end': points[-1].tolist()}
    return result


def build_flamethrower(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('Expected world or view')
    m = Mesh()
    m.profile('receiver', [(24., -3.8), (24., 2.8), (29., 4.1), (48., 4.1),
                           (52., 1.5), (50., -3.8)], 2.5, 'receiver', 'edge')
    m.profile('grip', [(29., -15.1), (25.8, -13.8), (31., -4.3), (36., -4.7),
                       (34., -7.2), (32.8, -15.3)], 1.85, 'grip', 'edge')
    m.ring_profile('trigger_guard', [(33.9, -4.2), (43.3, -4.2), (43., -8.5), (33.3, -8.2)],
                   [(35.4, -5.3), (42., -5.3), (41.8, -7.2), (34.7, -7.1)], .8)
    m.tube('fuel_inlet', [(26., -2.6, -2.5, 1.4, 1.4), (30., -2.6, -2.5, 1.4, 1.4)],
           6, 'dark', caps=(True, True))
    m.tube('handguard', [(49., 0., 0., 3.6, 3.6), (55., 0., 0., 3.6, 3.6),
                         (73., 0., 0., 2.8, 2.8)], 8, 'handguard', caps=(True, True))
    m.tube('barrel', [(70., 0., 0., 1.55, 1.55), (86., 0., 0., 1.55, 1.55)],
           8, 'dark', caps=(True, True))
    m.tube('nozzle', [(83., 0., 0., 2.6, 2.6), (92., 0., 0., 3.2, 3.2)],
           8, 'edge', caps=(True, False))
    def rim(x, radius):
        return [(x, radius * math.cos(math.pi/8 + i*math.tau/8),
                 radius * math.sin(math.pi/8 + i*math.tau/8)) for i in range(8)]
    outer, inner, floor = rim(92., 3.2), rim(92., 2.25), rim(87.5, 2.25)
    for i in range(8):
        j = (i+1) % 8
        m.poly([outer[i], outer[j], inner[j], inner[i]], 'edge', (1, 0, 0))
        m.poly([inner[i], inner[j], floor[j], floor[i]], 'dark',
               (0, -inner[i][1]-inner[j][1], -inner[i][2]-inner[j][2]))
    m.poly(floor, 'bore', (1, 0, 0), group='bore_floor')
    m.tube('igniter_pipe', [(55., -2., -3.4, .85, .85), (89., -2., -3.4, .85, .85)],
           4, 'dark', caps=(True, True))
    m.box('igniter_tip', (87.5, -2.9, -4.3), (90., -.9, -1.8), 'edge')
    for side, name in ((-1, 'right'), (1, 'left')):
        y = side * 1.05
        m.box('rear_sight_' + name, (31., y-.4, 3.8), (33., y+.4, 9.), 'dark')
    m.box('front_sight', (81.3, -.5, 2.0), (82.7, .5, 8.6), 'edge')
    if detail == 'view':
        add_hands(m)
    result = m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             inlet=list(INLET), support=[62., 0., -2.])
    return result


def build_backpack():
    m = Mesh()
    m.box('pack_backplate', (-7.2, -6.5, 7.5), (-4.6, 6.5, 20.8), 'grip', 'edge')
    for side, name in ((-1, 'right'), (1, 'left')):
        y = side * 3.45
        loops = []
        for z, radius in ((7.8, 2.55), (9., 3.25), (20.6, 3.25), (22., 2.55)):
            loops.append([(-10. + radius * math.cos(math.pi/8 + i*math.tau/8),
                           y + radius * math.sin(math.pi/8 + i*math.tau/8), z) for i in range(8)])
        m.loft('pack_tank_' + name, loops, 'plastic', uv_axes=(1, 2))
        m.box('pack_valve_' + name, (-11.1, y-1.1, 21.7), (-8.9, y+1.1, 23.2), 'dark', 'edge')
        # Broad closed retaining rails read clearly from a rear camera.
        for z, band in ((10., 'lower'), (18., 'upper')):
            m.box('pack_band_' + name + '_' + band,
                  (-13.5, y-2.9, z), (-12.7, y+2.9, z+1.0), 'dark')
        m.box('pack_shoulder_' + name, (-6.6, y-.65, 19.4), (-3.8, y+.65, 21.4), 'dark')
    m.limb('pack_pressure_bottle', (-10.5, 0., 9.), (-10.5, 0., 20.8),
           1.45, 1.45, 'receiver', 6)
    m.box('pack_manifold', (-11.4, -5., 21.9), (-9.4, 5., 22.8), 'edge')
    m.box('pack_outlet', (-11.1, -7.7, 9.), (-8.9, -5.8, 11.), 'dark', 'edge')
    result = m.finish('world')
    result.pop('rifle_bounds')
    result['anchors'] = {'outlet': list(PACK_OUTLET)}
    return result


def combine_meshes(meshes, detail):
    """Keep named components and one shared atlas while joining MD2 topology."""
    out = dict(detail=detail, vertices=[], faces=[], normals=[], uvs=[], materials=[], parts=[], anchors={})
    for mesh in meshes:
        vertex_base, face_base = len(out['vertices']), len(out['faces'])
        out['vertices'].extend(mesh['vertices'])
        out['normals'].extend(mesh['normals'])
        out['faces'].extend([[i+vertex_base for i in face] for face in mesh['faces']])
        out['uvs'].extend(mesh['uvs'])
        out['materials'].extend(mesh['materials'])
        out['parts'].extend([dict(p, first_triangle=p['first_triangle']+face_base) for p in mesh['parts']])
        out['anchors'].update(mesh['anchors'])
    return out
