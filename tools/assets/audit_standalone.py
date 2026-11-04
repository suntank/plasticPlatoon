#!/usr/bin/env python3
"""Audit a Plastic Platoon data directory without reading home/system game data.

This is a dependency inventory, not a copyright or full gameplay certification.
Archive conflicts are retained as separate providers: this engine's non-numbered
archive precedence depends on directory enumeration, so guessing a winner would
hide possible failures.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

from build_overlay import model_images

ROOT = Path(__file__).resolve().parents[2]
SKY_FACES = ('rt', 'bk', 'lf', 'ft', 'up', 'dn')


def safe_name(name):
    if ('\\' in name or not name or PurePosixPath(name).is_absolute()
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError(f'unsafe asset path: {name!r}')
    return name


def pak_members(data):
    """Read a Quake II PACK archive with strict table and member bounds."""
    if len(data) < 12:
        raise ValueError('truncated PAK header')
    magic, start, size = struct.unpack_from('<4sii', data)
    if magic != b'PACK' or start < 12 or size < 0 or size % 64 or start + size > len(data):
        raise ValueError('invalid PAK directory')
    members = []
    for offset in range(start, start + size, 64):
        raw, begin, length = struct.unpack_from('<56sii', data, offset)
        name = safe_name(raw.split(b'\0', 1)[0].decode('utf-8'))
        if begin < 12 or length < 0 or begin + length > len(data):
            raise ValueError(f'invalid PAK member bounds: {name}')
        members.append((name, data[begin:begin + length]))
    return members


def inventory(data_dir):
    """Return every provider; never consult ~/.yq2 or installed stock assets."""
    assets, archives, errors = defaultdict(list), [], []
    for path in sorted(data_dir.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(data_dir).as_posix()
        if not path.resolve().is_relative_to(data_dir.resolve()):
            errors.append({'provider': relative, 'error': 'symlink escapes audited directory'})
            continue
        # Only top-level archives are part of the engine data search path.
        if path.parent == data_dir and path.suffix.lower() in ('.pak', '.pk3'):
            data = path.read_bytes()
            entry = {'path': relative, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'numbered_stock_namespace': bool(re.fullmatch(r'pak\d+\.pak', path.name, re.I))}
            archives.append(entry)
            try:
                if path.suffix.lower() == '.pak':
                    members = pak_members(data)
                else:
                    with zipfile.ZipFile(path) as archive:
                        members = [(safe_name(item.filename), archive.read(item))
                                   for item in archive.infolist() if not item.is_dir()]
                entry['files'] = len(members)
                for name, content in members:
                    assets[name].append({'provider': relative + ':' + name, 'data': content})
            except (ValueError, UnicodeError, zipfile.BadZipFile, OSError) as error:
                errors.append({'provider': relative, 'error': str(error)})
            continue
        assets[relative].append({'provider': 'loose:' + relative, 'data': path.read_bytes()})
    return dict(assets), archives, errors


def image_candidates(reference):
    path = PurePosixPath(reference)
    if path.suffix.lower() in ('.pcx', '.wal'):
        return [str(path.with_suffix(suffix)) for suffix in ('.png', '.tga', '.jpg')] + [reference]
    return [reference]


def bsp_dependencies(name, data):
    """Inspect Q2 BSP38 texinfo plus explicit entity resource names.

    Mod_LoadTexinfo attempts every entry, including unrendered sky/nodraw and
    entries unused by faces. Their absence may produce a warning/fallback rather
    than prevent play, but they remain real resource requests.
    """
    header_size = 8 + 19 * 8
    if len(data) < header_size or struct.unpack_from('<4si', data) != (b'IBSP', 38):
        raise ValueError(f'invalid BSP38 header: {name}')
    lumps = []
    for index in range(19):
        offset, length = struct.unpack_from('<ii', data, 8 + index * 8)
        if offset < 0 or length < 0 or offset + length > len(data):
            raise ValueError(f'invalid BSP lump {index}: {name}')
        lumps.append(data[offset:offset + length])
    if len(lumps[5]) % 76:
        raise ValueError(f'invalid BSP texinfo length: {name}')
    references = []
    uses_sky = False
    for offset in range(0, len(lumps[5]), 76):
        flags, = struct.unpack_from('<i', lumps[5], offset + 32)
        texture = lumps[5][offset + 40:offset + 72].split(b'\0', 1)[0].decode('utf-8')
        uses_sky |= bool(flags & 4)
        texture = safe_name(texture)
        references.append(('map_texture', f'textures/{texture}.wal',
                           [f'textures/{texture}{suffix}'
                            for suffix in ('.wal', '.png', '.tga', '.jpg', '.m32', '.m8')]))
    entity_text = lumps[0].rstrip(b'\0').decode('utf-8')
    entities = re.findall(r'\{([^{}]*)\}', entity_text, re.S)
    world = {}
    for index, entity in enumerate(entities):
        values = dict(re.findall(r'"([^"\n]*)"\s*"([^"\n]*)"', entity))
        if index == 0:
            world = values
        for key, kind in (('model', 'entity_model'), ('noise', 'entity_sound')):
            value = values.get(key, '')
            if not value or value.startswith('*'):
                continue
            if key == 'noise':
                value = 'sound/' + value.removeprefix('sound/')
            references.append((kind, safe_name(value), [value]))
    if uses_sky:
        sky = world.get('sky', 'unit1_')
        for face in SKY_FACES:
            references.append(('map_sky', f'env/{sky}{face}',
                               [f'env/{sky}{face}{suffix}' for suffix in ('.pcx', '.tga', '.png')]
                               + [f'pics/Skies/{sky}{face}{suffix}' for suffix in ('.m32', '.m8')]))
    # Multiple surfaces often refer to one material.
    return sorted(set((kind, reference, tuple(candidates))
                      for kind, reference, candidates in references))


def dependency_report(assets):
    names = set(assets)
    missing, invalid, checked = [], [], 0
    for name, providers in sorted(assets.items()):
        if PurePosixPath(name).suffix.lower() not in ('.md2', '.sp2', '.bsp'):
            continue
        for item in providers:
            try:
                if name.lower().endswith('.bsp'):
                    references = bsp_dependencies(name, item['data'])
                else:
                    references = [('model_image', ref, image_candidates(ref))
                                  for ref in model_images(name, item['data'])]
                for kind, reference, candidates in references:
                    checked += 1
                    if not any(candidate in names for candidate in candidates):
                        missing.append({'kind': kind, 'asset': name, 'provider': item['provider'],
                                        'reference': reference, 'candidates': list(candidates)})
            except (ValueError, UnicodeError, struct.error) as error:
                invalid.append({'asset': name, 'provider': item['provider'], 'error': str(error)})
    return {'references_checked': checked, 'missing': missing, 'invalid': invalid}


def source_literal_references(root, names):
    """Potential calls, not a claim that every inherited monster is reachable."""
    references = defaultdict(set)
    pattern = re.compile(r'gi\.(soundindex|modelindex|imageindex)\s*\(\s*"([^"\n]+)"')
    for path in sorted((root / 'src/game').rglob('*.c')):
        source = path.read_text(errors='replace')
        for match in pattern.finditer(source):
            kind, value = match.groups()
            if value.startswith(('*', '#')):
                continue  # player-relative sounds/inline models need runtime context
            if kind == 'soundindex':
                value = 'sound/' + value
                candidates = [value]
            elif kind == 'imageindex':
                value = 'pics/' + value
                if not PurePosixPath(value).suffix:
                    value += '.pcx'
                candidates = image_candidates(value)
            else:
                candidates = [value]
            if not any(candidate in names for candidate in candidates):
                line = source.count('\n', 0, match.start()) + 1
                references[(kind, value)].add(f'{path.relative_to(root)}:{line}')
    return [{'kind': kind, 'reference': reference, 'calls': sorted(calls)}
            for (kind, reference), calls in sorted(references.items())]


def strip_candidates(root):
    candidates = []
    patterns = [
        ('homogenizeTextures.psd', 'Texture authoring source; not loaded by the game.'),
        ('blender/*.blend', 'Model authoring source; optional for runtime, useful for source releases.'),
        ('blender/*.blend1', 'Editor backup; not loaded by the game.'),
        ('autosave/*', 'Editor autosave; not loaded by the game.'),
        ('kingpin.zip', 'Legacy external source archive; review contents and rights before public hosting.'),
        ('test-crash.*', 'Map compiler diagnostics; not loaded by the game.'),
        ('test.prt', 'Map compiler intermediate; not loaded by the game.'),
        ('**/__pycache__/*.pyc', 'Generated Python cache; not needed in the repository or runtime.'),
    ]
    for pattern, reason in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                candidates.append({'path': path.relative_to(root).as_posix(),
                                   'bytes': path.stat().st_size, 'reason': reason})
    for name in ('build', 'debug', 'release'):
        path = root / name
        if path.is_dir():
            candidates.append({'path': name + '/', 'bytes': sum(p.stat().st_size for p in path.rglob('*') if p.is_file()),
                               'reason': 'Generated build output; rebuild or distribute separately as release artifacts.'})
    return candidates


def provenance_report(root):
    """Record an explicit owner declaration without certifying asset rights."""
    declaration_path = root / 'tools/assets/asset-provenance.json'
    unreviewed = {'status': 'unreviewed',
                  'reason': 'Names, hashes and dependency closure do not establish ownership or redistribution rights. Review art/audio/source inputs and choose asset licenses.'}
    if not declaration_path.is_file():
        return unreviewed
    try:
        declaration = json.loads(declaration_path.read_text())
    except (OSError, ValueError) as error:
        return {**unreviewed, 'declaration_error': str(error)}
    if (not isinstance(declaration, dict)
            or declaration.get('status') not in ('owner_declared_original', 'user_declared_original')
            or not isinstance(declaration.get('owner_statement'), str)
            or not declaration['owner_statement'].strip()):
        return {**unreviewed, 'declaration_error': 'A recognized status and explicit owner_statement are required.'}
    cleanup_recorded = False
    try:
        cleanup = json.loads((root / 'tools/assets/review/public-cleanup.json').read_text())
        cleanup_recorded = cleanup.get('history_cleanup', {}).get('old_objects_removed', False) is True
    except (OSError, ValueError, AttributeError):
        pass
    return {'status': 'owner_declared_original',
            'declaration_file': declaration_path.relative_to(root).as_posix(),
            'owner_statement': declaration['owner_statement'],
            'license': declaration.get('license'),
            'license_document': declaration.get('license_document'),
            'scope': declaration.get('scope', []), 'excluded': declaration.get('excluded', []),
            'limitations': declaration.get('limitations', []),
            'source_history_review': 'cleanup_recorded' if cleanup_recorded else 'required',
            'reason': ('Owner declaration and public-source cleanup recorded; run audit_public_source.py --history to check the current object store. '
                       if cleanup_recorded else 'Owner declaration recorded; source/history review remains. ')
                      + 'This audit does not independently certify ownership or redistribution rights.'}


def audit(data_dir, root=ROOT, maps=('pp_sandbox_coop1',)):
    data_dir = Path(data_dir).resolve()
    root = Path(root).resolve()
    assets, archives, errors = inventory(data_dir)
    requirements = [
        ('renderer_palette', 'pics/colormap.pcx', ['pics/colormap.pcx'],
         'GetPCXPalette loads an indexed PCX directly; a PNG replacement cannot satisfy this.'),
        ('console_font', 'pics/conchars.pcx', image_candidates('pics/conchars.pcx'),
         'GL1/GL3 accept high-color replacements; the software renderer requires PCX.'),
        ('default_bindings', 'default.cfg', ['default.cfg'],
         'Provides fresh-install bindings and defaults; absence can leave the controls unbound.'),
    ]
    for name in maps:
        reference = f'maps/{name}.bsp'
        requirements.append(('launch_map', reference, [reference], 'Selected initial map.'))
    boot = [{'kind': kind, 'reference': reference, 'candidates': candidates,
             'present': any(candidate in assets for candidate in candidates), 'reason': reason}
            for kind, reference, candidates, reason in requirements]
    boot.append({'kind': 'loose_weapon_tuning', 'reference': 'tuning/default.json',
                 'candidates': ['loose:tuning/default.json'],
                 'present': (data_dir / 'tuning/default.json').is_file(),
                 'reason': 'The game module uses fopen rather than archive lookup for the approved weapon profile.'})
    dependencies = dependency_report(assets)
    conflicting = []
    for name, providers in sorted(assets.items()):
        if len({hashlib.sha256(p['data']).digest() for p in providers}) > 1:
            conflicting.append({'asset': name, 'providers': [p['provider'] for p in providers]})
    legacy = [{'path': name, 'providers': [p['provider'] for p in providers],
               'reason': 'Legacy stock player namespace; inspect original ownership before publishing.'}
              for name, providers in sorted(assets.items()) if name.startswith('players/male/')]
    numbered = [item['path'] for item in archives if item['numbered_stock_namespace']]
    strict_failures = (errors or not all(item['present'] for item in boot)
                       or dependencies['missing'] or dependencies['invalid'] or numbered or legacy or conflicting)
    return {
        'schema': 1, 'data_directory': str(data_dir), 'repository': str(root),
        'runtime_dependency_checks_pass': not bool(strict_failures),
        'public_release_readiness': 'not_certified',
        'provenance': provenance_report(root),
        'limitations': [
            'Audits only this data directory; never reads home or system game data.',
            'Checks all archive providers because non-numbered archive precedence is filesystem dependent.',
            'Parses MD2/SP2 image references and all BSP38 texinfo materials, sky faces and explicit model/noise entity keys; missing map images may trigger warning/fallback rather than prevent play.',
            'Potential source literal calls include inherited or unreachable entities; dynamic names, player sounds, client effects and scripted resource loads still need runtime testing.',
            'Presence checks do not decode images/audio or prove rendering, gameplay, platform-library availability or asset rights.',
            'Numbered PAK and players/male names are review markers, not hash-based identification of proprietary bytes.',
        ],
        'inventory': {'unique_asset_paths': len(assets), 'providers': sum(map(len, assets.values())),
                      'archives': archives, 'archive_errors': errors, 'conflicting_providers': conflicting},
        'boot_requirements': boot,
        'conditional_renderer_requirements': [
            {'reference': 'pics/conchars.pcx', 'present': 'pics/conchars.pcx' in assets,
             'condition': 'Software renderer: indexed PCX is required even when a GL-compatible PNG exists.'},
            {'reference': 'pics/16to8.dat', 'present': 'pics/16to8.dat' in assets,
             'condition': 'GL1 only when the optional paletted-texture path is enabled.'},
        ],
        'dependencies': dependencies,
        'potential_missing_game_source_literals': source_literal_references(root, set(assets)),
        'stock_review_markers': {'numbered_paks': numbered, 'legacy_player_files': legacy},
        'development_strip_candidates': strip_candidates(root),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'release/baseq2', help='exact runtime data directory to audit')
    parser.add_argument('--root', type=Path, default=ROOT, help='repository for source-call and development-file inventory')
    parser.add_argument('--map', action='append', dest='maps', help='expected launch map; repeatable (default: pp_sandbox_coop1)')
    parser.add_argument('--output', type=Path, help='save JSON; otherwise print JSON to stdout')
    parser.add_argument('--strict', action='store_true', help='exit 1 for missing dependencies, invalid archives/models, conflicting providers, or stock review markers; does not certify rights')
    args = parser.parse_args()
    if not args.data.is_dir():
        parser.error(f'data directory does not exist: {args.data}')
    result = audit(args.data, args.root, tuple(args.maps or ('pp_sandbox_coop1',)))
    output = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        provenance = ('owner declaration and source cleanup recorded'
                      if result['provenance'].get('source_history_review') == 'cleanup_recorded'
                      else 'owner declaration recorded; source/history review remains'
                      if result['provenance']['status'] == 'owner_declared_original'
                      else 'asset rights unreviewed')
        print(f'{args.output}: {len(result["dependencies"]["missing"])} missing embedded references; '
              f'{len(result["potential_missing_game_source_literals"])} potentially missing source literals; '
              + provenance)
    else:
        print(output, end='')
    return int(args.strict and not result['runtime_dependency_checks_pass'])


if __name__ == '__main__':
    raise SystemExit(main())
