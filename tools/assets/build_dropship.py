#!/usr/bin/env python3
"""Build the original low-poly green player transport and its linked rotor."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from build_m16 import encode_md2
from md2_assets import MD2
from dropship_geometry import build_dropship,atlas_uvs,REGIONS,BODY_SOCKET,ROTOR_AXLE

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'baseq2'
MANIFEST=ROOT/'tools/assets/dropship-manifest.json'
DIRECTORY='models/vehicles/platoon_dropship'
MODELS={DIRECTORY+'/body.md2':'body',DIRECTORY+'/main_rotor.md2':'main_rotor'}
SKIN=DIRECTORY+'/green.png'
DEPENDENCIES=('build_dropship.py','dropship_geometry.py','build_m16.py','m16_geometry.py')
BASELINES={'body':dict(path='models/monsters/boss2/tris.md2',triangles=2580,position_vertices=1292,
                       file_bytes=125648,sha256='3c2435e7252fecaf6e3035905319608e1193f5172ebec659fc082cc4a71615d9'),
           'main_rotor':dict(path='models/monsters/boss2/propeller.md2',triangles=411,position_vertices=212,
                            file_bytes=18468,sha256='dd41fa090a6ec3d9cf1dbb83fb4d928bd25a08de5d432243e92cee4569b06cf1')}
COLORS={'plastic':(66,90,43),'dark':(35,48,28),'edge':(85,107,54),
        'glass':(26,46,47),'engine':(60,78,41),'metal':(44,56,40),'lamp':(233,215,153),
        'blade':(52,68,39)}
INK=(219,221,173)
AMBER=(209,161,68)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def star(draw,cx,cy,radius):
    points=[(cx+radius*(1 if i%2==0 else .42)*math.cos(-math.pi/2+i*math.pi/5),
             cy+radius*(1 if i%2==0 else .42)*math.sin(-math.pi/2+i*math.pi/5)) for i in range(10)]
    draw.polygon(points,fill=INK)


def glazing(draw, box):
    x, y, X, Y = box
    draw.rounded_rectangle((x,y,X,Y),radius=3,fill=(108,125,78))
    draw.rounded_rectangle((x+2,y+2,X-2,Y-2),radius=2,fill=COLORS['glass'])
    draw.polygon([(x+4,y+4),(X-4,y+4),(X-4,y+9),(x+4,Y-5)],fill=(58,86,85))
    draw.line((x+6,y+6,X-6,y+6),fill=(123,157,143),width=2)


def texture_bytes():
    image=Image.new('RGB',(256,256),COLORS['plastic']);pixels=image.load()
    for material,(x,y,X,Y) in REGIONS.items():
        color=COLORS.get(material,COLORS['plastic'])
        for v in range(y,Y):
            for u in range(x,X):
                shade=.96+.07*(1-(v-y)/max(1,Y-y-1))
                pixels[u,v]=tuple(round(c*shade) for c in color)
    draw=ImageDraw.Draw(image)
    x,y,X,Y=REGIONS['glass']
    glazing(draw,(x+1,y+1,X-2,Y-2))
    x,y,X,Y=REGIONS['windshield']
    mid=(x+X)//2
    glazing(draw,(x+2,y+2,mid-3,Y-3))
    glazing(draw,(mid+2,y+2,X-3,Y-3))

    x,y,X,Y=REGIONS['engine']
    for u in range(x+10,X-8,7):
        draw.rounded_rectangle((u,y+8,u+3,Y-10),radius=1,fill=COLORS['dark'])
        draw.line((u+4,y+10,u+4,Y-10),fill=COLORS['edge'])
    x,y,X,Y=REGIONS['intake']
    draw.ellipse((x+6,y+6,X-7,Y-7),fill=(23,31,24),outline=COLORS['edge'],width=3)
    draw.ellipse((x+19,y+16,X-20,Y-17),fill=COLORS['metal'])
    x,y,X,Y=REGIONS['step']
    draw.rectangle((x+4,y+6,X-5,Y-7),fill=COLORS['dark'])
    for v in range(y+9,Y-8,6):
        draw.line((x+10,v,X-11,v),fill=COLORS['edge'],width=2)
    x,y,X,Y=REGIONS['blade']
    draw.rectangle((X-8,y,X-1,Y-1),fill=AMBER)
    draw.line((X-9,y,X-9,Y-1),fill=INK)
    x,y,X,Y=REGIONS['marker']
    draw.rounded_rectangle((x+12,y+7,X-13,Y-8),radius=5,fill=COLORS['dark'])
    draw.rounded_rectangle((x+15,y+9,X-16,Y-10),radius=3,fill=AMBER)

    # Door art is drawn in physical panel proportions before atlas packing.
    door=Image.new('RGB',(184,96),COLORS['plastic']);d=ImageDraw.Draw(door)
    d.rectangle((0,81,183,95),fill=COLORS['dark'])
    d.rounded_rectangle((9,6,174,88),radius=7,fill=(72,97,48),outline=COLORS['dark'],width=3)
    d.line((15,88,168,88),fill=COLORS['edge'],width=2)
    for a,b in ((24,77),(91,144)):
        glazing(d,(a,16,b,44))
    d.rounded_rectangle((150,56,165,62),radius=2,fill=COLORS['dark'])
    d.line((152,56,162,56),fill=INK,width=2)
    d.line((13,74,168,74),fill=(133,150,89),width=2)
    star(d,84,64,14)
    number=Image.new('L',(14,10))
    ImageDraw.Draw(number).text((0,0),'07',font=ImageFont.load_default_imagefont(),fill=255)
    door.paste(INK,(24,53),number.resize((28,20),Image.Resampling.NEAREST))
    x,y,X,Y=REGIONS['cargo']
    image.paste(door.resize((X-x,Y-y),Image.Resampling.BILINEAR),(x,y))
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9)
    return out.getvalue()


def build_assets():
    assets={SKIN:texture_bytes()}
    manifest=dict(schema=1,generator='tools/assets/build_dropship.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        method='Faceted molded-plastic troop transport with framed glazing, cargo markings, a shrouded tail fan and swept rotor blades',
        coordinate_contract=dict(forward='+X',body_socket=list(BODY_SOCKET),rotor_axle=list(ROTOR_AXLE),
                                 mission_bounds=[[-114,-68,36],[68,68,96]],body_frames=1,rotor_frames=1),
        gameplay='Dedicated friendly paths; existing rotor attachment, spin, hover, path speeds, waits and triggers retained; enemy models untouched',
        models=[])
    for path,kind in MODELS.items():
        mesh=build_dropship(kind)
        raw,validation=encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
                                  mesh['faces'],atlas_uvs(mesh),[SKIN],['stand02'])
        assets[path]=raw;stats=MD2.read(raw).stats();stats.pop('frame_names')
        manifest['models'].append(dict(path=path,kind=kind,baseline=BASELINES[kind],after=stats,
                                       validation=validation,parts=mesh['parts'],anchors=mesh['anchors']))
    manifest['files']=[dict(path=p,bytes=len(raw),sha256=sha(raw)) for p,raw in sorted(assets.items())]
    return assets,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();assets,manifest=build_assets()
    outputs={BASE/path:raw for path,raw in assets.items()}
    outputs[MANIFEST]=(json.dumps(manifest,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes()!=raw:raise ValueError('Stale dropship output: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for entry in manifest['models']:
        print(f"{entry['kind']}: {entry['after']['triangles']} triangles, {entry['after']['file_bytes']} bytes")
    print('Verified friendly dropship' if args.verify else 'Built friendly dropship and linked main rotor')


if __name__=='__main__':main()
