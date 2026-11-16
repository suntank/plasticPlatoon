#!/usr/bin/env python3
"""Audit flying projectile assets without NumPy or Pillow."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def verify(root=ROOT):
    manifest = json.loads((root/'tools/assets/projectiles-manifest.json').read_text())
    for name,expected in manifest['dependencies_sha256'].items():
        if hashlib.sha256((root/'tools/assets'/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Projectile generator changed; run tools/assets/build_projectiles.py')
    ownership = json.loads((root/'tools/assets/platoon.json').read_text())['procedural_replacements']['projectiles']
    inventory = {entry['path']:entry for entry in manifest['files']}
    if set(ownership['models']+ownership['textures'])!=set(inventory):
        raise ValueError('Projectile ownership and manifest inventory differ')
    for name,entry in inventory.items():
        raw = (root/'baseq2'/name).read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Stale projectile asset: '+name)
        if name.endswith('.md2'):
            h = struct.unpack_from('<17i',raw)
            if h[:2]!=(844121161,8) or h[16]!=len(raw) or h[10]!=1 or h[4]!=40+4*h[6] or h[8]>128:
                raise ValueError('Invalid or excessive projectile model: '+name)
            for index in range(h[5]):
                skin = raw[h[11]+64*index:h[11]+64*(index+1)].split(b'\0')[0].decode('ascii')
                if skin not in inventory or not (root/'baseq2'/skin).is_file():
                    raise ValueError('Missing projectile atlas: '+skin)
    return len(inventory)


if __name__=='__main__':
    print(f'Verified {verify()} flying projectile models and atlases')
