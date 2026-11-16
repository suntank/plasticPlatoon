#!/usr/bin/env python3
"""Sync only insect fragments in existing mission packs, preserving every other member."""
import argparse
import json
from pathlib import Path
from build_projectile_overlays import (sha,checked_path,archive_members,
    untouched_fingerprint,updated_archive,atomic_write)
from verify_body_parts_runtime import verify as verify_assets

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'tools/assets/body-parts-overlays.json'
MANIFEST=ROOT/'tools/assets/body-parts-overlays-manifest.json'


def process(write=False):
    verify_assets()
    config_raw=CONFIG.read_bytes();config=json.loads(config_raw);records=[]
    inventory={f['path']:f for f in json.loads((ROOT/'tools/assets/body-parts-manifest.json').read_text())['files']}
    for spec in config['archives']:
        path=checked_path(ROOT,spec['path']);raw=path.read_bytes()
        members,comment=archive_members(raw);managed=spec['managed_members']
        if len(managed)!=3 or not set(managed)<=set(inventory):raise ValueError('Invalid insect overlay inventory')
        if not set(managed)<={i.filename for i,_ in members}:raise ValueError('Missing existing insect model/atlas')
        if untouched_fingerprint(members,managed)!=(spec['untouched_members'],spec['untouched_sha256']):
            raise ValueError('Unmanaged insect mission content changed: '+spec['path'])
        sources={n:checked_path(ROOT,'baseq2/'+n).read_bytes() for n in managed}
        replacement=updated_archive(members,comment,sources)
        if replacement:
            if not write:raise ValueError('Stale insect mission body parts: '+spec['path'])
            atomic_write(path,replacement);raw=replacement;members,_=archive_members(raw)
        records.append(dict(path=spec['path'],sha256=sha(raw),bytes=len(raw),
            untouched_members=spec['untouched_members'],untouched_sha256=spec['untouched_sha256'],
            managed={n:sha(v) for n,v in sources.items()}))
    receipt=dict(schema=1,config_sha256=sha(config_raw),archives=records,
                 proof='Only the three existing insect fragment members per archive may change; all other content is hash-pinned')
    raw=(json.dumps(receipt,indent=2)+'\n').encode()
    if write:
        if not MANIFEST.exists() or MANIFEST.read_bytes()!=raw:atomic_write(MANIFEST,raw)
    elif MANIFEST.read_bytes()!=raw:raise ValueError('Stale body-part overlay receipt')
    return len(records)


def sync():return process(True)
def verify():return process(False)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');a=p.parse_args()
    print(('Verified' if a.verify else 'Synced'),process(not a.verify),'insect mission archives; other members unchanged')
