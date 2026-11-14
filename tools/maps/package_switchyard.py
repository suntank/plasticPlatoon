#!/usr/bin/env python3
"""Install an exact verified Switchyard build and its existing material dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_endline import material_closure
from verify_sandkeep import parse_entities

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_files(source, bsp):
    files = {Path('maps/pp_switchyard.map'): source, Path('maps/pp_switchyard.bsp'): bsp,
             Path('maps/README-switchyard.md'): ROOT / 'maps/README-switchyard.md',
             Path('maps/switchyard-floorplan.png'): ROOT / 'maps/switchyard-floorplan.png',
             Path('switchyard_dm.cfg'): BASE / 'switchyard_dm.cfg'}
    # Include animated followers as well as every directly used material.
    for material in material_closure(source):
        for suffix in ('.wal', '.png', '.tga'):
            relative = Path('textures') / (material + suffix)
            path = BASE / relative
            if path.is_file():
                files[relative] = path
    entities = parse_entities(source.read_text())
    if not entities or entities[0]['keys'].get('classname') != 'worldspawn':
        raise ValueError('the MAP must begin with worldspawn')
    sky = entities[0]['keys'].get('sky')
    if sky:
        if not re.fullmatch(r'[A-Za-z0-9_/-]+', sky) or '..' in sky:
            raise ValueError('invalid sky basename: ' + sky)
        for side in ('rt', 'bk', 'lf', 'ft', 'up', 'dn'):
            found = False
            for suffix in ('.tga', '.png', '.jpg', '.pcx'):
                relative = Path('env') / (sky + side + suffix)
                path = BASE / relative
                if path.is_file():
                    files[relative] = path
                    found = True
            if not found:
                raise ValueError(f'missing sky face: env/{sky}{side}')
    for path in files.values():
        if not path.is_file():
            raise ValueError('missing package input: ' + str(path))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'maps/source/pp_switchyard.map')
    parser.add_argument('--bsp', type=Path, default=BASE / 'maps/pp_switchyard.bsp')
    parser.add_argument('--verification', type=Path,
                        default=ROOT / 'build/maps/pp_switchyard/verification.json')
    parser.add_argument('--release-dir', type=Path, default=ROOT / 'release/baseq2')
    args = parser.parse_args()
    try:
        report = json.loads(args.verification.read_text())
        bsp_sha = report.get('bsp_sha256') or report.get('bsp', {}).get('sha256')
        if not (report.get('passed') and report.get('map_sha256') == sha(args.source)
                and bsp_sha == sha(args.bsp)):
            parser.error('passing verification for these exact MAP/BSP bytes is required')
        files = package_files(args.source, args.bsp)
        build = ROOT / 'build/maps/pp_switchyard'
        build.mkdir(parents=True, exist_ok=True)
        archive = build / 'operation-switchyard.pk3'
        # Stable entry metadata makes identical inputs produce identical PK3s.
        with tempfile.NamedTemporaryFile(dir=build, suffix='.pk3.tmp', delete=False) as staged:
            temporary = Path(staged.name)
        try:
            with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as output:
                for relative, path in sorted(files.items()):
                    info = ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    output.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED,
                                    compresslevel=9)
            temporary.replace(archive)
            archive.chmod(0o644)
        finally:
            temporary.unlink(missing_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = build / 'backups' / stamp
        destinations = list(dict.fromkeys([BASE.resolve(), args.release_dir.expanduser().resolve()]))
        installed = []
        for index, destination in enumerate(destinations):
            for relative, path in {**files, Path(archive.name): archive}.items():
                target = destination / relative
                if target.is_file() and sha(path) == sha(target):
                    continue
                if target.exists():
                    saved = backup / str(index) / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, saved)
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as staged:
                    staged_path = Path(staged.name)
                try:
                    shutil.copy2(path, staged_path)
                    staged_path.replace(target)
                finally:
                    staged_path.unlink(missing_ok=True)
            installed.append(str(destination / archive.name))
        manifest = {'archive': str(archive), 'archive_sha256': sha(archive),
                    'map_sha256': sha(args.source), 'bsp_sha256': sha(args.bsp),
                    'installed': installed,
                    'backup': str(backup) if backup.exists() else None,
                    'files': {str(relative): sha(path) for relative, path in sorted(files.items())}}
        (build / 'package.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({key: value for key, value in manifest.items() if key != 'files'}, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
