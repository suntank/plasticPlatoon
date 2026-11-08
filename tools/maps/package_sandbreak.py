#!/usr/bin/env python3
"""Package verified Operation Sandbreak maps and existing project materials."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from verify_sandkeep import BSP, PLAYER_MASK, PLAYER_MAXS, PLAYER_MINS, parse_entities, vec

ROOT = Path(__file__).resolve().parents[2]
NAME = 'pp_sandbreak'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_debrief(source, compiled):
    """Read the shipped debrief's collision and target graph independently."""
    bsp = BSP(compiled)
    entities = parse_entities(source.read_text())
    errors = []

    def require(value, message):
        if not value:
            errors.append(message)

    def logic(items):
        return Counter(tuple(sorted((k, v) for k, v in e['keys'].items() if k != 'model'))
                       for e in items if e['keys']['classname'] != 'light')

    require(logic(entities) == logic(bsp.entities), 'Debrief source/BSP gameplay entity mismatch')
    require(bool(bsp.lumps['visibility']) and bool(bsp.lumps['lighting']), 'Debrief lacks VIS or RAD')
    starts = [e['keys'] for e in bsp.entities
              if e['keys']['classname'] in ('info_player_start', 'info_player_coop')]
    require(Counter(e['classname'] for e in starts) ==
            Counter(info_player_start=1, info_player_coop=3), 'Debrief needs four co-op starts')
    placement_checks = []
    for e in starts:
        p = vec(e['origin'])
        hit = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
        support = bsp.collision((p[0], p[1], p[2]-2), (-4,-4,-24), (4,4,32), PLAYER_MASK)
        require(not hit and bool(support), f'Debrief start is blocked or unsupported: {e}')
        placement_checks.append(dict(origin=p, collision=hit, supported=bool(support)))
    for i,a in enumerate(starts):
        for b in starts[i+1:]:
            require(math.dist(vec(a['origin']), vec(b['origin'])) >= 64, 'Debrief starts too close')
    names = {e['keys']['targetname'] for e in entities if 'targetname' in e['keys']}
    for e in entities:
        for field in ('target', 'deathtarget', 'killtarget'):
            if field in e['keys']:
                require(e['keys'][field] in names, f'Debrief dangling {field}: {e["keys"]}')
    exits = [e['keys'] for e in entities if e['keys']['classname'] == 'target_changelevel']
    require(len(exits) == 1 and exits[0].get('map') == NAME, 'Debrief replay destination must be bundled assault')
    buttons = [e['keys'] for e in entities if e['keys']['classname'] == 'func_button']
    require(len(buttons) == 1 and buttons[0].get('target') == exits[0].get('targetname')
            if exits else False, 'Debrief replay button must directly target replay')
    route_samples = 0
    for start in starts:
        points = [vec(start['origin']), (0,-240,24), (0,304,24)]
        for a,b in zip(points, points[1:]):
            steps = max(1, math.ceil(math.dist(a,b)/8))
            for i in range(steps+1):
                p = tuple(a[j]+(b[j]-a[j])*i/steps for j in range(3))
                hit = bsp.collision(p, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK)
                require(not hit, f'Debrief route blocked at {p}: {hit}')
                route_samples += 1
    return dict(passed=not errors, errors=errors, placements=placement_checks,
                route_samples=route_samples, map_sha256=sha(source), bsp_sha256=sha(compiled))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-user', action='store_true',
                        help='also install the archive in ~/.yq2/baseq2')
    args = parser.parse_args()
    build = ROOT / 'build/maps' / NAME
    source = ROOT / 'maps/source' / f'{NAME}.map'
    compiled = ROOT / 'baseq2/maps' / f'{NAME}.bsp'
    try:
        report = json.loads((build/'verification.json').read_text())
        if not (report.get('passed') and report.get('map_sha256') == sha(source)
                and report.get('bsp_sha256') == sha(compiled)):
            parser.error('Run verify_sandbreak.py successfully on this exact source/BSP before packaging')
        end_source = ROOT / 'maps/source/pp_sandbreak_end.map'
        end_bsp = ROOT / 'baseq2/maps/pp_sandbreak_end.bsp'
        debrief = verify_debrief(end_source, end_bsp)
        (build/'debrief-verification.json').write_text(json.dumps(debrief, indent=2)+'\n')
        if not debrief['passed']:
            parser.error('Debrief verification failed: '+ '; '.join(debrief['errors']))
        files = {
            f'maps/{NAME}.map': source, f'maps/{NAME}.bsp': compiled,
            'maps/pp_sandbreak_end.map': end_source, 'maps/pp_sandbreak_end.bsp': end_bsp,
            'sandbreak_coop.cfg': ROOT/'baseq2/sandbreak_coop.cfg',
            'sandbreak-readme.txt': ROOT/'maps/README-sandbreak.md',
        }
        textures = {t for p in (source,end_source) for e in parse_entities(p.read_text())
                    for t in e['textures']}
        for texture in textures:
            for suffix in ('wal','png'):
                name=f'textures/{texture}.{suffix}'
                files[name]=ROOT/'baseq2'/name
        for face in ('bk','dn','ft','lf','rt','up'):
            name=f'env/bluesky1{face}.png'
            files[name]=ROOT/'baseq2'/name
        missing = [str(p) for p in files.values() if not p.is_file()]
        if missing:
            parser.error('Missing package inputs: '+', '.join(missing))
        destinations = [ROOT/'baseq2', ROOT/'release/baseq2']
        if args.install_user:
            destinations.append(Path.home()/'.yq2/baseq2')
        with tempfile.TemporaryDirectory(prefix='pp-sandbreak-package-') as temporary:
            archive=Path(temporary)/'operation-sandbreak.pk3'
            with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
                for name,path in sorted(files.items()):
                    info=ZipInfo(name,(1980,1,1,0,0,0))
                    info.create_system=3
                    info.external_attr=0o100644 << 16
                    package.writestr(info,path.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
            digest=sha(archive)
            for dest in destinations:
                dest.mkdir(parents=True,exist_ok=True)
                target=dest/archive.name
                if not target.exists() or sha(target) != digest:
                    staged=target.with_suffix('.pk3.tmp')
                    try:
                        shutil.copyfile(archive,staged)
                        staged.replace(target)
                    finally:
                        staged.unlink(missing_ok=True)
        manifest=dict(archive='operation-sandbreak.pk3',sha256=digest,
                      installed=[str(d/'operation-sandbreak.pk3') for d in destinations],
                      files={n:sha(p) for n,p in sorted(files.items())},debrief_verification=debrief)
        (build/'package.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps({k:v for k,v in manifest.items() if k not in ('files','debrief_verification')},indent=2))
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
