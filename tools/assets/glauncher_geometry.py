#!/usr/bin/env python3
"""Original low-poly rotary grenade launcher with a recessed wide muzzle.

Artistic coordinates only: X forward, Y left, Z up. The closed M16 mitten
hands cradle the forward grip; a broad drum preserves the existing silhouette.
"""
import math
from m16_geometry import Mesh, add_hands

MUZZLE = (88.,0.,3.6)
REAR_SIGHT = (32.,0.,9.4)
FRONT_SIGHT = (83.,0.,9.4)
GRIP = (34.,0.,-8.)
BARREL_RADIUS = 3.8
BORE_RADIUS = 2.6
DRUM_SIDES = 8
DRUM_CENTER_Z = -3.5
DRUM_FIRST_FRAME = 8
# One complete step between identical resting chamber silhouettes.
DRUM_STEPS = (0., .18, .63, .93, 1.)
# The default mittens do not use this atlas tile.
SIGHT_INSERT_MATERIAL = 'palm'


def add_barrel(m):
    """A closed cup-shaped solid: outer wall, annular lip and recessed bore."""
    sides=8
    m.tube('barrel',[(51,0,3.6,BARREL_RADIUS,BARREL_RADIUS),
                     (88,0,3.6,BARREL_RADIUS,BARREL_RADIUS)],
           sides,'plastic',caps=(True,False))
    def ring(x,r):
        return [(x,r*math.cos(math.pi/8+i*math.tau/sides),
                   3.6+r*math.sin(math.pi/8+i*math.tau/sides)) for i in range(sides)]
    outer,inner,floor=ring(88,BARREL_RADIUS),ring(88,BORE_RADIUS),ring(84.5,BORE_RADIUS)
    for i in range(sides):
        j=(i+1)%sides
        m.poly([outer[i],outer[j],inner[j],inner[i]],'edge',(1,0,0))
        inward=(0,-inner[i][1]-inner[j][1],7.2-inner[i][2]-inner[j][2])
        m.poly([inner[i],inner[j],floor[j],floor[i]],'dark',inward)
    m.poly(floor,'bore',(1,0,0),group='bore_floor')


def add_drum(m):
    """Beveled drum with one repeating molded panel per chamber."""
    m.tube('drum', [(36, 0, DRUM_CENTER_Z, 6.9, 6.9),
                    (37.6, 0, DRUM_CENTER_Z, 8.1, 8.1),
                    (47.8, 0, DRUM_CENTER_Z, 8.1, 8.1),
                    (49.4, 0, DRUM_CENTER_Z, 6.9, 6.9)],
           DRUM_SIDES, 'magazine', caps=(True, True))
    # The tube helper wraps a single texture around the whole shell. Repeat
    # the panel on every facet so resting at either end of a step looks equal.
    start = m.parts[-1]['first_triangle']
    caps = 6 * DRUM_SIDES
    for face in m.uvs[start:start + caps]:
        side_start = min(v for _, v in face)
        for uv in face:
            uv[1] = (uv[1] - side_start) * DRUM_SIDES
    for i in range(start + caps, len(m.faces)):
        m.materials[i] = 'dark'
        m.uvs[i] = [[.5, .5]] * 3


def build_glauncher(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('Expected world or view')
    m=Mesh()
    m.profile('stock',[(1,-9.4),(1,.8),(5,3.1),(22,1.3),(29,2.5),
                       (31,-2.8),(22,-4.0),(10,-5.2)],2.55,'plastic','edge')
    m.profile('butt_plate',[(0,-9.4),(0,1.2),(1.6,1.2),(1.6,-9.4)],
              2.75,'dark','edge')
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.profile('receiver',[(28,-3.8),(28,4.8),(31,6.4),(51,6.4),
                          (55,4.6),(55,-3.8)],3.2,'receiver','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    add_drum(m)
    m.box('drum_latch',(48,-3.6,-2.8),(52,-3.,1.5),'dark')
    add_barrel(m)
    m.tube('fore_end',[(55,0,-.4,3.1,3.1),(72,0,-.4,2.7,2.7)],
           8,'handguard',caps=(True,True))
    m.profile('fore_grip',[(60,-3.0),(65,-3.0),(66,-10.6),(61,-10.6)],
              1.35,'grip','edge')
    for side in (-1,1):
        y=side*1.25
        m.box('rear_sight_'+('left' if side>0 else 'right'),
              (31,y-.42,6.2),(33,y+.42,9.8),'dark')
    m.box('front_sight',(82.4,-.46,6.6),(83.6,.46,8.7),'dark')
    m.box('front_sight_insert',(82.65,-.34,8.66),(83.35,.34,9.4),SIGHT_INSERT_MATERIAL)
    if detail=='view':
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.])
    return result
