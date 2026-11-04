#!/usr/bin/env python3
"""Reindex existing mission WALs with the original project palette.

Only indexed mipmap payloads and their material metadata change. Editable PNG/
TGA artwork, BSP geometry, texture headers/flags/animation chains and all other
archive members remain intact. No commercial game palette or assets are read.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from PIL import Image

from platoon_palette import PROJECT_PALETTE, PROJECT_PALETTE_SHA256, quantize_opaque

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_WALS = {'textures/common/caulk.wal', 'textures/e1u1/rpip2_2.wal'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def companion(name, assets):
    path = Path(name)
    for suffix in ('.png', '.tga', '.jpg'):
        candidate = path.with_suffix(suffix).as_posix()
        if candidate in assets:
            return candidate, assets[candidate]
    if name not in BOOTSTRAP_WALS:
        raise ValueError(f'No original truecolor companion for {name}')
    return None


def reindex_wal(name, original, image_bytes):
    if len(original) < 100:
        raise ValueError(f'Truncated WAL: {name}')
    _, width, height, *rest = struct.unpack_from('<32sII4I32siii', original)
    offsets = rest[:4]
    sizes = [(width >> mip) * (height >> mip) for mip in range(4)]
    if min(width, height) < 8 or width & (width - 1) or height & (height - 1):
        raise ValueError(f'Invalid WAL dimensions: {name}')
    if offsets[0] != 100 or any(offset < 100 or offset + size > len(original)
                                   for offset, size in zip(offsets, sizes)):
        raise ValueError(f'Invalid WAL mip offsets: {name}')
    output = bytearray(original)
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert('RGB')
    for mip, (offset, length) in enumerate(zip(offsets, sizes)):
        resized = image.resize((width >> mip, height >> mip), Image.Resampling.BOX)
        indexed = quantize_opaque(resized, PROJECT_PALETTE).tobytes()
        assert len(indexed) == length
        output[offset:offset + length] = indexed
    assert output[:100] == original[:100]
    return bytes(output)


def converted(assets):
    result, records = dict(assets), []
    for name, data in sorted(assets.items()):
        if not name.endswith('.wal'):
            continue
        image = companion(name, assets)
        if image is None:
            continue
        image_name, image_bytes = image
        output = reindex_wal(name, data, image_bytes)
        result[name] = output
        records.append({'path': name, 'sha256': sha(output), 'source': image_name,
                        'source_sha256': sha(image_bytes), 'header_sha256': sha(data[:100])})
    # Material manifests describe current indexed output, retaining all authored
    # dimensions, flags, source art hashes and animation metadata.
    for name in sorted(result):
        if not name.endswith('/materials.json'):
            continue
        report = json.loads(result[name])
        report['palette_sha256'] = PROJECT_PALETTE_SHA256
        report['palette_source'] = 'Original palette in tools/assets/build_bootstrap.py'
        for material, entry in report.get('materials', {}).items():
            wal = 'textures/' + material + '.wal'
            if wal in result:
                entry['wal_sha256'] = sha(result[wal])
                entry.pop('palette_indices', None)
                if 'indexed_fallback' in entry:
                    entry['indexed_fallback'] = 'Nearest opaque project-palette color; truecolor source preserved'
        result[name] = (json.dumps(report, indent=2) + '\n').encode()
    for name in assets:
        if not (name.endswith('.wal') or name.endswith('/materials.json')):
            assert result[name] == assets[name], name
    return result, records


def encode_archive(assets):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in sorted(assets.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, data, compresslevel=9)
    return stream.getvalue()


def migrate(basedir, write=False):
    loose = {p.relative_to(basedir).as_posix(): p.read_bytes()
             for p in (basedir / 'textures').rglob('*') if p.is_file()}
    migrated, records = converted(loose)
    changes = []
    for name in loose:
        if migrated[name] != loose[name]:
            changes.append(name)
            if write:
                (basedir / name).write_bytes(migrated[name])
    containers = []
    # The main pack contains only the two original bootstrap WALs. Its builder
    # owns its exact inventory/hash and must remain the only writer for it.
    for path in sorted(basedir.glob('operation-*.pk3')):
        with zipfile.ZipFile(path) as package:
            names = package.namelist()
            if len(names) != len(set(names)):
                raise ValueError(f'Duplicate archive entries: {path}')
            assets = {name: package.read(name) for name in names}
        result, archive_records = converted(assets)
        changed = sorted(name for name in assets if assets[name] != result[name])
        if changed:
            changes.extend(path.name + ':' + name for name in changed)
            if write:
                path.write_bytes(encode_archive(result))
        containers.append({'archive': path.name, 'sha256': sha(path.read_bytes()),
                           'files': archive_records})
    report = {'schema': 1, 'generator': 'tools/maps/reindex_materials.py',
              'palette_source': 'tools/assets/build_bootstrap.py',
              'palette_sha256': PROJECT_PALETTE_SHA256,
              'preserved': 'All truecolor artwork, BSP bytes and non-material archive members; WAL header metadata unchanged',
              'loose_files': records, 'archives': containers}
    return report, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--basedir', type=Path, default=ROOT / 'baseq2')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'tools/maps/material-palette-manifest.json')
    parser.add_argument('--write', action='store_true', help='write reindexed WALs and updated mission packages')
    args = parser.parse_args()
    report, changes = migrate(args.basedir.resolve(), args.write)
    if not args.write and changes:
        parser.error('Materials need reindexing: ' + ', '.join(changes))
    if args.write:
        args.manifest.write_text(json.dumps(report, indent=2) + '\n')
    elif not args.manifest.is_file() or json.loads(args.manifest.read_text()) != report:
        parser.error('Material palette manifest differs from the current inputs')
    count = len(report['loose_files']) + sum(len(a['files']) for a in report['archives'])
    print(f'{"Reindexed" if args.write else "Verified"} {count} loose/archive WALs with the original project palette; {len(changes)} changed members')


if __name__ == '__main__':
    main()
