"""Cache the sealed BSP and full VIS inputs to q2tool's RAD stage."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from zipfile import BadZipFile, ZipFile

from map_inventory import LUMPS

_LIGHT_VALUES = {b'light', b'_light', b'_color', b'wait', b'_wait', b'_angwait',
                 b'_falloff', b'_cone', b'angle'}
_NUMBER = re.compile(rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
_PROPERTY = re.compile(rb'[ \t]*"([^"\r\n]*)"[ \t]+"([^"\r\n]*)"[ \t]*(?:(?://|[;#]).*)?')
_PAK = re.compile(r'pak[0-9]+\.pak', re.IGNORECASE)
_BSP_HEADER = struct.pack('<4si', b'IBSP', 38)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def topology_hash(source):
    """Ignore only values read by RAD on existing eligible point lights."""
    if any(marker in source for marker in (b'$include', b'/*', b'\x00')):
        return None
    depth, offset = 0, 0
    spans = []
    for line in source.splitlines(keepends=True):
        text = line.strip()
        if not text or text.startswith((b'//', b';', b'#')):
            pass
        elif text == b'{' and depth == 0:
            depth, properties, has_brush = 1, {}, False
        elif text == b'{' and depth == 1:
            depth, has_brush = 2, True
        elif text == b'}' and depth == 2:
            depth = 1
        elif text == b'}' and depth == 1:
            depth = 0
            classname = properties.get(b'classname', (b'', 0, 0))[0]
            named = any(properties.get(key, (b'', 0, 0))[0].strip()
                        for key in (b'targetname', b'target'))
            if not has_brush and classname in (b'light', b'light_spot') and named and b'origin' in properties:
                for key, (value, start, end) in properties.items():
                    if key not in _LIGHT_VALUES:
                        continue
                    numbers = value.split()
                    if (len(value) < 1023 and len(numbers) == (3 if key == b'_color' else 1)
                            and all(_NUMBER.fullmatch(number) for number in numbers)):
                        spans.append((start, end))
        elif depth == 1:
            match = _PROPERTY.fullmatch(line.rstrip(b'\r\n'))
            if not match:
                return None
            key, value = match.groups()
            if key != key.strip() or key in properties:
                return None
            start, end = match.span(2)
            properties[key] = value, offset + start, offset + end
        elif depth != 2 or not text.startswith(b'(') or any(token in text for token in (b'{', b'}', b'"')):
            return None
        offset += len(line)
    if depth:
        return None
    digest = hashlib.sha256()
    offset = 0
    for start, end in spans:
        digest.update(source[offset:start])
        digest.update(b'<RAD value>')
        offset = end
    digest.update(source[offset:])
    return digest.hexdigest()


def asset_hash(basedir, textures):
    """Include files affecting BSP texture lookup, including animated WALs and PAKs."""
    for texture in textures:
        parts = texture.replace('\\', '/').split('/')
        if ':' in texture or any(part in ('', '.', '..') for part in parts):
            return None

    def texture_files(directory, ancestors=()):
        resolved = directory.resolve()
        if resolved in ancestors:
            raise ValueError('cycle in compile texture directory')
        for path in sorted(directory.iterdir()):
            if path.is_dir():
                yield from texture_files(path, (*ancestors, resolved))
            elif path.is_file():
                yield path

    files = [path for path in basedir.iterdir() if _PAK.fullmatch(path.name) and path.is_file()]
    palette = basedir / 'pics' / 'colormap.pcx'
    if palette.is_file():
        files.append(palette)
    texture_dir = basedir / 'textures'
    if texture_dir.is_dir():
        files.extend(texture_files(texture_dir))
    entries = [(path.relative_to(basedir).as_posix(), file_hash(path)) for path in sorted(files)]
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def cache_key(source, topology, assets, manifest, large_bounds):
    inputs = [1, str(source), topology, assets, manifest['basedir'], manifest['tool'],
              manifest['tool_sha256'], manifest['threads'], large_bounds, 'full-vis']
    return hashlib.sha256(json.dumps(inputs).encode()).hexdigest()


def load_bundle(path, key):
    try:
        with ZipFile(path) as archive:
            metadata = json.loads(archive.read('manifest.json'))
            if metadata['key'] != key:
                return None
            bsp = archive.read('map.bsp')
            portal = archive.read('map.prt') if metadata['portal_sha256'] is not None else None
        if not bsp.startswith(_BSP_HEADER) or len(bsp) < 160 or hashlib.sha256(bsp).hexdigest() != metadata['bsp_sha256']:
            return None
        if portal is not None and hashlib.sha256(portal).hexdigest() != metadata['portal_sha256']:
            return None
        return metadata['source_sha256'], bsp, portal
    except (OSError, BadZipFile, KeyError, RuntimeError, ValueError, TypeError):
        return None


def save_bundle(path, key, source_sha, bsp_path, portal_path, bsp_sha):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        metadata = {'key': key, 'source_sha256': source_sha, 'bsp_sha256': bsp_sha,
                    'portal_sha256': file_hash(portal_path) if portal_path.is_file() else None}
        with ZipFile(temporary, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(metadata))
            archive.write(bsp_path, 'map.bsp')
            if metadata['portal_sha256'] is not None:
                archive.write(portal_path, 'map.prt')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def geometry_matches(cached, updated):
    """Ensure the entity refresh preserved all original nonentity BSP lumps."""
    if not updated.startswith(_BSP_HEADER) or len(updated) < 160:
        return False
    for index, name in enumerate(LUMPS):
        old_start, old_size = struct.unpack_from('<ii', cached, 8 + index * 8)
        new_start, new_size = struct.unpack_from('<ii', updated, 8 + index * 8)
        if new_size < 0 or new_start < 0 or new_start + new_size > len(updated):
            return False
        if name == 'entities':
            continue
        if old_size != new_size or cached[old_start:old_start + old_size] != updated[new_start:new_start + new_size]:
            return False
    return True
