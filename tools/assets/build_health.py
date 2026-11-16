#!/usr/bin/env python3
"""Build the five original low-poly health and health-boost pickups."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from asset_sources import source_bytes
from md2_assets import MD2
from build_m16 import encode_md2
from health_geometry import build_health, atlas_uvs, KINDS, LABELS, REGIONS

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'baseq2'
MANIFEST=ROOT/'tools/assets/health-manifest.json'
MODELS={**{f'models/items/healing/{kind}/tris.md2':kind for kind in KINDS[:3]},
        'models/items/mega_h/tris.md2':'mega','models/items/adrenal/tris.md2':'adrenaline'}
TEXTURES={kind:path.rsplit('/',1)[0]+('/skin_health.png' if kind=='large' else '/skin.png')
          for path,kind in MODELS.items()}
BASELINES={'stimpack':dict(triangles=800,position_vertices=402,file_bytes=34480),
           'medium':dict(triangles=800,position_vertices=394,file_bytes=34492),
           'large':dict(triangles=998,position_vertices=500,file_bytes=43104),
           'mega':dict(triangles=800,position_vertices=402,file_bytes=35704),
           'adrenaline':dict(triangles=998,position_vertices=500,file_bytes=43104)}
DEPENDENCIES=('build_health.py','health_geometry.py','pickup_normals.py','build_m16.py','m16_geometry.py')
COLORS={'plastic':(42,64,29),'dark':(24,36,18),'edge':(59,82,39),'cream':(182,187,147)}
INK=(213,216,175)
GLYPHS={
 '0':('111','101','101','101','111'), '1':('010','110','010','010','111'),
 '2':('111','001','111','100','111'), '5':('111','100','111','001','111'),
 '+':('000','010','111','010','000'),
 'B':('110','101','110','101','110'), 'O':('111','101','101','101','111'),
 'S':('111','100','111','001','111'), 'T':('111','010','010','010','010')}


def sha(raw): return hashlib.sha256(raw).hexdigest()


def cross(draw, cx, cy, radius, color=INK):
    arm=radius//3
    draw.rectangle((cx-arm,cy-radius,cx+arm,cy+radius),fill=color)
    draw.rectangle((cx-radius,cy-arm,cx+radius,cy+arm),fill=color)


def text(draw, word, rectangle):
    x,y,X,Y=rectangle; columns=len(word)*4-1
    scale=min((X-x)//columns,(Y-y)//5)
    left,top=x+(X-x-columns*scale)//2,y+(Y-y-5*scale)//2
    for index,letter in enumerate(word):
        for row,bits in enumerate(GLYPHS[letter]):
            for col,on in enumerate(bits):
                if on=='1':
                    a,b=left+(index*4+col)*scale,top+row*scale
                    draw.rectangle((a,b,a+scale-1,b+scale-1),fill=INK)


def medical_panel(kind):
    # Author in the receiving face's physical proportions, then pack into
    # the atlas. This keeps the medical cross square on tall and wide items.
    width,height={'stimpack':(28,67),'medium':(82,70),'large':(178,111),
                  'mega':(96,154),'adrenaline':(178,111)}[kind]
    panel=Image.new('RGB',(width,height),COLORS['plastic']); draw=ImageDraw.Draw(panel)
    if kind=='stimpack':
        cross(draw,14,18,9);text(draw,'+2',(2,40,26,63))
    elif kind=='medium':
        cross(draw,41,23,16);text(draw,'+10',(9,47,73,66))
    elif kind=='mega':
        cross(draw,48,48,28);text(draw,'+100',(8,104,88,140))
    else:
        cross(draw,89,34,24);text(draw,LABELS[kind],(14,69,164,103))
    return panel


def texture_bytes(kind):
    image=Image.new('RGB',(256,256),COLORS['plastic']); pixels=image.load()
    for material,(x,y,X,Y) in REGIONS.items():
        color=COLORS.get(material,COLORS['plastic'])
        for v in range(y,Y):
            for u in range(x,X):
                shade=.96+.06*(1-(v-y)/max(1,Y-y-1))
                pixels[u,v]=tuple(round(channel*shade) for channel in color)
    top_size=(200,91) if kind in ('large','adrenaline') else (80,80)
    top_panel=Image.new('RGB',top_size,COLORS['plastic'])
    cross(ImageDraw.Draw(top_panel),top_size[0]//2,top_size[1]//2,round(min(top_size)*.34))
    x,y,X,Y=REGIONS['cross']
    image.paste(top_panel.resize((X-x,Y-y),Image.Resampling.NEAREST),(x,y))
    for material,panel in (('injector',medical_panel('stimpack')),('label',medical_panel(kind))):
        x,y,X,Y=REGIONS[material]
        image.paste(panel.resize((X-x,Y-y),Image.Resampling.NEAREST),(x,y))
    # Flat rolled-cloth ends use concentric paint rather than extra geometry.
    draw=ImageDraw.Draw(image)
    draw.rectangle(REGIONS['roll_end'],fill=COLORS['cream'])
    for radius in (32,23,13):
        draw.ellipse((204-radius,112-radius,204+radius,112+radius),outline=COLORS['edge'],width=3)
    out=io.BytesIO();image.save(out,format='PNG',compress_level=9)
    return out.getvalue()


def build_assets():
    pickups=json.loads((ROOT/'tools/assets/pickups.json').read_text())
    assets={}
    manifest=dict(schema=1,generator='tools/assets/build_health.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        source_archive=pickups['source_archive'],
        method='original closed solids, medical markings on solid faces, static original frame identity',
        shading='smooth curved walls with flat caps; beveled corners blend into unchanged flat medical panels',
        gameplay='Existing paths, pickup sounds, counts, caps, respawn and mega-health decay are unchanged',
        texture_isolation='Large medkit uses skin_health.png; legacy shared skin.png stays intact for mission compatibility',
        models=[])
    for path,kind in MODELS.items():
        # Adrenaline was an exact copy of the legacy large kit. The pinned
        # original large-kit input preserves its matching frame identity too.
        source_path=path if kind!='adrenaline' else 'models/items/healing/large/tris.md2'
        source=MD2.read(source_bytes(pickups,'baseq2/'+source_path),source_compat=True)
        mesh=build_health(kind); assets[TEXTURES[kind]]=texture_bytes(kind)
        raw,validation=encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
                                  mesh['faces'],atlas_uvs(mesh),[TEXTURES[kind]],[source.names[0]])
        assets[path]=raw
        stats=MD2.read(raw).stats();stats.pop('frame_names')
        entry=dict(path=path,kind=kind,label=LABELS[kind],baseline=BASELINES[kind],after=stats,
                   validation=validation,parts=mesh['parts'],source_frame_from=source_path)
        if kind=='stimpack':
            lod=path.replace('/tris.md2','/lod1.md2');assets[lod]=raw
            entry['lod']=dict(path=lod,sha256=sha(raw),method='same authored low-budget injector at every distance')
        manifest['models'].append(entry)
    manifest['files']=[dict(path=path,bytes=len(raw),sha256=sha(raw)) for path,raw in sorted(assets.items())]
    return assets,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();assets,manifest=build_assets()
    outputs={BASE/path:raw for path,raw in assets.items()}
    outputs[MANIFEST]=(json.dumps(manifest,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes()!=raw: raise ValueError('Stale health output: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for entry in manifest['models']:
        print(f"{entry['kind']}: {entry['after']['triangles']} triangles, {entry['after']['file_bytes']} bytes")
    print('Verified health pickups' if args.verify else 'Built five health pickups and matching distant injector')


if __name__=='__main__': main()
