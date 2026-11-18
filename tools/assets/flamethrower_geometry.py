#!/usr/bin/env python3
"""Original molded-plastic flame wand, twin fuel tanks and flexible hose.

The wand uses the shared rifle-hand coordinates (X forward, Y left, Z up).
The backpack is authored in the soldier's local frame-zero space, so its
independent torso animation never inherits the gun's aiming motion.
"""
import math
import numpy as np
from m16_geometry import Mesh, add_hands
from flamethrower_tanks import add_tank

MUZZLE = (92., 0., 0.)
REAR_SIGHT = (32., 0., 7.65)
FRONT_SIGHT = (82., 0., 7.65)
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
    close = detail == 'view'
    m = Mesh()
    section = [(-.66,-1),(.66,-1),(1,-.55),(1,.45),
               (.65,1),(-.65,1),(-1,.45),(-1,-.55)]
    stations = [(24.6,1.79,-.30,2.62),(30.75,2.43,.03,3.99),
                (44.5,2.57,.14,3.92),(51.5,1.89,-.07,2.47)]
    rings = [[(x+.21*h*z,w*y,mid+h*z) for y,z in section] for x,w,mid,h in stations]
    start = len(m.faces)
    m.loft('receiver', rings, 'plastic', uv_axes=(0,2))
    for band in range(len(rings)-1):
        for side in (2,6):
            face = start+2*(band*len(section)+side)
            m.materials[face:face+2] = ['receiver']*2
    m.profile('grip', [(29., -15.1), (25.8, -13.8), (31., -4.3), (36., -4.7),
                       (34., -7.2), (32.8, -15.3)], 1.85, 'grip', 'edge')
    outer = [(33.9,-4.2),(43.3,-4.2),(43.,-8.5),(33.3,-8.2)]
    inner = [(35.4,-5.3),(42.,-5.3),(41.8,-7.2),(34.7,-7.1)]
    if close:
        outer[2:3] = [(43.,-6.9),(41.4,-8.5)]
        inner[2:3] = [(41.8,-6.35),(40.75,-7.2)]
    m.ring_profile('trigger_guard', outer, inner, .8)
    m.tube('fuel_inlet', [(26., -2.6, -2.5, 1.4, 1.4), (30., -2.6, -2.5, 1.4, 1.4)],
           6, 'dark', caps=(True, True))
    m.tube('handguard', [(49.,0.,0.,2.46,2.54),(55.,0.,0.,3.6,3.6),
                         (73.,0.,0.,2.8,2.73)], 8,'handguard', caps=(True,True))
    m.tube('barrel', [(70., 0., 0., 1.55, 1.55), (86., 0., 0., 1.55, 1.55)],
           8, 'dark', caps=(True, True))
    # A rounded collar expands into a flared lip and a recessed bell.
    sides = 10 if close else 8
    phase = math.pi/sides
    m.tube('nozzle', [(82.,0.,0.,2.27,2.27),(88.9,0.,0.,3.89,3.89),
                     (92.,0.,0.,3.65,3.65)], sides,'palm',
           caps=(True,False), phase=phase)
    def rim(x, radius):
        return [(x, radius*math.cos(phase+i*math.tau/sides),
                 radius*math.sin(phase+i*math.tau/sides)) for i in range(sides)]
    outer, inner, floor = rim(92.,3.65),rim(92.,2.48),rim(87.5,2.18)
    for i in range(sides):
        j = (i+1) % sides
        m.poly([outer[i],outer[j],inner[j],inner[i]], 'edge',(1,0,0),group='rim')
        m.poly([inner[i],inner[j],floor[j],floor[i]], 'bore',
               (0,-inner[i][1]-inner[j][1],-inner[i][2]-inner[j][2]),group='inner_wall')
    m.poly(floor, 'bore', (1, 0, 0), group='bore_floor')
    m.tube('igniter_pipe', [(55., -2., -3.4, .85, .85), (89., -2., -3.4, .85, .85)],
           4, 'dark', caps=(True, True))
    m.profile('igniter_tip',[(87.3,-4.3),(89.65,-4.3),(90.15,-2.53),(88.4,-1.95)],
              1.,'edge','dark',y=-2.)
    for side, name in ((-1, 'right'), (1, 'left')):
        y = side * 1.05
        m.profile('rear_sight_'+name,[(30.6,3.45),(34.1,3.57),(33.31,7.67),(31.95,7.88)],
                  .32,'dark','dark',y=y)
    m.profile('front_sight',[(80.72,1.25),(83.55,1.31),(82.45,7.65),(81.72,7.65)],
              .38,'edge','edge')
    if close:
        add_hands(m)
    result = m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             inlet=list(INLET), support=[62., 0., -2.])
    return result


def build_backpack():
    m = Mesh()
    section = [(-5.2,7.5),(5.2,7.5),(6.5,9.4),(6.5,18.6),
               (4.8,20.8),(-4.8,20.8),(-6.5,18.6),(-6.5,9.4)]
    m.loft('pack_backplate', [[(x,y*scale,14.15+(z-14.15)*scale) for y,z in section]
                              for x,scale in ((-7.2,1.),(-4.6,.90))], 'grip')
    for side, name in ((-1, 'right'), (1, 'left')):
        y = side * 3.45
        add_tank(m,'pack_tank_'+name,(-10.,y),'magazine')
        m.profile('pack_valve_'+name,[(-11.2,21.57),(-8.82,21.65),(-9.15,23.16),(-10.71,23.19)],
                  1.07,'dark','edge',y=y)
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
