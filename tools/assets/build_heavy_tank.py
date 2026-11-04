#!/usr/bin/env python3
"""Build the original Plastic Platoon tan toy heavy tank as two static MD2s.

No downloaded model or texture inputs. The turret is a separate model whose
origin is its yaw/pitch pivot; hull and turret share one small painted atlas.
Run with --review to render assembled views and an independently turned turret.
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

from md2_assets import HEADER, IDENT, MD2, ROOT, gl_strips, normal_table, raster, sha

DIRECTORY = "models/monsters/plastic_tank"
SKIN = f"{DIRECTORY}/tan.png"
MANIFEST = ROOT / "tools/assets/heavy-tank-manifest.json"
REVIEW = ROOT / "tools/assets/review/heavy-tank.png"
PIVOT = np.array([0., 0., 24.])
MUZZLE = [80., 0., 8.]
TAN, LIGHT, TRACK, RUBBER, EDGE, STENCIL, VENT, TREAD, WHEEL, HATCH, RIVET, PORT, LAMP, DARK, PANEL, EXHAUST = range(16)


def texture() -> bytes:
    image = Image.new("RGB", (256, 256))
    draw = ImageDraw.Draw(image)
    colors = [(196, 157, 102), (218, 182, 129), (113, 88, 54), (86, 70, 45),
              (165, 127, 77), (194, 155, 101), (180, 143, 93), (114, 87, 51),
              (176, 140, 87), (208, 169, 112), (188, 149, 94), (62, 54, 39),
              (223, 224, 151), (60, 48, 30), (194, 155, 101), (145, 112, 69)]
    for index, color in enumerate(colors):
        x, y = index % 4 * 64, index // 4 * 64
        draw.rectangle((x, y, x + 63, y + 63), fill=color)
        # Subtle deterministic mottling recalls molded pigment rather than rust.
        for py in range(3, 61, 7):
            for px in range(3, 61, 7):
                shift = ((px * 13 + py * 7 + index * 3) % 5) - 2
                draw.point((x + px, y + py), fill=tuple(max(0, min(255, c + shift)) for c in color))
    def tile(index):
        return index % 4 * 64, index // 4 * 64
    x, y = tile(STENCIL)
    draw.rounded_rectangle((x + 8, y + 8, x + 55, y + 55), radius=5, outline=(153, 117, 73), width=2)
    star = [(x + 32 + math.cos(-math.pi / 2 + i * math.pi / 5) * (16 if i % 2 == 0 else 6.5),
             y + 26 + math.sin(-math.pi / 2 + i * math.pi / 5) * (16 if i % 2 == 0 else 6.5)) for i in range(10)]
    draw.polygon(star, fill=(233, 211, 168))
    # Fixed tiny bitmap stencil: no host font dependency in runtime assets.
    glyphs = {"H": [5,5,7,5,5], "-": [0,0,7,0,0], "0": [7,5,5,5,7], "7": [7,1,2,2,2]}
    for column, letter in enumerate("H-07"):
        for row, bits in enumerate(glyphs[letter]):
            for bit in range(3):
                if bits & (1 << (2-bit)):
                    px, py = x + 17 + column*8 + bit*2, y + 44 + row*2
                    draw.rectangle((px,py,px+1,py+1),fill=(235,214,174))
    for index in (VENT, EXHAUST):
        x, y = tile(index)
        draw.rectangle((x + 7, y + 8, x + 56, y + 55), outline=(127, 96, 59), width=3)
        for py in range(15, 53, 7):
            draw.rectangle((x + 12, y + py, x + 51, y + py + 3), fill=(86, 66, 41))
            draw.line((x + 12, y + py + 4, x + 51, y + py + 4), fill=(207, 169, 112))
    x, y = tile(TREAD)
    for py in (12, 29, 46):
        draw.rectangle((x + 4, y + py, x + 59, y + py + 5), fill=(151, 115, 68))
        draw.line((x + 4, y + py + 6, x + 59, y + py + 6), fill=(79, 62, 41), width=2)
    x, y = tile(WHEEL)
    for bounds, fill in (((5, 5, 58, 58), (118, 91, 55)), ((9, 9, 54, 54), (190, 153, 95)),
                         ((16, 16, 47, 47), (162, 125, 75)), ((25, 25, 38, 38), (215, 176, 115))):
        draw.ellipse(tuple((x if n % 2 == 0 else y) + v for n, v in enumerate(bounds)), fill=fill)
    x, y = tile(HATCH)
    draw.ellipse((x + 5, y + 5, x + 58, y + 58), outline=(157, 121, 74), width=3)
    draw.rectangle((x + 22, y + 24, x + 41, y + 39), fill=(179, 139, 86), outline=(226, 192, 141), width=2)
    x, y = tile(RIVET)
    for px, py in ((13, 13), (50, 13), (13, 50), (50, 50)):
        draw.ellipse((x + px - 3, y + py - 3, x + px + 3, y + py + 3), fill=(225, 188, 131), outline=(143, 107, 65))
    x, y = tile(PORT)
    draw.ellipse((x + 8, y + 8, x + 55, y + 55), fill=(35, 32, 23), outline=(104, 83, 51), width=4)
    x, y = tile(LAMP)
    draw.ellipse((x + 6, y + 6, x + 57, y + 57), fill=(242, 235, 177), outline=(160, 138, 85), width=4)
    draw.line((x + 19, y + 13, x + 35, y + 13), fill=(255, 252, 215), width=4)
    x, y = tile(PANEL)
    draw.rounded_rectangle((x + 6, y + 7, x + 57, y + 56), radius=5, outline=(149, 112, 66), width=2)
    draw.line((x + 9, y + 10, x + 54, y + 10), fill=(222, 184, 127), width=2)
    out = io.BytesIO()
    image.save(out, format="PNG", compress_level=9)
    return out.getvalue()


class Mesh:
    def __init__(self):
        self.vertices, self.faces, self.uvs, self.normals = [], [], [], []

    @staticmethod
    def uv(material, u, v):
        # Inset each patch to keep bilinear/mipmap sampling away from neighbors.
        return [(material % 4 * 64 + 6 + u * 52) / 256,
                (material // 4 * 64 + 6 + v * 52) / 256]

    def poly(self, points, material=TAN, normal=None):
        points = np.asarray(points, dtype=float)
        face_normal = np.cross(points[1] - points[0], points[2] - points[0])
        if normal is not None and np.dot(face_normal, normal) < 0:
            points = points[::-1]
            face_normal = -face_normal
        face_normal /= np.linalg.norm(face_normal)
        base = len(self.vertices)
        self.vertices.extend(points.tolist())
        self.normals.extend([face_normal.tolist()] * len(points))
        if len(points) == 4:
            coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
        else:
            coords = [(.5 + .48 * math.cos(2 * math.pi * i / len(points)),
                       .5 + .48 * math.sin(2 * math.pi * i / len(points))) for i in range(len(points))]
        for i in range(1, len(points) - 1):
            self.faces.append([base, base + i, base + i + 1])
            self.uvs.append([self.uv(material, *coords[j]) for j in (0, i, i + 1)])

    def box(self, low, high, material=TAN, top=None, front=None):
        x, y, z = low
        X, Y, Z = high
        self.poly([(x,y,z), (X,y,z), (X,Y,z), (x,Y,z)], material, [0,0,-1])
        self.poly([(x,y,Z), (X,y,Z), (X,Y,Z), (x,Y,Z)], top if top is not None else material, [0,0,1])
        self.poly([(x,y,z), (X,y,z), (X,y,Z), (x,y,Z)], material, [0,-1,0])
        self.poly([(x,Y,z), (X,Y,z), (X,Y,Z), (x,Y,Z)], material, [0,1,0])
        self.poly([(x,y,z), (x,Y,z), (x,Y,Z), (x,y,Z)], material, [-1,0,0])
        self.poly([(X,y,z), (X,Y,z), (X,Y,Z), (X,y,Z)], front if front is not None else material, [1,0,0])

    def ring_hull(self, rings, material=TAN, top=PANEL, bottom=EDGE, side_materials=None):
        """Closed chamfered xy hull from (xmin,xmax,ymin,ymax,z,corner) rings."""
        loops = []
        for x, X, y, Y, z, r in rings:
            loops.append(np.array([(x+r,y,z), (X-r,y,z), (X,y+r,z), (X,Y-r,z),
                                   (X-r,Y,z), (x+r,Y,z), (x,Y-r,z), (x,y+r,z)]))
        centre = np.mean(np.concatenate(loops), axis=0)
        for band, (lower, upper) in enumerate(zip(loops, loops[1:])):
            for i in range(8):
                j = (i + 1) % 8
                points = [lower[i], lower[j], upper[j], upper[i]]
                surface = (side_materials or {}).get((band, i), material)
                self.poly(points, surface, np.mean(points, axis=0) - centre)
        self.poly(loops[0], bottom, [0,0,-1])
        self.poly(loops[-1], top, [0,0,1])

    def cylinder(self, start, end, radius, material=TAN, cap=None, segments=10):
        start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        axis = end - start
        axis /= np.linalg.norm(axis)
        ref = np.array([0.,0.,1.]) if abs(axis[2]) < .9 else np.array([1.,0.,0.])
        u = np.cross(axis, ref); u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        radial = np.array([u * math.cos(i*math.tau/segments) + v * math.sin(i*math.tau/segments) for i in range(segments)])
        a, b = start + radial * radius, end + radial * radius
        base = len(self.vertices)
        self.vertices.extend(a.tolist() + b.tolist())
        self.normals.extend(radial.tolist() * 2)
        for i in range(segments):
            j = (i + 1) % segments
            # The radial side points outward for this orthonormal basis.
            for face, coords in (([i,j,segments+j], [(0,0),(1,0),(1,1)]),
                                 ([i,segments+j,segments+i], [(0,0),(1,1),(0,1)])):
                self.faces.append([base + k for k in face])
                self.uvs.append([self.uv(material, *uv) for uv in coords])
        self.poly(a, cap if cap is not None else material, -axis)
        self.poly(b, cap if cap is not None else material, axis)

    def track(self, side):
        outer = np.array([[-46,-24],[45,-24],[55,-14],[55,3],[44,13],[-44,13],[-55,3],[-55,-14]], dtype=float)
        inner = np.array([[-43,-17],[42,-17],[47,-12],[47,0],[40,6],[-40,6],[-47,0],[-47,-12]], dtype=float)
        ys = sorted([side * 30., side * 42.])
        for i in range(8):
            j = (i + 1) % 8
            for y, direction in ((ys[0], -1), (ys[1], 1)):
                self.poly([(outer[i,0],y,outer[i,1]), (outer[j,0],y,outer[j,1]),
                           (inner[j,0],y,inner[j,1]), (inner[i,0],y,inner[i,1])], TRACK, [0,direction,0])
            self.poly([(outer[i,0],ys[0],outer[i,1]), (outer[j,0],ys[0],outer[j,1]),
                       (outer[j,0],ys[1],outer[j,1]), (outer[i,0],ys[1],outer[i,1])], TREAD,
                      [np.mean(outer[[i,j],0]),0,np.mean(outer[[i,j],1])+5])
            self.poly([(inner[i,0],ys[0],inner[i,1]), (inner[j,0],ys[0],inner[j,1]),
                       (inner[j,0],ys[1],inner[j,1]), (inner[i,0],ys[1],inner[i,1])], RUBBER,
                      [-np.mean(inner[[i,j],0]),0,-np.mean(inner[[i,j],1])-5])
        for x in (-36,-18,0,18,36):
            self.cylinder((x,side*31,-5), (x,side*41,-5), 10.3, EDGE, WHEEL, 10)
            self.cylinder((x,side*40.8,-5), (x,side*42.2,-5), 3.2, LIGHT, RIVET, 6)
        # Slightly proud tread shoes make the toy readable from above and below.
        for x in (-42,-28,-14,0,14,28,42):
            self.box((x-2.2,ys[0]-.25,10.8), (x+2.2,ys[1]+.25,13.7), TRACK, TREAD)
            self.box((x-2.2,ys[0]-.25,-24), (x+2.2,ys[1]+.25,-21.5), TRACK, TREAD)


def hull() -> Mesh:
    m = Mesh()
    m.ring_hull([(-50,50,-30,30,-19,5),(-53,53,-32,32,-15,6),(-53,53,-32,32,3,6),(-48,48,-29,29,8,6)], EDGE, TAN)
    m.ring_hull([(-49,48,-32,32,3,7),(-43,42,-28,28,21,6),(-41,40,-26,26,23,5)], TAN, PANEL)
    m.track(-1); m.track(1)
    # Dark turret race and tan molded bearing lip remain on the stationary hull.
    m.cylinder((0,0,22),(0,0,24),23,TRACK,TRACK,16)
    m.cylinder((0,0,23.5),(0,0,25),21,TAN,TAN,16)
    # Front glacis applique and two chunky plastic lamp guards.
    # Keep the applique clear of the sloped glacis after byte quantization.
    m.poly([(43.2,-18,20.4),(47.667,-18,7),(47.667,18,7),(43.2,18,20.4)], STENCIL, [1,0,.3])
    for side in (-1,1):
        y = side * 23
        # The lens is the guard's actual front face. A separate x=52.02
        # overlay quantizes onto x=52 in MD2 and fights the backing face.
        m.box((44,y-4,10), (52,y+4,17), EDGE, LIGHT, front=LAMP)
    # Raised grille plates: a sub-quantum offset would merge into the deck.
    for side in (-1,1):
        y = side * 17
        m.poly([(-39,y-7,23.75),(-24,y-7,23.75),(-24,y+7,23.75),(-39,y+7,23.75)], VENT, [0,0,1])
    m.box((-51,-20,-1),(-48,20,7),EDGE,EXHAUST)
    return m


def turret() -> Mesh:
    m = Mesh()
    m.cylinder((0,0,0),(0,0,2),20,EDGE,EDGE,16)
    m.ring_hull([(-25,28,-21,21,1,6),(-28,30,-23,23,5,7),(-24,26,-20,20,18,7),(-21,22,-17,17,21,6)], TAN, TAN)
    # Separate inset side panels carry a pale toy-army stencil.
    for side in (-1,1):
        y = side*23.12
        m.poly([(-15,y,6),(14,y,6),(12,side*20.8,16),(-15,side*20.8,16)], STENCIL, [0,side,0])
    m.ring_hull([(23,37,-10,10,3,3),(23,37,-10,10,14,3),(25,35,-8,8,16,2)], EDGE, LIGHT)
    m.cylinder((33,0,8),(73,0,8),3.5,TAN,TAN,12)
    m.cylinder((36,0,8),(39,0,8),4.5,EDGE,EDGE,12)
    m.cylinder((60,0,8),(64,0,8),4.2,LIGHT,LIGHT,12)
    # Paint the muzzle opening on its +X wall instead of layering a nearly
    # coplanar polygon over the cap; both would quantize to x=80.
    m.ring_hull([(73,80,-5,5,3,1),(73,80,-5,5,12,1),(74,79,-4,4,13,1)],
                TAN, LIGHT, side_materials={(0,2): PORT})
    # Cupola, hinge and molded lifting loops; all move with the turret.
    m.cylinder((-8,0,20.8),(-8,0,24),9,TAN,HATCH,12)
    m.box((-14,-1.6,23.7),(-2,1.6,24.8),EDGE,LIGHT)
    for side in (-1,1):
        y = side*12
        m.box((-15,y-1.1,20),(-8,y+1.1,23),EDGE,LIGHT)
    # Rear bustle storage and six molded rivet heads.
    m.box((-29,-12,7),(-25,12,15),EDGE,PANEL)
    for x in (-19,18):
        for y in (-12,12):
            m.cylinder((x,y,20),(x,y,21.6),1.4,LIGHT,LIGHT,6)
    return m


def encode(mesh: Mesh, name: str) -> bytes:
    p = np.asarray(mesh.vertices)
    # Quake II culls GL_FRONT: MD2 exterior triangles run clockwise when
    # viewed from outside. Keep the authored outward lighting normals, but
    # reverse each triangle AND its corresponding UV corners at export.
    faces = np.asarray(mesh.faces, dtype=np.int32)[:, ::-1]
    uvs = np.asarray(mesh.uvs)[:, ::-1, :]
    vectors = np.asarray(mesh.normals)
    scale = (np.maximum(np.ptp(p, axis=0), .001) / 255).astype('<f4')
    trans = p.min(axis=0).astype('<f4')
    q = np.clip(np.rint((p - trans)/scale),0,255).astype(np.uint8)
    decoded = q * scale + trans
    area = np.linalg.norm(np.cross(decoded[faces[:,1]] - decoded[faces[:,0]], decoded[faces[:,2]] - decoded[faces[:,0]]),axis=1)
    if (area < 1e-8).any():
        raise ValueError(f'{name}: MD2 quantization collapsed a triangle')
    normals = np.argmax(vectors @ normal_table().T, axis=1).astype(np.uint8)
    st, indices, keys = [], [], {}
    for coords in uvs:
        ids = []
        for uv in coords:
            key = tuple(np.rint(uv * 256 - .5).astype(int))
            if key not in keys:
                keys[key] = len(st); st.append(key)
            ids.append(keys[key])
        indices.append(ids)
    frame = struct.pack('<6f16s', *scale,*trans,b'idle01') + np.column_stack((q,normals)).astype(np.uint8).tobytes()
    sections = (SKIN.encode().ljust(64,b'\0'), np.asarray(st,dtype='<i2').tobytes(),
                np.column_stack((faces,indices)).astype('<u2').tobytes(), frame, gl_strips(faces,uvs))
    offsets, cursor = [], HEADER.size
    for part in sections:
        offsets.append(cursor); cursor += len(part)
    header = HEADER.pack(IDENT,8,256,256,len(frame),1,len(p),len(st),len(faces),len(sections[-1])//4,1,*offsets,cursor)
    data = header + b''.join(sections)
    model = MD2.read(data)
    if model.header[6] > 2048 or model.header[8] > 4096:
        raise ValueError(f'{name}: loader count exceeded')
    if len(model.faces) != len(faces):
        raise AssertionError("GL strip topology changed triangle count")
    triangles = model.positions[0][model.faces]
    crossed = np.cross(triangles[:, 1] - triangles[:, 0],
                       triangles[:, 2] - triangles[:, 0])
    lighting_normals = normal_table()[model.normals[0]][model.faces].mean(axis=1)
    if (np.einsum('ij,ij->i', crossed, lighting_normals) >= 0).any():
        raise ValueError(f'{name}: triangle winding disagrees with Quake II front-face culling')
    return data


def combined(hull_model, turret_model, yaw=0., pitch=0.):
    yaw, pitch = math.radians(yaw), math.radians(pitch)
    rz = np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
    ry = np.array([[math.cos(pitch),0,math.sin(pitch)],[0,1,0],[-math.sin(pitch),0,math.cos(pitch)]])
    rotation = rz @ ry
    moved = turret_model.positions[0] @ rotation.T + PIVOT
    n = normal_table()[turret_model.normals[0]] @ rotation.T
    return replace(hull_model,
                   faces=np.concatenate((hull_model.faces,turret_model.faces+hull_model.header[6])),
                   uvs=np.concatenate((hull_model.uvs,turret_model.uvs)),
                   positions=np.array([np.concatenate((hull_model.positions[0],moved))]),
                   normals=np.array([np.concatenate((hull_model.normals[0],np.argmax(n @ normal_table().T,axis=1)))]))


def review(models, png):
    hull_model, turret_model = (MD2.read(models[n]) for n in ('hull','turret'))
    canvas = Image.new('RGB',(1200,860),(22,25,30))
    draw = ImageDraw.Draw(canvas)
    draw.text((15,12),'Plastic Platoon | original tan plastic heavy tank | actual MD2 geometry + 256 px atlas',fill='white')
    texture_image = Image.open(io.BytesIO(png))
    for row,(yaw,pitch,label) in enumerate(((0,0,'Turret forward'),(95,-8,'Hull stationary; turret yaw +95 degrees, barrel -8 degrees'))):
        model = combined(hull_model,turret_model,yaw,pitch)
        for col,angle in enumerate((25,115,205,295)):
            pic,_ = raster(model,texture_image,angle,500,(np.array([7.,0.,10.]),91.),elevation=24,cull_front=True)
            canvas.paste(pic.resize((300,300),Image.Resampling.LANCZOS),(col*300,43+row*390))
            draw.text((col*300+12,375+row*390),f'View {angle} degrees',fill='#c4c9d0')
        draw.text((15,350+row*390),label,fill='#c4c9d0')
    draw.text((15,827),'Hull origin: ground at z=-24 | independent turret pivot: hull [0,0,24] | rocket muzzle: turret [80,0,8]',fill='#d0b481')
    REVIEW.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(REVIEW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',help='regenerate in memory and compare exact output bytes')
    parser.add_argument('--review',action='store_true',help='render assembled MD2 review sheet')
    args = parser.parse_args()
    models = {name:encode(build(),name) for name,build in (('hull',hull),('turret',turret))}
    png = texture()
    report = {'schema':1,'description':'Original molded tan toy tracked heavy tank, procedurally authored for Plastic Platoon',
              'builder':'tools/assets/build_heavy_tank.py','builder_sha256':sha(Path(__file__).read_bytes()),
              'sources':'Original geometry and texture; no external asset inputs',
              'face_winding':'Clockwise exterior triangles for Quake II GL_FRONT culling; outward lighting normals',
              'coordinate_contract':{'forward_axis':'+X','hull_ground_z':-24,'turret_pivot_in_hull':PIVOT.tolist(),
                                     'rocket_muzzle_in_turret':MUZZLE,'turret_yaw_degrees':'unrestricted',
                                     'barrel_pitch_degrees':[-10,10]},
              'models':[{ 'path':f'{DIRECTORY}/{name}.md2',**MD2.read(data).stats()} for name,data in models.items()],
              'texture':{'path':SKIN,'dimensions':[256,256],'sha256':sha(png),'file_bytes':len(png)},
              'review':'tools/assets/review/heavy-tank.png'}
    files = {ROOT/'baseq2'/f'{DIRECTORY}/{name}.md2':data for name,data in models.items()}
    files[ROOT/'baseq2'/SKIN] = png
    files[MANIFEST] = (json.dumps(report,indent=2)+'\n').encode()
    for path,data in files.items():
        if args.verify:
            if path.read_bytes() != data:
                raise ValueError(f'asset differs from reproducible build: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
    if args.review:
        review(models,png)
    for entry in report['models']:
        print(f"{'Verified' if args.verify else 'Built'} {entry['path']}: {entry['position_vertices']} vertices, {entry['triangles']} triangles, bounds {entry['bounds']}")


if __name__ == '__main__':
    main()
