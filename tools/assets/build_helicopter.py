#!/usr/bin/env python3
"""Reproduce the original tan plastic gunship and independent rotor MD2s.

The existing tank's molded tan material palette and mesh primitives provide the
shared toy-army finish. No external meshes, textures, fonts or Blender needed.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import io
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw

from build_heavy_tank import (Mesh, texture as tank_texture, TAN, LIGHT, EDGE,
                             STENCIL, VENT, HATCH, RIVET, PORT, LAMP, DARK, PANEL)
from md2_assets import HEADER, IDENT, MD2, ROOT, gl_strips, normal_table, raster, sha

DIRECTORY = "models/monsters/plastic_helicopter"
SKIN = f"{DIRECTORY}/tan.png"
MANIFEST = ROOT / "tools/assets/helicopter-manifest.json"
REVIEW = ROOT / "tools/assets/review/helicopter.png"
MAIN_PIVOT = np.array([0., 0., 48.])
TAIL_PIVOT = np.array([-88., 8., 16.])
GUN_MUZZLES = [[64., -24., -10.], [64., 24., -10.]]
ROCKET_MUZZLES = [[30., -46., -2.], [30., 46., -2.]]
GLASS = 3  # The tank's rubber tile becomes glossy brown cockpit glazing.


def texture() -> bytes:
    image = Image.open(io.BytesIO(tank_texture())).convert("RGB")
    draw = ImageDraw.Draw(image)
    x, y = GLASS % 4 * 64, GLASS // 4 * 64
    draw.rectangle((x, y, x + 63, y + 63), fill=(61, 57, 43))
    draw.polygon([(x + 7, y + 8), (x + 52, y + 8), (x + 7, y + 47)], fill=(95, 88, 65))
    draw.polygon([(x + 12, y + 8), (x + 21, y + 8), (x + 7, y + 24), (x + 7, y + 15)], fill=(154, 143, 104))
    draw.line((x + 9, y + 55, x + 55, y + 55), fill=(46, 43, 32), width=2)
    out = io.BytesIO()
    image.save(out, format="PNG", compress_level=9)
    return out.getvalue()


def x_hull(mesh, sections, materials=None, cap=TAN):
    """Chamfered closed fuselage from x/halfwidth/bottom/top sections."""
    loops = []
    for x, width, low, high in sections:
        bevel = min(width * .32, (high - low) * .2)
        loops.append(np.array([(x,-width+bevel,low), (x,width-bevel,low),
                               (x,width,low+bevel), (x,width,high-bevel),
                               (x,width-bevel,high), (x,-width+bevel,high),
                               (x,-width,high-bevel), (x,-width,low+bevel)]))
    center = np.concatenate(loops).mean(axis=0)
    for band, (a, b) in enumerate(zip(loops, loops[1:])):
        for side in range(8):
            points = [a[side], a[(side+1)%8], b[(side+1)%8], b[side]]
            mesh.poly(points, (materials or {}).get((band, side), TAN),
                      np.mean(points, axis=0) - center)
    mesh.poly(loops[0], cap, [-1, 0, 0])
    mesh.poly(loops[-1], cap, [1, 0, 0])


def body() -> Mesh:
    m = Mesh()
    # Broad, angular canopy and tapered nose keep the toy gunship readable.
    # Glazing is painted on the actual fuselage faces, not a coplanar overlay.
    materials = {(0,2): STENCIL, (0,6): STENCIL,
                 (1,2): PANEL, (1,6): PANEL,
                 (2,2): GLASS, (2,3): GLASS, (2,4): GLASS,
                 (2,5): GLASS, (2,6): GLASS,
                 (3,2): GLASS, (3,3): GLASS, (3,4): GLASS,
                 (3,5): GLASS, (3,6): GLASS}
    x_hull(m, [(-38,11,-11,14), (-23,22,-17,20), (18,23,-15,27),
               (41,18,-12,23), (57,8,-6,7)], materials, EDGE)
    # A raised center spar separates the port/starboard windshield panes.
    m.cylinder((19,0,28),(42,0,24),1.6,LIGHT,LIGHT,6)
    m.cylinder((42,0,24),(57,0,9),1.6,LIGHT,LIGHT,6)
    # Twin turbine cowlings, molded vents and exhausts behind the rotor mast.
    for side in (-1,1):
        y = side * 10
        m.ring_hull([(-29,8,y-7,y+7,20,3),(-27,9,y-8,y+8,31,3),
                     (-23,5,y-6,y+6,37,3)], TAN, VENT)
        m.cylinder((-31,y,27),(-38,y,27),4.2,EDGE,PORT,8)
    m.cylinder((0,0,30),(0,0,45),4.0,EDGE,EDGE,10)
    m.cylinder((0,0,43),(0,0,48),6.2,TAN,HATCH,10)
    # Long rising boom, vertical stabilizer, and horizontal tailplane.
    x_hull(m, [(-88,2.8,13,19),(-72,4.8,11,21),(-34,8.8,3,19)], cap=EDGE)
    for side in (-1,1):
        y = side * 1.8
        m.poly([(-91,y,14),(-90,y,44),(-78,y,38),(-72,y,15)], TAN, [0,side,0])
    # Thickness on the fin: four edge strips join its two exterior sides.
    fin = [(-91,14),(-90,44),(-78,38),(-72,15)]
    for i,(x,z) in enumerate(fin):
        X,Z = fin[(i+1)%4]
        p = [(x,-1.8,z),(X,-1.8,Z),(X,1.8,Z),(x,1.8,z)]
        m.poly(p,LIGHT,np.mean(p,axis=0)-[-82,0,26])
    m.box((-79,-19,17),(-71,19,19.5),TAN,LIGHT)
    m.cylinder((-88,0,16),(-88,8,16),2.7,EDGE,EDGE,8)
    # Sturdy tan skids with swept-up front toes and four visible supports.
    for side in (-1,1):
        y = side * 26
        m.cylinder((-36,y,-29.5),(45,y,-29.5),2.5,EDGE,TAN,8)
        m.cylinder((45,y,-29.5),(54,y,-23),2.5,EDGE,TAN,8)
        for x in (-19,23):
            m.cylinder((x,side*16,-11),(x,y,-28),2.2,TAN,TAN,6)
        # Stub wing carries the seven-tube launcher, clear of the main body.
        m.box((-6, min(side*18,side*46),-5),
              (14, max(side*18,side*46),0),TAN,LIGHT)
        y = side * 46
        m.cylinder((-3,y,-2),(27,y,-2),9.0,TAN,EDGE,10)
        # Seven individually modeled launch tubes make the armament explicit.
        offsets = [(0,0)] + [(5.3*math.cos(i*math.tau/6),5.3*math.sin(i*math.tau/6)) for i in range(6)]
        for dy,dz in offsets:
            m.cylinder((27.5,y+dy,-2+dz),(30,y+dy,-2+dz),2.25,LIGHT,PORT,6)
        # Paired forward machineguns align with the gameplay muzzle contract.
        y = side * 24
        m.box((22,y-3.5,-14),(39,y+3.5,-6),EDGE,PANEL)
        m.cylinder((37,y,-10),(60,y,-10),2.0,DARK,DARK,8)
        m.cylinder((58,y,-10),(64,y,-10),2.7,EDGE,PORT,8)
    # Chin searchlight is its own non-overlapping exterior cap.
    m.cylinder((45,0,-6),(49,0,-11),4.0,EDGE,LAMP,8)
    return m


def main_rotor() -> Mesh:
    m = Mesh()
    m.cylinder((0,0,-2),(0,0,3.5),6,TAN,HATCH,12)
    for i in range(4):
        angle = i * math.pi/2
        rotation = np.array([[math.cos(angle),-math.sin(angle),0],
                             [math.sin(angle),math.cos(angle),0],[0,0,1]])
        blade = Mesh()
        # Thick blades have visible upper/lower faces from every flight angle.
        blade.box((6,-2.2,-.8),(19,2.2,1.4),EDGE,LIGHT)
        blade.poly([(17,-3,-.6),(88,-5,-.6),(92,1,-.6),(19,3,-.6)],DARK,[0,0,-1])
        blade.poly([(17,-3,1.2),(88,-5,1.2),(92,1,1.2),(19,3,1.2)],TAN,[0,0,1])
        outline = [(17,-3),(88,-5),(92,1),(19,3)]
        for j,(x,y) in enumerate(outline):
            X,Y = outline[(j+1)%4]
            p = [(x,y,-.6),(X,Y,-.6),(X,Y,1.2),(x,y,1.2)]
            blade.poly(p,EDGE,np.mean(p,axis=0)-[50,0,0])
        # A light outer tip is actual geometry with no stacked top decal.
        # Edge ends already define the blade's full 92-unit sweep radius.
        merge(m,blade,rotation)
    return m


def tail_rotor() -> Mesh:
    m = Mesh()
    # Axis along local +Y; gameplay rotates this model's PITCH around Y.
    m.cylinder((0,-1.5,0),(0,2.5,0),2.6,EDGE,HATCH,8)
    for i in range(4):
        angle = i * math.pi/2
        rotation = np.array([[math.cos(angle),0,math.sin(angle)],
                             [0,1,0],[-math.sin(angle),0,math.cos(angle)]])
        blade=Mesh()
        blade.box((2,-.6,-1.4),(17,.8,1.4),TAN,LIGHT)
        merge(m,blade,rotation)
    return m


def merge(target, source, rotation):
    base = len(target.vertices)
    target.vertices.extend((np.asarray(source.vertices) @ rotation.T).tolist())
    target.normals.extend((np.asarray(source.normals) @ rotation.T).tolist())
    target.faces.extend((np.asarray(source.faces)+base).tolist())
    target.uvs.extend(source.uvs)


def encode(mesh: Mesh, name: str, frames: int=1) -> bytes:
    p = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces,dtype=np.int32)[:,::-1]
    uvs = np.asarray(mesh.uvs)[:,::-1,:]
    scale = (np.maximum(np.ptp(p,axis=0),.001)/255).astype('<f4')
    trans = p.min(axis=0).astype('<f4')
    q = np.clip(np.rint((p-trans)/scale),0,255).astype(np.uint8)
    normals = np.argmax(np.asarray(mesh.normals) @ normal_table().T,axis=1).astype(np.uint8)
    st,indices,keys = [],[],{}
    for coords in uvs:
        ids=[]
        for uv in coords:
            key=tuple(np.rint(uv*256-.5).astype(int))
            if key not in keys:
                keys[key]=len(st);st.append(key)
            ids.append(keys[key])
        indices.append(ids)
    vertices=np.column_stack((q,normals)).astype(np.uint8).tobytes()
    frame_size=40+len(vertices)
    timeline=b''.join(struct.pack('<6f16s',*scale,*trans,f'flight{i:02}'.encode())+vertices for i in range(frames))
    sections=(SKIN.encode().ljust(64,b'\0'),np.asarray(st,dtype='<i2').tobytes(),
              np.column_stack((faces,indices)).astype('<u2').tobytes(),timeline,gl_strips(faces,uvs))
    offsets,cursor=[],HEADER.size
    for part in sections:
        offsets.append(cursor);cursor+=len(part)
    data=HEADER.pack(IDENT,8,256,256,frame_size,1,len(p),len(st),len(faces),len(sections[-1])//4,frames,*offsets,cursor)+b''.join(sections)
    model=MD2.read(data)
    if len(p)>2048 or len(faces)>4096:
        raise ValueError(f'{name}: loader geometry limit exceeded')
    triangles=model.positions[0][model.faces]
    cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    light=normal_table()[model.normals[0]][model.faces].mean(axis=1)
    if (np.einsum('ij,ij->i',cross,light)>=0).any():
        raise ValueError(f'{name}: degenerate or inverted face after quantization')
    return data


def combined(models, main_angle=0., tail_angle=0.):
    parts=[]
    for name,pivot,angle,axis in [('body',np.zeros(3),0,2),('main_rotor',MAIN_PIVOT,main_angle,2),('tail_rotor',TAIL_PIVOT,tail_angle,1)]:
        model=models[name]
        angle=math.radians(angle)
        if axis==2:
            r=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1]])
        else:
            r=np.array([[math.cos(angle),0,math.sin(angle)],[0,1,0],[-math.sin(angle),0,math.cos(angle)]])
        parts.append((model,model.positions[0]@r.T+pivot,normal_table()[model.normals[0]]@r.T))
    offsets=np.cumsum([0]+[part[0].header[6] for part in parts[:-1]])
    return replace(models['body'],
        faces=np.concatenate([p[0].faces+offset for p,offset in zip(parts,offsets)]),
        uvs=np.concatenate([p[0].uvs for p in parts]),
        positions=np.array([np.concatenate([p[1] for p in parts])]),
        normals=np.array([np.argmax(np.concatenate([p[2] for p in parts])@normal_table().T,axis=1)]))


def review(models,png):
    decoded={name:MD2.read(data) for name,data in models.items()}
    canvas=Image.new('RGB',(1440,1010),(22,25,30))
    draw=ImageDraw.Draw(canvas)
    draw.text((18,15),'Plastic Platoon | tan plastic gunship | actual MD2 models and 256 px tank-matched atlas',fill='white')
    skin=Image.open(io.BytesIO(png))
    for row,(rotor,tail,label) in enumerate(((15,20,'Main rotor 15 degrees | tail rotor 20 degrees'),(55,65,'Independent rotor rotation | same stationary fuselage'))):
        model=combined(decoded,rotor,tail)
        for col,angle in enumerate((25,115,205,295)):
            pic,_=raster(model,skin,angle,600,(np.array([0.,0.,6.]),105),elevation=24,cull_front=True)
            canvas.paste(pic.resize((360,360),Image.Resampling.LANCZOS),(col*360,45+row*440))
            draw.text((col*360+18,415+row*440),f'View {angle} degrees',fill='#c4c9d0')
        draw.text((18,450+row*440),label,fill='#d0b481')
    draw.text((18,950),'Twin machineguns | paired seven-tube rocket pods | separate four-blade main and tail rotors | molded tan landing skids',fill='#d0b481')
    draw.text((18,978),'Main rotor pivot: [0,0,48], yaw spin | tail rotor pivot: [-88,8,16], pitch spin | body animation slots: 0-31',fill='#c4c9d0')
    REVIEW.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(REVIEW)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--review',action='store_true')
    args=parser.parse_args()
    models={name:encode(build(),name,frames) for name,build,frames in [('body',body,32),('main_rotor',main_rotor,1),('tail_rotor',tail_rotor,1)]}
    png=texture()
    report={'schema':1,'description':'Original tan molded plastic attack helicopter with twin machineguns and seven-tube rocket pods',
            'builder':'tools/assets/build_helicopter.py','builder_sha256':sha(Path(__file__).read_bytes()),
            'shared_geometry_library':'tools/assets/build_heavy_tank.py',
            'shared_geometry_library_sha256':sha((ROOT/'tools/assets/build_heavy_tank.py').read_bytes()),
            'sources':'Original procedural geometry; tank palette extended with cockpit glazing; no external inputs',
            'face_winding':'Clockwise exterior triangles for Quake II GL_FRONT culling; outward lighting normals',
            'coordinate_contract':{'forward_axis':'+X','main_rotor_pivot':MAIN_PIVOT.tolist(),'main_rotor_axis':'local Z / yaw',
                                   'tail_rotor_pivot':TAIL_PIVOT.tolist(),'tail_rotor_axis':'local Y / pitch',
                                   'machinegun_muzzles':GUN_MUZZLES,'rocket_muzzles':ROCKET_MUZZLES,'body_frames':32},
            'models':[{'path':f'{DIRECTORY}/{name}.md2',**MD2.read(data).stats()} for name,data in models.items()],
            'texture':{'path':SKIN,'dimensions':[256,256],'sha256':sha(png),'file_bytes':len(png)},
            'review':'tools/assets/review/helicopter.png'}
    files={ROOT/'baseq2'/f'{DIRECTORY}/{name}.md2':data for name,data in models.items()}
    files[ROOT/'baseq2'/SKIN]=png
    files[MANIFEST]=(json.dumps(report,indent=2)+'\n').encode()
    for path,data in files.items():
        if args.verify:
            if path.read_bytes()!=data:
                raise ValueError(f'asset differs from reproducible build: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if args.review:
        review(models,png)
    for entry in report['models']:
        print(f"{'Verified' if args.verify else 'Built'} {entry['path']}: {entry['position_vertices']} vertices, {entry['triangles']} triangles, bounds {entry['bounds']}")


if __name__=='__main__':
    main()
