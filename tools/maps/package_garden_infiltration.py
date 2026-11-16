#!/usr/bin/env python3
"""Package a verified Garden Infiltration build without installing into a runtime.

The separate mission archive contains only this map, its launch configurations,
used materials (including animation followers), sky and transport dependencies.
It never writes pp_garden or an existing game's assets, settings or saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from dropship_dependencies import dropship_files
from verify_sandkeep import parse_entities


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
MAP_NAME = 'pp_garden_infiltration'
ARCHIVE_NAME = 'operation-garden-infiltration.pk3'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset_name(name):
    """Keep MAP/WAL-controlled paths within the package's asset directories."""
    path = PurePosixPath(name)
    if (not re.fullmatch(r'[A-Za-z0-9_+/-]+', name) or path.is_absolute()
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('unsafe asset basename: ' + name)
    return name


def package_contents(source, bsp, runtime_source, translation):
    source_data, bsp_data = source.read_bytes(), bsp.read_bytes()
    if len(bsp_data) < 160 or struct.unpack_from('<4si', bsp_data) != (b'IBSP', 38):
        raise ValueError('expected a compiled Quake II IBSP38 map')
    entities = parse_entities(source_data.decode('utf-8-sig'))
    if not entities or entities[0]['keys'].get('classname') != 'worldspawn':
        raise ValueError('the MAP must begin with worldspawn')
    files = {f'maps/{MAP_NAME}.map': source_data,
             f'maps/{MAP_NAME}.bsp': bsp_data}
    runtime_data = runtime_source.read_bytes()
    translation_data = translation.read_bytes()
    receipt = json.loads(translation_data)
    if (receipt.get('authored_source_sha256') != digest(source_data)
            or receipt.get('runtime_source_sha256') != digest(runtime_data)):
        raise ValueError('translation receipt must match the authored and runtime MAP bytes')
    if (not isinstance(receipt.get('translation'), list)
            or len(receipt['translation']) != 3
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in receipt['translation'])):
        raise ValueError('translation receipt must specify a three-coordinate offset')
    files[f'maps/{MAP_NAME}_runtime.map'] = runtime_data
    files['maps/garden-infiltration-translation.json'] = translation_data
    for name in ('garden_infiltration_solo.cfg', 'garden_infiltration_coop.cfg'):
        files[name] = (BASE / name).read_bytes()

    # Animation followers are only in WAL metadata; copying direct MAP textures
    # alone can leave an otherwise valid mission missing its switch animation.
    pending = [name for entity in entities for name in entity['textures']]
    seen = set()
    while pending:
        name = asset_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        relative = 'textures/' + name + '.wal'
        data = (BASE / relative).read_bytes()
        if len(data) < 100:
            raise ValueError('truncated WAL header: ' + relative)
        files[relative] = data
        follower = struct.unpack_from('<32s', data, 56)[0].split(b'\0')[0].decode('ascii')
        if follower:
            pending.append(follower)
        for suffix in ('.png', '.tga'):
            relative = 'textures/' + name + suffix
            path = BASE / relative
            if path.is_file():
                files[relative] = path.read_bytes()

    sky = entities[0]['keys'].get('sky', 'sandkeep')
    asset_name(sky)
    for side in ('rt', 'bk', 'lf', 'ft', 'up', 'dn'):
        found = False
        for suffix in ('.tga', '.png', '.jpg', '.pcx'):
            relative = 'env/' + sky + side + suffix
            path = BASE / relative
            if path.is_file():
                files[relative] = path.read_bytes()
                found = True
        if not found:
            raise ValueError(f'missing sky face: env/{sky}{side}')

    for relative, path in dropship_files(BASE).items():
        files[relative] = path.read_bytes()
    # Source audio uses uppercase names on this workstation; the native game
    # requests lowercase paths. Store the requested name in the case-sensitive
    # archive without renaming or replacing the existing source sound.
    audio = BASE / 'sound/bosshovr/bhvengn1.wav'
    if not audio.is_file():
        audio = BASE / 'sound/bosshovr/BHVENGN1.wav'
    if audio.is_file():
        files['sound/bosshovr/bhvengn1.wav'] = audio.read_bytes()
    readme = ROOT / 'maps/README-garden-infiltration.md'
    if readme.is_file():
        files['maps/README-garden-infiltration.md'] = readme.read_bytes()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=ROOT / f'maps/source/{MAP_NAME}.map')
    parser.add_argument('--bsp', type=Path, default=BASE / f'maps/{MAP_NAME}.bsp')
    parser.add_argument('--verification', type=Path,
                        default=ROOT / f'build/maps/{MAP_NAME}/verification.json')
    parser.add_argument('--runtime-source', type=Path,
                        default=ROOT / f'build/maps/{MAP_NAME}/runtime-source/{MAP_NAME}.map')
    parser.add_argument('--translation', type=Path,
                        default=ROOT / f'build/maps/{MAP_NAME}/runtime-source/translation.json')
    parser.add_argument('--design', type=Path,
                        default=ROOT / f'maps/source/{MAP_NAME}.design.json')
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'build/garden-infiltration-deploy')
    args = parser.parse_args()
    try:
        out = args.output_dir.expanduser().resolve()
        for runtime in (BASE, ROOT / 'release', Path.home() / '.yq2'):
            if out == runtime.resolve() or out.is_relative_to(runtime.resolve()):
                raise ValueError('use a separate package output directory, outside existing runtimes')
        report_data = args.verification.read_bytes()
        report = json.loads(report_data)
        if (report.get('diagnostic') or report.get('geometry_only')
                or report.get('release_ready') is False):
            raise ValueError('diagnostic or non-release-ready verification cannot be packaged')
        files = package_contents(args.source, args.bsp, args.runtime_source, args.translation)
        source_sha = digest(files[f'maps/{MAP_NAME}.map'])
        runtime_source_sha = digest(files[f'maps/{MAP_NAME}_runtime.map'])
        bsp_sha = digest(files[f'maps/{MAP_NAME}.bsp'])
        verified_source = report.get('source_sha256') or report.get('map_sha256')
        verified_bsp = report.get('bsp_sha256') or report.get('bsp', {}).get('sha256')
        if not (report.get('passed') is True and verified_source == source_sha
                and verified_bsp == bsp_sha):
            raise ValueError('passing verification for these exact MAP/BSP bytes is required')
        if (report.get('runtime_source_sha256') is not None
                and report['runtime_source_sha256'] != runtime_source_sha):
            raise ValueError('verification must match the exact translated runtime MAP bytes')
        if args.design.is_file():
            design_data = args.design.read_bytes()
            if (report.get('design_sha256') is not None
                    and report['design_sha256'] != digest(design_data)):
                raise ValueError('verification must match the exact mission design bytes')
            files['maps/garden-infiltration-design.json'] = design_data

        out.mkdir(parents=True, exist_ok=True)
        archive = out / ARCHIVE_NAME
        with tempfile.NamedTemporaryFile(dir=out, suffix='.pk3.tmp', delete=False) as stage:
            temporary = Path(stage.name)
        try:
            with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as output:
                for name, data in sorted(files.items()):
                    info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    output.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
            temporary.replace(archive)
            archive.chmod(0o644)
        finally:
            temporary.unlink(missing_ok=True)
        manifest = {'map': MAP_NAME, 'archive': str(archive),
                    'archive_sha256': digest(archive.read_bytes()),
                    'source_sha256': source_sha, 'bsp_sha256': bsp_sha,
                    'runtime_source_sha256': runtime_source_sha,
                    'translation_sha256': digest(files['maps/garden-infiltration-translation.json']),
                    'verification_sha256': digest(report_data),
                    'files': {name: digest(data) for name, data in sorted(files.items())},
                    'file_bytes': {name: len(data) for name, data in sorted(files.items())},
                    'installed': False}
        (out / 'package.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({key: value for key, value in manifest.items()
                          if key not in ('files', 'file_bytes')}, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, struct.error) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
