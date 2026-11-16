#!/usr/bin/env python3
"""Standard-library gate for the dedicated red Sandkeep boss media."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def verify():
    m=json.loads((ROOT/'tools/assets/boss-helicopter-manifest.json').read_text())
    for name,h in m['dependencies_sha256'].items():
        if hashlib.sha256((ROOT/'tools/assets'/name).read_bytes()).hexdigest()!=h:raise ValueError('Stale boss generator: '+name)
    owner=json.loads((ROOT/'tools/assets/platoon.json').read_text())['procedural_replacements']['boss_helicopter']
    inventory={f['path']:f for f in m['files']}
    if len(inventory)!=4 or set(inventory)!=set(owner['models']+owner['textures']):raise ValueError('Boss ownership mismatch')
    for name,f in inventory.items():
        raw=(ROOT/'baseq2'/name).read_bytes()
        if len(raw)!=f['bytes'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:raise ValueError('Stale boss media: '+name)
        if name.endswith('.md2'):
            h=struct.unpack_from('<17i',raw)
            if h[:2]!=(844121161,8) or h[16]!=len(raw) or h[10]!=1 or h[4]!=40+4*h[6] or not 0<h[8]<=1000:raise ValueError('Invalid boss model')
            skins=[raw[h[11]+64*i:h[11]+64*(i+1)].split(b'\0')[0].decode() for i in range(h[5])]
            expected=owner['textures'] if name.endswith('/body.md2') else owner['textures'][:1]
            if skins!=expected:raise ValueError('Boss skin layout mismatch')
        elif raw[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>2I',raw,16)!=(256,256):raise ValueError('Invalid boss atlas')
    return len(inventory)
if __name__=='__main__':print('Verified',verify(),'boss helicopter model/atlas files')
