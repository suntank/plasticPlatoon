#!/usr/bin/env python3
"""Original green transport helicopter, fitted to the existing mission envelope."""
import math
import numpy as np
from m16_geometry import Mesh

KINDS=('body','main_rotor')
BODY_SOCKET=(-3.9,.5,81.3)
ROTOR_AXLE=(0.,.25,81.3)
REGIONS={'plastic':(4,4,60,60),'dark':(68,4,124,60),'edge':(132,4,188,60),
         'glass':(196,4,252,60),'engine':(4,72,60,128),'metal':(68,72,124,128),
         'blade':(132,72,188,128),'lamp':(196,72,252,104),'marker':(196,108,252,136),
         'cargo':(4,144,124,252),
         'windshield':(132,144,252,196),'intake':(132,204,188,252),
         'step':(196,204,252,252)}


def hull(m,name,sections,materials=None,material='plastic',cap='edge',y=0.,roof_uv=False):
    """Closed chamfered hull; every painted panel is an actual exterior face."""
    loops=[]
    for x,width,low,high in sections:
        b=min(width*.30,(high-low)*.20)
        loops.append([(x,y-width+b,low),(x,y+width-b,low),(x,y+width,low+b),
                      (x,y+width,high-b),(x,y+width-b,high),(x,y-width+b,high),
                      (x,y-width,high-b),(x,y-width,low+b)])
    m.part(name)
    for band,(a,b) in enumerate(zip(loops,loops[1:])):
        for side in range(8):
            j=(side+1)%8
            points=[a[side],a[j],b[j],b[side]]
            centre=(np.asarray(a).mean(axis=0)+np.asarray(b).mean(axis=0))/2
            uv=[(0,1),(0,0),(1,0),(1,1)]
            if side==6:
                uv=[(1,0),(1,1),(0,1),(0,0)]
            elif side==4 and roof_uv:
                uv=[(1,1),(0,1),(0,0),(1,0)]
            m.poly(points,(materials or {}).get((band,side),material),
                   np.asarray(points).mean(axis=0)-centre,uv,group=f'band{band}_side{side}')
    m.poly(loops[0],cap,(-1,0,0),group='rear_cap')
    m.poly(loops[-1],cap,(1,0,0),group='front_cap')


def body(m):
    sections = [(-51,10,55,68),(-30,28,46,75.5),(17,28,46,77.4),
                (35,25,48,76),(54,16.5,50.5,64),(64,9,53.5,60.5)]
    panels = {(band,side): 'dark' for band in range(len(sections)-1) for side in (0,1,7)}
    panels.update({(band,side): 'glass' for band in (2,3) for side in (2,3,5,6)})
    panels.update({(1,2):'cargo',(1,6):'cargo',(3,4):'windshield',(4,4):'edge'})
    hull(m,'transport_fuselage',sections,panels,roof_uv=True)
    m.limb('mast_socket',(-3.9,.5,76.5),BODY_SOCKET,3.1,3.1,'metal',8)

    hull(m,'rising_tail_boom',[(-112,2.8,70,75),(-84,4.2,65,74),(-43,8.5,57,72)],
         {(0,1):'dark',(0,7):'dark',(1,1):'dark',(1,7):'dark'})
    fin = [(-94,81),(-96,87.4),(-102,91.5),(-109,90),
           (-112,82),(-111,74),(-104,70),(-97,74.4)]
    # A recessed molded fan reads from either side of the open tail shroud.
    cx, cz = -103.4, 81.8
    opening = [(cx+5.7*math.cos(i*math.tau/8),cz+5.7*math.sin(i*math.tau/8)) for i in range(8)]
    m.ring_profile('vertical_tail_fin',fin,opening,2.2)
    fan = [(cx+radius*math.cos((i+offset)*math.tau/4),
            cz+radius*math.sin((i+offset)*math.tau/4))
           for i in range(4) for offset,radius in ((.06,6.2),(.24,6.4),(.40,2.0))]
    m.profile('tail_fan',fan,.65,'metal','dark')
    m.box('horizontal_tailplane',(-105,-16,71.5),(-96,16,73.6),'plastic','edge')

    for side,name in ((-1,'port'),(1,'starboard')):
        hull(m,'engine_'+name,[(-45,4.6,70.5,77.5),(-35,6.8,70.8,82),
                              (-11,5.8,73,81)],
             {(1,4):'engine',(1,2):'engine',(1,6):'engine'},cap='intake',y=side*14.5,roof_uv=True)
        low,high=sorted((side*21,side*41.8))
        m.box('stub_wing_'+name,(-12,low,51),(13,high,53.5),'dark','step')
        hull(m,'wing_pod_'+name,[(-19,3.4,50,55),(-10,5.4,48.5,56.5),
                                (14,5.4,48.5,56.5),(21,3.2,50,55)],
             {(1,4):'step',(2,2 if side>0 else 6):'marker'},cap='edge',y=side*37.8,roof_uv=True)
        skid = [(-38,40,1.2),(-31,38.2,1.65),(42,38.2,1.65),(55,43.5,1.2)]
        m.loft('skid_rail_'+name,[[(x,side*30+r*math.cos(i*math.tau/6),
                                   z+r*math.sin(i*math.tau/6)) for i in range(6)]
                                 for x,z,r in skid],'metal')
        for x,position in ((-21,'rear'),(26,'front')):
            m.limb('skid_support_'+name+'_'+position,(x,side*20,48.6),(x-4,side*30,39.3),
                   1.8,1.45,'plastic',4)
    hull(m,'nose_searchlight',[(47,4.5,48.5,53),(58.5,3.5,49.5,54.5)],
         material='metal',cap='lamp')


