#!/usr/bin/env python3
"""Long beveled toy pistol with a fitted, molded right mitten and wrist.

Artistic model coordinates only: X forward, Y left, Z up. Surface detail is
painted into the shared plastic atlas; all solid parts have closed ends.
"""
import math

import numpy as np

from m16_geometry import Mesh, _area, _triangulate

MUZZLE = (57.1,0.,3.75)
REAR_SIGHT = (27.2,0.,6.7)
FRONT_SIGHT = (54.7,0.,6.7)
GRIP = (32.,0.,-5.5)


def oval_sweep(m, name, sections, sides=8):
    """Follow the limb with oval sections perpendicular to its centerline."""
    centers = np.array([s[:3] for s in sections])
    rings = []
    for i, (center, section) in enumerate(zip(centers, sections)):
        axis = centers[min(i+1, len(centers)-1)] - centers[max(i-1, 0)]
        axis /= np.linalg.norm(axis)
        across = np.cross(axis, (0, 0, 1))
        across /= np.linalg.norm(across)
        depth = np.cross(axis, across)
        rings.append([center + section[3]*math.cos(a)*across + section[4]*math.sin(a)*depth
                      for a in (j*math.tau/sides for j in range(sides))])
    m.loft(name, rings)


def add_pistol_hand(m):
    """A continuous molded wrap outside the grip, with a rounded rear heel."""
    # One swept forearm/wrist avoids exposed overlapping limb caps. Its
    # narrow distal end is buried inside the palm; the cuff is a material band.
    arm_start=len(m.faces)
    oval_sweep(m, 'arm_right', [(11.,-7.8,-24.,3.7,3.1), (21.5,-3.1,-13.1,2.65,2.15),
                               (22.5,-2.6,-12.,2.55,2.05), (24.6,-1.7,-9.9,1.95,1.65),
                               (26.9,-.4,-7.6,1.45,1.1)])
    m.materials[arm_start+16:arm_start+32]=['cuff']*16
    # These concave sections wrap the backstrap, palm side and front fingers.
    # The inner boundary leaves the actual grip empty, rather than burying
    # a solid ellipsoid through it. Rounded ends narrow the heel and knuckles.
    loops=[]
    def back(z): return 27.2+(30.6-27.2)*(z+9.8)/9.3
    def front(z):
        return (33.5+(34.5-33.5)*(z+11.2)/8.1 if z<=-3.1 else
                34.5+(35.3-34.5)*(z+3.1)/2.4)
    for z,back_shift,front_shift,p,f in ((-9.0,-.9,.7,.40,.35),
                                        (-8.5,-.7,.6,.87,1.0),
                                        (-7.6,-.3,.0,1.05,1.18),
                                        (-6.7,.0,.0,1.08,.82),
                                        (-5.7,.0,.0,1.0,1.18),
                                        (-4.8,.0,.0,.9,.82),
                                        (-3.8,.3,-.1,.78,1.18),
                                        (-3.2,1.1,-.3,.80,.9),
                                        (-2.8,2.0,-.5,.51,.6)):
        b=z+back_shift; t=z+front_shift; middle=(b+t)/2
        # A lower rear heel and higher fingertips angle the underside into
        # the wrist; the upper rear web rises above the index knuckle.
        loop=[(back(b)-.85*p,1.8+.65*p,b),(back(b)-2.50*p,.65,b-.15*p),
              (back(b)-2.12*p,-1.65,b),(back(middle)+.2,-2.02-1.6*p,middle),
              (front(t)+.40,-2.02-1.25*f,t-.2),(front(t)+.22+1.55*f,-1.0,t),
              (front(t)+.22+1.15*f,1.55,t+.15),(front(t)+.40,2.02+1.5*f,t+.12),
              (back(t)+1.70-f,2.02+.85*f,t),(back(t)+1.6-f,2.02,t),
              (front(t)+.22,2.02,t),(front(t)+.22,-2.02,t),
              (back(b)-.22,-2.02,b),(back(b)-.22,1.65,b)]
        assert _area([p[:2] for p in loop])>0
        loops.append(loop)
    m.part('hand_right_palm')
    count=len(loops[0])
    for a,b in zip(loops,loops[1:]):
        for i in range(count):
            j=(i+1)%count
            # Consistent CCW sections give outward walls even on the concave
            # grip-facing boundary; a radial normal is wrong for this shape.
            points=[a[i],a[j],b[j],b[i]]
            finger=4 <= i <= 8
            uv=[((x-25.)/13.,(-z-1.5)/8.5) for x,y,z in points]
            if i < 4:
                uv=[(u/4,(-z-.5)/10) for u,(_,_,z) in zip((i,j,j,i),points)]
                m.poly(points,'palm',uv=uv)
            else:
                m.poly(points,'fingers' if finger else 'hand',uv=uv if finger else None)
    # Concave ends must be ear-clipped. A fan would span the grip cavity.
    for loop,normal in ((loops[0],(0,0,-1)),(loops[-1],(0,0,1))):
        for ids in _triangulate([p[:2] for p in loop]):
            m.poly([loop[i] for i in ids],'hand',normal)
    # The thumb root is buried in the heel behind the backstrap, then arches
    # around the visible side without entering the handle's interior.
    oval_sweep(m, 'hand_right_thumb',
               [(26.9,1.25,-5.1,1.30,1.50),(28.65,3.56,-3.5,1.49,1.38),
                (31.4,3.55,-2.15,1.15,1.),(34.35,3.03,-2.22,.87,.72),
                (35.25,2.86,-2.49,.40,.40)])


