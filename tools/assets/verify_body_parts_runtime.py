#!/usr/bin/env python3
"""Standard-library gate for shared low-poly body fragments and color atlases."""
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify():
    m=json.loads((ROOT/'tools/assets/body-parts-manifest.json').read_text())
    if m['source']!=json.loads((ROOT/'tools/assets/body-parts-source.json').read_text()):raise ValueError('Body-part baseline metadata differs')
    source=m['source']['source_archive']
    if sha((ROOT/source['path']).read_bytes())!=source['sha256']:raise ValueError('Body-part baseline archive changed')
    for name,h in m['dependencies_sha256'].items():
        if sha((ROOT/'tools/assets'/name).read_bytes())!=h:raise ValueError('Stale body-part generator: '+name)
    owner=json.loads((ROOT/'tools/assets/platoon.json').read_text())['procedural_replacements']['body_parts']
    files={f['path']:f for f in m['files']}
    if len(files)!=39 or set(files)!=set(owner['models']+owner['textures']):raise ValueError('Body-part ownership differs')
    for name,f in files.items():
        raw=(ROOT/'baseq2'/name).read_bytes()
        if len(raw)!=f['bytes'] or sha(raw)!=f['sha256']:raise ValueError('Stale body part: '+name)
        if name.endswith('.md2'):
            h=struct.unpack_from('<17i',raw)
            if h[:2]!=(844121161,8) or h[16]!=len(raw) or h[10]!=1 or h[4]!=40+4*h[6] or not 0<h[8]<=160:
                raise ValueError('Invalid body-part mesh: '+name)
            skin=raw[h[11]:h[11]+64].split(b'\0')[0].decode()
            if h[5]!=1 or skin!=name.rsplit('/',1)[0]+'/skin.png' or skin not in files:raise ValueError('Invalid body-part atlas')
        elif raw[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>2I',raw,16)!=(256,256):raise ValueError('Invalid body-part texture')
    return len(owner['models'])
if __name__=='__main__':print('Verified',verify(),'body-part models and color atlases')
