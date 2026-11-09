#!/usr/bin/env python3
"""Rebuild full VIS while preserving an existing BSP's exact geometry and lighting.

A BSP-only build supplies the portals, then full VIS runs without the -fast flag.
Every nonlighting geometry/entity lump must match the original before VIS can be
transferred. Output is always a separate candidate for inspection/installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from map_inventory import LUMPS, bsp_inventory

ROOT = Path(__file__).resolve().parents[2]


def lump_bytes(raw, name):
    offset, size = struct.unpack_from('<ii', raw, 8 + 8 * LUMPS.index(name))
    return raw[offset:offset + size]


def replace_visibility(original, compiled, output):
    """Validate inputs and atomically write output; never alter either input."""
    original, compiled, output = map(Path, (original, compiled, output))
    if output.resolve() in (original.resolve(), compiled.resolve()):
        raise ValueError('output must be separate from both input BSPs')
    before = bsp_inventory(original, require_release=True)
    candidate = bsp_inventory(compiled)
    old, new = original.read_bytes(), compiled.read_bytes()
    if not candidate['clusters']:
        raise ValueError('compiled BSP has no visibility')
    for name in LUMPS:
        if name in ('visibility', 'lighting'):
            continue
        a, b = lump_bytes(old, name), lump_bytes(new, name)
        if name == 'faces':
            # IBSP38 dface: geometry occupies 12 bytes, then 4 styles and lightofs.
            a = b''.join(a[i:i + 12] for i in range(0, len(a), 20))
            b = b''.join(b[i:i + 12] for i in range(0, len(b), 20))
        if a != b:
            raise ValueError(f'{name} differs: rebuild the complete map instead')
    merged = bytearray(160)
    struct.pack_into('<4si', merged, 0, b'IBSP', 38)
    for i, name in enumerate(LUMPS):
        payload = lump_bytes(new if name == 'visibility' else old, name)
        merged.extend(bytes((-len(merged)) % 4))
        struct.pack_into('<ii', merged, 8 + 8 * i, len(merged), len(payload))
        merged.extend(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.bsp', delete=False) as f:
            temporary = Path(f.name)
            f.write(merged)
        after = bsp_inventory(temporary, require_release=True)
        # Validate the actual new rows against the original leaves before publish.
        os.chmod(temporary, original.stat().st_mode & 0o777)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        'original': str(original.resolve()), 'compiled': str(compiled.resolve()),
        'output': str(output.resolve()), 'original_sha256': before['sha256'],
        'compiled_sha256': candidate['sha256'], 'output_sha256': after['sha256'],
        'unchanged_lumps': [n for n in LUMPS if n != 'visibility'],
        'clusters': after['clusters'],
        'pvs_visible_clusters_mean_before': before['pvs_visible_clusters_mean'],
        'pvs_visible_clusters_mean_after': after['pvs_visible_clusters_mean'],
        'pvs_visible_fraction_mean_before': before['pvs_visible_fraction_mean'],
        'pvs_visible_fraction_mean_after': after['pvs_visible_fraction_mean'],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--source', type=Path, help='current MAP source to compile with full VIS')
    source.add_argument('--compiled-bsp', type=Path, help='reuse an already full-VIS compiled matching BSP')
    p.add_argument('--bsp', required=True, type=Path, help='existing lit BSP to preserve')
    p.add_argument('--output', required=True, type=Path, help='separate candidate BSP')
    p.add_argument('--tool', default=os.environ.get('Q2TOOL', 'q2tool'))
    p.add_argument('--basedir', type=Path, default=ROOT / 'baseq2')
    p.add_argument('--build-dir', type=Path, default=ROOT / 'build/visibility')
    p.add_argument('--threads', type=int, default=2)
    a = p.parse_args()
    if a.threads < 1:
        p.error('--threads must be positive')
    if a.output.resolve() == a.bsp.resolve():
        p.error('--output must be separate from --bsp')
    try:
        compiled = a.compiled_bsp
        source_sha = None
        if a.source:
            compiled = a.build_dir / 'compiled' / (a.source.stem + '.bsp')
            staged = a.build_dir / 'compile' / a.source.stem / (a.source.stem + '.bsp')
            if a.bsp.resolve() in (compiled.resolve(), staged.resolve()):
                raise ValueError('build directory would overwrite the original BSP')
            source_sha = hashlib.sha256(a.source.read_bytes()).hexdigest()
            cmd = [sys.executable, str(ROOT / 'tools/performance/compile_map.py'),
                   '--source', str(a.source.resolve()), '--tool', a.tool,
                   '--basedir', str(a.basedir.resolve()), '--threads', str(a.threads),
                   '--profile', 'preview', '--vis',
                   '--build-dir', str(a.build_dir / 'compile'),
                   '--output-dir', str(a.build_dir / 'compiled')]
            subprocess.run(cmd, check=True)
            if hashlib.sha256(a.source.read_bytes()).hexdigest() != source_sha:
                raise ValueError('MAP source changed during compilation; rerun from current source')
        result = replace_visibility(a.bsp, compiled, a.output)
        if a.source:
            result.update(source=str(a.source.resolve()), source_sha256=source_sha)
        report = a.output.with_suffix('.visibility.json')
        report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        p.exit(1, f'Visibility rebuild failed: {e}\n')


if __name__ == '__main__':
    main()
