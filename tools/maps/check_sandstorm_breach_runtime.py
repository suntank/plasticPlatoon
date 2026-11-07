#!/usr/bin/env python3
"""Verify both co-op reinforcement orders in the real game engine.

This is a cheat-assisted integration check, not a combat playthrough. It uses
the existing isolated capture harness, including its temporary runtime and
local-only RCON. Both views and the engine's entity snapshots are checked.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from verify_sandkeep import parse_entities, vec

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / 'build/sandstorm-qa'
ENTITY_LINE = re.compile(r'monster_soldier_ss:\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)')
DEATH = re.compile(r'(?m)^Player(?: P2)? (?:died\.|was squished|blew up|was in the wrong place|tried to invade)')


def soldier_positions():
    source = parse_entities((ROOT / 'maps/source/pp_sandstorm.map').read_text())
    result = {}
    for event in ('breach_alarm', 'yard_reinforcements'):
        result[event] = [vec(e['keys']['origin']) for e in source
                         if e['keys']['classname'] == 'monster_soldier_ss'
                         and e['keys'].get('targetname') == event]
        if len(result[event]) != 4:
            raise AssertionError(f'Expected four soldiers for {event}, found {len(result[event])}')
    return result


def assert_slot_alive(folder, view, *, x=None, y=None):
    path = folder / 'poses' / ('qa_' + view + '-views.csv')
    with path.open(newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if r.get('slot') == '1']
    if not rows:
        raise AssertionError(f'{view}: no camera evidence for player 2')
    eye = tuple(float(rows[-1][k]) for k in ('x', 'y', 'z'))
    # Dead players' camera drops; all intended checkpoints stand above z=40.
    if not 40 <= eye[2] <= 90:
        raise AssertionError(f'{view}: player 2 camera is not standing: {eye}')
    if x is not None and abs(eye[0] - x) > 3:
        raise AssertionError(f'{view}: player 2 x position differs: {eye}')
    if y is not None and abs(eye[1] - y) > 3:
        raise AssertionError(f'{view}: player 2 y position differs: {eye}')


def entity_snapshots(log):
    chunks = re.split(r'rcon LOCAL_RCON_TOKEN listentities monsters', log)[1:]
    return [[tuple(map(float, match)) for match in ENTITY_LINE.findall(chunk)] for chunk in chunks]


def assert_squad(snapshot, origins, *, active, label):
    for origin in origins:
        matches = [p for p in snapshot if abs(p[0]-origin[0]) < .12 and abs(p[1]-origin[1]) < .12]
        if len(matches) != 1:
            raise AssertionError(f'{label}: expected one soldier at {origin[:2]}, got {matches}')
        # Triggered monsters start at exactly their authored origin. The real
        # spawn callback raises them one unit, and gravity settles them on the
        # floor at origin+1/32. The harness keeps them stationary with notarget.
        delta = matches[0][2] - origin[2]
        if active and not .015 < delta < 2:
            raise AssertionError(f'{label}: soldier was not activated: {matches[0]}')
        if not active and abs(delta) >= .015:
            raise AssertionError(f'{label}: soldier should remain dormant: {matches[0]}')


def assert_door_positions(report, names):
    views = {v['name']: v for v in report['views']}
    for name, opened in names.items():
        eye = views[name].get('actual_eye_pose')
        if not eye:
            raise AssertionError(f'{name}: missing measured player position')
        # Starting y=586 approaches the north-facing door. A closed door stops
        # the hull at about 586; an open door lets it proceed to about 630.
        if opened and not 605 <= eye['y'] <= 655:
            raise AssertionError(f'{name}: door did not open: {eye}')
        if not opened and not 580 <= eye['y'] <= 595:
            raise AssertionError(f'{name}: door was not closed: {eye}')


def audit(folder, bsp_hash, positions, loud):
    report = json.loads((folder / 'run.json').read_text())
    if not report.get('complete') or report.get('map_sha256') != bsp_hash:
        raise AssertionError(f'{folder.name}: capture failed or used the wrong BSP: {report.get("validation_errors")}')
    log = (folder / 'qconsole.log').read_text(errors='replace')
    deaths = DEATH.findall(log)
    if deaths:
        raise AssertionError(f'{folder.name}: a player died: {deaths}')
    views = {v['name']: v for v in report['views']}
    snapshots = entity_snapshots(log)
    needed = 3
    if len(snapshots) != needed:
        raise AssertionError(f'{folder.name}: expected {needed} monster snapshots, got {len(snapshots)}')
    for event in positions:
        assert_squad(snapshots[0], positions[event], active=False, label=f'{folder.name} before {event}')
    if loud:
        if 'BREACH CHARGE PLANTED' not in log or 'COMPOUND ALERT' not in log:
            raise AssertionError('Loud run did not reach both event messages')
        assert_squad(snapshots[1], positions['breach_alarm'], active=True, label='loud breach response')
        assert_squad(snapshots[1], positions['yard_reinforcements'], active=False, label='loud yard still dormant')
        for event in positions:
            assert_squad(snapshots[2], positions[event], active=True, label=f'loud after yard: {event}')
        assert_door_positions(report, {'loud_outer_west_open': True, 'loud_outer_east_open': True,
                                       'loud_inner_west_closed': False, 'loud_inner_east_closed': False,
                                       'loud_inner_west_open': True, 'loud_inner_east_open': True})
        if not -820 <= views['loud_wall_open']['actual_eye_pose']['y'] <= -520:
            raise AssertionError('Player did not walk through the demolished breach')
        assert_slot_alive(folder, 'loud_charge_armed', x=0, y=-881)
        for checkpoint in ('loud_inner_east_closed', 'second_wave_other_player_in_open_bay',
                           'loud_inner_east_open'):
            assert_slot_alive(folder, checkpoint, x=-859.2, y=750)
    else:
        before_breach = re.split(r'rcon LOCAL_RCON_TOKEN listentities monsters', log)[1]
        if 'COMPOUND ALERT' not in log or 'BREACH CHARGE PLANTED' in before_breach:
            raise AssertionError('The courtyard response triggered the loud breach prematurely')
        if 'BREACH CHARGE PLANTED' not in log:
            raise AssertionError('The subsequent deliberate breach did not arm')
        assert_squad(snapshots[1], positions['yard_reinforcements'], active=True, label='quiet yard response')
        assert_squad(snapshots[1], positions['breach_alarm'], active=False, label='quiet breach still dormant')
        for event in positions:
            assert_squad(snapshots[2], positions[event], active=True, label=f'quiet after breach: {event}')
        assert_door_positions(report, {'quiet_outer_west_closed': False, 'quiet_outer_east_closed': False,
                                       'quiet_inner_west_open': True, 'quiet_inner_east_open': True,
                                       'quiet_outer_west_open_after': True, 'quiet_outer_east_open_after': True})
        assert_slot_alive(folder, 'quiet_alert')
        assert_slot_alive(folder, 'quiet_inner_east_open')
        assert_slot_alive(folder, 'quiet_outer_east_open_after')
    return {'passed': True, 'map_sha256': bsp_hash, 'folder': str(folder),
            'event_order': 'breach then yard' if loud else 'yard then breach'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp', required=True, type=Path)
    parser.add_argument('--label', required=True, help='Fresh, simple label for both output folders')
    parser.add_argument('--renderer', choices=('gl1', 'gl3'), default='gl1')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,40}', args.label):
        parser.error('label must contain only letters, digits, underscores or hyphens')
    if not args.bsp.is_file():
        parser.error('BSP does not exist')
    bsp_hash = hashlib.sha256(args.bsp.read_bytes()).hexdigest()
    positions = soldier_positions()
    results = []
    for mode in ('quiet', 'loud'):
        label = args.label + '_' + mode
        folder = QA / label
        if folder.exists():
            parser.error(f'output folder already exists: {folder}')
        subprocess.run([sys.executable, str(ROOT / 'tools/maps/capture_sandkeep.py'),
                        '--label', label, '--map-name', 'pp_sandstorm', '--map', str(args.bsp),
                        '--materials', str(ROOT / 'baseq2'), '--assets', str(ROOT / 'baseq2'),
                        '--views', str(ROOT / f'tools/maps/sandstorm_breach_{mode}.json'),
                        '--output-root', str(QA), '--players', '2', '--renderer', args.renderer], check=True)
        results.append(audit(folder, bsp_hash, positions, loud=mode == 'loud'))
    print(json.dumps({'passed': True, 'checks': results}, indent=2))


if __name__ == '__main__':
    main()
