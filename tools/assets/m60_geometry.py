#!/usr/bin/env python3
"""Molded-plastic M60 with a contoured box feed and folded bipod.

Artistic model coordinates only: X forward, Y left, Z up. The rifle's existing
closed mittens and arms fit the grip and ribbed supporting handguard unchanged.
"""
from m16_geometry import Mesh, add_hands
from shotgun_parts import oval_sections

MUZZLE = (100.,0.,0.)
REAR_SIGHT = (32.,0.,8.6)
FRONT_SIGHT = (90.,0.,8.6)
GRIP = (34.,0.,-8.)


def build_m60(detail='world'):
    if detail not in ('world','view'):
        raise ValueError('Expected world or view')
    close = detail == 'view'
    m = Mesh()
    stock = [(0,0,-3.0,2.87,5.55),(5,0,-2.73,3.02,5.08),
             (21.5,0,-1.20,2.33,3.04),(28.4,0,-.65,1.99,2.55)]
    m.loft('stock', oval_sections(stock,6), 'plastic', uv_axes=(0,2))
    butt = [(-.35,0,-3.,2.87,5.55),(.72,0,-3.,2.98,5.62)]
    m.loft('butt_plate', oval_sections(butt,6), 'dark')
    section = [(-.63,-1),(.63,-1),(1,-.58),(1,.56),
               (.67,1),(-.67,1),(-1,.56),(-1,-.58)]
    stations = [(24.9,1.97,-.52,3.52),(30.0,2.94,.05,4.92),
                (47.4,3.02,.15,4.89),(54.,2.32,-.25,3.69)]
    if not close:
        stations = [stations[i] for i in (0,1,3)]
    receiver = [[(x+.17*h*z,w*y,mid+h*z) for y,z in section] for x,w,mid,h in stations]
    receiver_start = len(m.faces)
    m.loft('receiver', receiver, 'plastic', uv_axes=(0,2))
    for band in range(len(receiver)-1):
        for side in (2,6):
            face = receiver_start+2*(band*len(section)+side)
            m.materials[face:face+2] = ['receiver']*2

    # The cover crowns over the receiver and eases down at the front and rear.
    cover = []
    for x,w,top in ((27.9,2.35,5.18),(32,3.03,6.78),(48,2.98,6.42),(51.3,2.23,5.06)):
        cover.append([(x,-w,3.92),(x,w,3.92),(x,w,top-.64),
                      (x,w*.63,top),(x,-w*.63,top),(x,-w,top-.64)])
    m.loft('feed_cover', cover if close else [cover[i] for i in (0,1,3)], 'palm', uv_axes=(0,1))
    m.profile('grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                      (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    # The feed box has a beveled lid and a recessed panel facing the player.
    outline = [(-.82,-1),(.80,-1),(1,-.67),(1,.57),
               (.73,1),(-.70,1),(-1,.49),(-1,-.61)]
    box_stations = [(2.85,.84),(9.18,1.),(10.58,.79)] if close else [(2.85,.88),(10.58,1.)]
    box = [[(41+6.3*x*scale,y,-5.0+3.68*z*scale) for x,z in outline]
           for y,scale in box_stations]
    box_start = len(m.faces)
    m.loft('ammo_box', box, 'plastic', uv_axes=(0,2))
    for band in range(len(box)-1):
        lid = box_start+2*(band*len(outline)+3)
        m.materials[lid:lid+6] = ['edge']*6
    cap_triangles = len(outline)-2
    cap_scale = box_stations[-1][1]
    for face in range(len(m.faces)-cap_triangles,len(m.faces)):
        m.materials[face] = 'magazine'
        m.uvs[face] = [[.5+(x-41.)/(12.6*cap_scale), .5-(z+5.)/(7.36*cap_scale)]
                       for x,_,z in (m.vertices[i] for i in m.faces[face])]
    belt = []
    for y,mid in ((2.35,1.0),(5.40,.44),(7.58,-1.04)):
        belt.append([(38.8,y,mid-.73),(47.7,y,mid-.73),
                     (47.7,y,mid+.61),(38.8,y,mid+.61)])
    m.loft('feed_belt', belt, 'magazine', uv_axes=(0,1))
    m.tube('handguard',[(51.4,0,0,2.7,2.63),(55,0,0,3.6,3.6),
                        (73,0,0,2.75,2.8)],10 if close else 8,'handguard',caps=(True,True))
    m.tube('barrel',[(72,0,0,1.12,1.12),(97,0,0,1.12,1.12)],
           6,'dark',caps=(True,True))
    m.tube('flash_hider',[(96.5,0,0,1.55,1.55),(100,0,0,1.55,1.55)],
           8 if detail=='view' else 6,'edge',caps=(True,True),end_material='bore')
    m.tube('gas_tube',[(69,0,-2.8,.8,.8),(93,0,-2.8,.8,.8)],
           6,'dark',caps=(True,True))
    m.profile('gas_block',[(87.9,-3.2),(90.7,-3.21),(91.1,.98),(88.55,.84)],
              1.6,'edge','plastic')
    # Folded legs remain close to the barrel instead of changing bracing rules.
    for side,name in ((1,'left'),(-1,'right')):
        m.limb('folded_bipod_'+name,(77,side*2.0,-1.5),
               (94,side*2.3,-4.2),.85,.8,'dark',6 if close else 4)
    m.ring_profile('front_sight_frame',[(87.1,-.6),(92.9,-.6),(90,6.6)],
                   [(88.5,.8),(91.5,.8),(90,4.7)],.65)
    m.profile('front_sight',[(89.24,5.95),(90.78,5.95),(90.38,8.6),(89.73,8.6)],
              .37,'edge','edge')
    for side in (-1,1):
        y=side*1.0
        m.profile('rear_sight_'+('left' if side>0 else 'right'),
                  [(30.30,6.02),(34,6.34),(33.22,8.7),(31.95,8.84)],
                  .32,'dark','dark',y=y)
    if close:
        add_hands(m)
    result=m.finish(detail)
    result.pop('rifle_bounds')
    result['anchors']=dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                           front_sight=list(FRONT_SIGHT),grip=list(GRIP),
                           support=[62.,0.,-2.])
    return result
