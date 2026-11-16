#!/usr/bin/env python3
"""Original molded-plastic medical pickups; all visible parts are closed solids."""
import math
import numpy as np
from m16_geometry import Mesh
from pickup_normals import PickupNormals

KINDS = ('stimpack', 'medium', 'large', 'mega', 'adrenaline')
LABELS = {'stimpack': '+2', 'medium': '+10', 'large': '+25',
          'mega': '+100', 'adrenaline': 'BOOST'}
REGIONS = {'plastic': (4,4,60,60), 'dark': (68,4,124,60),
           'edge': (132,4,188,60), 'cream': (196,4,252,60),
           'cross': (4,72,84,152), 'injector': (92,72,148,152),
           'roll_end': (156,72,252,152), 'label': (4,164,252,236)}


def marked_box(m, name, low, high, front='label', top='cross', bevel=0.):
    """Printed markings occupy actual solid faces, without floating decals."""
    x,y,z = low; X,Y,Z = high
    if not bevel:
        outline = [(x,y),(X,y),(X,Y),(x,Y)]
    else:
        b = bevel
        outline = [(x+b,y),(X-b,y),(X,y+b),(X,Y-b),
                   (X-b,Y),(x+b,Y),(x,Y-b),(x,y+b)]
    m.part(name)
    for index, (a,b) in enumerate(zip(outline,outline[1:]+outline[:1])):
        material = front if a[1]==b[1] and a[1] in (y,Y) else 'plastic'
        normal = (b[1]-a[1],a[0]-b[0],0)
        points = [(a[0],a[1],z),(b[0],b[1],z),(b[0],b[1],Z),(a[0],a[1],Z)]
        m.poly(points, material, normal, [(0,1),(1,1),(1,0),(0,0)], group=f'side{index}')
    for height,normal,material in ((z,(0,0,-1),'dark'),(Z,(0,0,1),top)):
        m.poly([(a,b,height) for a,b in outline],material,normal,
               [((a-x)/(X-x),1-(b-y)/(Y-y)) for a,b in outline],group=f'cap{height}')


def turned(m, name, rings, sides=8, material='plastic'):
    loops = [[(r*math.cos(math.pi/sides+i*math.tau/sides),
               r*math.sin(math.pi/sides+i*math.tau/sides),z) for i in range(sides)]
             for z,r in rings]
    m.loft(name, loops, material)


def injector(m):
    # A short, deliberately blunt molded needle avoids sub-pixel slivers.
    turned(m,'needle',[(0.,.25),(2.6,.25)],6,'cream')
    turned(m,'nozzle',[(2.3,.55),(4.4,1.35)],6,'edge')
    marked_box(m,'injector_barrel',(-1.9,-1.55,4.1),(1.9,1.55,10.8),
               front='injector',top='edge',bevel=.5)
    m.box('finger_flange',(-3.1,-1.8,10.5),(3.1,1.8,11.25),'edge')
    turned(m,'plunger_stem',[(11.,.55),(13.9,.55)],6,'dark')
    turned(m,'thumb_pad',[(13.6,1.9),(14.9,1.9)],8,'edge')


def bandages(m):
    for y,name in ((-2.65,'front'),(2.65,'rear')):
        m.part('bandage_roll_'+name)
        loops = [[(x,y+2.6*math.cos(i*math.tau/8+math.pi/8),
                    -11.55+2.6*math.sin(i*math.tau/8+math.pi/8)) for i in range(8)]
                 for x in (-7.5,7.5)]
        for i in range(8):
            j=(i+1)%8
            m.poly([loops[0][i],loops[0][j],loops[1][j],loops[1][i]],'cream',
                   (0,loops[0][i][1]+loops[0][j][1]-2*y,
                    loops[0][i][2]+loops[0][j][2]+23.1))
        for index,normal in ((0,(-1,0,0)),(1,(1,0,0))):
            m.poly(loops[index],'roll_end',normal,
                   [((p[1]-y)/5.2+.5,.5-(p[2]+11.55)/5.2) for p in loops[index]],
                   group=f'end{index}')
    m.box('bundle_strap',(-1.9,-5.3,-14.25),(1.9,5.3,-8.7),'plastic')
    marked_box(m,'medical_patch',(-4.1,-3.5,-9.1),(4.1,3.5,-7.4),top='label',front='plastic')


def medkit(m, booster=False):
    marked_box(m,'case_body',(-10.,-4.55,-15.1),(10.,4.55,-4.),bevel=1.1)
    m.box('lid_seam',(-9.8,-4.6,-4.3),(9.8,4.6,-3.7),'dark')
    marked_box(m,'case_lid',(-10.,-4.55,-3.8),(10.,4.55,-2.),front='edge',bevel=1.1)
    m.ring_profile('carry_handle',[(-4.,-2.2),(4.,-2.2),(4.,.1),(-4.,.1)],
                   [(-2.8,-1.4),(2.8,-1.4),(2.8,-.7),(-2.8,-.7)],.65,'dark')
    for x,name in ((-7.,'left'),(7.,'right')):
        m.box('latch_'+name,(x-.7,-4.95,-5.5),(x+.7,-4.35,-2.35),
              'cream' if booster else 'edge')


def mega(m):
    marked_box(m,'medical_canister',(-6.8,-6.8,-11.8),(6.8,6.8,3.6),bevel=2.)
    turned(m,'base_rim',[(-12.,6.9),(-10.8,6.9)],8,'dark')
    turned(m,'sealed_lid',[(3.4,6.9),(5.5,6.9)],8,'edge')
    marked_box(m,'lid_marking',(-3.9,-3.9,5.3),(3.9,3.9,6.),front='edge')
    m.ring_profile('carry_handle',[(-3.2,5.8),(3.2,5.8),(3.2,8.1),(-3.2,8.1)],
                   [(-2.2,6.6),(2.2,6.6),(2.2,7.3),(-2.2,7.3)],.6,'dark',y=4.5)


def build_health(kind):
    if kind not in KINDS:
        raise ValueError('Unknown health pickup: '+kind)
    m=Mesh()
    if kind=='stimpack': injector(m)
    elif kind=='medium': bandages(m)
    elif kind in ('large','adrenaline'): medkit(m,kind=='adrenaline')
    else: mega(m)
    result=m.finish('pickup'); result.pop('rifle_bounds')
    result.update(anchors={},kind=kind,label=LABELS[kind])
    shading=PickupNormals(result)
    if kind=='stimpack':
        for name in ('needle','nozzle','plunger_stem','thumb_pad'):shading.rounded_sides(name)
        shading.bevel_box('injector_barrel')
    elif kind=='medium':
        for name in ('bandage_roll_front','bandage_roll_rear'):shading.rounded_sides(name,axis=0)
    elif kind in ('large','adrenaline'):
        for name in ('case_body','case_lid'):shading.bevel_box(name)
    elif kind=='mega':
        shading.bevel_box('medical_canister')
        for name in ('base_rim','sealed_lid'):shading.rounded_sides(name)
    return shading.finish()


def atlas_uvs(mesh):
    local=np.asarray(mesh['uvs'],dtype=float)
    if local.shape!=(len(mesh['faces']),3,2) or not np.isfinite(local).all() or local.min()<0 or local.max()>1:
        raise ValueError('Invalid local health UV coordinates')
    rectangles=np.asarray([REGIONS[material] for material in mesh['materials']])
    low,high=rectangles[:,:2],rectangles[:,2:]
    return (low[:,None,:]+.5+local*(high-low-1)[:,None,:])/256.
