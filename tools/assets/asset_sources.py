#!/usr/bin/env python3
"""Read checked original project inputs without consulting Git or a user install."""
from functools import lru_cache
import hashlib
import io
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=3)
def _archive_files(path, expected_sha256, size, mtime_ns):
    """Cache validated bytes; the stat key invalidates an edited archive."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('source archive hash changed: ' + path)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError('duplicate path in source archive: ' + path)
        for name in names:
            member = PurePosixPath(name)
            if (member.is_absolute() or '\\' in name or not name.startswith('baseq2/')
                    or any(part in ('', '.', '..') for part in name.split('/'))):
                raise ValueError('unsafe path in source archive: ' + name)
        return {name: archive.read(name) for name in names}


def source_files(metadata):
    """Return original inputs from the archive explicitly pinned by metadata."""
    archive = metadata.get('source_archive')
    if not isinstance(archive, dict) or not archive.get('path') or not archive.get('sha256'):
        raise ValueError('a pinned source_archive is required; Git source fallbacks are unsupported')
    path = (ROOT / archive['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('source archive escapes the project')
    stat = path.stat()
    return _archive_files(str(path), archive['sha256'], stat.st_size, stat.st_mtime_ns)


def source_bytes(metadata, path):
    """Read one original input; callers must supply checked archive metadata."""
    return source_files(metadata)[path]
