#!/usr/bin/env python3
"""Check shipped M16 outputs without adding NumPy to normal engine builds.

The authored mesh rebuild and all-pose tests live in build_m16.py/test_m16.py.
This small packaging gate prevents stale geometry, art, or generator revisions
from silently entering a release. It does not attempt to regenerate models.
"""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root=ROOT):
    manifest = json.loads((root / 'tools/assets/m16-manifest.json').read_text())
    for name, key in (('build_m16.py', 'generator_sha256'),
                      ('m16_geometry.py', 'geometry_sha256')):
        if digest(root / 'tools/assets' / name) != manifest[key]:
            raise ValueError('M16 generator changed; rebuild with tools/assets/build_m16.py')
    config = json.loads((root / 'tools/assets/platoon.json').read_text())
    ownership = config['procedural_replacements']['m16']
    required = set(ownership['models'] + ownership['textures'])
    entries = {entry['path']: entry for entry in manifest['files']}
    if not required <= set(entries):
        raise ValueError('M16 manifest omits a registered procedural replacement')
    # Derived tall variants are independently regenerated/verified by the
    # soldier-height builder; canonical input files are owned here.
    for name in sorted(required):
        path = root / 'baseq2' / name
        entry = entries[name]
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('M16 runtime output changed: ' + name)
    for model in manifest['models']:
        if model['path'] not in required:
            continue
        data = (root / 'baseq2' / model['path']).read_bytes()
        header = struct.unpack_from('<17i', data)
        if header[:2] != (844121161, 8) or header[16] != len(data):
            raise ValueError('Invalid M16 MD2: ' + model['path'])
        if header[4] != 40 + 4 * header[6] or header[6] > 2048 or header[8] > 4096:
            raise ValueError('M16 layout exceeds runtime budget: ' + model['path'])
        expected_frames = {'pickup': 1, 'view': 1, 'player': 198, 'enemy': 475}[model['role']]
        if header[10] != expected_frames:
            raise ValueError('M16 frame layout changed: ' + model['path'])
        for i in range(header[5]):
            skin = data[header[11]+64*i:header[11]+64*(i+1)].split(b'\0')[0].decode('ascii')
            if not (root / 'baseq2' / skin).is_file():
                raise ValueError('Missing M16 skin: ' + skin)
    return len(required)


if __name__ == '__main__':
    print(f'Verified {verify()} authored M16 runtime files')
