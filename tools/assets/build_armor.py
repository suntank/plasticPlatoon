#!/usr/bin/env python3
"""Build original low-poly armor pickups and the matching distant wrist guard."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from asset_sources import source_bytes
from md2_assets import MD2
from build_m16 import encode_md2
from armor_geometry import build_armor,atlas_uvs,KINDS,REGIONS

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'baseq2'
MANIFEST=ROOT/'tools/assets/armor-manifest.json'
MODELS={f'models/items/armor/{kind}/tris.md2':kind for kind in KINDS}
TEXTURES={kind:f'models/items/armor/{kind}/skin.png' for kind in KINDS}
BASELINES={'shard':dict(triangles=800,position_vertices=382,file_bytes=35696),
           'jacket':dict(triangles=799,position_vertices=404,file_bytes=36180),
           'combat':dict(triangles=1000,position_vertices=500,file_bytes=42984),
           'body':dict(triangles=1000,position_vertices=502,file_bytes=43608)}
DEPENDENCIES=('build_armor.py','armor_geometry.py','pickup_normals.py','build_m16.py','m16_geometry.py')
COLORS={'plastic':(42,64,29),'dark':(24,36,18),'edge':(59,82,39),
        'webbing':(74,82,44),'sole':(25,32,19),'lining':(29,42,21)}
INK=(179,188,139)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def texture_bytes(kind):
    image=Image.new('RGB',(256,256),COLORS['plastic']);pixels=image.load()
    for material,(x,y,X,Y) in REGIONS.items():
        color=COLORS.get(material,COLORS['plastic'])
        for v in range(y,Y):
            for u in range(x,X):
                shade=.96+.06*(1-(v-y)/max(1,Y-y-1))
                pixels[u,v]=tuple(round(c*shade) for c in color)
    draw=ImageDraw.Draw(image)
    x,y,X,Y=REGIONS['tier']
    draw.line([(x+22,y+17),(X-22,y+17),(X-25,y+69),((x+X)//2,Y-15),
               (x+25,y+69),(x+22,y+17)],fill=INK,width=5)
    if kind=='shard':
        cx,cy=(x+X)//2,y+48
        draw.rectangle((cx-4,cy-16,cx+4,cy+16),fill=INK)
        draw.rectangle((cx-16,cy-4,cx+16,cy+4),fill=INK)
    else:
        count={'jacket':1,'combat':2,'body':3}[kind]
        for index in range(count):
            cx=(x+X)//2+(index-(count-1)/2)*17
            draw.rectangle((round(cx-4),y+34,round(cx+4),y+64),fill=INK)
    x,y,X,Y=REGIONS['cuff']
    # Paint supplies the cuff straps; its bands stay clear of the open rim.
    for a,b in ((y+9,y+23),(Y-23,Y-9)):
        draw.rectangle((x,a,X-1,b),fill=COLORS['webbing'])
        draw.line((x,a,X-1,a),fill=COLORS['edge'],width=2)
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9)
    return out.getvalue()


def build_assets():
    pickups=json.loads((ROOT/'tools/assets/pickups.json').read_text())
    assets={}
    manifest=dict(schema=1,generator='tools/assets/build_armor.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        source_archive=pickups['source_archive'],
        method='original closed primitives with real cuff, helmet, neck and arm openings; one static pose',
        shading='smooth outer/inner helmet dome, cuffs and boot uppers; flat rims, soles, plates and straps retain creases',
        gameplay='Existing paths, armor amounts, protection, salvage, caps, rotation and respawn are unchanged',
        models=[])
    for path,kind in MODELS.items():
        source=MD2.read(source_bytes(pickups,'baseq2/'+path),source_compat=True)
        mesh=build_armor(kind);assets[TEXTURES[kind]]=texture_bytes(kind)
        raw,validation=encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
                                  mesh['faces'],atlas_uvs(mesh),[TEXTURES[kind]],[source.names[0]])
        assets[path]=raw;stats=MD2.read(raw).stats();stats.pop('frame_names')
        entry=dict(path=path,kind=kind,baseline=BASELINES[kind],after=stats,
                   validation=validation,parts=mesh['parts'])
        if kind=='shard':
            lod=path.replace('/tris.md2','/lod1.md2');assets[lod]=raw
            entry['lod']=dict(path=lod,sha256=sha(raw),method='same authored low-budget wrist guard at every distance')
        manifest['models'].append(entry)
    manifest['files']=[dict(path=p,bytes=len(raw),sha256=sha(raw)) for p,raw in sorted(assets.items())]
    return assets,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();assets,manifest=build_assets()
    outputs={BASE/path:raw for path,raw in assets.items()}
    outputs[MANIFEST]=(json.dumps(manifest,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes()!=raw:raise ValueError('Stale armor output: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for entry in manifest['models']:
        print(f"{entry['kind']}: {entry['after']['triangles']} triangles, {entry['after']['file_bytes']} bytes")
    print('Verified armor pickups' if args.verify else 'Built four armor pickups and matching distant wrist guard')


if __name__=='__main__':main()
