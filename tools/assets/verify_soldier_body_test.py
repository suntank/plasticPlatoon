#!/usr/bin/env python3
"""Standard-library gate for official soldier bodies and immutable originals."""
import hashlib
import json
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify():
    m=json.loads((ROOT/'tools/assets/soldier-body-test-manifest.json').read_text())
    if m.get('default_enabled') is not True:raise ValueError('Official soldier bodies must be enabled by default')
    if m['source']!=json.loads((ROOT/'tools/assets/soldier-body-test-source.json').read_text()):raise ValueError('Baseline metadata changed')
    owner=json.loads((ROOT/'tools/assets/platoon.json').read_text())['procedural_replacements']['soldier_body_test']
    if len(m['models'])!=4 or set(owner['models'])!={f['path'] for f in m['models']}:raise ValueError('Trial ownership mismatch')
    for n,h in m['dependencies_sha256'].items():
        if sha((ROOT/'tools/assets'/n).read_bytes())!=h:raise ValueError('Stale soldier trial generator: '+n)
    if sha((ROOT/m['source']['archive']).read_bytes())!=m['source']['sha256']:raise ValueError('Soldier backup changed')
    for f in m['source']['files']:
        if sha((ROOT/'baseq2'/f['path']).read_bytes())!=f['sha256']:raise ValueError('Original soldier changed: '+f['path'])
    for f in m['models']:
        raw=(ROOT/'baseq2'/f['path']).read_bytes();h=struct.unpack_from('<17i',raw)
        if sha(raw)!=f['sha256'] or len(raw)!=f['bytes'] or h[16]!=len(raw):raise ValueError('Stale trial model')
        if h[8]>=1800 or h[10] not in (198,475):raise ValueError('Invalid trial model')
    return len(m['models'])
if __name__=='__main__':print('Verified',verify(),'official soldier bodies and backups')
