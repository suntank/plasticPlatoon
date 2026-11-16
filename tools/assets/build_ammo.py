#!/usr/bin/env python3
"""Build labeled ammo cases and five distinct original low-poly ammo pickups."""
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
from ammo_geometry import build_ammo, atlas_uvs, KINDS, LABELS, REGIONS

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'baseq2'
MANIFEST = ROOT/'tools/assets/ammo-manifest.json'
MODELS = {f'models/items/ammo/{kind}/medium/tris.md2':kind for kind in KINDS}
TEXTURES = {kind:f'models/items/ammo/{kind}/medium/'+('skin_ammo.png' if kind=='rockets' else 'skin.png')
            for kind in KINDS}
LOD_KINDS = ('shells','bullets','grenades')
BASELINES = {'shells':dict(triangles=1000,position_vertices=456,file_bytes=49776),
             'bullets':dict(triangles=999,position_vertices=458,file_bytes=49196),
             'grenades':dict(triangles=800,position_vertices=398,file_bytes=37256),
             'gl_ammo':dict(triangles=999,position_vertices=500,file_bytes=40856),
             'rockets':dict(triangles=500,position_vertices=252,file_bytes=22188),
             'cells':dict(triangles=899,position_vertices=453,file_bytes=39812),
             'slugs':dict(triangles=900,position_vertices=452,file_bytes=37512)}
DEPENDENCIES = ('build_ammo.py','ammo_geometry.py','build_m16.py','m16_geometry.py')
COLORS = {'plastic':(42,64,29), 'dark':(24,36,18), 'edge':(59,82,39),
          'brass':(112,101,47), 'band':(85,88,36)}
LETTER_COLOR = (198,203,160)
# A repository-native stencil alphabet keeps label rendering identical across
# machines without relying on installed fonts or generated image assets.
GLYPHS = {
 'A':('01110','10001','10001','11111','10001','10001','10001'),
 'B':('11110','10001','10001','11110','10001','10001','11110'),
 'C':('01111','10000','10000','10000','10000','10000','01111'),
 'D':('11110','10001','10001','10001','10001','10001','11110'),
 'E':('11111','10000','10000','11110','10000','10000','11111'),
 'F':('11111','10000','10000','11110','10000','10000','10000'),
 'G':('01111','10000','10000','10111','10001','10001','01110'),
 'H':('10001','10001','10001','11111','10001','10001','10001'),
 'I':('11111','00100','00100','00100','00100','00100','11111'),
 'K':('10001','10010','10100','11000','10100','10010','10001'),
 'L':('10000','10000','10000','10000','10000','10000','11111'),
 'M':('10001','11011','10101','10101','10001','10001','10001'),
 'N':('10001','11001','11001','10101','10011','10011','10001'),
 'O':('01110','10001','10001','10001','10001','10001','01110'),
 'P':('11110','10001','10001','11110','10000','10000','10000'),
 'R':('11110','10001','10001','11110','10100','10010','10001'),
 'S':('01111','10000','10000','01110','00001','00001','11110'),
 'T':('11111','00100','00100','00100','00100','00100','00100'),
 'U':('10001','10001','10001','10001','10001','10001','01110'),
 ' ':('00000',)*7}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def stencil(draw, text, rectangle):
    x,y,X,Y = rectangle
    columns = len(text)*6-1
    scale = min((X-x-18)//columns, (Y-y-16)//7)
    left,top = x+(X-x-columns*scale)//2, y+(Y-y-7*scale)//2
    for index,letter in enumerate(text):
        for row,bits in enumerate(GLYPHS[letter]):
            for col,on in enumerate(bits):
                if on=='1':
                    a,b = left+(index*6+col)*scale, top+row*scale
                    draw.rectangle((a,b,a+scale-1,b+scale-1), fill=LETTER_COLOR)


def texture_bytes(kind):
    image = Image.new('RGB',(256,256),COLORS['plastic'])
    pixels = image.load()
    for material,(x,y,X,Y) in REGIONS.items():
        color = COLORS.get(material,COLORS['plastic'])
        for v in range(y,Y):
            for u in range(x,X):
                shade = .95 + .07*(1-(v-y)/max(1,Y-y-1)) + ((u+v)%13-6)*.001
                pixels[u,v] = tuple(round(channel*shade) for channel in color)
    draw = ImageDraw.Draw(image)
    for material in ('label','lid_label'):
        stencil(draw,LABELS[kind],REGIONS[material])
    if kind=='grenades':
        x,y,X,Y = REGIONS['plastic']
        for u in (x+14,x+28,x+42):
            draw.line((u,y+2,u,Y-3),fill=COLORS['dark'],width=2)
        for v in (y+14,y+28,y+42):
            draw.line((x+2,v,X-3,v),fill=COLORS['dark'],width=2)
    out = io.BytesIO(); image.save(out,format='PNG',compress_level=9)
    return out.getvalue()


def build_assets():
    originals = json.loads((ROOT/'tools/assets/platoon-originals.json').read_text())
    assets = {}
    manifest = dict(schema=1,generator='tools/assets/build_ammo.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        source_archive=originals['source_archive'],method='original closed primitives; exact stencil labels; one static pose',
        labels='SHELLS and BULLETS on both broad case faces and lid; cream stencil on green plastic',
        projectile_isolation='Rocket pickup uses skin_ammo.png; original shared projectile skin.png is untouched',
        models=[])
    for path,kind in MODELS.items():
        source = MD2.read(source_bytes(originals,'baseq2/'+path),source_compat=True)
        mesh = build_ammo(kind)
        texture = texture_bytes(kind)
        assets[TEXTURES[kind]] = texture
        raw,validation = encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
                                    mesh['faces'],atlas_uvs(mesh),[TEXTURES[kind]],[source.names[0]])
        assets[path] = raw
        stats = MD2.read(raw).stats(); stats.pop('frame_names')
        entry = dict(path=path,kind=kind,baseline=BASELINES[kind],after=stats,
                     validation=validation,parts=mesh['parts'],label=LABELS[kind])
        if kind in LOD_KINDS:
            lod = path.replace('/tris.md2','/lod1.md2')
            assets[lod] = raw
            entry['lod'] = dict(path=lod,sha256=sha(raw),method='same authored low-budget model; no silhouette or label transition')
        manifest['models'].append(entry)
    manifest['files'] = [dict(path=path,bytes=len(raw),sha256=sha(raw)) for path,raw in sorted(assets.items())]
    return assets,manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    args = parser.parse_args()
    assets,manifest = build_assets()
    outputs = {BASE/path:raw for path,raw in assets.items()}
    outputs[MANIFEST] = (json.dumps(manifest,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes()!=raw:
                raise ValueError('Stale ammo output: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for entry in manifest['models']:
        print(f"{entry['kind']}: {entry['after']['triangles']} triangles, {entry['after']['file_bytes']} bytes")
    print('Verified ammo pickups' if args.verify else 'Built seven ammo pickups and three matching distant siblings')


if __name__=='__main__':main()
