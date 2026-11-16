#!/usr/bin/env python3
"""Original low-poly boots, helmet, plate carrier and hollow armor bracer."""
import math
import numpy as np
from m16_geometry import Mesh
from pickup_normals import PickupNormals

KINDS=('shard','jacket','combat','body')
REGIONS={'plastic':(4,4,60,60),'dark':(68,4,124,60),
         'edge':(132,4,188,60),'webbing':(196,4,252,60),
         'sole':(4,72,60,128),'lining':(68,72,124,128),
         'tier':(136,72,248,184),'cuff':(4,144,116,252)}


def oval(rx,ry,z,cx=0.,cy=0.,sides=8):
    return [(cx+rx*math.cos(i*math.tau/sides),cy+ry*math.sin(i*math.tau/sides),z)
            for i in range(sides)]


def cuff(m,name,zlo,zhi,rx,ry,thickness,cx=0.,cy=0.,sides=6,material='cuff'):
    """A closed annular wall with a real opening through both ends."""
    outer=[oval(rx,ry,z,cx,cy,sides) for z in (zlo,zhi)]
    inner=[oval(rx-thickness,ry-thickness,z,cx,cy,sides) for z in (zlo,zhi)]
    m.part(name)
    for i in range(sides):
        j=(i+1)%sides
        normal=(outer[0][i][0]+outer[0][j][0]-2*cx,
                outer[0][i][1]+outer[0][j][1]-2*cy,0)
        m.poly([outer[0][i],outer[0][j],outer[1][j],outer[1][i]],material,normal,
               [(0,1),(1,1),(1,0),(0,0)],group=f'outer{i}')
        m.poly([inner[0][j],inner[0][i],inner[1][i],inner[1][j]],'lining',
               [-v for v in normal],group=f'inner{i}')
        for k,direction in ((0,-1),(1,1)):
            m.poly([outer[k][i],outer[k][j],inner[k][j],inner[k][i]],'edge',
                   (0,0,direction),group=f'rim{k}_{i}')


def shard(m):
    cuff(m,'open_wrist_guard',-5.1,5.1,4.6,3.2,.8)
    m.profile('guard_plate',[(-3.6,-2.8),(-2.5,-4.1),(2.5,-4.1),
                             (3.6,-2.8),(3.6,2.8),(2.5,4.1),(-2.5,4.1),(-3.6,2.8)],
              .5,'tier','edge',y=-2.65)


def boots(m):
    # The separate shafts retain an open cuff. Foot solids close the inside
    # at ankle height, as a boot should, without plugging its visible mouth.
    for x,name in ((-7.1,'left'),(7.1,'right')):
        outline=[(-3.2,-8.8),(3.2,-8.8),(4.5,-7.1),(4.5,6.5),
                 (3.3,8.5),(-3.3,8.5),(-4.5,6.5),(-4.5,-7.1)]
        sole=[[(x+a,b,z) for a,b in outline] for z in (-11.8,-10.5)]
        m.loft('sole_'+name,sole,'sole')
        lower=[(x+a*.97,b*.98,-10.65) for a,b in outline]
        upper=[(x+a*.88,b*.95, -7.4 if b<0 else -5.8) for a,b in outline]
        m.loft('foot_'+name,[lower,upper],'plastic')
        cuff(m,'open_boot_shaft_'+name,-7.,10.6,3.5,4.7,.75,cx=x,cy=3.55)
        m.profile('shin_plate_'+name,[(x-2.6,1.2),(x+2.6,1.2),(x+2.9,6.8),
                                     (x+2.1,9.2),(x-2.1,9.2),(x-2.9,6.8)],
                  .55,'tier','edge',y=-.95)


