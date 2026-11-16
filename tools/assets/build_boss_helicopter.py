#!/usr/bin/env python3
"""Build the red armored Sandkeep boss, preserving the old shared helicopter files."""
import argparse,hashlib,io,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from boss_helicopter_geometry import build,atlas_uvs,DIRECTORY,MATERIALS
from build_m16 import encode_md2
from md2_assets import MD2
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'tools/assets/boss-helicopter-manifest.json'
SKINS=[DIRECTORY+'/red.png',DIRECTORY+'/damaged.png']
MODELS={DIRECTORY+'/body.md2':'body',DIRECTORY+'/main_rotor.md2':'main_rotor'}
DEPENDENCIES=('build_boss_helicopter.py','boss_helicopter_geometry.py','dropship_geometry.py','build_m16.py','m16_geometry.py')
COLORS=[(128,40,29),(161,55,39),(48,49,43),(23,35,40),
        (114,33,25),(103,36,28),(122,43,31),(25,29,25),
        (79,28,23),(143,46,30),(125,39,28),(26,29,24),
        (20,24,22),(180,177,130),(140,45,31),(49,52,42)]


def sha(raw):return hashlib.sha256(raw).hexdigest()


def texture(damaged=False):
    image=Image.new('RGB',(256,256));draw=ImageDraw.Draw(image)
    for i,color in enumerate(COLORS):
        x,y=i%4*64,i//4*64
        if damaged and i in (0,1,4,6,8,10,14):color=tuple(round(c*.72) for c in color)
        draw.rectangle((x,y,x+63,y+63),fill=color)
    # Glass, machinery and pale boss chevrons are excluded by the existing
    # vehicle pigment mask; both undamaged and damaged skins remain red.
    draw.polygon([(197,7),(245,7),(197,48)],fill=(56,74,77))
    for y in range(78,122,8):draw.rectangle((139,y,181,y+3),fill=COLORS[7])
    for y in (143,163):draw.line([(139,y),(159,y+12),(179,y)],fill=(224,214,166),width=5)
    draw.rectangle((118,74,122,118),fill=(202,185,132))
    if damaged:
        for x,y in ((18,18),(24,82),(145,146),(20,142),(150,209)):
            draw.line([(x,y),(x+16,y+17),(x+8,y+28)],fill=(40,36,30),width=4)
            draw.line([(x+2,y),(x+18,y+17)],fill=(181,155,108),width=2)
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9);return out.getvalue()


def build_assets():
    assets={s:texture(i==1) for i,s in enumerate(SKINS)};entries=[]
    for path,kind in MODELS.items():
        mesh=build(kind)
        raw,validation=encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
            mesh['faces'],atlas_uvs(mesh),SKINS if kind=='body' else SKINS[:1],['stand02'])
        assets[path]=raw
        entries.append(dict(path=path,kind=kind,after=MD2.read(raw).stats(),validation=validation,parts=mesh['parts'],anchors=mesh['anchors']))
    manifest=dict(schema=1,generator='tools/assets/build_boss_helicopter.py',
        dependencies_sha256={n:sha((ROOT/'tools/assets'/n).read_bytes()) for n in DEPENDENCIES},
        models=entries,baseline_triangles=2991,method='original red armored gunship, recessed cannon/rocket bores, six-blade linked rotor',
        files=[dict(path=p,bytes=len(raw),sha256=sha(raw)) for p,raw in sorted(assets.items())])
    return assets,manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');a=p.parse_args()
    assets,m=build_assets();outputs={ROOT/'baseq2'/p:v for p,v in assets.items()};outputs[MANIFEST]=(json.dumps(m,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if a.verify:
            if not path.is_file() or path.read_bytes()!=raw:raise ValueError('Stale boss helicopter: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for e in m['models']:print(e['kind'],e['after']['triangles'],'triangles')
if __name__=='__main__':main()
