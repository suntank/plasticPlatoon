#!/usr/bin/env python3
"""Synchronize only authored rocket media inside the two mission overlays.

All other member contents are pinned by a checked inventory fingerprint. Both
archives are preflighted before any write; archive replacement is atomic.
This tool uses only the standard library and never imports an asset generator.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CONFIG = 'tools/assets/projectile-overlays.json'
MANIFEST = 'tools/assets/projectile-overlays-manifest.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_path(root, name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('unsafe projectile overlay path: ' + name)
    result = root / name
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('projectile overlay path escapes source tree: ' + name)
    return result


def archive_members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError('duplicate mission archive member')
        for name in names:
            checked_path(ROOT, name.rstrip('/'))
        return [(copy.copy(info), archive.read(info)) for info in infos], archive.comment


def untouched_fingerprint(members, managed):
    records = [dict(path=info.filename, bytes=len(raw), sha256=sha(raw))
               for info, raw in members if info.filename not in managed]
    records.sort(key=lambda entry: entry['path'])
    return len(records), sha(json.dumps(records, sort_keys=True, separators=(',', ':')).encode())


def fingerprint_exclusions(root, spec, managed, allowed_peers):
    """Exclude only fixed, separately verified owner payloads from shared proofs.

    A peer is never written by this sync. Its own archive gate must run as
    well; neither owner can grant exemptions for arbitrary mission content.
    """
    result = set(managed)
    peers = spec.get('peer_owners', {})
    if not isinstance(peers, dict):
        raise ValueError('invalid separately owned mission payloads')
    ownership = json.loads(checked_path(root, 'tools/assets/platoon.json').read_text())['procedural_replacements'] if peers else {}
    for owner, paths in peers.items():
        if owner not in allowed_peers or paths != list(allowed_peers[owner]):
            raise ValueError('unexpected separately owned mission payload: ' + owner)
        if owner not in ownership:
            raise ValueError('unregistered peer mission owner: ' + owner)
        registered = ownership[owner]['models'] + ownership[owner]['textures']
        if not set(paths) <= set(registered) or result.intersection(paths):
            raise ValueError('peer mission payload differs from procedural ownership')
        result.update(paths)
    return result


def configuration(root):
    raw = checked_path(root, CONFIG).read_bytes()
    config = json.loads(raw)
    if config.get('schema') != 1 or not config.get('archives'):
        raise ValueError('invalid projectile overlay configuration')
    managed = config['managed_members']
    if len(managed) != len(set(managed)) or not managed:
        raise ValueError('invalid managed projectile member inventory')
    if not set(config['required_existing_members']) <= set(managed):
        raise ValueError('required member is not projectile-owned')
    paths = [entry['path'] for entry in config['archives']]
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate mission overlay')
    return config, sha(raw)


def source_assets(root, config):
    raw = checked_path(root, config['projectile_manifest']).read_bytes()
    manifest = json.loads(raw)
    if manifest['generator'] != 'tools/assets/build_projectiles.py':
        raise ValueError('unexpected projectile generator')
    for name, expected in manifest['dependencies_sha256'].items():
        if sha(checked_path(root, 'tools/assets/' + name).read_bytes()) != expected:
            raise ValueError('projectile generator changed; regenerate projectiles')
    ownership = json.loads(checked_path(root, 'tools/assets/platoon.json').read_text())['procedural_replacements']['projectiles']
    inventory = {entry['path']: entry for entry in manifest['files']}
    if len(inventory) != len(manifest['files']) or set(inventory) != set(ownership['models'] + ownership['textures']):
        raise ValueError('projectile manifest and ownership differ')
    files = {}
    for name, entry in inventory.items():
        data = checked_path(root, 'baseq2/' + name).read_bytes()
        if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
            raise ValueError('stale canonical projectile asset: ' + name)
        files[name] = data
    if not set(config['managed_members']) <= set(files):
        raise ValueError('mission member is not owned by the projectile generator')
    return {name: files[name] for name in config['managed_members']}, sha(raw)


def inspect_archive(root, spec, config):
    raw = checked_path(root, spec['path']).read_bytes()
    members, comment = archive_members(raw)
    names = {info.filename for info, _ in members}
    if not set(config['required_existing_members']) <= names:
        raise ValueError('mission archive lacks its existing rocket model: ' + spec['path'])
    count, fingerprint = untouched_fingerprint(members, config['managed_members'])
    if count != spec['untouched_members'] or fingerprint != spec['untouched_sha256']:
        raise ValueError('unmanaged mission contents changed; refusing projectile sync: ' + spec['path'])
    return raw, members, comment


def updated_archive(members, comment, sources):
    present = {info.filename for info, _ in members}
    if all(name in present and next(raw for info, raw in members if info.filename == name) == data
           for name, data in sources.items()):
        return None
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.comment = comment
        for info, raw in members:
            archive.writestr(copy.copy(info), sources.get(info.filename, raw), compresslevel=9)
        for name in sorted(set(sources) - present):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, sources[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def archive_record(spec, raw, members, sources):
    by_name = {info.filename: data for info, data in members}
    for name, expected in sources.items():
        if by_name.get(name) != expected:
            raise ValueError('mission projectile differs from canonical source: ' + spec['path'] + ':' + name)
    return dict(path=spec['path'], bytes=len(raw), sha256=sha(raw), members=len(members),
                untouched_members=spec['untouched_members'], untouched_sha256=spec['untouched_sha256'],
                managed={name: dict(bytes=len(data), sha256=sha(data)) for name, data in sorted(sources.items())})


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def receipt(config_sha, source_sha, records):
    return dict(schema=1, generator='tools/assets/build_projectile_overlays.py',
                config_sha256=config_sha, projectile_manifest_sha256=source_sha,
                archives=records, proof='Every unmanaged member retains its pinned path, length and content hash.')


def verify(root=ROOT):
    config, config_sha = configuration(root)
    sources, source_sha = source_assets(root, config)
    records = []
    for spec in config['archives']:
        raw, members, _ = inspect_archive(root, spec, config)
        records.append(archive_record(spec, raw, members, sources))
    expected = receipt(config_sha, source_sha, records)
    if json.loads(checked_path(root, MANIFEST).read_text()) != expected:
        raise ValueError('projectile overlay receipt is stale; run build_projectile_overlays.py')
    return expected


def sync(root=ROOT):
    config, config_sha = configuration(root)
    sources, source_sha = source_assets(root, config)
    plans, records = [], []
    # Validate and prepare every mission before making the first archive write.
    for spec in config['archives']:
        raw, members, comment = inspect_archive(root, spec, config)
        updated = updated_archive(members, comment, sources)
        result = updated if updated is not None else raw
        result_members, _ = archive_members(result)
        if untouched_fingerprint(result_members, config['managed_members']) != (spec['untouched_members'], spec['untouched_sha256']):
            raise ValueError('projectile sync altered unmanaged mission contents')
        records.append(archive_record(spec, result, result_members, sources))
        if updated is not None:
            plans.append((checked_path(root, spec['path']), updated))
    for path, raw in plans:
        atomic_write(path, raw)
    output = (json.dumps(receipt(config_sha, source_sha, records), indent=2) + '\n').encode()
    path = checked_path(root, MANIFEST)
    if not path.exists() or path.read_bytes() != output:
        atomic_write(path, output)
    return verify(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = verify() if args.verify else sync()
    print(f"{'Verified' if args.verify else 'Synced and verified'} projectile media in {len(result['archives'])} mission overlays; other members unchanged")


if __name__ == '__main__':
    main()
