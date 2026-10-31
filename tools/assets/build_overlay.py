#!/usr/bin/env python3
"""Package project assets above stock numbered PAKs without redistributing them."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def build_overlay(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    files = sorted(p for directory in ('models', 'players', 'sprites', 'performance')
                   for p in (source / directory).rglob('*') if p.is_file()
                   and p.suffix.lower() in ('.md2', '.md3', '.sp2', '.png', '.pcx', '.tga', '.jpg', '.cfg'))
    if not files:
        raise ValueError(f'no project assets found in {source}')
    for p in files:
        if not p.resolve().is_relative_to(source):
            raise ValueError(f'asset symlink escapes project source: {p}')
    manifest = {'schema': 1, 'files': []}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + '-', dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for p in files:
                data = p.read_bytes()
                entry = {'path': p.relative_to(source).as_posix(), 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()}
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
    return manifest

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--output', type=Path, default=ROOT / 'release/baseq2/plastic-platoon.pk3')
    a = p.parse_args()
    m = build_overlay(a.source, a.output)
    print(f'{a.output}: {len(m["files"])} assets, {m["archive_bytes"]} bytes, SHA256 {m["archive_sha256"]}')

if __name__ == '__main__':
    main()
