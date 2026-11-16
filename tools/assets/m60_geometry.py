#!/usr/bin/env python3
"""Original simple-shape M60 with a box feed and folded bipod.

Artistic model coordinates only: X forward, Y left, Z up. The rifle's existing
closed mittens and arms fit the grip and ribbed supporting handguard unchanged.
"""
from m16_geometry import Mesh, add_hands

MUZZLE = (100.,0.,0.)
REAR_SIGHT = (32.,0.,8.6)
FRONT_SIGHT = (90.,0.,8.6)
GRIP = (34.,0.,-8.)


def build_m60(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('Expected world or view')
    m=Mesh()
    m.profile('stock',[(0,-8.6),(0,2.6),(5,3.0),(23,1.3),(28,1.9),
                       (29,-3.0),(22,-4.2)],3.0,'plastic','edge')
    m.profile('butt_plate',[(0,-8.6),(1.2,-8.4),(1.2,2.6),(0,2.6)],
              3.15,'dark','edge')
    m.profile('receiver',[(25,-4.8),(25,3.7),(28,5.0),(51,5.0),
                          (54,2.8),(54,-4.1),(47,-5.3)],3.0,'receiver','edge')
    m.box('feed_cover',(28,-3.2,4.3),(51,3.2,6.2),'receiver','edge')
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    # Compact left feed box stays above the supporting forearm's path.
    m.box('ammo_box',(35,3.,-8.5),(46,10.5,-2.0),'magazine','edge')
    m.box('feed_belt',(39,2.5,-1.0),(47,7.,1.0),'dark','edge')
    m.tube('handguard',[(52,0,0,3.6,3.6),(55,0,0,3.6,3.6),
                        (73,0,0,2.75,2.8)],8,'handguard',caps=(True,True))
    m.tube('barrel',[(72,0,0,1.12,1.12),(97,0,0,1.12,1.12)],
           6,'dark',caps=(True,True))
    m.tube('flash_hider',[(96.5,0,0,1.55,1.55),(100,0,0,1.55,1.55)],
           8 if detail=='view' else 6,'edge',caps=(True,True),end_material='bore')
    m.tube('gas_tube',[(69,0,-2.8,.8,.8),(93,0,-2.8,.8,.8)],
           6,'dark',caps=(True,True))
    m.box('gas_block',(88,-1.6,-3.3),(91,1.6,1.0),'edge')
    # Folded legs remain close to the barrel instead of changing bracing rules.
    for side,name in ((1,'left'),(-1,'right')):
        m.limb('folded_bipod_'+name,(77,side*2.0,-1.5),
               (94,side*2.3,-4.2),.85,.8,'dark',4)
    m.ring_profile('front_sight_frame',[(87.1,-.6),(92.9,-.6),(90,6.6)],
                   [(88.5,.8),(91.5,.8),(90,4.7)],.65)
    m.box('front_sight',(89.5,-.4,6.0),(90.5,.4,8.6),'edge')
    for side in (-1,1):
        y=side*1.0
        m.box('rear_sight_'+('left' if side>0 else 'right'),
              (31,y-.35,6.2),(33,y+.35,9.0),'dark')
    if detail=='view':
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.])
    return result
