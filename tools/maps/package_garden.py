#!/usr/bin/env python3
"""Package the original Garden shell and its complete material dependencies."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_endline import material_closure
from verify_sandkeep import BSP, parse_entities

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'baseq2'
sys.path.insert(0, str(ROOT / 'tools/performance'))
from map_inventory import bsp_inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE)
    args = parser.parse_args()
    source, compiled = BASE / 'maps/pp_garden.map', BASE / 'maps/pp_garden.bsp'
    inventory = bsp_inventory(compiled, require_release=True)
    authored = parse_entities(source.read_text())
    bsp = BSP(compiled)

    def signature(entities):
        return Counter(tuple(sorted((k, v) for k, v in e['keys'].items()
                                    if k != 'model' and not k.startswith('_')))
                       for e in entities if e['keys'].get('classname') not in ('worldspawn', 'light'))

    if signature(authored) != signature(bsp.entities):
        parser.error('compiled original Garden entities differ from its editable source')
    if len(bsp.brushes) != sum(len(e['brushes']) for e in authored):
        parser.error('compiled original Garden brush count differs from its editable source')
    files = {'maps/pp_garden.map': source, 'maps/pp_garden.bsp': compiled,
             'maps/README-garden.md': ROOT / 'maps/README-garden.md'}
    for name in material_closure(source):
        for suffix in ('.wal', '.png', '.tga'):
            relative = 'textures/' + name + suffix
            if (BASE / relative).is_file():
                files[relative] = BASE / relative
    sky = authored[0]['keys'].get('sky', 'sandkeep')
    if not sky.isidentifier():
        parser.error('unsafe sky basename')
    for side in ('rt', 'bk', 'lf', 'ft', 'up', 'dn'):
        matches = [BASE / ('env/' + sky + side + suffix)
                   for suffix in ('.tga', '.png', '.jpg', '.pcx')]
        matches = [path for path in matches if path.is_file()]
        if not matches:
            parser.error('missing sky face: ' + sky + side)
        files.update((p.relative_to(BASE).as_posix(), p) for p in matches)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / 'operation-garden.pk3'
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(files.items()):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes())
    archive.chmod(0o644)
    report = {'archive': str(archive), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'inventory': inventory,
              'scope': 'Release BSP inventory, entity and brush-count checks; no original compile receipt is available.',
              'files': {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in sorted(files.items())}}
    destination = ROOT / 'build/maps/pp_garden/package.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('files', 'inventory')}, indent=2))


if __name__ == '__main__':
    main()
