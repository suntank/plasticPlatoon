#!/usr/bin/env python3
"""Original molded-plastic pump shotgun; artistic units, X forward/Y left/Z up.

Closed primitive solids share the M16 palette and mitten geometry. The fore-end,
action bars and support hand translate together; its forearm bends at the wrist.
"""
import numpy as np
from m16_geometry import Mesh, add_hands

MUZZLE = (100., 0., 4.8)
REAR_SIGHT = (32., 0., 8.6)
FRONT_SIGHT = (95., 0., 8.6)
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
    # Broad butt, sloping comb and narrow wrist preserve a clear shotgun stock.
    m.profile('stock',[(0,-10),(0,3),(4,3.8),(23,1.4),(29,2.0),
                       (30,-2.8),(23,-3.9),(6,-7.4)],2.65,'plastic','edge')
    m.profile('butt_plate',[(0,-10),(1.2,-9.8),(1.2,3),(0,3)],2.8,'dark','edge')
    m.profile('receiver',[(28,-3.8),(28,5.7),(31,6.8),(48,6.8),
                          (52,5.3),(52,-2.7),(46,-4.5)],2.6,'receiver','edge')
    # Same high molded grip and right mitten as the M16.
    m.profile('pistol_grip',[(29,-15.1),(25.8,-13.8),(31,-4.3),(36,-4.7),
                            (34,-7.2),(32.8,-15.3)],1.85,'grip','edge')
    m.ring_profile('trigger_guard',[(33.9,-4.2),(43.3,-4.2),(43,-8.5),(33.3,-8.2)],
                   [(35.4,-5.3),(42,-5.3),(41.8,-7.2),(34.7,-7.1)],.72)
    m.tube('barrel',[(49,0,4.8,1.75,1.75),(99,0,4.8,1.6,1.6),
                     (100,0,4.8,1.85,1.85)],8 if detail=='view' else 6,
           'dark',caps=(True,True),end_material='bore')
    m.tube('magazine_tube',[(48,0,-.1,1.25,1.25),(92,0,-.1,1.25,1.25)],
           6,'edge',caps=(True,True))
    m.box('barrel_band',(86.5,-1.1,-.6),(88,1.1,4.9),'plastic')
    shift = PUMP_TRAVEL*pump
    m.tube('pump',[(53-shift,0,-.1,2.5,2.6),(55-shift,0,-.1,3.25,3.25),
                   (71-shift,0,-.1,3.05,3.05),(73-shift,0,-.1,2.45,2.5)],
           8,'handguard',caps=(True,True))
    # Visible side rails make the short stroke read as a mechanical action.
    for side in (-1,1):
        y = side*2.25
        m.box('action_bar_'+str(side),(44-shift,y-.3,-1.8),
              (60-shift,y+.3,-.9),'dark')
    # Actual center channel, with low rear notch and front bead/blade.
    for side in (-1,1):
        y=side*1.0
        m.box('rear_sight_'+('left' if side>0 else 'right'),
              (31,y-.35,6.6),(33,y+.35,9.0),'dark')
    m.box('front_sight',(94.4,-.35,6.1),(95.6,.35,8.6),'edge')
    if detail == 'view':
        m.profile('ejection_port',[(36,1),(46,1),(46,4.9),(36,4.9)],
                  .16,'dark','dark',y=-2.62)
        first = len(m.parts)
        add_hands(m)
        # Translate the complete support mitten/cuff; hold the elbow fixed and
        # bring the forearm's distal ring back with the pump, avoiding a gap.
        for i, part in enumerate(m.parts[first:],first):
            if part['name'] == 'arm_left' or part['name'].startswith(('cuff_left','hand_left')):
                end = m.parts[i+1]['first_triangle'] if i+1<len(m.parts) else len(m.faces)
                indices = np.unique(np.asarray(m.faces[part['first_triangle']:end]))
                for index in indices:
                    point = m.vertices[index]
                    weight = np.clip((point[0]-14.)/45.5,0,1) if part['name']=='arm_left' else 1.
                    point[0] -= shift*weight
    result = m.finish(detail)
    result['anchors'] = dict(muzzle=list(MUZZLE), rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT), grip=list(GRIP),
                             support=[62.-shift,0.,-2.])
    result.pop('rifle_bounds')
    return result
