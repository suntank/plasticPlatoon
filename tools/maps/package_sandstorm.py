#!/usr/bin/env python3
"""Install the exact verified Operation Sandstorm source, BSP and material pack."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from verify_sandkeep import parse_entities
from verify_sandstorm import ROOT, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp', type=Path, default=ROOT / 'build/sandstorm-candidate/maps/pp_sandstorm.bsp')
    parser.add_argument('--verification', type=Path, default=ROOT / 'build/maps/pp_sandstorm/verification.json')
    parser.add_argument('--output', type=Path, action='append',
                        help='Install destination; may repeat. Default: baseq2 and release/baseq2.')
    args = parser.parse_args()
    source = ROOT / 'maps/source/pp_sandstorm.map'
    routes = ROOT / 'tools/maps/sandstorm_routes.json'
    report = json.loads(args.verification.read_text())
    if not (report.get('passed') and report.get('map_sha256') == sha(source)
            and report.get('bsp_sha256') == sha(args.bsp)
            and report.get('routes_sha256') == sha(routes)):
        parser.error('Passing verification for these exact MAP, BSP and route bytes is required')
    files = {Path('maps/pp_sandstorm.bsp'): args.bsp,
             Path('maps/pp_sandstorm.map'): source,
             Path('sandstorm-readme.txt'): ROOT / 'maps/README-sandstorm.md'}
    for name in ('sandstorm_solo.cfg', 'sandstorm_coop.cfg'):
        files[Path(name)] = ROOT / 'baseq2' / name
    textures = {t for e in parse_entities(source.read_text()) for t in e['textures']}
    for texture in textures:
        for extension in ('wal', 'png', 'tga'):
            relative = Path('textures') / (texture + '.' + extension)
            path = ROOT / 'baseq2' / relative
            if extension == 'wal' or path.is_file():
                files[relative] = path
    for rel in ('models/items/adrenal/tris.md2', 'sound/world/explod1.wav'):
        files[Path(rel)] = ROOT / 'baseq2' / rel
    for path in (ROOT / 'baseq2/env').glob('sandkeep*.tga'):
        files[path.relative_to(ROOT / 'baseq2')] = path
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        parser.error('Missing package inputs: ' + ', '.join(missing))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'build/maps/pp_sandstorm/backups' / stamp
    outputs = args.output or [ROOT / 'baseq2', ROOT / 'release/baseq2']
    outputs = list(dict.fromkeys(path.resolve() for path in outputs))

    def install(src, destination, relative, index):
        dst = destination / relative
        if dst.exists() and sha(src) == sha(dst):
            return
        if dst.exists():
            saved = backup / str(index) / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, saved)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dst.parent, delete=False) as file:
            temporary = Path(file.name)
        try:
            shutil.copy2(src, temporary)
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix='sandstorm-package-') as tmp:
        archive = Path(tmp) / 'operation-sandstorm.pk3'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
            for relative, path in sorted(files.items()):
                info = ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                package.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED,
                                 compresslevel=9)
        archive_sha = sha(archive)
        for index, destination in enumerate(outputs):
            destination.mkdir(parents=True, exist_ok=True)
            for relative, path in files.items():
                install(path, destination, relative, index)
            install(archive, destination, Path(archive.name), index)
    result = {'archives': [str(path / 'operation-sandstorm.pk3') for path in outputs],
              'archive_sha256': archive_sha, 'files': len(files),
              'map_sha256': report['map_sha256'], 'bsp_sha256': report['bsp_sha256'],
              'destinations': {str(i): str(path) for i, path in enumerate(outputs)},
              'backup': str(backup) if backup.exists() else None}
    manifest = ROOT / 'build/maps/pp_sandstorm/package.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