def main_rotor(m):
    # The existing client rotates around (0,.25) and translates that axle to
    # the body socket. Z is already encoded at its original mission height.
    cx,cy,_=ROTOR_AXLE
    hub = [(81.3,2.7),(89.2,5.7),(94.6,2.7)]
    m.loft('rotor_hub',[[(cx+r*math.cos(i*math.tau/6),cy+r*math.sin(i*math.tau/6),z)
                        for i in range(6)] for z,r in hub],'metal')
    for index in range(4):
        angle=index*math.pi/2
        outline=[(4.2,-2.4),(63,-4.8),(66,-.7),(4.2,2.7)]
        loops=[[(cx+x*math.cos(angle)-y*math.sin(angle),
                 cy+x*math.sin(angle)+y*math.cos(angle),z) for x,y in outline]
               for z in (88.8,90.2)]
        m.part('rotor_blade_'+str(index))
        # Project the blade atlas radially so the tip band follows the span.
        uv=[((x-4.2)/(66-4.2),(y+4.8)/7.5) for x,y in outline]
        m.poly(loops[0],'blade',(0,0,-1),uv,group='lower')
        m.poly(loops[1],'blade',(0,0,1),uv,group='upper')
        for i in range(4):
            j=(i+1)%4
            outward=np.cross(np.asarray(loops[0][j])-loops[0][i],(0,0,1))
            m.poly([loops[0][i],loops[0][j],loops[1][j],loops[1][i]],'edge',
                   outward,group=f'edge{i}')


def build_dropship(kind):
    if kind not in KINDS:raise ValueError('Unknown dropship part: '+kind)
    m=Mesh();{'body':body,'main_rotor':main_rotor}[kind](m)
    result=m.finish(kind);result.pop('rifle_bounds')
    result.update(anchors={'socket':list(BODY_SOCKET)} if kind=='body' else {'axle':list(ROTOR_AXLE)},kind=kind)
    return result


def atlas_uvs(mesh):
    local=np.asarray(mesh['uvs'],dtype=float)
    if local.shape!=(len(mesh['faces']),3,2) or not np.isfinite(local).all() or local.min()<0 or local.max()>1:
        raise ValueError('Invalid dropship UVs')
    rectangles=np.asarray([REGIONS[material] for material in mesh['materials']])
    low,high=rectangles[:,:2],rectangles[:,2:]
    return (low[:,None,:]+.5+local*(high-low-1)[:,None,:])/256.
