#!/usr/bin/env python3
"""Original low-poly ammunition pickups made from closed molded-plastic parts."""
import math
import numpy as np
from flamethrower_tanks import TANK_PROFILE, add_tank
from m16_geometry import Mesh

KINDS = ('shells', 'bullets', 'grenades', 'gl_ammo', 'rockets', 'cells', 'slugs')
LABELS = {'shells':'SHELLS', 'bullets':'HEAVY BULLETS', 'grenades':'FRAG',
          'gl_ammo':'GL ROUNDS', 'rockets':'ROCKETS', 'cells':'NAPALM', 'slugs':'SNIPER'}
# Pixel rectangles in the shared 256-square atlas layout. Each ammo type has
# its own label but the same UV convention and molded-plastic palette.
REGIONS = {'plastic':(4,4,60,60), 'dark':(68,4,124,60),
           'edge':(132,4,188,60), 'brass':(196,4,252,60),
           'label':(8,72,248,140), 'lid_label':(8,152,248,224),
           'band':(8,232,64,252),
           'tank_surface':(196,4,252,60)}  # Uses the brass tile on the fuel-only atlas.


def labeled_box(m, name, low, high, side_labels=False, lid_label=False):
    """A closed box whose actual faces carry correctly oriented lettering."""
    x,y,z = low; X,Y,Z = high
    m.part(name)
    specs = [([(x,y,z),(x,Y,z),(X,Y,z),(X,y,z)], (0,0,-1), 'plastic'),
             ([(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)], (0,0,1), 'lid_label' if lid_label else 'edge'),
             ([(x,y,z),(X,y,z),(X,y,Z),(x,y,Z)], (0,-1,0), 'label' if side_labels else 'plastic'),
             ([(X,Y,z),(x,Y,z),(x,Y,Z),(X,Y,Z)], (0,1,0), 'label' if side_labels else 'plastic'),
             ([(x,Y,z),(x,y,z),(x,y,Z),(x,Y,Z)], (-1,0,0), 'plastic'),
             ([(X,y,z),(X,Y,z),(X,Y,Z),(X,y,Z)], (1,0,0), 'plastic')]
    for face,(points,normal,material) in enumerate(specs):
        m.poly(points, material, normal, [(0,1),(1,1),(1,0),(0,0)], group=f'face{face}')


def add_case(m, kind):
    if kind == 'shells':
        x,y,bottom,top,lid_top = 10.,6.,-14.,-3.,-1.3
        handle_x,handle_y,handle_top = 4.,4.8,3.4
    else:
        x,y,bottom,top,lid_top = 14.5,9.2,-14.2,7.,8.7
        handle_x,handle_y,handle_top = 5.,7.8,12.4
    labeled_box(m, 'case_body', (-x,-y,bottom), (x,y,top), side_labels=True)
    m.box('lid_seam', (-x-.3,-y-.3,top-.35), (x+.3,y+.3,top+.2), 'dark')
    labeled_box(m, 'case_lid', (-x-.6,-y-.6,top+.1), (x+.6,y+.6,lid_top), lid_label=True)
    for side,name in ((-1,'left'),(1,'right')):
        cx = side * (x-2.)
        m.box('latch_'+name, (cx-.75,-y-.95,top-1.4), (cx+.75,-y-.35,lid_top-.1), 'dark')
    m.ring_profile('carry_handle', [(-handle_x,lid_top-.2),(handle_x,lid_top-.2),
                                   (handle_x,handle_top),(-handle_x,handle_top)],
                   [(-handle_x+1.2,lid_top+1.),(handle_x-1.2,lid_top+1.),
                    (handle_x-1.2,handle_top-1.),(-handle_x+1.2,handle_top-1.)],
                   .65, 'dark', y=handle_y)
    for side,name in ((-1,'front'),(1,'rear')):
        cy = side * (y-1.)
        m.box('base_rail_'+name, (-x+.8,cy-.7,bottom-.3), (x-.8,cy+.7,bottom+.4), 'dark')


def turned(m, name, rings, sides=8, material='plastic', bands=None, center=(0.,0.)):
    """Closed vertical cylinder/ogive with no zero-radius quantization slivers."""
    cx,cy = center
    loops = [[(cx+r*math.cos(math.pi/sides+i*math.tau/sides),
               cy+r*math.sin(math.pi/sides+i*math.tau/sides),z) for i in range(sides)]
             for z,r in rings]
    start = len(m.faces)
    m.loft(name, loops, material)
    if bands:
        for band, pigment in enumerate(bands):
            a = start + band*2*sides
            m.materials[a:a+2*sides] = [pigment]*(2*sides)


