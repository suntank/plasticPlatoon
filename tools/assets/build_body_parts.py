#!/usr/bin/env python3
"""Build low-poly soldier, mechanical and insect body fragments with color skins."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from asset_sources import source_bytes
from body_parts_geometry import build
from build_m16 import encode_md2
from md2_assets import MD2

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'tools/assets/body-parts-manifest.json'
SOURCE=ROOT/'tools/assets/body-parts-source.json'
KINDS=('arm','bone','bone2','chest','gear','head','head2','leg','skull','sm_meat','sm_metal')
MODELS={f'models/objects/gibs/{kind}/tris.md2':kind for kind in KINDS}
MODELS.update({f'models/objects/gibs/{species}/{part}.md2':species+'_'+part
               for species in ('ant','spider') for part in ('chunk','leg')})
DEPENDENCIES=('build_body_parts.py','body_parts_geometry.py','build_m16.py',
              'm16_geometry.py','md2_assets.py','asset_sources.py')
TILES={'plastic':0,'edge':1,'dark':2,'wound':3,'inner':4,'metal':5}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def atlas(species=None,player=False):
    if species:
        colors=([(69,43,33),(103,68,48),(44,27,25),(181,38,30),(215,63,40),(237,108,65)]
                if species=='spider' else [(111,40,22),(151,61,30),(64,24,19),(194,40,27),(228,78,45),(247,121,77)])
    elif player:
        colors=[(44,70,31),(64,87,39),(27,30,25),(73,88,40),(51,65,31),(74,77,68)]
    else:
        colors=[(111,91,48),(139,117,65),(27,30,25),(104,80,37),(82,64,31),(74,77,68)]
    image=Image.new('RGB',(256,256));draw=ImageDraw.Draw(image)
    for i in range(16):
        x,y=i%4*64,i//4*64
        draw.rectangle((x,y,x+63,y+63),fill=colors[i%6])
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9);return out.getvalue()


def build_assets():
    source=json.loads(SOURCE.read_text());assets={};models=[]
    for path,kind in MODELS.items():
        original=MD2.read(source_bytes(source,'baseq2/'+path))
        mesh=build(kind);points=np.asarray(mesh['vertices']);normals=np.asarray(mesh['normals'])
        low,high=original.positions[0].min(axis=0),original.positions[0].max(axis=0)
        # Preserve every legacy piece's local origin and extent for toss/spawners.
        scale=(high-low)/np.ptp(points,axis=0)
        points=(points-points.min(axis=0))*scale+low
        normals/=scale;normals/=np.linalg.norm(normals,axis=1)[:,None]
        tile=np.array([TILES[m] for m in mesh['materials']])
        origin=np.column_stack((tile%4,tile//4))*64
        uv=(origin[:,None,:]+4.5+np.asarray(mesh['uvs'])*55)/256
        directory=Path(path).parent.as_posix();skin=directory+'/skin.png'
        raw,validation=encode_md2(points[None],normals[None],mesh['faces'],uv,[skin],original.names)
        species=kind.split('_')[0] if kind.startswith(('ant_','spider_')) else None
        assets[path]=raw;assets[skin]=atlas(species)
        if not species:assets[directory+'/player.png']=atlas(player=True)
        models.append(dict(path=path,kind=kind,before=original.stats(),after=MD2.read(raw).stats(),
                           validation=validation,parts=mesh['parts']))
    manifest=dict(schema=1,generator='tools/assets/build_body_parts.py',source=json.loads(SOURCE.read_text()),
        dependencies_sha256={n:sha((ROOT/'tools/assets'/n).read_bytes()) for n in DEPENDENCIES},
        method='original closed primitives, smooth molded surfaces, source bounds/origins and frame identity retained',
        colors='tan enemy pigment with existing red variants; dedicated green player atlases; species-specific insect shell/wound tiles',
        models=models,files=[dict(path=p,bytes=len(v),sha256=sha(v)) for p,v in sorted(assets.items())])
    return assets,manifest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');a=p.parse_args(argv)
    assets,m=build_assets();outputs={ROOT/'baseq2'/p:v for p,v in assets.items()}
    outputs[MANIFEST]=(json.dumps(m,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if a.verify:
            if not path.is_file() or path.read_bytes()!=raw:raise ValueError('Stale body part: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for e in m['models']:print(e['kind'],e['before']['triangles'],'->',e['after']['triangles'],'triangles')


if __name__=='__main__':main()
