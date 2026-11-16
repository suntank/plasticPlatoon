"""Armored boss gunship, fitted to the original Sandkeep helicopter envelope."""
import math
import numpy as np
from m16_geometry import Mesh
from dropship_geometry import hull,BODY_SOCKET,ROTOR_AXLE

DIRECTORY='models/monsters/plastic_boss'
MATERIALS={'plastic':0,'edge':1,'metal':2,'glass':3,'armor':4,'blade':5,
           'engine':6,'dark':7,'belly':8,'mark':10,'lamp':13,'wing':14}


def bore(m,name,x0,x1,y,z,radius,inside):
    """Closed cannon/launcher with an actual recessed dark mouth."""
    m.part(name)
    loops=[]
    for x,r in ((x0,radius),(x1,radius),(x1,inside),(x1-1.5,inside)):
        loops.append([(x,y+r*math.cos(i*math.tau/6),z+r*math.sin(i*math.tau/6)) for i in range(6)])
    for band,(a,b) in enumerate(zip(loops,loops[1:])):
        for i in range(6):
            j=(i+1)%6
            normal=np.array([0,(a[i][1]+a[j][1])/2-y,(a[i][2]+a[j][2])/2-z])
            if band==1:normal=np.array([1,0,0])
            if band==2:normal=-normal
            m.poly([a[i],a[j],b[j],b[i]],'metal' if band<2 else 'dark',normal,group=f'b{band}_{i}')
    m.poly(loops[0],'metal',(-1,0,0),group='rear')
    m.poly(loops[-1],'dark',(1,0,0),group='inside')


def body(m):
    windows={(b,s):'glass' for b in (2,3) for s in (3,4,5)}
    windows.update({(1,2):'mark',(1,6):'mark'})
    hull(m,'armored_fuselage',[(-45,9,59,72),(-26,21,48,77),
        (18,21,48,78),(45,12,53,70),(64,5,56,61)],windows,cap='belly')
    # Strong roof/canopy spars, with no transport doors or broad cargo cabin.
    m.limb('cockpit_spine',(18,0,78.4),(45,0,70.4),1.1,1.1,'edge',6)
    m.limb('windshield_spine',(45,0,70.4),(64,0,61.4),1,1,'edge',6)
    for side,label in ((-1,'left'),(1,'right')):
        first=len(m.vertices)
        hull(m,'armored_engine_'+label,[(-44,6.5,69,79),(-31,8.6,70,85),
             (-9,8.6,73,85),(3,6.6,74,82)],{(1,4):'engine',(1,2):'engine',(1,6):'engine'},cap='dark')
        for v in m.vertices[first:]:v[1]+=side*12
        m.limb('engine_exhaust_'+label,(-43,side*12,74),(-49,side*12,74),3.7,3.7,'dark',6)
        ylo,yhi=sorted((side*19,side*48))
        m.box('armored_wing_'+label,(-24,ylo,49),(-2,yhi,53),'wing','armor')
        m.box('rocket_housing_'+label,(-22,side*42.5-6.7,42),(-2,side*42.5+6.7,49),'armor','edge')
        for n,y in enumerate((side*40,side*45)):
            bore(m,'rocket_tube_'+label+str(n),-17,0,y,45,2.25,1.55)
        m.box('cannon_fairing_'+label,(24,side*15-4,47),(44,side*15+4,54),'armor')
        bore(m,'heavy_cannon_'+label,41,60,side*15,50,2.7,1.65)
        m.limb('landing_strut_'+label,(-20,side*16,49),(-20,side*27,38.2),1.8,1.8,'metal',6)
        m.limb('front_strut_'+label,(27,side*14,51),(27,side*27,38.2),1.8,1.8,'metal',6)
        m.limb('short_skid_'+label,(-35,side*27,38.2),(41,side*27,38.2),1.6,1.6,'dark',6)
        m.limb('skid_toe_'+label,(41,side*27,38.2),(48,side*27,43),1.6,1.6,'dark',6)
    hull(m,'armored_tail',[(-112,2.8,69,77),(-84,4.5,64,75),(-43,8.5,57,71)],material='armor')
    m.profile('tail_fin',[(-112,69),(-111,93),(-103,90),(-95,70)],1.6,'armor','edge')
    m.box('tailplane',(-104,-17,72),(-95,17,74),'wing','edge')
    m.limb('mast',(-3.9,.5,77),BODY_SOCKET,3.5,3.5,'metal',8)
    m.box('armored_chin',(44,-9,48),(58,9,54),'belly')
    m.box('nose_sensor',(61,-3,56.5),(65,3,59.5),'glass')


def rotor(m):
    cx,cy,_=ROTOR_AXLE
    m.limb('heavy_rotor_hub',(cx,cy,81.3),(cx,cy,94.6),3.8,3.8,'metal',8)
    for i in range(6):
        angle=i*math.tau/6
        outline=[(5,-2),(62,-3),(66,1.4),(8,2.2)]
        loops=[[(cx+x*math.cos(angle)-y*math.sin(angle),cy+x*math.sin(angle)+y*math.cos(angle),z)
                for x,y in outline] for z in (88.8,90.2)]
        m.part('six_blade_rotor_'+str(i))
        m.poly(loops[0],'dark',(0,0,-1),group='underside')
        m.poly(loops[1],'blade',(0,0,1),group='top')
        for side in range(4):
            j=(side+1)%4
            normal=np.cross(np.array(loops[0][j])-loops[0][side],[0,0,1])
            m.poly([loops[0][side],loops[0][j],loops[1][j],loops[1][side]],
                   'edge',normal,group='edge'+str(side))


def build(kind):
    m=Mesh();{'body':body,'main_rotor':rotor}[kind](m)
    mesh=m.finish(kind);mesh.pop('rifle_bounds')
    mesh['anchors']={'socket':list(BODY_SOCKET),'guns':[[60,-15,50],[60,15,50]],
                     'rockets':[[0,45,45],[0,40,45],[0,-40,45],[0,-45,45]]} if kind=='body' else {'axle':list(ROTOR_AXLE)}
    return mesh


def atlas_uvs(mesh):
    tiles=np.array([MATERIALS[m] for m in mesh['materials']])
    origins=np.column_stack((tiles%4,tiles//4))*64
    return (origins[:,None,:]+4.5+np.asarray(mesh['uvs'])*55)/256
