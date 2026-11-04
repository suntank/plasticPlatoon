#!/usr/bin/env python3
"""Package Plastic Platoon assets and stage a portable runtime without stock PAKs."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import os
import shutil
import struct
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ASSET_DIRECTORIES = ('models', 'players', 'sprites', 'pics', 'env', 'textures/sandbox',
                     'textures/common', 'textures/e1u1', 'performance', 'sound')
ASSET_SUFFIXES = ('.md2', '.md3', '.sp2', '.png', '.pcx', '.tga', '.jpg', '.wal', '.cfg', '.wav', '.dat')
PORTABLE_MAPS = ('pp_sandbox1', 'pp_sandbox2', 'pp_sandbox_coop1')
EXTERNAL_IMAGES = {}


def asset_files(source):
    source = Path(source).resolve()
    files = sorted(p for directory in ASSET_DIRECTORIES
                   for p in (source / directory).rglob('*') if p.is_file()
                   and p.suffix.lower() in ASSET_SUFFIXES
                   and not p.relative_to(source).as_posix().startswith('players/male/'))
    # Personal configs are never release inputs. Mission configs ship in their
    # own operation archives; this is the original, reproducible TC default.
    if (source / 'default.cfg').is_file():
        files.append(source / 'default.cfg')
    # JSON reports elsewhere (for example performance captures) are not assets.
    files = sorted(files + [p for p in (source / 'tuning').rglob('*')
                            if p.is_file() and p.suffix.lower() == '.json'])
    files = sorted(files + [source / 'maps' / (name + '.bsp') for name in PORTABLE_MAPS
                            if (source / 'maps' / (name + '.bsp')).is_file()])
    if not files:
        raise ValueError(f'no project assets found in {source}')
    for p in files:
        if not p.resolve().is_relative_to(source):
            raise ValueError(f'asset symlink escapes project source: {p}')
    return files


def build_overlay(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    files = asset_files(source)
    manifest = {'schema': 1, 'files': []}
    tuning = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + '-', dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for p in files:
                data = p.read_bytes()
                entry = {'path': p.relative_to(source).as_posix(), 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()}
                if entry['path'].startswith('tuning/'):
                    if not isinstance(json.loads(data), dict):
                        raise ValueError(f'tuning profile must be a JSON object: {p}')
                    tuning[entry['path']] = data
                manifest['files'].append(entry)
                info = zipfile.ZipInfo(entry['path'], date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.chmod(temporary, 0o644)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    manifest['archive_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest['archive_bytes'] = output.stat().st_size
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # The game module uses fopen rather than the engine's archive filesystem.
    # Ship identical loose profiles for weapons and packed profiles for effects.
    for name, data in tuning.items():
        destination = output.parent / name
        if destination.is_file() and destination.read_bytes() == data:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=destination.name + '-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as profile:
                profile.write(data)
            os.chmod(temporary, 0o644)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return manifest


def model_images(name, data):
    """Read image dependencies without requiring the conversion dependencies."""
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == '.md2':
        if len(data) < 68:
            raise ValueError(f'truncated MD2 header: {name}')
        header = struct.unpack_from('<17i', data)
        count, offset, end = header[5], header[11], header[16]
        if (header[:2] != (844121161, 8) or not 0 <= count <= 32
                or offset < 68 or offset + 64 * count > end or end > len(data)):
            raise ValueError(f'invalid MD2 skin table: {name}')
        images = [data[offset + i * 64:offset + (i + 1) * 64] for i in range(count)]
    elif suffix == '.sp2':
        if len(data) < 12:
            raise ValueError(f'truncated SP2 header: {name}')
        ident, version, count = struct.unpack_from('<3i', data)
        if (ident, version) != (844317769, 2) or not 0 < count <= 32 or len(data) != 12 + 80 * count:
            raise ValueError(f'invalid SP2 frames: {name}')
        images = [data[28 + i * 80:92 + i * 80] for i in range(count)]
    else:
        return []
    references = []
    for image in images:
        try:
            reference = image.split(b'\0', 1)[0].decode('utf-8')
        except UnicodeDecodeError as error:
            raise ValueError(f'invalid image path in {name}') from error
        path = PurePosixPath(reference)
        if (not reference or '\\' in reference or path.is_absolute()
                or any(part in ('', '.', '..') for part in reference.split('/'))):
            raise ValueError(f'unsafe image dependency in {name}: {reference!r}')
        references.append(reference)
    return references


def check_image_dependencies(assets):
    """Require model/sprite images in the pack, accepting renderer replacements.

    The renderer accepts PNG/TGA/JPG replacements for a referenced PCX. Sprite
    frame dimensions describe world-space size and need not match image pixels.
    """
    names = {name.lower() for name in assets}
    checked, external = 0, []
    for name, data in assets.items():
        for reference in model_images(name, data):
            path = PurePosixPath(reference)
            candidates = [reference]
            if path.suffix.lower() in ('.pcx', '.wal'):
                candidates.extend(str(path.with_suffix(suffix)) for suffix in ('.png', '.tga', '.jpg'))
            if not any(candidate.lower() in names for candidate in candidates):
                reason = EXTERNAL_IMAGES.get((name, reference))
                if reason is None:
                    raise ValueError(f'missing image dependency: {name} -> {reference}')
                external.append({'model': name, 'image': reference, 'reason': reason})
            checked += 1
    return {'image_references': checked, 'external_images': external}


def verify_overlay(source, output):
    """Verify exact loose-tree/archive/manifest equality and image closure."""
    source, output = Path(source).resolve(), Path(output).resolve()
    files = asset_files(source)
    expected = {p.relative_to(source).as_posix(): p for p in files}
    manifest = json.loads(output.with_suffix('.manifest.json').read_text())
    if manifest.get('schema') != 1:
        raise ValueError('unsupported overlay manifest schema')
    archive_data = output.read_bytes()
    if (manifest.get('archive_bytes') != len(archive_data)
            or manifest.get('archive_sha256') != hashlib.sha256(archive_data).hexdigest()):
        raise ValueError('archive bytes/hash differ from manifest')
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if names != sorted(expected):
            raise ValueError('archive entries differ from loose asset inventory')
        assets, entries = {}, []
        for name in names:
            data = archive.read(name)
            if data != expected[name].read_bytes():
                raise ValueError(f'archive differs from loose asset: {name}')
            if name.startswith('tuning/'):
                loose = output.parent / name
                if not loose.is_file() or loose.read_bytes() != data:
                    raise ValueError(f'loose tuning differs from archive: {name}')
            entries.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            assets[name] = data
    if manifest.get('files') != entries:
        raise ValueError('manifest entries differ from archive contents')
    dependencies = check_image_dependencies(assets)
    return manifest, dependencies


def stage_portable(source, output):
    """Stage all versioned mission packs, launcher, license and runtime notes."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source != (ROOT / 'baseq2').resolve() or output.parent == source:
        return
    for package in sorted(source.glob('operation-*.pk3')):
        shutil.copyfile(package, output.parent / package.name)
    release = output.parent.parent
    launcher = release / 'play-portable.sh'
    launcher.write_bytes((ROOT / 'packaging/portable/launch.sh').read_bytes())
    launcher.chmod(0o755)
    shutil.copyfile(ROOT / 'LICENSE', release / 'LICENSE')
    shutil.copyfile(ROOT / 'ASSET-LICENSE.md', release / 'ASSET-LICENSE.md')
    shutil.copyfile(ROOT / 'tools/assets/asset-provenance.json', release / 'asset-provenance.json')
    shutil.copyfile(ROOT / 'packaging/portable/README.txt', release / 'README.txt')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--output', type=Path, default=ROOT / 'release/baseq2/plastic-platoon.pk3')
    p.add_argument('--verify', action='store_true', help='check archive, manifest, loose assets and image dependencies without writing')
    a = p.parse_args()
    if a.verify:
        m, dependencies = verify_overlay(a.source, a.output)
        print(f'Verified {len(m["files"])} packaged assets and {dependencies["image_references"]} model/sprite image references.')
        for dependency in dependencies['external_images']:
            print(f'External image: {dependency["model"]} -> {dependency["image"]}. {dependency["reason"]}')
        return
    m = build_overlay(a.source, a.output)
    stage_portable(a.source, a.output)
    print(f'{a.output}: {len(m["files"])} assets, {m["archive_bytes"]} bytes, SHA256 {m["archive_sha256"]}')

if __name__ == '__main__':
    main()
