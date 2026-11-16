"""Original molded toy-soldier fragments and distinct insect shell/leg pieces."""
import math
import numpy as np
from m16_geometry import Mesh


def oval(center,radii,sides=8):
    x,y,z=center;rx,ry=radii
    return [(x+rx*math.cos((i+.5)*math.tau/sides),
             y+ry*math.sin((i+.5)*math.tau/sides),z) for i in range(sides)]


def blob(m,name,center,radii,material='plastic',sides=6):
    x,y,z=center;rx,ry,rz=radii
    m.loft(name,[oval((x,y,z+height*rz),(rx*width,ry*width),sides)
                for height,width in ((-1,.45),(0,1),(1,.45))],material)


def bent_leg(m,spider):
    points=np.array([(-8,0,0),(0,0,1),(8 if spider else 6,3,-4),
                     (11 if spider else 8,4,-5)],dtype=float)
    loops=[]
    for i,point in enumerate(points):
        tangent=points[min(i+1,3)]-points[max(i-1,0)];tangent/=np.linalg.norm(tangent)
        u=np.cross(tangent,[0,0,1]);u/=np.linalg.norm(u);v=np.cross(tangent,u)
        radius=([1.8,1.65,1.05,.6] if spider else [2.1,1.9,1.35,.7])[i]
        loops.append([point+radius*(u*math.cos(j*math.tau/6)+v*math.sin(j*math.tau/6)) for j in range(6)])
    m.loft('continuous_bent_insect_leg',loops,'plastic')


def build(kind):
    m=Mesh()
    if kind=='arm':
        m.limb('torn_sleeve',(-8,-1,2),(1,0,2),3,2.6,'plastic')
        m.limb('forearm',(1,0,2),(9,2,2.3),2.3,1.7,'edge')
        blob(m,'mitten',(11,3,2.4),(2.6,2,1.8),'plastic')
        blob(m,'thumb',(9.5,5,2.5),(1.7,1,1),'edge')
    elif kind=='leg':
        m.limb('trouser_leg',(0,0,14),(0,0,-5),3.8,3.1,'plastic')
        m.limb('boot_shaft',(0,0,-5),(0,0,-12),3.4,3.6,'dark')
        m.profile('boot_foot',[(-3.5,-15),(6,-15),(6.8,-13),(4.5,-10),(-3.5,-10)],
                  3.6,'dark','edge')
        m.limb('cuff',(0,0,-4),(0,0,-6),3.8,3.8,'edge')
    elif kind=='bone':
        m.limb('broken_limb',(-1,-8,2),(0,7,2),2.1,2.8,'plastic')
        blob(m,'joint',(0,8,2),(3.2,3.1,2.5),'edge')
    elif kind=='bone2':
        blob(m,'broken_joint',(0,0,0),(3.6,4.3,1.7),'edge')
    elif kind=='chest':
        m.tube('vest_torso',[(-12,0,0,5,3.8),(-6,0,0,7.5,5.2),
                              (6,0,0,7.2,5),(9,0,0,4.5,3.5)],8,'plastic',(True,True),'inner')
        m.limb('neck_stub',(8,0,0),(12,0,0),2.7,2.4,'edge')
        for i,y in enumerate((-4.7,0,4.7)):
            m.box('vest_pouch_'+str(i),(-4,y-1.75,4),(3,y+1.75,6.5),'edge')
        m.box('belt',(-11,-5.4,-4.1),(-8,5.4,4.1),'dark')
    elif kind in ('head','head2','skull'):
        m.loft('toy_head',[oval((0,0,z),(rx,ry)) for z,rx,ry in
                           ((-4,2.4,2.2),(-2,3.7,3.2),(1.8,3.7,3.2))],'edge')
        m.loft('molded_helmet',[oval((0,0,z),(rx,ry)) for z,rx,ry in
                               ((1.1,5,4.5),(4.3,4.2,4),(6,1.6,1.5))],'plastic')
        m.box('nose',(3.3,-.6,-1),(4.6,.6,.3),'edge')
        for i,y in enumerate((-1.7,1.7)):
            m.box('eye_'+str(i),(3.35,y-.35,.2),(3.7,y+.35,.7),'dark')
    elif kind=='sm_meat':
        blob(m,'broken_plastic_piece',(0,0,0),(5,2.5,3),'plastic')
    elif kind=='sm_metal':
        m.profile('bent_machine_plate',[(-5,-1),(0,-2),(5,0),(4,3),(-4,2)],1.8,'metal','dark')
        m.box('raised_rib',(-3,-2,-.2),(3,2,1),'edge')
    elif kind=='gear':
        outer=[(4*math.cos(i*math.tau/6),4*math.sin(i*math.tau/6)) for i in range(6)]
        inner=[(1.7*math.cos(i*math.tau/6),1.7*math.sin(i*math.tau/6)) for i in range(6)]
        m.ring_profile('broken_hex_fastener',outer,inner,1.2,'metal')
    elif kind.endswith('_chunk'):
        spider=kind.startswith('spider')
        m.tube('broken_carapace',[(-8 if spider else -6,0,0,2,2),
               (-2,0,0,6.3 if spider else 4.6,4.8),
               (6 if spider else 4,0,0,4.2 if spider else 3.4,3.5)],
               8 if spider else 6,'plastic',(True,True),'wound')
        m.limb('exposed_end',(5 if spider else 3,0,0),(10 if spider else 8,0,0),2.5,1.8,'inner')
    elif kind.endswith('_leg'):
        bent_leg(m,kind.startswith('spider'))
    else:raise ValueError('Unknown body part: '+kind)
    result=m.finish('world');result.pop('rifle_bounds');result['anchors']={}
    return result
