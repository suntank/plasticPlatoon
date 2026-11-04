#!/usr/bin/env python3
"""Package the exact verified Sandwatch build, without replacing Sandkeep."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from verify_sandwatch import ROOT, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp',type=Path,default=ROOT/'build/sandwatch-candidate/maps/pp_sandwatch.bsp')
    p.add_argument('--output',type=Path,default=ROOT/'release/baseq2')
    a=p.parse_args()
    source=ROOT/'maps/source/pp_sandwatch.map'
    report=json.loads((ROOT/'build/maps/pp_sandwatch/verification.json').read_text())
    if not (report.get('passed') and report['map_sha256']==sha(source) and report['bsp_sha256']==sha(a.bsp)):
        p.error('A passing verification for these exact source/BSP bytes is required')
    files={Path('maps/pp_sandwatch.bsp'):a.bsp,Path('maps/pp_sandwatch.map'):source}
    for name in ('sandwatch_solo.cfg','sandwatch_coop.cfg'):
        files[Path(name)]=ROOT/'baseq2'/name
    # Only textures used by this map, plus the shared original sandbox sky.
    from verify_sandkeep import parse_entities
    textures={t for e in parse_entities(source.read_text()) for t in e['textures']}
    for texture in textures:
        for suffix in ('wal','png'):
            rel=Path('textures')/(texture+'.'+suffix)
            files[rel]=ROOT/'baseq2'/rel
    files.update((f.relative_to(ROOT/'baseq2'),f) for f in (ROOT/'baseq2/env').glob('sandkeep*.tga'))
    files[Path('sandwatch-readme.txt')]=ROOT/'maps/README-sandwatch.md'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=ROOT/'build/maps/pp_sandwatch/backups'/stamp
    a.output.mkdir(parents=True,exist_ok=True)
    def install(src,rel):
        dst=a.output/rel
        if dst.exists() and sha(src)==sha(dst):
            return
        if dst.exists():
            saved=backup/rel
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dst,saved)
        dst.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dst.parent,delete=False) as f:
            temporary=Path(f.name)
        try:
            shutil.copy2(src,temporary)
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='sandwatch-package-') as tmp:
        archive=Path(tmp)/'operation-sandwatch.pk3'
        with ZipFile(archive,'w',ZIP_DEFLATED) as z:
            for rel,src in sorted(files.items()):
                info=ZipInfo(rel.as_posix(),(1980,1,1,0,0,0))
                info.external_attr=0o644<<16
                z.writestr(info,src.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
        for rel,src in files.items():
            install(src,rel)
        install(archive,Path(archive.name))
    result={'archive':str(a.output/'operation-sandwatch.pk3'),
            'sha256':sha(a.output/'operation-sandwatch.pk3'),'files':len(files),
            'backup':str(backup) if backup.exists() else None}
    (ROOT/'build/maps/pp_sandwatch/package.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
