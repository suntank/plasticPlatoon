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
from PIL import Image,ImageDraw
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
COLORS={'plastic':(42,64,29),'dark':(24,36,18),'edge':(59,82,39),
        'glass':(34,47,43),'engine':(42,64,29),'metal':(31,44,22),'lamp':(180,185,137),
        'blade':(48,68,31)}
INK=(177,186,138)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def star(draw,cx,cy,radius,color=INK):
    points=[(cx+radius*(1 if i%2==0 else .42)*math.cos(-math.pi/2+i*math.pi/5),
             cy+radius*(1 if i%2==0 else .42)*math.sin(-math.pi/2+i*math.pi/5)) for i in range(10)]
    draw.polygon(points,fill=color)


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
    draw.polygon([(x+5,y+6),(X-8,y+6),(x+5,Y-10)],fill=(68,85,75))
    draw.polygon([(x+10,y+6),(x+17,y+6),(x+5,y+25),(x+5,y+16)],fill=(126,144,115))
    draw.rectangle((x+2,y+2,X-3,Y-3),outline=COLORS['edge'],width=3)
    x,y,X,Y=REGIONS['engine']
    for v in range(y+9,Y-5,8):draw.rectangle((x+7,v,X-8,v+3),fill=COLORS['dark'])
    x,y,X,Y=REGIONS['blade'];draw.rectangle((X-7,y,X-1,Y-1),fill=INK)
    star(draw,192,197,36)
    # Door art is drawn in physical panel proportions before atlas packing.
    door=Image.new('RGB',(184,96),COLORS['plastic']);d=ImageDraw.Draw(door)
    d.rectangle((4,4,179,91),outline=COLORS['dark'],width=3)
    d.line((92,5,92,91),fill=COLORS['edge'],width=3)
    for a,b in ((14,78),(105,169)):
        d.rectangle((a,12,b,47),fill=COLORS['glass'],outline=COLORS['edge'],width=3)
        d.polygon([(a+4,16),(b-6,16),(a+4,38)],fill=(68,85,75))
    d.rectangle((80,59,87,72),fill=COLORS['dark']);d.rectangle((98,59,105,72),fill=COLORS['dark'])
    star(d,46,71,15);star(d,138,71,15)
    x,y,X,Y=REGIONS['cargo'];image.paste(door.resize((X-x,Y-y),Image.Resampling.NEAREST),(x,y))
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9)
    return out.getvalue()


def build_assets():
    assets={SKIN:texture_bytes()}
    manifest=dict(schema=1,generator='tools/assets/build_dropship.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        method='original closed molded-plastic primitives; green transport adapted from original silhouette and authored enemy helicopter language',
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
