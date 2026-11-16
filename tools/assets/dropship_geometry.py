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
         'blade':(132,72,188,128),'lamp':(196,72,252,128),
         'cargo':(4,144,124,252),'star':(136,144,248,252)}


def hull(m,name,sections,materials=None,material='plastic',cap='edge'):
    """Closed chamfered hull; every painted panel is an actual exterior face."""
    loops=[]
    for x,width,low,high in sections:
        b=min(width*.30,(high-low)*.20)
        loops.append([(x,-width+b,low),(x,width-b,low),(x,width,low+b),
                      (x,width,high-b),(x,width-b,high),(x,-width+b,high),
                      (x,-width,high-b),(x,-width,low+b)])
    m.part(name)
    for band,(a,b) in enumerate(zip(loops,loops[1:])):
        for side in range(8):
            j=(side+1)%8
            points=[a[side],a[j],b[j],b[side]]
            centre=(np.asarray(a).mean(axis=0)+np.asarray(b).mean(axis=0))/2
            uv=[(0,1),(0,0),(1,0),(1,1)]
            if side==6:uv=[(1,0),(1,1),(0,1),(0,0)]
            m.poly(points,(materials or {}).get((band,side),material),
                   np.asarray(points).mean(axis=0)-centre,uv,group=f'band{band}_side{side}')
    m.poly(loops[0],cap,(-1,0,0),group='rear_cap')
    m.poly(loops[-1],cap,(1,0,0),group='front_cap')


def body(m):
    panes={(band,side):'glass' for band in (2,3) for side in (2,3,4,5,6)}
    panes.update({(1,2):'cargo',(1,6):'cargo'})
    hull(m,'transport_fuselage',[(-47,10,55,69),(-29,28,46,76),
                                (17,28,46,77),(44,19,50,72),(64,8,54,61)],panes)
    for a,b,name in (((17,0,77.4),(44,0,72.4),'canopy_roof_spar'),
                     ((44,0,72.4),(64,0,61.4),'windshield_spar')):
        m.limb(name,a,b,.85,.85,'edge',6)
    # Two raised engine housings keep the original large twin-engine profile.
    for side,name in ((-1,'port'),(1,'starboard')):
        start=len(m.vertices)
        hull(m,'engine_'+name,[(-42,5.8,69,76),(-32,7.4,70,82),(-13,6.6,73,82)],
             {(0,4):'engine',(1,4):'engine'},cap='dark')
        for i in range(start,len(m.vertices)):m.vertices[i][1]+=side*12.5
        m.limb('exhaust_'+name,(-42,side*12.5,73),(-47,side*12.5,73),3.1,3.1,'dark',6)
    m.limb('mast_socket',(-3.9,.5,76.5),BODY_SOCKET,3.1,3.1,'metal',8)
    hull(m,'rising_tail_boom',[(-112,2.7,70,76),(-85,4.7,65,75),(-43,9,58,72)])
    m.profile('vertical_tail_fin',[(-112,70),(-112,91.5),(-103,88.5),(-96,71)],1.4,'plastic','edge')
    m.box('horizontal_tailplane',(-105,-16,71.5),(-96,16,73.6),'plastic','edge')
    for side,name in ((-1,'port'),(1,'starboard')):
        low,high=sorted((side*21,side*43.8))
        m.box('stub_wing_'+name,(-12,low,55.5),(13,high,58),'plastic','edge')
        start=len(m.vertices)
        hull(m,'wing_pod_'+name,[(-18,4.2,50,59),(-10,6.4,49,61),(17,5.6,50,60)],
             {(0,4):'edge',(1,4):'edge'},cap='dark')
        for i in range(start,len(m.vertices)):m.vertices[i][1]+=side*36.5
        y=side*30.
        m.limb('skid_rail_'+name,(-36,y,38.2),(44,y,38.2),1.6,1.6,'metal',6)
        m.limb('skid_toe_'+name,(44,y,38.2),(54,y,43.2),1.6,1.6,'metal',6)
        for x,position in ((-21,'rear'),(26,'front')):
            m.limb('skid_support_'+name+'_'+position,(x,side*19,48.5),(x,y,39.2),
                   1.35,1.35,'plastic',6)
    # Compact chin fittings echo the original craft, without tan gunship pods.
    m.box('chin_mount',(48,-3.2,48.3),(57,3.2,53.5),'edge')
    m.limb('chin_barrel',(56,0,50.6),(65,0,50.6),1.45,1.45,'dark',6)
    m.box('nose_lamp',(58,-3.3,53.7),(63,3.3,56.3),'lamp')


def main_rotor(m):
    # The existing client rotates around (0,.25) and translates that axle to
    # the body socket. Z is already encoded at its original mission height.
    cx,cy,_=ROTOR_AXLE
    m.limb('rotor_hub',(cx,cy,81.3),(cx,cy,94.6),3.5,3.5,'metal',8)
    for index in range(4):
        angle=index*math.pi/2
        outline=[(5,-2.2),(63.5,-3.6),(66,1.4),(8,2.2)]
        loops=[[(cx+x*math.cos(angle)-y*math.sin(angle),
                 cy+x*math.sin(angle)+y*math.cos(angle),z) for x,y in outline]
               for z in (88.8,90.2)]
        m.part('rotor_blade_'+str(index))
        m.poly(loops[0],'dark',(0,0,-1),group='lower')
        m.poly(loops[1],'blade',(0,0,1),group='upper')
        for i in range(4):
            j=(i+1)%4
            m.poly([loops[0][i],loops[0][j],loops[1][j],loops[1][i]],'edge',
                   np.asarray(loops[0][i])+np.asarray(loops[0][j])-[2*cx,2*cy,177.6],group=f'edge{i}')


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
