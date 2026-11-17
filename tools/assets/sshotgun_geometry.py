#!/usr/bin/env python3
"""Molded toy scattergun. Artistic coordinates run X forward, Y left, Z up."""
from m16_geometry import Mesh, add_right_hand
from shotgun_parts import add_support_hand, oval_sections

MUZZLE = (100., 0., 3.8)
MUZZLE_LEFT = (100., 2.15, 3.8)
MUZZLE_RIGHT = (100., -2.15, 3.8)
REAR_SIGHT = (32., 0., 6.72)
FRONT_SIGHT = (95., 0., 6.72)
GRIP = (34., 0., -8.)


def build_sshotgun(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('Expected world or view')
    close = detail == 'view'
    m = Mesh()
    stock = [(0,0,-3.5,2,6.45),(5,0,-3.3,2.12,6.0),
             (22,0,-.95,1.48,2.82),(30.8,0,.05,1.85,2.65)]
    m.loft('stock', oval_sections(stock, 6),'plastic',uv_axes=(0,2))
    m.loft('butt_plate', oval_sections([(-.45,0,-3.5,2.0,6.38),
                                        (.75,0,-3.5,2.08,6.55)], 6),'dark')
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')

    # The narrow wrist fans out into a low, rounded saddle. Past the rear
    # sight the upper barrels are exposed all the way back to the shoulder.
    outline = [(-.58,-1),(.58,-1),(1,-.55),(1,.53),
               (.55,1),(-.55,1),(-1,.53),(-1,-.55)]
    stations = [(27.6,1.60,.15,2.5),(32.2,2.70,.85,4.95),
                (38.1,3.85,0,3.8),(48.6,4.0,-.55,2.9),(51.5,3.4,-.25,2.1)]
    if not close:
        stations = [stations[i] for i in (0,1,2,4)]
    rings = [[(x+.21*z*h,y*w,mid+z*h) for y,z in outline] for x,w,mid,h in stations]
    first = len(m.faces)
    m.loft('receiver',rings,'plastic',uv_axes=(0,2))
    for band in range(len(rings)-1):
        for side in (2,6):
            start = first + 2*(band*len(outline)+side)
            m.materials[start:start+2] = ['receiver']*2
    m.ring_profile('trigger_guard',[(33.9,-3.7),(43.3,-3.5),(43,-6.7),(41.2,-8.25),(33.3,-8.2)],
                   [(35.4,-4.8),(42,-4.7),(41.8,-6.1),(40.7,-7.1),(34.7,-7.1)],.72)

    for anchor,name in ((MUZZLE_LEFT,'barrel_left'),(MUZZLE_RIGHT,'barrel_right')):
        x,y,z = anchor
        m.tube(name,[(32.7,.73*y,z,.72,.78),(40,y,z,2.13,2.15),
                     (x,y,z,2.04,2.04)],
               10 if close else 6,'magazine',caps=(True,True),end_material='bore',
               phase=0.)
    # A recessed center strip leaves daylight around the twin crowns.
    m.profile('sight_rib',[(35,4.8),(99,4.7),(99,5.25),(38,5.37)],
              .34,'dark','dark')
    m.loft('fore_end',oval_sections([(48.2,0,-.45,2.4,1.45),(54.5,0,-.55,3.1,2.1),
                                     (67,0,-.45,2.78,1.95),(72.8,0,.0,1.55,1.15)],
                                    8 if close else 6),'handguard',uv_axes=(0,2))
    # Swept rear ears and a pale molded bead make a small, open sight picture.
    for side,name in ((1,'rear_sight_left'),(-1,'rear_sight_right')):
        m.profile(name,[(31.4,5.10),(34.6,5.05),(33.15,6.73),(32.15,6.86)],
                  .31,'dark','dark',y=side*1.03)
    if close:
        bead = [(94.3,0,6.12,.22,.30),(95,0,6.12,.57,.60),(95.7,0,6.12,.22,.30)]
        m.loft('front_sight',oval_sections(bead,6),'palm')
    else:
        m.profile('front_sight',[(94.2,5.75),(95.8,5.75),(95.5,6.72),(94.6,6.72)],
                  .48,'palm','palm')
    m.profile('bead_base',[(94,4.9),(96,4.9),(95.5,6.0),(94.55,6.0)],.30,'dark','dark')
    if close:
        add_right_hand(m)
        add_support_hand(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),muzzle_left=list(MUZZLE_LEFT),
                           muzzle_right=list(MUZZLE_RIGHT),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[60.,0.,-2.])
    return result
