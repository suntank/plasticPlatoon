#!/usr/bin/env python3
"""Sync only the authored booster model/atlas in the existing Sandstorm preview.

Reuse the tested archive primitives while preserving all edited map/BSP and
other member contents. The old map packager's defaults are never invoked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_projectile_overlays import (sha, checked_path, archive_members,
    untouched_fingerprint, fingerprint_exclusions, updated_archive, atomic_write)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = 'tools/assets/health-overlays.json'
MANIFEST = 'tools/assets/health-overlays-manifest.json'
PEER_MEMBERS = {'dropship': (
    'models/vehicles/platoon_dropship/body.md2',
    'models/vehicles/platoon_dropship/main_rotor.md2',
    'models/vehicles/platoon_dropship/green.png')}


def exclusions(root, config, spec):
    peers = PEER_MEMBERS if spec['path'] == 'baseq2/operation-sandstorm-preview.pk3' else {}
    return fingerprint_exclusions(root, spec, config['managed_members'], peers)


def configuration(root):
    raw = checked_path(root, CONFIG).read_bytes()
    config = json.loads(raw)
    managed = config['managed_members']
    if config.get('schema') != 1 or not config.get('archives') or not managed:
        raise ValueError('invalid health overlay configuration')
    if len(managed) != len(set(managed)) or not set(config['required_existing_members']) <= set(managed):
        raise ValueError('invalid managed health member inventory')
    paths = [spec['path'] for spec in config['archives']]
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate health mission overlay')
    for spec in config['archives']:
        exclusions(root, config, spec)
    return config, sha(raw)


def source_assets(root, config):
    raw = checked_path(root, config['asset_manifest']).read_bytes()
    manifest = json.loads(raw)
    if manifest['generator'] != 'tools/assets/build_health.py':
        raise ValueError('unexpected health generator')
    for name, expected in manifest['dependencies_sha256'].items():
        if sha(checked_path(root, 'tools/assets/' + name).read_bytes()) != expected:
            raise ValueError('health generator changed; regenerate health')
    ownership = json.loads(checked_path(root, 'tools/assets/platoon.json').read_text())['procedural_replacements']['health']
    inventory = {entry['path']: entry for entry in manifest['files']}
    if len(inventory) != len(manifest['files']) or set(inventory) != set(ownership['models'] + ownership['textures']):
        raise ValueError('health manifest and ownership differ')
    files = {}
    for name, entry in inventory.items():
        data = checked_path(root, 'baseq2/' + name).read_bytes()
        if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
            raise ValueError('stale canonical health asset: ' + name)
        files[name] = data
    if not set(config['managed_members']) <= set(files):
        raise ValueError('mission member is not owned by health generator')
    return {name: files[name] for name in config['managed_members']}, sha(raw)


def inspect_archive(root, spec, config):
    raw = checked_path(root, spec['path']).read_bytes()
    members, comment = archive_members(raw)
    if not set(config['required_existing_members']) <= {info.filename for info, _ in members}:
        raise ValueError('mission archive lacks its existing booster model')
    excluded = exclusions(root, config, spec)
    if untouched_fingerprint(members, excluded) != (spec['untouched_members'], spec['untouched_sha256']):
        raise ValueError('unmanaged mission contents changed; refusing health sync: ' + spec['path'])
    return raw, members, comment


def record(spec, raw, members, sources):
    current = {info.filename: data for info, data in members}
    for name, expected in sources.items():
        if current.get(name) != expected:
            raise ValueError('mission health differs from canonical source: ' + name)
    output = dict(path=spec['path'],
                  untouched_members=spec['untouched_members'], untouched_sha256=spec['untouched_sha256'],
                  managed={name: dict(bytes=len(data), sha256=sha(data)) for name, data in sorted(sources.items())},
                  separately_owned=spec.get('peer_owners', {}))
    # A peer sync may change its payload or ZIP representation afterwards.
    # The stable receipt proves immutable members plus this owner's exact
    # payload; the combined gates prove the separately owned members.
    if not spec.get('peer_owners'):
        output.update(bytes=len(raw), sha256=sha(raw), members=len(members))
    return output


def receipt(config_sha, source_sha, records):
    return dict(schema=1, generator='tools/assets/build_health_overlays.py',
                config_sha256=config_sha, health_manifest_sha256=source_sha,
                archives=records, proof='All immutable Sandstorm member contents retain their pinned hashes; separately owned dropship media require their own archive gate.')


def verify(root=ROOT):
    config, config_sha = configuration(root)
    sources, source_sha = source_assets(root, config)
    records = []
    for spec in config['archives']:
        raw, members, _ = inspect_archive(root, spec, config)
        records.append(record(spec, raw, members, sources))
    expected = receipt(config_sha, source_sha, records)
    if json.loads(checked_path(root, MANIFEST).read_text()) != expected:
        raise ValueError('health overlay receipt is stale; run build_health_overlays.py')
    return expected


def sync(root=ROOT):
    config, config_sha = configuration(root)
    sources, source_sha = source_assets(root, config)
    plans, records = [], []
    for spec in config['archives']:
        raw, members, comment = inspect_archive(root, spec, config)
        updated = updated_archive(members, comment, sources)
        result = updated if updated is not None else raw
        result_members, _ = archive_members(result)
        excluded = exclusions(root, config, spec)
        if untouched_fingerprint(result_members, excluded) != (spec['untouched_members'], spec['untouched_sha256']):
            raise ValueError('health sync altered unmanaged mission contents')
        records.append(record(spec, result, result_members, sources))
        if updated is not None:
            plans.append((checked_path(root, spec['path']), updated))
    for path, data in plans:
        atomic_write(path, data)
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
    print(f"{'Verified' if args.verify else 'Synced and verified'} authored health in {len(result['archives'])} mission overlay; edited map and other members unchanged")


if __name__ == '__main__':
    main()