def helmet(m):
    outer=[oval(rx,ry,z) for z,rx,ry in ((-2.25,8.45,9.4),(3.9,7.5,8.4),
                                        (7.2,4.7,5.2),(8.55,1.25,1.4))]
    inner=[oval(rx,ry,z) for z,rx,ry in ((-2.25,7.4,8.3),(3.3,6.5,7.3),
                                        (6.3,3.8,4.25),(7.4,1.,1.1))]
    m.part('hollow_helmet_shell')
    for loops,material,direction in ((outer,'plastic',1),(inner,'lining',-1)):
        for band,(a,b) in enumerate(zip(loops,loops[1:])):
            for i in range(8):
                j=(i+1)%8
                normal=(direction*(a[i][0]+a[j][0]),direction*(a[i][1]+a[j][1]),0)
                m.poly([a[i],a[j],b[j],b[i]],material,normal,group=f'{material}{band}_{i}')
        m.poly(loops[-1],material,(0,0,direction),group=material+'_crown')
    for i in range(8):
        j=(i+1)%8
        m.poly([outer[0][i],outer[0][j],inner[0][j],inner[0][i]],'edge',(0,0,-1),group=f'lip{i}')
    m.ring_profile('chin_strap',[(-6.5,-1.9),(6.5,-1.9),(3.2,-8.55),(-3.2,-8.55)],
                   [(-5.35,-2.7),(5.35,-2.7),(2.55,-7.6),(-2.55,-7.6)],.55,'webbing')
    m.profile('helmet_badge',[(-1.65,-1.4),(1.65,-1.4),(1.65,1.7),(-1.65,1.7)],
              .45,'tier','edge',y=-8.95)


def vest(m):
    outline=[(-8.4,-11.8),(8.4,-11.8),(10.,-5.2),(9.2,1.3),
             (7.0,4.2),(6.4,10.6),(3.4,10.9),(2.5,6.),
             (-2.5,6.),(-3.4,10.9),(-6.4,10.6),(-7.,4.2),(-9.2,1.3),(-10.,-5.2)]
    for y,name in ((-5.75,'chest'),(5.75,'back')):
        m.profile(name+'_armor_panel',outline,1.05,'plastic','edge',y=y)
        m.box('waist_band_'+name,(-8.65,y-1.25,-8.5),(8.65,y+1.25,-6.65),'webbing')
    for x,name in ((-5.0,'left'),(5.0,'right')):
        m.box('shoulder_bridge_'+name,(x-1.35,-5.75,9.75),(x+1.35,5.75,11.8),'webbing')
    for x,name in ((-8.1,'left'),(8.1,'right')):
        m.box('side_bridge_'+name,(x-1.1,-5.75,-8.3),(x+1.1,5.75,1.4),'plastic')
    for x,name in ((-5.2,'left'),(0.,'center'),(5.2,'right')):
        first=len(m.faces)
        m.box('front_pouch_'+name,(x-2.05,-8.95,-4.2),(x+2.05,-6.55,1.3),
              'edge')
        if name=='center':
            m.materials[first+4:first+6]=['tier','tier']


def build_armor(kind):
    if kind not in KINDS: raise ValueError('Unknown armor: '+kind)
    m=Mesh()
    {'shard':shard,'jacket':boots,'combat':helmet,'body':vest}[kind](m)
    result=m.finish('pickup');result.pop('rifle_bounds')
    result.update(anchors={},kind=kind)
    shading=PickupNormals(result)
    for part in result['parts']:
        name=part['name'];faces=shading.part(name)
        if name.startswith(('open_wrist_guard','open_boot_shaft')):
            materials=np.array(result['materials'])[faces]
            shading.smooth(faces[materials=='cuff'])
            shading.smooth(faces[materials=='lining'])
            shading.flat(faces[materials=='edge'])
        elif name=='hollow_helmet_shell':
            materials=np.array(result['materials'])[faces]
            shading.smooth(faces[materials=='plastic'])
            shading.smooth(faces[materials=='lining'])
        elif name.startswith('sole_'):
            shading.rounded_sides(name)
        elif name.startswith('foot_'):
            bottom=shading.face_normals[faces,2]<-.99999
            shading.smooth(faces[~bottom]);shading.flat(faces[bottom])
    return shading.finish()


def atlas_uvs(mesh):
    local=np.asarray(mesh['uvs'],dtype=float)
    if local.shape!=(len(mesh['faces']),3,2) or not np.isfinite(local).all() or local.min()<0 or local.max()>1:
        raise ValueError('Invalid local armor UVs')
    rectangles=np.asarray([REGIONS[material] for material in mesh['materials']])
    low,high=rectangles[:,:2],rectangles[:,2:]
    return (low[:,None,:]+.5+local*(high-low-1)[:,None,:])/256.
