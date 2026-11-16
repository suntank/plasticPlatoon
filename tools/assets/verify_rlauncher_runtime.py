#!/usr/bin/env python3
"""Verify the authored rlauncher outputs using only the Python standard library."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def verify(root=ROOT):
    manifest = json.loads((root/'tools/assets/rlauncher-manifest.json').read_text())
    for name, expected in manifest['dependencies_sha256'].items():
        if hashlib.sha256((root/'tools/assets'/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Rocket launcher generator changed; run tools/assets/build_rlauncher.py')
    ownership = json.loads((root/'tools/assets/platoon.json').read_text())['procedural_replacements']['rlauncher']
    inventory = {entry['path']:entry for entry in manifest['files']}
    if not set(ownership['models']+ownership['textures']) <= set(inventory):
        raise ValueError('Rocket launcher manifest omits a registered replacement')
    for name, entry in inventory.items():
        raw = (root/'baseq2'/name).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Stale rlauncher asset: '+name)
    for model in manifest['models']:
        raw = (root/'baseq2'/model['path']).read_bytes()
        h = struct.unpack_from('<17i',raw)
        frames = {'pickup':1,'view':1,'player':198,'enemy':475,'enemy_tall':475}[model['role']]
        if h[:2] != (844121161,8) or h[16] != len(raw) or h[10] != frames or h[4] != 40+4*h[6]:
            raise ValueError('Invalid rlauncher MD2: '+model['path'])
        for i in range(h[5]):
            skin = raw[h[11]+64*i:h[11]+64*(i+1)].split(b'\0')[0].decode('ascii')
            if not (root/'baseq2'/skin).is_file():raise ValueError('Missing rlauncher skin: '+skin)
    heavy=json.loads((root/'tools/assets/rocket-soldier-manifest.json').read_text())
    if heavy!=manifest['enemy_retarget']:raise ValueError('Stale Rocket launcher rocket-soldier provenance')
    for path,expected in heavy['sources'].items():
        if not path.startswith('archived:') and hashlib.sha256((root/'baseq2'/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Rocket launcher attachment source changed: '+path)
    header = manifest['ads_header']
    if hashlib.sha256((root/header['path']).read_bytes()).hexdigest() != header['sha256']:
        raise ValueError('Rocket launcher sight alignment header is stale')
    return len(inventory)


if __name__ == '__main__':
    print(f'Verified {verify()} authored rlauncher assets and model sight alignment')
