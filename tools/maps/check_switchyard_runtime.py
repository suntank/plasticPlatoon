#!/usr/bin/env python3
"""Exercise local DM clients and sample brush rendering in an isolated game.

The default map is Switchyard. A different map plus --views can calibrate the
same renderer, settings and four-view capture protocol against Temple. Geometry
counters are reported separately from alias models and CPU wall time.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from zipfile import ZipFile

from check_endline_runtime import Runtime, ENTITY
from verify_sandkeep import BSP, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK, vec
from verify_temple import Collision, mean, sha

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/assets'))
from smoke_standalone import diagnostics


class ArenaRuntime(Runtime):
    def __init__(self, args):
        super().__init__(args)
        self.map_name = args.map_name
        (self.base/'maps/pp_endline.bsp').rename(self.base/'maps'/f'{self.map_name}.bsp')
        (self.out/'pp_endline.map').rename(self.out/f'{self.map_name}.map')
        cfg = (self.base/'endline-qa.cfg').read_text().replace('pp_endline', self.map_name)
        # Local-client setup queues map loading; apply DM after its co-op
        # defaults and before the queued map command executes.
        cfg += f'\nset deathmatch 1\nset coop 0\nset singleplayer 0\nset dmflags {args.dmflags}\n'
        cfg += '\n'.join(f'set {key} {value}' for key, value in dict(r_novis=0, r_cull=1,
            r_drawworld=1, r_drawentities=1, r_drawprofile=0, r_pickup_lod=1,
            gl1_multitexture=1, gl1_lightmapcopies=0, r_gl1_batch_world=1,
            r_gl1_batch_inline=1, cl_gun=args.viewweapon).items())+'\n'
        (self.base/'endline-qa.cfg').write_text(cfg)
        (self.out/'settings.cfg').write_text(cfg.replace(self.token, 'LOCAL_RCON_TOKEN'))
        self.report.update(map_name=self.map_name, dmflags=args.dmflags,
            renderer=args.renderer, renderer_sha256=sha(self.root/f'ref_{args.renderer}.so'),
            staged_art_archive_sha256=sha(self.base/'zz-endline-qa-art.pk3'),
            purpose='Local DM clients and sampled brush-rendering budget; teleportation, audio disabled')

    def entities(self):
        start = len(self.console())
        self.run('listentities all', .15)
        chunk = self.until(lambda: self.console()[start:]
            if '\ninfo_player_intermission:' in self.console()[start:] else None,
            6, 'Entity snapshot did not finish')
        return [(kind, tuple(map(float, xyz))) for kind, *xyz in ENTITY.findall(chunk)]


def read_points(args, bsp):
    collision = Collision(bsp)
    if args.views:
        requested = [{'name': view['name'], 'origin': tuple(view['pose'][:3]),
                      'pitch': view['pose'][3], 'yaw': view['pose'][4]}
                     for view in json.loads(args.views.read_text())]
    else:
        document = json.loads(args.routes.read_text())
        requested = []
        for name, floor in document['nodes'].items():
            origin, rise, blocker = collision.standing(floor)
            if origin is None:
                raise ValueError(f'Camera node {name} is obstructed: {blocker}')
            requested.append(dict(name=name, origin=origin, pitch=0, yaw=0))
    for view in requested:
        if bsp.collision(view['origin'], PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
            original = view['origin']
            replacement = None
            # Architecture captures allow a point camera closer to a wall
            # than an actual player AABB. Explicitly record a small inset for
            # this multiplayer protocol rather than spawning into the wall.
            if args.views:
                for distance in (8, 16, 24, 32):
                    for dx, dy in ((-distance, 0), (distance, 0), (0, -distance), (0, distance)):
                        candidate = (original[0]+dx, original[1]+dy, original[2])
                        if not bsp.collision(candidate, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
                            replacement = candidate
                            break
                    if replacement:
                        break
            if replacement is None:
                raise ValueError(f'Camera point {view["name"]} has no clear standing hull')
            view['origin'] = replacement
            view['standing_camera_inset'] = {'original': original, 'actual': replacement}
    return requested


def parking_points(bsp, cameras, players):
    """Choose clear floor positions separated from every camera and spawn."""
    avoid = [view['origin'] for view in cameras]
    avoid += [vec(entity['keys']['origin']) for entity in bsp.entities
              if entity['keys'].get('classname', '').startswith('info_player_')
              and entity['keys'].get('origin')]
    selected = []
    for face in bsp.faces:
        normal_z = bsp.planes[face[0]][2] * (-1 if face[1] else 1)
        if normal_z < .7 or bsp.texinfo[face[4]][8] & (4 | 128):
            continue
        vertices = []
        for edge in bsp.surfedges[face[2]:face[2]+face[3]]:
            a, b = bsp.edges[abs(edge)]
            vertices.append(bsp.vertexes[a if edge >= 0 else b])
        floor = mean(vertices)
        origin = (floor[0], floor[1], floor[2]+24.125)
        if any(math.dist(origin, point) < 80 for point in avoid+selected):
            continue
        if bsp.collision(origin, PLAYER_MINS, PLAYER_MAXS, PLAYER_MASK):
            continue
        selected.append(origin)
        if len(selected) == players:
            return selected
    raise ValueError('Not enough safe parking points for isolated camera changes')


def capture_metrics(runtime, label):
    poses = runtime.capture(label)
    path = runtime.base/'perf'/f'qa_{label}-views.csv'
    rows = list(csv.DictReader(path.open()))
    frames = {}
    for row in rows:
        frames.setdefault(row['frame'], []).append(row)
    complete = [group for group in frames.values()
                if len(group) == runtime.args.players
                and len({row['slot'] for row in group}) == runtime.args.players]
    counters_ready = bool(rows) and all(float(row['renderer_counters']) > 0
        and float(row['world_triangles']) >= 0 and float(row['model_triangles']) >= 0 for row in rows)
    runtime.check(label+'_complete_living_views', bool(complete)
                  and set(poses) == {str(i) for i in range(runtime.args.players)}
                  and all(abs(float(row['roll'])) < 10 for row in rows) and counters_ready,
                  rendered_slots=sorted(poses), complete_frames=len(complete),
                  geometry_counters_supported=counters_ready)
    def describe(row):
        return {'slot': int(row['slot']), 'frame': int(row['frame']),
                'world_triangles': float(row['world_triangles']),
                'model_triangles': float(row['model_triangles']),
                'scene_triangles': float(row['world_triangles'])+float(row['model_triangles']),
                'draws': float(row['draws']),
                'actual_eye': {key: float(row[key]) for key in ('x', 'y', 'z', 'pitch', 'yaw', 'roll')}}
    worst_view = max(rows, key=lambda row: float(row['world_triangles']))
    worst_display = max(complete, key=lambda group: sum(float(row['world_triangles']) for row in group))
    scene = lambda row: float(row['world_triangles'])+float(row['model_triangles'])
    worst_scene_display = max(complete, key=lambda group: sum(scene(row) for row in group))
    return {'label': label, 'complete_display_frames': len(complete),
        'world_triangles_per_view_max': max(float(row['world_triangles']) for row in rows),
        'world_triangles_per_display_max': max(sum(float(row['world_triangles']) for row in group) for group in complete),
        'model_triangles_per_view_max': max(float(row['model_triangles']) for row in rows),
        'model_triangles_per_display_max': max(sum(float(row['model_triangles']) for row in group) for group in complete),
        'scene_triangles_per_view_max': max(scene(row) for row in rows),
        'scene_triangles_per_display_max': max(sum(scene(row) for row in group) for group in complete),
        'draws_per_view_max': max(float(row['draws']) for row in rows),
        'draws_per_display_max': max(sum(float(row['draws']) for row in group) for group in complete),
        'worst_view': describe(worst_view),
        'worst_display_views': [describe(row) for row in worst_display],
        'worst_scene_view': describe(max(rows, key=scene)),
        'worst_scene_display_views': [describe(row) for row in worst_scene_display]}


def summary_from_csv(report, folder):
    """Also read older calibration reports that predate scene-total fields."""
    maxima = {key: {'per_view_max': 0., 'per_display_max': 0.}
              for key in ('world_triangles', 'model_triangles', 'scene_triangles', 'draws')}
    for phase in report['render_samples']:
        groups = {}
        with (folder/'poses'/f'qa_{phase["label"]}-views.csv').open() as stream:
            for row in csv.DictReader(stream):
                values = {key: float(row[key]) for key in ('world_triangles', 'model_triangles', 'draws')}
                values['scene_triangles'] = values['world_triangles']+values['model_triangles']
                groups.setdefault(row['frame'], []).append(values)
                for key, value in values.items():
                    maxima[key]['per_view_max'] = max(maxima[key]['per_view_max'], value)
        for group in groups.values():
            if len(group) != report['players']:
                continue
            for key in maxima:
                maxima[key]['per_display_max'] = max(maxima[key]['per_display_max'], sum(row[key] for row in group))
    return maxima


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-name', default='pp_switchyard')
    parser.add_argument('--bsp', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--routes', type=Path, default=ROOT/'tools/maps/switchyard_routes.json')
    parser.add_argument('--views', type=Path, help='optional named floor camera poses instead of navigation nodes')
    parser.add_argument('--runtime', type=Path, default=ROOT/'release')
    parser.add_argument('--renderer', choices=('gl1', 'gl3'), default='gl1')
    parser.add_argument('--players', type=int, choices=(2, 4), default=4)
    parser.add_argument('--dmflags', type=int, default=512)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output-root', type=Path, default=ROOT/'build/switchyard-runtime')
    parser.add_argument('--yaw-step', type=int, choices=(45, 90), default=45)
    parser.add_argument('--skip-sweep', action='store_true')
    parser.add_argument('--size', default='640x480')
    parser.add_argument('--display-backend', choices=('xvfb', 'offscreen'), default='xvfb')
    parser.add_argument('--keep-runtime', action='store_true')
    parser.add_argument('--viewweapon', type=int, choices=(0, 1), default=1,
                        help='render normal first-person weapons (default: 1)')
    parser.add_argument('--temple-reference', type=Path,
                        default=ROOT/'build/switchyard-qa/temple-four-armed-current-sweep/run.json',
                        help='optional current same-renderer Temple sweep report for sampled comparison')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', args.label):
        parser.error('--label must be a plain fresh directory name')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*', args.map_name):
        parser.error('--map-name must be a BSP basename')
    if not re.fullmatch(r'[0-9]+x[0-9]+', args.size):
        parser.error('--size must be WIDTHxHEIGHT')
    if (args.output_root/args.label).exists():
        parser.error('output exists; choose a fresh --label')
    args.bsp = args.bsp or ROOT/'baseq2/maps'/f'{args.map_name}.bsp'
    args.source = args.source or ROOT/'maps/source'/f'{args.map_name}.map'
    try:
        bsp = BSP(args.bsp)
        cameras = read_points(args, bsp) if not args.skip_sweep else []
        parking = parking_points(bsp, cameras, args.players) if cameras else []
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    runtime_args = SimpleNamespace(**vars(args), farsee=0, skill=1, egl_device=None)
    runtime = ArenaRuntime(runtime_args)
    try:
        runtime.start()
        entities = runtime.entities()
        runtime.check('all_clients_spawned', sum(kind == 'player' for kind, xyz in entities) == args.players)
        telefrags = [line for line in runtime.console().splitlines() if 'tried to invade' in line]
        runtime.check('no_join_telefrags', not telefrags, messages=telefrags)
        phases = [capture_metrics(runtime, 'spawn')]
        settings = (runtime.base/'perf/qa_spawn-settings.txt').read_text()
        runtime.check('deathmatch_and_all_local_views', 'deathmatch=1\n' in settings and 'coop=0\n' in settings
                      and f'ss_players={args.players}\n' in settings)
        if cameras:
            for start in range(0, len(cameras), args.players):
                group = [cameras[(start+i) % len(cameras)] for i in range(args.players)]
                for slot, origin in enumerate(parking):
                    runtime.pose([origin[0], origin[1], origin[2]-10, 0, 0], slot=slot, wait=.05)
                for yaw in range(0, 360, args.yaw_step):
                    for slot, view in enumerate(group):
                        x, y, z = view['origin']
                        runtime.pose([x, y, z-10, view['pitch'], view['yaw']+yaw], slot=slot, wait=.05)
                    metrics = capture_metrics(runtime, f'group{start//args.players}_yaw{yaw}')
                    metrics['camera_names'] = [view['name'] for view in group]
                    metrics['yaw_offset'] = yaw
                    metrics['worst_view']['camera_name'] = group[metrics['worst_view']['slot']]['name']
                    metrics['worst_scene_view']['camera_name'] = group[metrics['worst_scene_view']['slot']]['name']
                    for view in metrics['worst_display_views']:
                        view['camera_name'] = group[view['slot']]['name']
                    for view in metrics['worst_scene_display_views']:
                        view['camera_name'] = group[view['slot']]['name']
                    phases.append(metrics)
        runtime.report['render_samples'] = phases
        runtime.report['camera_points'] = cameras
        runtime.report['parking_points'] = parking
        runtime.report['sampling_protocol'] = {'players': args.players, 'framebuffer': args.size,
            'camera_points': len(cameras), 'yaw_step': args.yaw_step, 'renderer': args.renderer,
            'camera_source': str(args.views or args.routes), 'sweep_skipped': args.skip_sweep,
            'viewweapon': args.viewweapon}
        runtime.report['worst_view_case'] = max(phases, key=lambda phase: phase['world_triangles_per_view_max'])
        runtime.report['worst_display_case'] = max(phases, key=lambda phase: phase['world_triangles_per_display_max'])
        runtime.report['worst_scene_view_case'] = max(phases, key=lambda phase: phase['scene_triangles_per_view_max'])
        runtime.report['worst_scene_display_case'] = max(phases, key=lambda phase: phase['scene_triangles_per_display_max'])
        runtime.report['scene_geometry_summary'] = {
            key: {'per_view_max': max(phase[f'{key}_per_view_max'] for phase in phases),
                  'per_display_max': max(phase[f'{key}_per_display_max'] for phase in phases)}
            for key in ('world_triangles', 'model_triangles', 'scene_triangles', 'draws')}
        runtime.report['viewweapon_enabled'] = bool(args.viewweapon)
        maximum_view = max(phase['world_triangles_per_view_max'] for phase in phases)
        maximum_display = max(phase['world_triangles_per_display_max'] for phase in phases)
        runtime.report['sampled_budget_comparison'] = {
            'policy': 'Advisory: camera coverage differs from the historical Temple samples; no universal worst-case or FPS claim.',
            'temple_reference_bsp_sha256': '726bee0ebcdcfbbd100cbb7d69ab16fd38614a5c0aa8cca1bcd4a02968cdbe70',
            'temple_sampled_view_max': 917, 'temple_sampled_four_view_max': 2019,
            'view_ceiling_7_over_6': 1069, 'four_view_ceiling_7_over_6': 2355,
            'observed_world_triangles_per_view_max': maximum_view,
            'observed_world_triangles_per_display_max': maximum_display,
            'within_sampled_view_ceiling': maximum_view <= 1069,
            'within_sampled_display_ceiling': maximum_display <= 2355 if args.players == 4 else None}
        if args.temple_reference.is_file():
            reference = json.loads(args.temple_reference.read_text())
            measured = reference['sampled_budget_comparison']
            view_baseline = measured['observed_world_triangles_per_view_max']
            display_baseline = measured['observed_world_triangles_per_display_max']
            view_limit, display_limit = math.floor(view_baseline*7/6), math.floor(display_baseline*7/6)
            runtime.report['current_temple_sampled_comparison'] = {
                'reference': str(args.temple_reference), 'reference_sha256': sha(args.temple_reference),
                'same_runtime_hashes': all(reference.get(key) == runtime.report.get(key)
                    for key in ('binary_sha256', 'renderer_sha256', 'game_sha256')),
                'same_viewweapon_setting': reference.get('viewweapon_enabled', False) == bool(args.viewweapon),
                'same_staged_art_archive': reference.get('staged_art_archive_sha256') == runtime.report['staged_art_archive_sha256'],
                'temple_view_max': view_baseline, 'temple_four_view_max': display_baseline,
                'view_ceiling_7_over_6': view_limit, 'four_view_ceiling_7_over_6': display_limit,
                'observed_view_max': maximum_view, 'observed_display_max': maximum_display,
                'within_view_ceiling': maximum_view <= view_limit,
                'within_display_ceiling': maximum_display <= display_limit if args.players == 4 else None,
                'policy': 'Sampled comparison only: same runtime/settings/yaw protocol, different level-specific sites; no universal worst-case claim.'}
            reference_scene = reference.get('scene_geometry_summary') or summary_from_csv(reference, args.temple_reference.parent)
            runtime.report['current_temple_scene_comparison'] = {
                key: {scope: {'temple': reference_scene[key][scope],
                              'actual': runtime.report['scene_geometry_summary'][key][scope],
                              'ceiling_7_over_6': math.floor(reference_scene[key][scope]*7/6),
                              'ratio': runtime.report['scene_geometry_summary'][key][scope]/reference_scene[key][scope]
                                       if reference_scene[key][scope] else None}
                      for scope in ('per_view_max', 'per_display_max')}
                for key in reference_scene}
        available = {path.relative_to(runtime.base).as_posix() for path in runtime.base.rglob('*') if path.is_file()}
        for path in runtime.base.glob('*.pk3'):
            with ZipFile(path) as archive:
                available.update(archive.namelist())
        runtime.report['runtime_diagnostics'] = diagnostics(runtime.console(), available)
        missing = runtime.report['runtime_diagnostics']['missing_resource_paths']
        runtime.check('no_missing_assets', not missing, missing=missing)
        runtime.report['passed'] = True
    except Exception as error:
        runtime.report['error'] = str(error)
        print('Runtime check failed: '+str(error), flush=True)
    finally:
        runtime.close()
    print(json.dumps({'passed': runtime.report['passed'], 'report': str(runtime.out/'run.json'),
                      'budget': runtime.report.get('sampled_budget_comparison')}, indent=2))
    return 0 if runtime.report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
