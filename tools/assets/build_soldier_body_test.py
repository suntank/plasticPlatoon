#!/usr/bin/env python3
"""Build official anatomy-protected soldier retopology; never overwrite originals."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from md2_assets import MD2
from md2_animation import encode_vertex_subset
from soldier_body_topology import simplify_shared

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tools/assets/soldier-body-test-source.json'
MANIFEST=ROOT/'tools/assets/soldier-body-test-manifest.json'
PAIRS={'models/monsters/soldier/tris.md2':'enemy',
       'models/monsters/soldier/tall/tris.md2':'enemy_tall',
       'players/soldier/tris.md2':'player','players/soldier/tris_pistol.md2':'player_pistol'}
DEPS=('build_soldier_body_test.py','soldier_body_topology.py','md2_animation.py','md2_assets.py')

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args(argv)
    if a.snapshot:
        if SOURCE.exists():raise ValueError('Baseline exists; refusing to replace the backup')
        archive=ROOT/'tools/assets/sources/soldier-body-baseline.pk3'
        if archive.exists():raise ValueError('Backup archive already exists')
        stream=io.BytesIO();files=[]
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in PAIRS:
                raw=(ROOT/'baseq2'/path).read_bytes();z.writestr(zipfile.ZipInfo(path,(1980,1,1,0,0,0)),raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
                files.append(dict(path=path,sha256=sha(raw)))
        raw=stream.getvalue();archive.write_bytes(raw)
        SOURCE.write_text(json.dumps(dict(archive=str(archive.relative_to(ROOT)),sha256=sha(raw),files=files),indent=2)+'\n')
    if a.verify:
        from verify_soldier_body_test import verify
        print('Verified',verify(),'optional soldier bodies and original backup');return
    meta=json.loads(SOURCE.read_text());raw=(ROOT/meta['archive']).read_bytes()
    if sha(raw)!=meta['sha256']:raise ValueError('Backup changed')
    report=dict(schema=1,generator='tools/assets/build_soldier_body_test.py',default_enabled=True,
                toggle='cl_soldier_body_test',method='anatomy-protected animation-guided retopology; original vertex motion, UVs and normal bytes',
                dependencies_sha256={n:sha((ROOT/'tools/assets'/n).read_bytes()) for n in DEPS},source=meta,models=[])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for path,kind in PAIRS.items():
            data=z.read(path)
            if (ROOT/'baseq2'/path).read_bytes()!=data:raise ValueError('Original changed: '+path)
            model=MD2.read(data);pose=model.positions[146 if kind.startswith('enemy') else 0]
            # The taller body uses the same vertex topology, so classify its
            # anatomy in the unscaled canonical standing pose.
            if kind=='enemy_tall':pose=MD2.read(z.read('models/monsters/soldier/tris.md2')).positions[146]
            pins=np.flatnonzero((pose[:,2]>19)|(pose[:,2]<-17)|((pose[:,0]>5.5)&(pose[:,2]>0)&(pose[:,2]<19)))
            selected,faces,uvs,quality=simplify_shared(model,1050,max_displacement_ratio=.04,
                max_normal_angle_degrees=60,max_uv_displacement=.06,min_area_ratio=.15,protected_vertices=pins)
            output=encode_vertex_subset(model,selected,faces,uvs)
            name='models/experimental/soldier/'+kind+'.md2';dest=ROOT/'baseq2'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(output)
            report['models'].append(dict(path=name,source=path,sha256=sha(output),bytes=len(output),
                source_vertices=selected.tolist(),protected_vertices=pins.tolist(),quality=quality))
            print(kind,len(model.faces),'->',len(faces),'triangles; protected',len(pins),flush=True)
    MANIFEST.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
