#!/usr/bin/env python3
"""Check Temple's local deathmatch clients and touch-trigger doors in isolation.

Reuse the established runtime staging/control/capture helper. Only the project's
media is copied into disposable /tmp game directories; user settings and saves
are never read or changed. Teleportation isolates door operation from traversal.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from zipfile import ZipFile

from check_endline_runtime import Runtime, ENTITY
from verify_sandkeep import BSP, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK
from verify_temple import reference_floor, sha

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/assets'))
from smoke_standalone import diagnostics


class TempleRuntime(Runtime):
    def __init__(self, args):
        super().__init__(args)
        (self.base / 'maps/pp_endline.bsp').rename(self.base / 'maps/pp_temple.bsp')
        (self.out / 'pp_endline.map').rename(self.out / 'pp_temple.map')
        cfg = (self.base / 'endline-qa.cfg').read_text().replace('pp_endline', 'pp_temple')
        # cl_bench_local creates the real local clients and queues map loading.
        # These settings execute before that queued map command.
        cfg += f'\nset deathmatch 1\nset coop 0\nset singleplayer 0\nset dmflags {args.dmflags}\n'
        (self.base / 'endline-qa.cfg').write_text(cfg)
        (self.out / 'settings.cfg').write_text(cfg.replace(self.token, 'LOCAL_RCON_TOKEN'))
        self.report.update(map_name='pp_temple', requested_mode='deathmatch', dmflags=args.dmflags,
                           purpose='Local clients, DM spawning, and ordinary touch-trigger door operation')

    def entities(self):
        start = len(self.console())
        self.run('listentities all', .15)
        chunk = self.until(lambda: self.console()[start:]
                           if '\ninfo_player_intermission:' in self.console()[start:] else None,
                           6, 'Entity snapshot did not finish')
        return [(kind, tuple(map(float, xyz))) for kind, *xyz in ENTITY.findall(chunk)]

    def doors(self):
        return [position for classname, position in self.entities() if classname == 'func_door']


def approaches(bsp, reference):
    result = []
    for entity, model, offset in bsp.bmodels:
        if entity['keys'].get('classname') != 'func_door':
            continue
        bounds = bsp.models[model]
        center = [(bounds[i] + bounds[i+3])/2 for i in range(3)]
        candidates = []
        for axis in sorted(range(2), key=lambda i: bounds[i+3] - bounds[i]):
            for sign in (-1, 1):
                point = center[:]
                point[axis] = bounds[axis if sign < 0 else axis+3] + sign*24
                height = reference_floor(reference, point[0], point[1], bounds[2])
                if height is None or abs(height-bounds[2]) > 24:
                    continue
                point[2] = height+24.1
                for rise in range(19):
                    raised = (point[0], point[1], point[2]+rise)
                    if not bsp.collision(raised, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
                        candidates.append(raised)
                        break
        if not candidates:
            raise ValueError('No safe approach to ' + entity['keys']['targetname'])
        result.append(dict(name=entity['keys']['targetname'], point=candidates[0],
                           expected_offset=bsp.open_door_offset(entity, model, offset)))
    if len(result) != 6:
        raise ValueError(f'Expected six Temple doors, found {len(result)}')
    return result


def run_case(args, players, door_approaches):
    settings = SimpleNamespace(source=args.source, bsp=args.bsp, output_root=args.output_root,
        label=f'{args.label}-{players}', renderer=args.renderer, runtime=args.runtime,
        size=args.size, farsee=0, skill=1, players=players, display_backend=args.display_backend,
        egl_device=None, keep_runtime=args.keep_runtime, dmflags=args.dmflags)
    runtime = TempleRuntime(settings)
    try:
        runtime.start()
        origins = [origin for classname, origin in runtime.entities() if classname == 'player']
        runtime.check('all_local_clients_spawned', len(origins) == players, players=origins)
        closed = runtime.doors()
        runtime.check('six_closed_doors', len(closed) == 6 and all(abs(p[2]) < .01 for p in closed),
                      door_origins=closed)
        poses = runtime.capture(f'{players}_player_spawn')
        runtime.check('all_local_views_rendered', set(poses) == {str(i) for i in range(players)},
                      rendered_slots=sorted(poses))
        with (runtime.base/'perf'/f'qa_{players}_player_spawn-views.csv').open() as stream:
            views = list(csv.DictReader(stream))
        rolls = sorted({float(view['roll']) for view in views})
        runtime.check('all_spawn_views_alive', bool(views) and all(abs(roll) < 10 for roll in rolls),
                      camera_rolls=rolls)  # the engine fixes dead-player view roll at 40
        captured = (runtime.base/'perf'/f'qa_{players}_player_spawn-settings.txt').read_text()
        runtime.check('deathmatch_rules_active', 'deathmatch=1\n' in captured and 'coop=0\n' in captured,
                      settings=[line for line in captured.splitlines()
                                if re.match(r'^(deathmatch|coop|maxclients|ss_players|ss_active)=', line)])
        telefrags = [line for line in runtime.console().splitlines() if 'tried to invade' in line]
        runtime.report['join_telefrags'] = telefrags
        runtime.check('no_join_telefrags', not telefrags, messages=telefrags)
        for index, door in enumerate(door_approaches):
            before = runtime.doors()
            x, y, z = door['point']
            runtime.pose([x, y, z-10, 0, 0], wait=.2)  # teleport adds ten units
            expected = door['expected_offset'][2]
            after = runtime.until(lambda: positions if (positions := runtime.doors())[index][2] >= expected-.2 else None,
                                  15, door['name'] + ' did not reach its open position')
            runtime.check(door['name']+'_touch_trigger_opens', abs(after[index][2]-expected) < .3,
                          approach=door['point'], before=before[index], after=after[index], expected_z=expected)
        runtime.capture(f'{players}_player_doors_tested')
        available = {p.relative_to(runtime.base).as_posix()
                     for p in runtime.base.rglob('*') if p.is_file()}
        for archive in runtime.base.glob('*.pk3'):
            with ZipFile(archive) as media:
                available.update(media.namelist())
        runtime.report['runtime_diagnostics'] = diagnostics(runtime.console(), available)
        missing = runtime.report['runtime_diagnostics']['missing_resource_paths']
        runtime.check('no_missing_runtime_assets', not missing, missing=missing)
        runtime.report['passed'] = True
    except Exception as error:
        runtime.report['error'] = str(error)
        print(f'{players} players FAILED: {error}', flush=True)
    finally:
        runtime.close()
    return runtime.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp', type=Path, default=ROOT/'baseq2/maps/pp_temple.bsp')
    parser.add_argument('--source', type=Path, default=ROOT/'maps/source/pp_temple.map')
    parser.add_argument('--runtime', type=Path, default=ROOT/'release')
    parser.add_argument('--players', type=int, nargs='+', choices=(2, 4), default=[2, 4])
    parser.add_argument('--dmflags', type=int, default=512)
    parser.add_argument('--label', required=True, help='fresh output prefix')
    parser.add_argument('--output-root', type=Path, default=ROOT/'build/temple-runtime')
    parser.add_argument('--renderer', choices=('gl1', 'gl3'), default='gl3')
    parser.add_argument('--display-backend', choices=('xvfb', 'offscreen'), default='xvfb')
    parser.add_argument('--size', default='640x480')
    parser.add_argument('--keep-runtime', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', args.label):
        parser.error('--label must be a simple directory basename')
    if not re.fullmatch(r'[0-9]+x[0-9]+', args.size):
        parser.error('--size must be WIDTHxHEIGHT')
    args.players = list(dict.fromkeys(args.players))
    report_path = args.output_root / (args.label+'-report.json')
    if report_path.exists() or any((args.output_root/f'{args.label}-{p}').exists() for p in args.players):
        parser.error('choose a fresh --label; these output artifacts already exist')
    try:
        reference = json.loads((ROOT/'tools/maps/temple_layout.json').read_text())
        door_approaches = approaches(BSP(args.bsp), reference)
        result = {'bsp': str(args.bsp.resolve()), 'bsp_sha256': sha(args.bsp),
                  'source_sha256': sha(args.source), 'dmflags': args.dmflags,
                  'cases': [], 'approaches': door_approaches}
        for players in args.players:
            result['cases'].append(run_case(args, players, door_approaches))
        result['passed'] = all(case['passed'] for case in result['cases'])
        args.output_root.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'passed': result['passed'], 'report': str(report_path)}, indent=2))
        return 0 if result['passed'] else 1
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
