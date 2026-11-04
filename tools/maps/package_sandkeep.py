#!/usr/bin/env python3
"""Install a verified Sandkeep build and rebuild its overriding PK3 archive."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp', type=Path, required=True)
    p.add_argument('--verification', type=Path, default=ROOT / 'build/maps/pp_sandkeep/verification.json')
    p.add_argument('--output', type=Path, default=ROOT / 'release/baseq2')
    a = p.parse_args()
    source = ROOT / 'maps/source/pp_sandkeep.map'
    report = json.loads(a.verification.read_text())
    if not (report.get('passed') and report.get('map_sha256') == sha(source)
            and report.get('bsp', {}).get('sha256') == sha(a.bsp)):
        p.error('verification must pass for these exact MAP and BSP bytes')
    files = {Path('maps/pp_sandkeep.map'): source, Path('maps/pp_sandkeep.bsp'): a.bsp}
    for name in ('sandkeep_solo.cfg', 'sandkeep_coop.cfg'):
        files[Path(name)] = ROOT / 'baseq2' / name
    for pattern in ('textures/sandkeep/*', 'env/sandkeep*.tga'):
        files.update((f.relative_to(ROOT / 'baseq2'), f)
                     for f in (ROOT / 'baseq2').glob(pattern) if f.is_file())
    for f in files.values():
        if not f.is_file():
            p.error(f'missing package input: {f}')
    a.output.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'build/maps/pp_sandkeep/backups' / tag

    def install(src, dst):
        if dst.is_file() and sha(src) == sha(dst):
            return
        if dst.is_file():
            saved = backup / dst.relative_to(a.output)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, saved)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dst.parent, delete=False) as f:
            temporary = Path(f.name)
        try:
            shutil.copy2(src, temporary)
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix='sandkeep-package-') as tmp:
        archive = Path(tmp) / 'operation-sandkeep.pk3'
        with ZipFile(archive, 'w', compression=ZIP_DEFLATED, compresslevel=9) as z:
            for rel, src in sorted(files.items()):
                info = ZipInfo(rel.as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, src.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        for rel, src in files.items():
            install(src, a.output / rel)
        # Named PK3s override loose files: update it together with the BSP.
        install(archive, a.output / archive.name)
    result = dict(archive=str(a.output / 'operation-sandkeep.pk3'),
                  archive_sha256=sha(a.output / 'operation-sandkeep.pk3'),
                  backup=str(backup) if backup.exists() else None,
                  files={str(rel): sha(src) for rel, src in sorted(files.items())})
    manifest = ROOT / 'build/maps/pp_sandkeep/package.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
