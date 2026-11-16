#!/usr/bin/env python3
"""Standard-library gate for authored barrel media."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def verify():
    manifest = json.loads((ROOT/'tools/assets/barrels-manifest.json').read_text())
    for name,digest in manifest['dependencies_sha256'].items():
        if hashlib.sha256((ROOT/'tools/assets'/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Barrel generator changed: '+name)
    owner = json.loads((ROOT/'tools/assets/platoon.json').read_text())['procedural_replacements']['barrels']
    inventory = {f['path']:f for f in manifest['files']}
    if len(inventory)!=2 or set(owner['models']+owner['textures'])!=set(inventory):
        raise ValueError('Barrel ownership mismatch')
    for name,f in inventory.items():
        raw = (ROOT/'baseq2'/name).read_bytes()
        if len(raw)!=f['bytes'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:
            raise ValueError('Stale barrel asset: '+name)
        if name.endswith('.md2'):
            h = struct.unpack_from('<17i',raw)
            if h[:2]!=(844121161,8) or h[16]!=len(raw) or h[10]!=1 or h[4]!=40+4*h[6] or not 0<h[8]<=280:
                raise ValueError('Invalid barrel model')
            skins = [raw[h[11]+64*i:h[11]+64*(i+1)].split(b'\0')[0].decode() for i in range(h[5])]
            if skins!=owner['textures']: raise ValueError('Invalid barrel atlas reference')
        elif raw[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>2I',raw,16)!=(256,256):
            raise ValueError('Invalid barrel atlas')
    return len(inventory)


if __name__ == '__main__': print('Verified',verify(),'barrel model and atlas files')
