#!/usr/bin/env python3
"""Render the shipped MD2 experiment in Blender without inventing geometry.

Run with Blender's Python, for example:
  blender -b -t 4 -P tools/assets/render_m16.py -- --output /tmp/m16-studio
These are explicitly studio previews. The engine capture companion supplies
actual gameplay screenshots. UVs and vertex positions are read from the exact
MD2 files, and the scene file keeps each imported model editable.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import struct
import sys

import bpy
from mathutils import Vector


def read_md2(path: Path, frame: int):
    data = path.read_bytes()
    h = struct.unpack_from('<17i', data)
    ident, version, sw, sh, stride, ns, nv, nt, nf, nc, frames, os, ot, of, ofr, oc, end = h
    if ident != 844121161 or version != 8 or len(data) != end:
        raise ValueError(f'Invalid MD2: {path}')
    if not 0 <= frame < frames:
        raise ValueError(f'Frame {frame} outside {frames} in {path}')
    skins = [data[os+i*64:os+(i+1)*64].split(b'\0')[0].decode() for i in range(ns)]
    at = ofr + stride*frame
    sx,sy,sz,tx,ty,tz = struct.unpack_from('<6f', data, at)
    vertices, normals = [], []
    for i in range(nv):
        x,y,z,n = struct.unpack_from('<4B', data, at+40+i*4)
        vertices.append((x*sx+tx,y*sy+ty,z*sz+tz))
        normals.append(n)
    faces, uvs = [], []
    at = oc
    while True:
        count, = struct.unpack_from('<i', data, at); at += 4
        if not count: break
        row = [struct.unpack_from('<ffi',data,at+i*12) for i in range(abs(count))]
        at += abs(count)*12
        for i in range(2,abs(count)):
            ids = (0,i-1,i) if count<0 else ((i-2,i-1,i) if i%2==0 else (i-1,i-2,i))
            # Quake II aliases have clockwise exterior triangles. Blender uses
            # counter-clockwise front faces, so reverse both geometry and UVs.
            ids = ids[::-1]
            faces.append(tuple(row[j][2] for j in ids))
            uvs.append(tuple((row[j][0],1-row[j][1]) for j in ids))
    if len(faces) != nf:
        raise ValueError(f'Unexpected GL command triangle count in {path}')
    return vertices, faces, uvs, normals, skins


def material(name, color, roughness=.58):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    node=mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Roughness'].default_value=roughness
    node.inputs['Metallic'].default_value=0
    return mat


def load_model(scene, root, relative, name, frame=0, skin=None):
    verts,faces,uvs,normal_ids,skins=read_md2(root/'baseq2'/relative,frame)
    mesh=bpy.data.meshes.new(name+'_mesh')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    uv_layer=mesh.uv_layers.new(name='MD2 UV')
    for polygon,coords in zip(mesh.polygons,uvs):
        for loop,uv in zip(polygon.loop_indices,coords):uv_layer.data[loop].uv=uv
    normals_path=root/'src/client/refresh/constants/anorms.h'
    normal_table=[tuple(float(v) for v in row.split(','))
                  for row in re.findall(r'\{\s*([\d.eE+\-,\s]+)\}',normals_path.read_text())]
    for polygon in mesh.polygons:polygon.use_smooth=True
    mesh.normals_split_custom_set_from_vertices([normal_table[i] for i in normal_ids])
    obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj)
    obj['asset_path']=str(relative);obj['source_frame']=frame
    obj['source_triangles']=len(faces)
    texture=root/'baseq2'/(skin or skins[0])
    if not texture.is_file():raise FileNotFoundError(texture)
    mat=material(name+'_exported_texture',(1,1,1))
    nt=mat.node_tree
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(texture),check_existing=True)
    tex.interpolation='Linear';tex.extension='REPEAT'
    nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
    obj.data.materials.append(mat)
    return obj


def look_at(obj,point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()


def light(scene,name,location,power,size,point,color=(1,1,1)):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=location;look_at(obj,point)


def setup_scene(name,args,width,height):
    scene=bpy.data.scenes.new(name)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=args.samples
    scene.cycles.use_denoising=False
    scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=args.scale
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene.render.film_transparent=False
    scene.view_settings.view_transform='Standard'
    scene.view_settings.look='Medium High Contrast'
    scene.view_settings.exposure=0;scene.view_settings.gamma=1
    world=bpy.data.worlds.new(name+'_world');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.2,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.35
    scene.world=world
    cam_data=bpy.data.cameras.new(name+'_camera')
    cam=bpy.data.objects.new(name+'_camera',cam_data);scene.collection.objects.link(cam);scene.camera=cam
    return scene,cam


def ground(scene,z):
    mesh=bpy.data.meshes.new('Studio_floor_mesh')
    mesh.from_pydata([(-500,-500,z),(500,-500,z),(500,500,z),(-500,500,z)],[],[(0,1,2,3)])
    obj=bpy.data.objects.new('Studio floor (preview only)',mesh);scene.collection.objects.link(obj)
    obj.data.materials.append(material('Neutral studio floor',(.12,.14,.17),.86))


def stage_item(args):
    s,c=setup_scene('Pickup studio | exported MD2',args,1600,900)
    obj=load_model(s,args.repo,'models/weapons/g_machn/tris.md2','M16 pickup')
    verts=[v.co for v in obj.data.vertices]
    low=Vector([min(v[i] for v in verts) for i in range(3)])
    high=Vector([max(v[i] for v in verts) for i in range(3)])
    # Fixed framing from the measured original pickup, shared by before/after.
    center=Vector((-.1480954,-.03440785,16.88015403))
    c.location=center+Vector((48,-125,60));look_at(c,center);c.data.type='ORTHO';c.data.ortho_scale=92
    ground(s,5.19664422)
    light(s,'Broad key',center+Vector((-15,-45,100)),145000,72,center)
    light(s,'Soft fill',center+Vector((45,65,50)),75000,75,center,(.77,.88,1))
    light(s,'Rim',center+Vector((-55,40,55)),95000,50,center,(1,.88,.72))
    s['preview_notice']='Studio rendering of shipped MD2. Lighting and floor are not game assets.'
    return s,'m16_pickup_studio.png'


def stage_held(args):
    s,c=setup_scene('Soldier holding M16 | exported MD2',args,1600,1372)
    load_model(s,args.repo,'players/soldier/tris.md2','Existing soldier body',args.frame)
    load_model(s,args.repo,'players/soldier/w_machinegun.md2','M16 held player weapon',args.frame)
    center=Vector((7,-1,3))
    c.location=center+Vector((75,-115,48));look_at(c,center);c.data.type='ORTHO';c.data.ortho_scale=69
    ground(s,-24)
    light(s,'Broad key',(-25,-65,95),150000,70,center)
    light(s,'Soft fill',(65,50,50),75000,60,center,(.8,.9,1))
    light(s,'Rim',(-30,45,80),110000,45,center,(1,.87,.7))
    s['preview_notice']='Studio rendering of existing soldier plus replacement MD2 in original animation frame.'
    return s,'m16_held_studio.png'


def stage_fps(args):
    s,c=setup_scene('First person | exported MD2 at engine origin',args,1600,900)
    gun=load_model(s,args.repo,'models/weapons/v_machn/tris.md2','M16 and first-person hands')
    gun.location=args.fps_offset
    c.location=(0,0,0);look_at(c,(100,0,0));c.data.type='PERSP';c.data.sensor_fit='HORIZONTAL';c.data.angle=math.radians(90)
    c.data.clip_start=.1;c.data.clip_end=400
    # No hand or arm is added by this renderer; everything visible in the gun
    # object must be present in the shipped first-person MD2.
    light(s,'First-person key',(10,-35,55),50000,65,(25,-8,-8))
    light(s,'First-person fill',(45,35,25),28000,50,(25,-8,-8),(.8,.9,1))
    s['preview_notice']='Studio camera at Quake II eye origin, 90 degree horizontal FOV; not gameplay capture.'
    return s,'m16_fps_studio.png'


def stage_source(args,detail):
    """Keep the generated primitives separate for direct Blender editing."""
    sys.path.insert(0,str(args.repo/'tools/assets'))
    from m16_geometry import build_m16, MATERIALS
    data=build_m16(detail)
    s,c=setup_scene('Editable primitives | '+detail,args,1600,900)
    atlas=args.source_atlas or args.repo/'baseq2/models/weapons/g_machn/skin.png'
    mat=material('Original M16 atlas | '+detail,(1,1,1))
    nt=mat.node_tree;tex=nt.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(atlas),check_existing=True)
    tex.interpolation='Linear';tex.extension='REPEAT'
    nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
    for part in data['parts']:
        start=part['first_triangle'];stop=start+part['triangle_count']
        faces=data['faces'][start:stop]
        ids=sorted({v for face in faces for v in face});mapping={v:i for i,v in enumerate(ids)}
        mesh=bpy.data.meshes.new(part['name']+'_primitive_mesh')
        mesh.from_pydata([data['vertices'][i] for i in ids],[],
                         [[mapping[v] for v in face] for face in faces])
        mesh.update();layer=mesh.uv_layers.new(name='Original M16 atlas')
        for polygon,uvs,semantic in zip(mesh.polygons,data['uvs'][start:stop],data['materials'][start:stop]):
            tile=MATERIALS.index(semantic)
            for loop,(u,v) in zip(polygon.loop_indices,uvs):
                layer.data[loop].uv=((tile%4*64+4.5+u*55)/256,
                                     1-(tile//4*64+4.5+v*55)/256)
            polygon.use_smooth=True
        mesh.normals_split_custom_set_from_vertices([data['normals'][i] for i in ids])
        obj=bpy.data.objects.new(part['name'],mesh);s.collection.objects.link(obj)
        obj.data.materials.append(mat);obj['triangle_count']=part['triangle_count']
        obj['source']='tools/assets/m16_geometry.py';obj['detail']=detail
    center=Vector((50,0,-7 if detail=='view' else -4))
    c.location=center+Vector((55,-180,65));look_at(c,center);c.data.type='ORTHO';c.data.ortho_scale=122
    ground(s,-33 if detail=='view' else -21)
    light(s,'Broad key',(30,-65,115),190000,85,center)
    light(s,'Soft fill',(85,70,60),100000,80,center,(.8,.9,1))
    light(s,'Rim',(-10,50,75),125000,55,center,(1,.87,.7))
    s['preview_notice']='Original modeled primitives in artistic units; source coordinates before MD2 placement and quantization.'
    s['muzzle']=data['anchors']['muzzle'];s['rear_sight']=data['anchors']['rear_sight'];s['front_sight']=data['anchors']['front_sight']
    return s,'m16_source_'+detail+'.png'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=32)
    parser.add_argument('--scale',type=int,default=100)
    parser.add_argument('--frame',type=int,default=0)
    parser.add_argument('--fps-offset',type=float,nargs=3,default=(0.,0.,0.),
                        help='Optional design-review offset only; leave zero for actual MD2 placement.')
    parser.add_argument('--shots',nargs='+',choices=['item','held','fps','source_world','source_view'],default=['item','held','fps'])
    parser.add_argument('--render-shots',nargs='+',choices=['item','held','fps','source_world','source_view'],
                        help='Render only these shots while retaining all staged scenes in the Blender file.')
    parser.add_argument('--include-source',action='store_true',help='Add unrendered editable primitive scenes to the Blender file.')
    parser.add_argument('--source-atlas',type=Path,help='Optional atlas path for source review before writing the shipped MD2s.')
    parser.add_argument('--blend-name',default='m16_editable_studio.blend')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.output.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    scenes=[]
    for kind in args.shots:
        if kind.startswith('source_'):scene,name=stage_source(args,kind[7:])
        else:scene,name={'item':stage_item,'held':stage_held,'fps':stage_fps}[kind](args)
        scene.render.filepath=str(args.output/name);scene['render_kind']=kind;scenes.append(scene)
    if args.include_source:
        for detail in ('world','view'):stage_source(args,detail)
    bpy.context.window.scene=scenes[0]
    for unused in list(bpy.data.scenes):
        if not unused.objects:
            bpy.data.scenes.remove(unused)
    for image in bpy.data.images:
        if image.source=='FILE':image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output/args.blend_name))
    for scene in scenes:
        if args.render_shots is not None and scene['render_kind'] not in args.render_shots:
            continue
        bpy.context.window.scene=scene
        bpy.ops.render.render(write_still=True,scene=scene.name)
    print('M16 studio render complete: '+str(args.output))

if __name__=='__main__':main()
