#!/usr/bin/env python3
"""Original molded-plastic bazooka with flared ends and a real open bore.

Artistic coordinates only: X forward, Y left, Z up. The tube is a closed-wall
solid around a through-bore, with the existing M16 mittens on the two grips.
"""
import math
from m16_geometry import Mesh, add_hands

MUZZLE = (100.,0.,3.6)
REAR_SIGHT = (32.,0.,10.8)
FRONT_SIGHT = (89.,0.,10.8)
GRIP = (34.,0.,-8.)
BORE_RADIUS = 3.3


def add_tube(m):
    """Watertight tube wall, annular end rims and continuous dark inner bore."""
    sides=8
    m.tube('launch_tube',[(0,0,3.6,5.6,5.6),(8,0,3.6,4.5,4.5),
                           (92,0,3.6,4.5,4.5),(100,0,3.6,6.,6.)],
           sides,'plastic',caps=(False,False))
    def ring(x,r):
        return [(x,r*math.cos(math.pi/8+i*math.tau/sides),
                   3.6+r*math.sin(math.pi/8+i*math.tau/sides)) for i in range(sides)]
    back,front=ring(0,BORE_RADIUS),ring(100,BORE_RADIUS)
    outside_back,outside_front=ring(0,5.6),ring(100,6.)
    for i in range(sides):
        j=(i+1)%sides
        inward=(0,-back[i][1]-back[j][1],7.2-back[i][2]-back[j][2])
        m.poly([back[i],back[j],front[j],front[i]],'dark',inward)
        m.poly([outside_back[i],outside_back[j],back[j],back[i]],'edge',(-1,0,0))
        m.poly([outside_front[i],outside_front[j],front[j],front[i]],'edge',(1,0,0))


def build_rlauncher(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('Expected world or view')
    m=Mesh()
    add_tube(m)
    # Small mounting housing and shoulder pad beneath the long launch tube.
    m.profile('receiver',[(27,-4.8),(27,-.5),(31,1.2),(49,1.2),
                          (52,-1.5),(52,-4.8)],2.7,'receiver','edge')
    m.profile('shoulder_rest',[(16,-.7),(29,-.7),(29,-4.5),(20,-4.5)],
              3.0,'grip','edge')
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    m.tube('fore_end',[(55,0,-.6,3.1,3.1),(72,0,-.6,2.7,2.7)],
           8,'handguard',caps=(True,True))
    m.profile('fore_grip',[(60,-3.0),(65,-3.0),(66,-10.6),(61,-10.6)],
              1.35,'grip','edge')
    # Real sights stand above both flares, with an open central notch.
    for side in (-1,1):
        y=side*1.05
        m.box('rear_sight_'+('left' if side>0 else 'right'),
              (31,y-.35,7.2),(33,y+.35,11.4),'dark')
    m.box('front_sight',(88.4,-.4,7.2),(89.6,.4,10.8),'edge')
    if detail=='view':
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.],rear_opening=[0.,0.,3.6])
    return result
