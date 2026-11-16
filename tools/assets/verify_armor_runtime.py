#!/usr/bin/env python3
"""Audit authored armor meshes and atlases with only the standard library."""
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]


def verify(root=ROOT):
    manifest=json.loads((root/'tools/assets/armor-manifest.json').read_text())
    for name,expected in manifest['dependencies_sha256'].items():
        if hashlib.sha256((root/'tools/assets'/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Armor generator changed; run tools/assets/build_armor.py')
    owner=json.loads((root/'tools/assets/platoon.json').read_text())['procedural_replacements']['armor']
    inventory={entry['path']:entry for entry in manifest['files']}
    if len(inventory)!=len(manifest['files']) or set(owner['models']+owner['textures'])!=set(inventory):
        raise ValueError('Armor ownership and manifest differ')
    for name,entry in inventory.items():
        raw=(root/'baseq2'/name).read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Stale authored armor: '+name)
        if name.endswith('.md2'):
            h=struct.unpack_from('<17i',raw)
            if h[:2]!=(844121161,8) or h[16]!=len(raw) or h[10]!=1 or h[4]!=40+4*h[6] or not 0<h[8]<=280:
                raise ValueError('Invalid or excessive armor mesh: '+name)
            for index in range(h[5]):
                skin=raw[h[11]+64*index:h[11]+64*(index+1)].split(b'\0')[0].decode('ascii')
                if skin not in inventory or not(root/'baseq2'/skin).is_file():
                    raise ValueError('Missing armor atlas: '+skin)
    for entry in manifest['models']:
        if 'lod' in entry and (root/'baseq2'/entry['path']).read_bytes()!=(root/'baseq2'/entry['lod']['path']).read_bytes():
            raise ValueError('Distant armor shape differs: '+entry['path'])
    return len(inventory)


if __name__=='__main__':print(f'Verified {verify()} armor meshes, matching distant guard and atlases')
