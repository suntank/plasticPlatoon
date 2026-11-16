#!/usr/bin/env python3
"""Build the actual flying rocket, armed grenade and shared GL/mortar round."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from asset_sources import source_bytes
from md2_assets import MD2
from build_m16 import encode_md2
from build_ammo import texture_bytes
from ammo_geometry import atlas_uvs
from projectile_geometry import build_projectile, AMMO_KINDS

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'baseq2'
MANIFEST = ROOT/'tools/assets/projectiles-manifest.json'
MODELS = {'models/objects/rocket/tris.md2':'rocket',
          'models/objects/grenade2/tris.md2':'hand_grenade',
          'models/objects/grenade/tris.md2':'gl_round'}
TEXTURES = {'rocket':'models/objects/rocket/skin.png',
            'hand_grenade':'models/objects/grenade2/skin.png',
            'gl_round':'models/objects/grenade/skin.png'}
BASELINES = {'rocket':dict(triangles=500,position_vertices=252,file_bytes=22248),
             'hand_grenade':dict(triangles=800,position_vertices=396,file_bytes=35320),
             'gl_round':dict(triangles=999,position_vertices=500,file_bytes=41024)}
DEPENDENCIES = ('build_projectiles.py','projectile_geometry.py','build_ammo.py',
                'ammo_geometry.py','build_m16.py','m16_geometry.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_assets():
    originals = json.loads((ROOT/'tools/assets/platoon-originals.json').read_text())
    assets = {}
    manifest = dict(schema=1,generator='tools/assets/build_projectiles.py',
        dependencies_sha256={name:sha((ROOT/'tools/assets'/name).read_bytes()) for name in DEPENDENCIES},
        source_archive=originals['source_archive'],
        method='authored ammo shapes, flight orientation and preserved projectile origins',
        gameplay='Existing model paths, collision bounds, speeds, spin, fuses, damage, effects and sounds are unchanged',
        models=[])
    for path,kind in MODELS.items():
        source = MD2.read(source_bytes(originals,'baseq2/'+path),source_compat=True)
        mesh = build_projectile(kind)
        assets[TEXTURES[kind]] = texture_bytes(AMMO_KINDS[kind])
        raw,validation = encode_md2(np.asarray(mesh['vertices'])[None],np.asarray(mesh['normals'])[None],
                                    mesh['faces'],atlas_uvs(mesh),[TEXTURES[kind]],[source.names[0]])
        assets[path] = raw
        stats = MD2.read(raw).stats(); stats.pop('frame_names')
        manifest['models'].append(dict(path=path,kind=kind,ammo_source=AMMO_KINDS[kind],
            baseline=BASELINES[kind],after=stats,validation=validation,
            parts=mesh['parts'],anchors=mesh['anchors']))
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
                raise ValueError('Stale projectile output: '+str(path))
        elif not path.is_file() or path.read_bytes()!=raw:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for entry in manifest['models']:
        print(f"{entry['kind']}: {entry['after']['triangles']} triangles, {entry['after']['file_bytes']} bytes")
    print('Verified flying projectiles' if args.verify else 'Built flying projectiles; synchronize mission overlays before packaging')


if __name__=='__main__':main()
