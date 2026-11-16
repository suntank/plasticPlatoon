#!/usr/bin/env python3
"""Original side-by-side double-barrel shotgun in molded army-man plastic.

Artistic coordinates only: X forward, Y left, Z up. The same closed mitten
hands and forearms as the M16 cradle a fixed fore-end beneath the twin barrels.
"""
from m16_geometry import Mesh, add_hands

MUZZLE = (100., 0., 3.8)
MUZZLE_LEFT = (100., 2.15, 3.8)
MUZZLE_RIGHT = (100., -2.15, 3.8)
REAR_SIGHT = (32., 0., 8.6)
FRONT_SIGHT = (95., 0., 8.6)
GRIP = (34., 0., -8.)


def build_sshotgun(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('Expected world or view')
    m = Mesh()
    # A slim shoulder stock avoids a broad slab close to the first-person eye.
    m.profile('stock', [(0,-10),(0,2.5),(4,3.4),(22,1.3),(29,2.5),
                        (31,-2.8),(24,-4.0)], 1.85, 'plastic','edge')
    m.profile('butt_plate',[(0,-10),(1.2,-9.8),(1.2,2.5),(0,2.5)],
              2.0,'dark','edge')
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    # Keep the full-width twin-barrel breech, tapering its rear into the stock
    # instead of presenting a full-width rectangular block to the FPS camera.
    receiver_start = len(m.vertices)
    m.profile('receiver',[(28,-3.8),(28,4.8),(31,6.2),(46,6.2),
                          (51,4.5),(51,-2.2),(46,-4.5)],4.2,'receiver','edge')
    for point in m.vertices[receiver_start:]:
        width = 2.5 + 1.7 * min((point[0] - 28.) / 18., 1.)
        point[1] *= width / 4.2
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    # Two real, individually capped barrels, with contrasting dark muzzle faces.
    # The narrow central rib keeps the center sight ray above the paired bores.
    for side,name in ((1,'barrel_left'),(-1,'barrel_right')):
        y=side*2.15
        m.tube(name,[(48,y,3.8,2.08,2.08),(98.8,y,3.8,1.95,1.95),
                     (100,y,3.8,2.12,2.12)],8 if detail=='view' else 6,
               'dark',caps=(True,True),end_material='bore')
    m.box('sight_rib',(48,-.42,5.3),(99,.42,6.4),'edge')
    # Smooth fixed splinter fore-end, cupped by the existing supporting mitten.
    m.tube('fore_end',[(51,0,-.5,2.1,1.8),(55,0,-.5,2.95,2.05),
                       (69,0,-.5,2.7,1.9),(73,0,-.5,1.75,1.35)],
           8,'grip',caps=(True,True))
    m.box('breech_latch',(27.8,-.6,5.4),(31.2,.6,6.5),'edge')
    for side in (-1,1):
        y=side*1.0
        m.box('rear_sight_'+('left' if side>0 else 'right'),
              (31,y-.35,6.2),(33,y+.35,9.0),'dark')
    m.box('front_sight',(94.4,-.35,6.1),(95.6,.35,8.6),'edge')
    if detail=='view':
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    # The shared flash is centered between the two simultaneously fired bores.
    result['anchors']=dict(muzzle=list(MUZZLE),muzzle_left=list(MUZZLE_LEFT),
                           muzzle_right=list(MUZZLE_RIGHT),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.])
    return result
