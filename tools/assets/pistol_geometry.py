#!/usr/bin/env python3
"""Long beveled toy pistol with a fitted, molded right mitten and wrist.

Artistic model coordinates only: X forward, Y left, Z up. Surface detail is
painted into the shared plastic atlas; all solid parts have closed ends.
"""
from m16_geometry import Mesh, _area, _triangulate

MUZZLE = (57.1,0.,3.75)
REAR_SIGHT = (27.2,0.,6.7)
FRONT_SIGHT = (54.7,0.,6.7)
GRIP = (32.,0.,-5.5)


def add_pistol_hand(m):
    """A continuous molded wrap outside the grip, with a rounded rear heel."""
    # One swept forearm/wrist avoids exposed overlapping limb caps. Its
    # narrow distal end is buried inside the palm; the cuff is a material band.
    arm_start=len(m.faces)
    m.finger('arm_right',[(8,-10,-25),(21.8,-3,-12.2),(24.5,-1.8,-10),
                          (25.6,-.95,-8.9),(26.9,-.4,-7.7)],
             [3.6,2.1,1.85,1.6,.8])
    m.materials[arm_start+12:arm_start+24]=['cuff']*12
    # These concave sections wrap the backstrap, palm side and front fingers.
    # The inner boundary leaves the actual grip empty, rather than burying
    # a solid ellipsoid through it. Rounded ends narrow the heel and knuckles.
    loops=[]
    def back(z): return 27.2+(30.6-27.2)*(z+9.8)/9.3
    def front(z):
        return (33.5+(34.5-33.5)*(z+11.2)/8.1 if z<=-3.1 else
                34.5+(35.3-34.5)*(z+3.1)/2.4)
    for z,back_shift,front_shift,p,f in ((-9.0,-.9,.7,.58,.55),
                                        (-8.5,-.7,.6,.82,.92),
                                        (-7.6,-.3,.0,1.05,1.18),
                                        (-6.7,.0,.0,1.08,.82),
                                        (-5.7,.0,.0,1.0,1.18),
                                        (-4.8,.0,.0,.9,.82),
                                        (-3.8,.3,-.1,.78,1.18),
                                        (-3.2,.7,-.3,.68,.9),
                                        (-2.8,1.1,-.5,.58,.6)):
        b=z+back_shift; t=z+front_shift; middle=(b+t)/2
        # A lower rear heel and higher fingertips angle the underside into
        # the wrist; the upper rear web rises above the index knuckle.
        loop=[(back(b)-.65,2.02,b),(back(b)-1.4*p,2.02+.25*p,b),
              (back(b)-2*p,.45,b),(back(b)-1.6*p,-2.02-.6*p,b),
              (back(middle)+.4,-2.02-1.4*p,middle),
              (front(t)+.4,-2.02-1.2*f,t),
              (front(t)+.22+1.4*f,-1.2,t),(front(t)+.22+1.4*f,.8,t),
              (front(t)+.1,2.02+1.25*f,t),(back(t)+.75,2.02+1.25*f,t),
              (back(t)+.55,2.02,t),(front(t)+.22,2.02,t),
              (front(t)+.22,-2.02,t),(back(b)-.22,-2.02,b),
              (back(b)-.22,1.25,b)]
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
            finger=i in (5,6,7,8,9)
            uv=[((x-25.)/13.,(-z-1.5)/8.5) for x,y,z in points]
            m.poly(points,'fingers' if finger else 'hand',uv=uv)
    # Concave ends must be ear-clipped. A fan would span the grip cavity.
    for loop,normal in ((loops[0],(0,0,-1)),(loops[-1],(0,0,1))):
        for ids in _triangulate([p[:2] for p in loop]):
            m.poly([loop[i] for i in ids],'hand',normal)
    # The thumb root is buried in the heel behind the backstrap, then arches
    # around the visible side without entering the handle's interior.
    m.finger('hand_right_thumb',
             [(27.3,1.0,-4.9),(29.2,3.3,-2.6),(32.1,3.2,-1.9),
              (35.0,2.9,-2.5),(35.4,2.75,-2.75)],
             [1.3,1.1,.85,.65,.3])


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
    m.ring_profile('trigger_guard', [(34.4,-1.5),(42.4,-1.0),(42.0,-6.1),(33.7,-6.2)],
                   [(35.5,-2.5),(41.2,-2.2),(40.9,-4.9),(34.9,-5.0)], .65)
    # Eight corresponding corners create actual top/side shoulder bevels,
    # with a narrowed rear and muzzle. Rear serrations remain atlas detail.
    rings=[]
    for x,w,h in ((25.7,1.65,2.0),(27.0,2.05,2.5),
                   (55.5,2.05,2.5),(56.5,1.75,2.15)):
        z=MUZZLE[2]; bevel=.65
        rings.append([(x,-w,z-h+bevel),(x,-w+bevel,z-h),
                      (x,w-bevel,z-h),(x,w,z-h+bevel),
                      (x,w,z+h-bevel),(x,w-bevel,z+h),
                      (x,-w+bevel,z+h),(x,-w,z+h-bevel)])
    m.loft('slide',rings,'handguard',uv_axes=(0,2))
    # Keep the two end faces clean rather than projecting side serrations.
    m.materials[-12:] = ['edge']*12
    m.tube('barrel', [(55.8,0,3.75,.95,.95),(57.1,0,3.75,.95,.95)],
           8 if detail == 'view' else 6, 'dark', caps=(True,True), end_material='bore')
    # A real rear notch and front blade, with an unobstructed common sight ray.
    m.box('rear_sight_left', (26.4,.55,6.1),(28,1.05,7.0), 'dark')
    m.box('rear_sight_right', (26.4,-1.05,6.1),(28,-.55,7.0), 'dark')
    m.box('front_sight', (54.35,-.25,6.2),(55.05,.25,6.7), 'dark')
    if detail == 'view':
        m.box('slide_stop', (31,-2.0,.0),(35,-1.75,.5), 'dark')
        add_pistol_hand(m)
    result = m.finish(detail)
    result['anchors'] = dict(muzzle=list(MUZZLE),rear_sight=list(REAR_SIGHT),
                             front_sight=list(FRONT_SIGHT),grip=list(GRIP))
    result.pop('rifle_bounds')
    return result
