#!/usr/bin/env python3
"""Build an original faceted green fuel drum at the existing shared barrel path."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from asset_sources import source_bytes
from build_m16 import encode_md2
from m16_geometry import Mesh
from md2_assets import MD2

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'models/objects/barrels/tris.md2'
TEXTURE = 'models/objects/barrels/skin.png'
MANIFEST = ROOT / 'tools/assets/barrels-manifest.json'
DEPENDENCIES = ('build_barrels.py', 'build_m16.py', 'm16_geometry.py',
                'md2_assets.py', 'asset_sources.py')
REGIONS = {'plastic': (4,4,60,60), 'band': (68,4,124,60),
           'lid': (132,4,188,60), 'cap': (196,4,252,60),
           'label': (8,80,152,216)}
COLORS = {'plastic': (46,72,31), 'band': (58,83,39),
          'lid': (40,62,27), 'cap': (69,88,44)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ring(z, radius, center=(0,0), sides=8):
    # Rotate the octagon to present a broad flat panel on each cardinal side.
    radius /= math.cos(math.pi / sides)
    return [(center[0]+radius*math.cos((i+.5)*math.tau/sides),
             center[1]+radius*math.sin((i+.5)*math.tau/sides), z)
            for i in range(sides)]


def geometry():
    mesh = Mesh()
    smooth_normals = {}
    # Continuous watertight shell: two rolling hoops, bottom rim and recessed lid.
    sections = [(0,15),(1.1,16),(2.8,15),(11.5,15),(13,15.9),
                (14.5,15),(25.5,15),(27,15.9),(28.5,15),(37.2,15),
                (38.5,16),(39.8,16),(39.8,14.3),(39,14.3)]
    loops = [ring(z,r) for z,r in sections]
    mesh.part('eight_sided_drum_with_two_rolling_hoops')
    for band,(a,b) in enumerate(zip(loops,loops[1:])):
        first_vertex = len(mesh.vertices)
        for i in range(8):
            j = (i+1)%8
            material = 'band' if band in (0,1,3,4,6,7,9,10,11) else 'plastic'
            if band >= 12: material = 'lid'
            if band == 5 and i in (1,5): material = 'label'
            normal = (a[i][0]+a[j][0], a[i][1]+a[j][1], 0)
            if band == 11: normal = (0,0,1)
            if band == 12: normal = (-normal[0],-normal[1],0)
            mesh.poly([a[i],a[j],b[j],b[i]],material,normal,
                      [(0,1),(1,1),(1,0),(0,0)],group=f'panel{band}_{i}')
        # Smooth around the circumference, including duplicated UV corners.
        # Each height band stays separate so hoop shoulders and lid edges
        # retain their crease. Frustum slopes contribute the vertical normal.
        for index in range(first_vertex,len(mesh.vertices)):
            x,y,_ = mesh.vertices[index]
            radius = math.hypot(x,y)
            direction = np.array([x/radius,y/radius,0.])
            if band == 11:
                direction = np.array([0.,0.,1.])
            elif band == 12:
                direction *= -1
            else:
                dz = sections[band+1][0]-sections[band][0]
                dr = (sections[band+1][1]-sections[band][1])/math.cos(math.pi/8)
                direction[2] = -dr/dz
            smooth_normals[index] = (direction/np.linalg.norm(direction)).tolist()
    mesh.poly(loops[0],'lid',(0,0,-1),group='bottom')
    mesh.poly(loops[-1],'lid',(0,0,1),group='lid')
    # Two solid hexagonal plugs sit in the lid, below the protective top rim.
    for name,center,radius in [('large_bung',(-7,3),2.3),('small_bung',(7,-3),1.5)]:
        mesh.loft(name,[ring(38.85,radius,center,6),ring(39.65,radius,center,6)],'cap')
    result = mesh.finish('world')
    for index,direction in smooth_normals.items():
        result['normals'][index] = direction
    result.pop('rifle_bounds')
    result['anchors'] = {}
    return result


def texture_bytes():
    image = Image.new('RGB',(256,256),COLORS['plastic'])
    draw = ImageDraw.Draw(image)
    for name,(x,y,X,Y) in REGIONS.items():
        color = COLORS.get(name,COLORS['plastic'])
        draw.rectangle((x,y,X-1,Y-1),fill=color)
    # Repository-native stencil lettering; no host font or external artwork.
    glyphs = {'F':('11111','10000','10000','11110','10000','10000','10000'),
              'U':('10001','10001','10001','10001','10001','10001','01110'),
              'E':('11111','10000','10000','11110','10000','10000','11111'),
              'L':('10000','10000','10000','10000','10000','10000','11111')}
    ink = (177,187,132)
    for index,letter in enumerate('FUEL'):
        for row,bits in enumerate(glyphs[letter]):
            for col,on in enumerate(bits):
                if on == '1':
                    x,y = 34+(index*6+col)*4,139+row*4
                    draw.rectangle((x,y,x+3,y+3),fill=ink)
    # Small flame inside a diamond: a painted mark, with no extra geometry.
    draw.line([(80,95),(97,112),(80,129),(63,112),(80,95)],fill=ink,width=3)
    draw.polygon([(75,121),(70,114),(77,103),(78,111),(84,102),
                  (91,115),(85,122)],fill=ink)
    raw = io.BytesIO(); image.save(raw,format='PNG',compress_level=9)
    return raw.getvalue()


def build_assets():
    config = json.loads((ROOT/'tools/assets/platoon.json').read_text())
    original = MD2.read(source_bytes(config,'baseq2/'+MODEL),source_compat=True)
    mesh = geometry()
    local = np.asarray(mesh['uvs'])
    rectangles = np.asarray([REGIONS[m] for m in mesh['materials']])
    low,high = rectangles[:,:2],rectangles[:,2:]
    uv = (low[:,None,:]+.5+local*(high-low-1)[:,None,:])/256
    raw,validation = encode_md2(np.asarray(mesh['vertices'])[None],
        np.asarray(mesh['normals'])[None],mesh['faces'],uv,[TEXTURE],original.names)
    assets = {MODEL:raw,TEXTURE:texture_bytes()}
    manifest = dict(schema=1,generator='tools/assets/build_barrels.py',
        dependencies_sha256={n:sha((ROOT/'tools/assets'/n).read_bytes()) for n in DEPENDENCIES},
        source_archive=config['source_archive'],
        method='original eight-sided closed drum, two rolling hoops, recessed lid and two hexagonal bungs',
        shading='circumferential smooth normals across UV seams; hard hoop shoulders and flat lid/rim',
        gameplay='Shared original model path; original collision, pushing, health, damage, explosion and debris code unchanged',
        original=original.stats(),after=MD2.read(raw).stats(),
        previous_runtime=dict(triangles=899,file_bytes=38728),
        validation=validation,parts=mesh['parts'],
        files=[dict(path=p,bytes=len(v),sha256=sha(v)) for p,v in sorted(assets.items())])
    return assets,manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true'); args = parser.parse_args()
    assets,manifest = build_assets()
    outputs = {ROOT/'baseq2'/p:raw for p,raw in assets.items()}
    outputs[MANIFEST] = (json.dumps(manifest,indent=2)+'\n').encode()
    for path,raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes()!=raw: raise ValueError('Stale barrel asset: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    print(('Verified' if args.verify else 'Built'),manifest['after']['triangles'],'triangle green barrel')


if __name__ == '__main__': main()