def build_pistol(detail='world'):
    if detail not in ('world', 'view'):
        raise ValueError('detail must be world or view')
    m = Mesh()
    # A shallow frame flows into the grip instead of forming a second tall
    # block under the slide. The long upper body carries the silhouette.
    # Pull the rear forward and narrow it into the backstrap. Beveled lower
    # corners avoid a square shelf directly below the slide's rear face.
    frame_rings=[]
    for x,w,low in ((29.0,.8,.0),(35.5,1.7,-1.4),(55.5,1.65,.0)):
        top=1.5; bevel=.4
        frame_rings.append([(x,-w,top),(x,-w,low+bevel),(x,-w+bevel,low),
                            (x,w-bevel,low),(x,w,low+bevel),(x,w,top)])
    m.loft('frame',frame_rings,'receiver',uv_axes=(0,2))
    m.profile('grip', [(30,-11.2),(27.2,-9.8),(30.6,-.5),(35.3,-.7),
                       (34.5,-3.1),(33.5,-11.2)], 1.8,'grip','edge')
    if detail == 'view':
        m.ring_profile('trigger_guard',
                       [(34.4,-1.5),(42.4,-1.0),(42.15,-4.25),(41.25,-5.75),(39.7,-6.2),(33.7,-6.2)],
                       [(35.5,-2.5),(41.2,-2.2),(41.0,-3.95),(40.45,-4.75),(39.5,-5.05),(34.9,-5.0)], .65)
    else:
        m.ring_profile('trigger_guard', [(34.4,-1.5),(42.4,-1.0),(42.0,-6.1),(33.7,-6.2)],
                       [(35.5,-2.5),(41.2,-2.2),(40.9,-4.9),(34.9,-5.0)], .65)
    rings=[]
    if detail == 'view':
        # A sloping heel, crowned shoulders and narrower nose break up the
        # silhouette at the two ends nearest the player's line of sight.
        section = [(-.70,-1),(.70,-1),(1,-.68),(1,.43),(.91,.73),
                   (.64,.95),(0,1),(-.64,.95),(-.91,.73),(-1,.43),(-1,-.68)]
        for x,w,h,rake in ((25.5,1.50,1.77,.52),(27.55,2.18,2.50,.18),
                           (53.5,1.99,2.45,0.),(56.5,1.56,2.02,-.12)):
            rings.append([(x+rake*pz*h,py*w,MUZZLE[2]+pz*h) for py,pz in section])
        first = len(m.faces)
        m.loft('slide',rings,'handguard',uv_axes=(0,2))
        sides = len(section)
        for band in range(len(rings)-1):
            for edge in (3,4,5,6,7,8):
                start = first + 2*(band*sides+edge)
                m.materials[start:start+2] = ['plastic' if edge in (5,6) else 'edge']*2
        # Map the rear die impression face-on. Its atlas tile is unused by
        # the world pistol. The forward cap has plain molded plastic.
        cap = sides-2
        for face in range(len(m.faces)-2*cap, len(m.faces)-cap):
            m.materials[face] = 'magazine'
            m.uvs[face] = [[.5+y/3.0, .5-(z-MUZZLE[2])/3.54]
                           for _,y,z in (m.vertices[i] for i in m.faces[face])]
        m.materials[-cap:] = ['edge']*cap
    else:
        for x,w,h in ((25.7,1.65,2.0),(27.0,2.05,2.5),
                      (55.5,2.05,2.5),(56.5,1.75,2.15)):
            z=MUZZLE[2]; bevel=.65
            rings.append([(x,-w,z-h+bevel),(x,-w+bevel,z-h),
                          (x,w-bevel,z-h),(x,w,z-h+bevel),
                          (x,w,z+h-bevel),(x,w-bevel,z+h),
                          (x,-w+bevel,z+h),(x,-w,z+h-bevel)])
        m.loft('slide',rings,'handguard',uv_axes=(0,2))
        m.materials[-12:] = ['edge']*12
    m.tube('barrel', [(55.8,0,3.75,.95,.95),(57.1,0,3.75,.95,.95)],
           8 if detail == 'view' else 6, 'dark', caps=(True,True), end_material='bore')
    # A real rear notch and front blade, with an unobstructed common sight ray.
    if detail == 'view':
        for name,y in (('rear_sight_left',.80),('rear_sight_right',-.80)):
            m.profile(name, [(26.35,5.45),(28.2,5.6),(27.85,7.0),(26.85,7.0)],
                      .25,'dark','dark',y=y)
        m.profile('front_sight', [(54.05,5.65),(55.38,5.65),(55.0,6.7),(54.45,6.7)],
                  .25,'dark','dark')
        add_pistol_hand(m)
    else:
        m.box('rear_sight_left', (26.4,.55,6.1),(28,1.05,7.0), 'dark')
        m.box('rear_sight_right', (26.4,-1.05,6.1),(28,-.55,7.0), 'dark')
        m.box('front_sight', (54.35,-.25,6.2),(55.05,.25,6.7), 'dark')
    result = m.finish(detail)
    result['anchors'] = dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT),grip=list(GRIP))
    result.pop('rifle_bounds')
    return result
