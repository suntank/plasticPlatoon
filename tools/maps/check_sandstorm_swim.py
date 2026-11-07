#!/usr/bin/env python3
"""Check the deep-pool dive, pickup and exit in an isolated real engine.

Only the initial poses are teleported. The dive and swim to dry ground use
normal player movement. The capture harness preserves user settings and saves.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WATER = 32  # CONTENTS_WATER in the Q2 BSP format


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bsp', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--renderer', choices=('gl1', 'gl3'), default='gl3')
    args = parser.parse_args()
    output = ROOT/'build/sandstorm-qa'/args.label
    subprocess.run([sys.executable, str(ROOT/'tools/maps/capture_sandkeep.py'),
                    '--map-name', 'pp_sandstorm', '--map', str(args.bsp),
                    '--materials', str(ROOT/'baseq2'), '--assets', str(ROOT/'baseq2'),
                    '--renderer', args.renderer, '--label', args.label,
                    '--output-root', str(output.parent),
                    '--views', str(ROOT/'tools/maps/sandstorm_swim.json')], check=True)
    report = json.loads((output/'run.json').read_text())
    views = {v['name']: v for v in report['views']}
    assert report.get('complete'), 'Engine capture did not complete'
    dive = views['pool_dive_and_armor']
    end = views['pool_swim_exit']
    assert dive['actual_eye_world_contents'] & WATER, 'Dive did not reach the water volume'
    assert not end['actual_eye_world_contents'] & WATER, 'Exit camera remains underwater'

    # listentities reports server-side entities. The armor is a finite pickup:
    # it must exist before the dive and disappear after being collected.
    log = (output/'qconsole.log').read_text(errors='replace')
    snapshots = re.split(r'^rcon .*? listentities items\s*$', log, flags=re.MULTILINE)
    assert len(snapshots) >= 3, 'Missing before/after item listings'
    armor = re.compile(r'^item_armor_jacket:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', re.MULTILINE)
    def pool_armor(section):
        return [tuple(map(float, match.groups())) for match in armor.finditer(section)
                if abs(float(match.group(1))) < 20 and -175 < float(match.group(2)) < -130
                and float(match.group(3)) < -30]
    before, after = pool_armor(snapshots[1]), pool_armor(snapshots[2])
    assert len(before) == 1, f'Expected the pool armor before the dive, found {before}'
    assert not after, f'Pool armor remains after the dive: {after}'
    print(json.dumps({'passed': True, 'bsp_sha256': report['map_sha256'],
                      'dive_eye': dive['actual_eye_pose'], 'exit_eye': end['actual_eye_pose'],
                      'pickup_before': before[0], 'pickup_after': after}, indent=2))


if __name__ == '__main__':
    main()
