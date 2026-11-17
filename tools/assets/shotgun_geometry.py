#!/usr/bin/env python3
"""Original molded-plastic pump shotgun; artistic units, X forward/Y left/Z up.

The ribbed fore-end, action bars and support hand translate together.
"""
from m16_geometry import Mesh, add_right_hand
from shotgun_parts import add_support_hand, oval_sections

MUZZLE = (100., 0., 4.8)
REAR_SIGHT = (32., 0., 7.78)
FRONT_SIGHT = (95., 0., 7.78)
GRIP = (34., 0., -8.)
PUMP_TRAVEL = 7.
VIEW_PUMP_FRACTIONS = [0.] * 40
for _frame, _amount in ((10,.35),(11,.75),(12,1.),(13,1.),(14,.65),(15,.25)):
    VIEW_PUMP_FRACTIONS[_frame] = _amount


def pump_fractions(role, frames):
    """One back-and-forward cycle inside each existing firing animation."""
    result = [0.] * frames
    if role == 'view':
        if frames != 40: raise ValueError('Shotgun view animation needs 40 slots')
        return list(VIEW_PUMP_FRACTIONS)
    if role == 'player':
        for start in (46,160):
            for i, amount in enumerate((0.,0.,.45,1.,1.,.6,0.,0.)):
                result[start+i] = amount
    elif role == 'enemy':
        # All soldier firing poses: standing attacks 1/2, ducked attack3,
        # and the running attack. Existing body animation and timing remain.
        for start, amounts in ((3,(.3,.7,1.,1.,.6,.2)),
                               (18,(.25,.5,.75,1.,1.,.65,.3)),
                               (33,(.5,1.,.5,0.)),
                               (113,(.3,.7,1.,1.,.6,.2))):
            for i, amount in enumerate(amounts):
                result[start+i] = amount
    return result


def build_shotgun(detail='world', pump=0.):
    if detail not in ('world','view') or not 0. <= pump <= 1.:
        raise ValueError('Expected world/view and pump fraction in [0,1]')
    m = Mesh()
    # Rounded stock and a tight wrist blend into the receiver's swept heel.
    stock = [(0,0,-3.5,2.20,6.50),(5,0,-2.65,2.35,5.85),
             (22.5,0,-1.,1.48,2.80),(30.5,0,.15,1.72,2.50)]
    m.loft('stock', oval_sections(stock,6), 'plastic', uv_axes=(0,2))
    m.loft('butt_plate', oval_sections([(-.45,0,-3.5,2.14,6.36),
                                       (.85,0,-3.5,2.29,6.60)],6), 'dark')
    section = [(-.62,-1),(.62,-1),(1,-.56),(1,.48),
               (.61,1),(-.61,1),(-1,.48),(-1,-.56)]
    stations = [(27.5,1.55,.55,2.95),(33.0,2.27,1.10,5.35),
                (45.0,2.39,1.02,5.18),(51.8,1.92,1.20,4.35)]
    rings = [[(x+.22*z*h,y*w,mid+z*h) for y,z in section] for x,w,mid,h in stations]
    start = len(m.faces)
    m.loft('receiver',rings,'plastic',uv_axes=(0,2))
    for band in range(len(rings)-1):
        for side in (2,6):
            face = start + 2*(band*len(section)+side)
            m.materials[face:face+2] = ['receiver']*2
    # Same high molded grip and right mitten as the M16.
    m.profile('pistol_grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                            (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-6.9),(41.3,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-6.4),(40.9,-7.2),(34.7,-7.1)],.72)
    m.tube('barrel',[(46,0,4.8,1.58,1.56),(99,0,4.8,1.65,1.65),
                     (100,0,4.8,1.85,1.85)],8 if detail=='view' else 6,
           'magazine',caps=(True,True),end_material='bore',phase=0.)
    m.tube('magazine_tube',[(48,0,-.1,1.25,1.25),(92,0,-.1,1.25,1.25)],
           6,'edge',caps=(True,True))
    m.profile('barrel_band',[(86.2,-.4),(88.5,-.4),(88.5,4.35),(86.85,4.9)],
              .95,'plastic','edge')
    shift = PUMP_TRAVEL*pump
    pump_sections = [(52.7,1.97,2.05),(55.8,2.86,2.72),
                     (68.0,2.85,2.66),(72.2,2.37,2.27),(73.4,1.83,1.88)]
    start = len(m.faces)
    m.tube('pump',[(x-shift,0,-.25,w,h) for x,w,h in pump_sections],
           8,'handguard',caps=(True,True))
    # Project the molded ribs by distance so they stay evenly spaced across
    # the long fore-end and leave the rounded collars clean.
    rear, front = pump_sections[0][0]-shift, pump_sections[-1][0]-shift
    for face in range(start,len(m.faces)-12):
        m.uvs[face] = [[(m.vertices[index][0]-rear)/(front-rear),v]
                       for index, (_,v) in zip(m.faces[face],m.uvs[face])]
    m.materials[-12:] = ['grip']*12
    # Visible side rails make the short stroke read as a mechanical action.
    for side in (-1,1):
        y = side*2.25
        m.box('action_bar_'+str(side),(44-shift,y-.3,-1.8),
              (60-shift,y+.3,-.9),'dark')
    # A low, swept notch leads the eye to a rounded plastic front bead.
    for side in (-1,1):
        m.profile('rear_sight_'+('left' if side>0 else 'right'),
                  [(30.8,5.7),(34.6,6.0),(33.25,7.80),(32.15,7.96)],
                  .30,'dark','dark',y=side*.88)
    m.profile('front_sight',[(93.9,6.10),(96.1,6.1),(95.65,7.50),
                            (95.2,7.78),(94.65,7.55)], .35,'edge','edge')
    if detail == 'view':
        add_right_hand(m)
        # Lead the sleeve diagonally from the left shoulder into the palm.
        # The last two sections continue the forearm's line into the grip.
        sleeve = [(10,24,-27,3.8,3.3),(34,13.5,-16,3.25,2.8),
                  (50.9,5.15,-7.45,2.6,2.15),(53.4,3.85,-6.25,2.55,2.05),
                  (56,2.4,-4.95,1.85,1.55)]
        add_support_hand(m, shift, sleeve)
    result = m.finish(detail)
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             support=[60.1-shift,0.,-2.])
    result.pop('rifle_bounds')
    return result
