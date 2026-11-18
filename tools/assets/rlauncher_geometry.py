#!/usr/bin/env python3
"""Original molded-plastic bazooka with flared ends and a real open bore.

Artistic coordinates only: X forward, Y left, Z up. The tube is a closed-wall
solid around a through-bore, with the existing M16 mittens on the two grips.
"""
import math
from m16_geometry import Mesh, add_hands
from shotgun_parts import oval_sections

MUZZLE = (100.,0.,3.6)
REAR_SIGHT = (32.,0.,10.8)
FRONT_SIGHT = (89.,0.,10.8)
GRIP = (34.,0.,-8.)
BORE_RADIUS = 3.3


def add_tube(m, sides):
    """Watertight tube wall, annular end rims and continuous dark inner bore."""
    # Rolled rims soften the two flares while the middle keeps a slim profile.
    profile = [(0,5.55),(1.75,5.94),(8.1,4.56),(90.8,4.43),
               (94,4.60),(97.6,5.72),(99.1,6.05),(100,5.77)]
    phase = math.pi/sides
    first = len(m.faces)
    m.tube('launch_tube', [(x,0,3.6,r,r) for x,r in profile],
           sides,'magazine',phase=phase)
    # Paint bands by distance along the tube, including its short rolled rims.
    for face in range(first,len(m.faces)):
        m.uvs[face] = [[m.vertices[index][0]/100.,v]
                       for index, (_,v) in zip(m.faces[face],m.uvs[face])]

    back,front = oval_sections([(0,0,3.6,BORE_RADIUS,BORE_RADIUS),
                                (100,0,3.6,BORE_RADIUS,BORE_RADIUS)],sides)
    outer_back,outer_front = oval_sections([
        (0,0,3.6,profile[0][1],profile[0][1]),
        (100,0,3.6,profile[-1][1],profile[-1][1])],sides)
    for i in range(sides):
        j=(i+1)%sides
        inward=(0,-back[i][1]-back[j][1],7.2-back[i][2]-back[j][2])
        m.poly([back[i],back[j],front[j],front[i]],'bore',inward,group='inner_wall')
        m.poly([outer_back[i],outer_back[j],back[j],back[i]],'edge',(-1,0,0),group='rear_rim')
        m.poly([outer_front[i],outer_front[j],front[j],front[i]],'edge',(1,0,0),group='front_rim')


def build_rlauncher(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('Expected world or view')
    close = detail == 'view'
    m = Mesh()
    add_tube(m, 12 if close else 8)
    # The shallow mounting housing flows back into a rounded shoulder pad.
    section = [(-.64,-1),(.64,-1),(1,-.44),(1,.47),
               (.67,1),(-.67,1),(-1,.47),(-1,-.44)]
    stations = [(26.3,1.83,-2.8,1.23),(31.8,2.63,-2.45,2.57),
                (47.8,2.67,-2.42,2.54),(52.7,1.82,-2.92,1.78)]
    rings = [[(x+.16*h*z,w*y,mid+h*z) for y,z in section] for x,w,mid,h in stations]
    start = len(m.faces)
    m.loft('receiver', rings, 'plastic', uv_axes=(0,2))
    for band in range(len(rings)-1):
        for side in (2,6):
            face = start+2*(band*len(section)+side)
            m.materials[face:face+2] = ['receiver']*2
    pad = [(16.,0,-1.64,1.55,1.25),(21.,0,-2.48,2.98,2.05),
           (29.1,0,-2.17,2.35,1.86)]
    m.loft('shoulder_rest', oval_sections(pad,6), 'grip', uv_axes=(0,2))
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-6.9),(41.4,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-6.35),(40.75,-7.2),(34.7,-7.1)],.72)
    m.tube('fore_end',[(54.3,0,-.6,2.36,2.64),(57.,0,-.6,3.15,3.14),
                      (69.6,0,-.6,2.85,2.9),(72.4,0,-.6,2.39,2.43)],
           8,'handguard',caps=(True,True))
    m.profile('fore_grip',[(60,-3.0),(65,-3.0),(65.9,-9.6),(65.05,-10.45),(61.1,-10.45),(60.55,-9.7)],
              1.35,'grip','edge')
    # Real sights stand above both flares, with an open central notch.
    for side in (-1,1):
        y=side*1.05
        m.profile('rear_sight_'+('left' if side>0 else 'right'),
                  [(30.2,7.35),(34.1,7.50),(33.45,11.04),(32.02,11.20)],
                  .32,'dark','dark',y=y)
    m.profile('front_sight',[(87.6,7.4),(90.45,7.4),(89.55,10.8),(88.57,10.8)],
              .40,'edge','edge')
    if close:
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.],rear_opening=[0.,0.,3.6])
    return result