def add_grenade(m):
    turned(m, 'grenade_body', [(-12.,1.7),(-10.3,3.2),(-6.1,3.45),(-3.,2.7),(-1.7,1.3)],
           8, 'plastic')
    m.box('fuse', (-1.25,-1.1,-2.), (1.25,1.1,-.1), 'dark')
    m.profile('safety_lever', [(-1.3,.45),(1.3,.45),(3.7,-3.0),(3.7,-7.9),
                               (3.,-7.9),(3.,-3.3),(.9,-.25),(-1.3,-.25)], .55, 'edge')
    m.ring_profile('pull_ring', [(-2.7,-.5),(-.7,-.5),(-.7,-2.7),(-2.7,-2.7)],
                   [(-2.2,-1.),(-1.2,-1.),(-1.2,-2.2),(-2.2,-2.2)], .35, 'dark', y=-1.25)


def add_gl_round(m):
    turned(m, 'launcher_round', [(-12.,2.65),(-10.7,2.65),(-5.5,2.35),(-3.8,2.35),(-2.,1.1)],
           8, 'plastic', ['brass','brass','band','plastic'])


def add_rocket(m):
    turned(m, 'rocket_body', [(-9.6,1.55),(5.2,1.55),(8.7,1.1),(12.3,.25)],
           8, 'plastic', ['plastic','band','edge'])
    turned(m, 'rocket_nozzle', [(-11.8,1.2),(-9.2,1.2)], 6, 'dark')
    # Four broad solid fins, rather than open triangles with invisible backs.
    for index in range(4):
        angle = index*math.pi/2
        before = len(m.vertices)
        m.profile('rocket_fin_'+str(index), [(1.1,-11.6),(2.65,-11.6),(2.65,-7.4),(1.1,-8.9)],
                  .25, 'plastic', 'edge')
        for i in range(before, len(m.vertices)):
            x,y,z = m.vertices[i]
            m.vertices[i] = [x*math.cos(angle)-y*math.sin(angle),
                             x*math.sin(angle)+y*math.cos(angle),z]


def add_fuel_tanks(m):
    # Retain the pickup height and the backpack's profile with one fewer
    # ring at the bottom shoulder to fit the static ammo budget.
    profile = [(-14.2+1.19*(z-TANK_PROFILE[0][0]),radius)
               for z,radius in (TANK_PROFILE[0],*TANK_PROFILE[2:])]
    for side,name in ((-1,'right'),(1,'left')):
        y = side*3.45
        add_tank(m, 'fuel_tank_'+name, (0.,y), 'tank_surface',profile)
        m.profile('tank_valve_'+name,
                  [(-1.2,2.2),(1.18,2.3),(.85,4.08),(-.71,4.12)],
                  1.07, 'dark', 'edge', y=y)
    m.box('tank_manifold', (-1.,-4.9,3.15), (1.,4.9,4.20), 'edge')
    # Set the label just proud of the tanks so both faces are legible.
    start = len(m.vertices)
    labeled_box(m, 'tank_label_strap', (-2.65,-3.12,-6.25), (2.65,3.12,-4.0), side_labels=True)
    for point in m.vertices[start:]:
        point[0],point[1] = -point[1],point[0]


def add_sniper_rounds(m):
    labeled_box(m, 'rounds_clip', (-12.,-2.4,-14.), (12.,2.4,-11.8), side_labels=True)
    for index,x in enumerate((-8.7,-2.9,2.9,8.7)):
        turned(m, 'sniper_round_'+str(index), [(-12.8,1.6),(-4.3,1.6),(-2.5,1.05),(.7,.25)],
               6, 'brass', ['brass','brass','edge'], center=(x,0.))
    m.box('clip_back', (-11.,1.9,-13.), (11.,2.5,-8.5), 'plastic')


def build_ammo(kind):
    if kind not in KINDS:
        raise ValueError('Unknown ammunition: '+kind)
    m = Mesh()
    if kind in ('shells','bullets'):
        add_case(m, kind)
    else:
        {'grenades':add_grenade,'gl_ammo':add_gl_round,'rockets':add_rocket,
         'cells':add_fuel_tanks,'slugs':add_sniper_rounds}[kind](m)
    result = m.finish('pickup')
    result.pop('rifle_bounds')
    result['anchors'] = {}
    result['kind'] = kind
    result['label'] = LABELS[kind]
    return result


def atlas_uvs(mesh):
    local = np.asarray(mesh['uvs'], dtype=float)
    if local.shape != (len(mesh['faces']),3,2) or not np.isfinite(local).all() or local.min()<0 or local.max()>1:
        raise ValueError('Invalid local ammo UV coordinates')
    rectangles = np.asarray([REGIONS[material] for material in mesh['materials']])
    low, high = rectangles[:,:2], rectangles[:,2:]
    return (low[:,None,:] + .5 + local*(high-low-1)[:,None,:])/256.
