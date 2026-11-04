#!/usr/bin/env python3
"""Run bounded, fresh-config map captures using only this project's release.

Every map gets a new /tmp game directory. Stock PAKs, home assets, configuration,
saves, screenshots and previous performance captures are never copied. This is
a software-host load/render smoke check, not a gameplay or asset-rights review.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time
import zipfile

from audit_standalone import image_candidates

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPS = ('pp_sandbox1', 'pp_sandbox2', 'pp_sandbox_coop1', 'pp_heavy_test',
                'pp_rocket_test', 'pp_tank_test', 'pp_helicopter_test',
                'pp_bedroom', 'pp_sandkeep', 'pp_sandwatch')
ENVIRONMENT = {'SDL_VIDEODRIVER': 'offscreen', 'SDL_AUDIODRIVER': 'dummy',
               'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '2'}


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def release_files(release, renderers):
    """An allowlist prevents accidental use of saved config or stock archives."""
    required = [release / 'quake2', release / 'baseq2/game.so',
                release / 'baseq2/plastic-platoon.pk3',
                release / 'baseq2/tuning/default.json']
    required.extend(release / f'ref_{renderer}.so' for renderer in renderers)
    absent = [str(path) for path in required if not path.is_file()]
    if absent:
        raise ValueError('missing release inputs: ' + ', '.join(absent))
    optional = list(release.glob('ref_*.so')) + list((release / 'baseq2').glob('operation-*.pk3'))
    if (release / 'q2ded').is_file():
        optional.append(release / 'q2ded')
    files = sorted(set(required + optional))
    for path in files:
        if not path.resolve().is_relative_to(release.resolve()):
            raise ValueError(f'release input symlink escapes release: {path}')
    return files


def stage(release, files, target, hardlink=True):
    for source in files:
        destination = target / source.relative_to(release)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not hardlink:
            shutil.copy2(source, destination)
        else:
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)


def available_asset_names(release, files):
    names = set()
    for path in files:
        relative = path.relative_to(release).as_posix()
        if not relative.startswith('baseq2/'):
            continue
        relative = relative.removeprefix('baseq2/')
        if path.suffix.lower() == '.pk3':
            with zipfile.ZipFile(path) as archive:
                names.update(name for name in archive.namelist() if not name.endswith('/'))
        else:
            names.add(relative)
    return names


def diagnostics(log, available=None):
    """Keep unique exact resource messages and count repeated frame fallbacks."""
    missing, renderer, other, downloads = Counter(), Counter(), Counter(), Counter()
    resources = set()
    for line in log.splitlines():
        text = line.strip()
        if not text:
            continue
        download = re.search(r"couldn.t download (\S+) to ", text, re.I)
        if download:
            downloads[(download.group(1), text)] += 1
            continue
        if re.search(r'no such (?:oldframe|frame|thisframe|lastframe|skin)', text, re.I):
            renderer[text] += 1
            continue
        if (re.search(r"couldn.t load (?:sound/|models/|players/|sprites/|pics/|env/|textures/)", text, re.I)
                or re.search(r"couldn.t load [\w/.-]+\.wav", text, re.I)
                or 'Mod_LoadTexinfo:' in text and "Couldn't load" in text
                or re.search(r'\.(?:md2|sp2|bsp|pcx|png|tga|wal|wav) not found', text, re.I)):
            missing[text] += 1
            texture = re.search(r"Mod_LoadTexinfo: Couldn't load (\S+)", text)
            if texture:
                resources.add('textures/' + texture.group(1) + '.wal')
            else:
                path = re.search(r'((?:sound|models|players|sprites|pics|env|textures)/[^\s:]+)', text)
                if path:
                    resources.add(path.group(1))
                else:
                    sound = re.search(r"couldn.t load ([\w/.-]+\.wav)", text, re.I)
                    if sound:
                        resources.add('sound/' + sound.group(1))
            continue
        if re.search(r'couldn.t|failed|\bwarning\b|\berror\b|unknown command|not found|no ogg', text, re.I):
            other[text] += 1
    counted = lambda counter: [{'message': message, 'count': count}
                               for message, count in sorted(counter.items())]
    download_candidates = []
    for (reference, message), count in sorted(downloads.items()):
        candidates = image_candidates(reference)
        resolved = [candidate for candidate in candidates if available is not None and candidate in available]
        download_candidates.append({'reference': reference, 'message': message, 'count': count,
                                    'candidates': candidates, 'resolved_candidates': resolved,
                                    'actually_missing': not bool(resolved)})
    missing_downloads = {item['reference'] for item in download_candidates if item['actually_missing']}
    reported = resources | missing_downloads
    # The network downloader requests legacy PCX names even when the renderer
    # can load a PNG/TGA/JPG in the local PK3. Keep evidence of those requests,
    # but do not label the replacement-backed resources absent.
    actual = {reference for reference in reported if available is None
              or not any(candidate in available for candidate in image_candidates(reference))}
    return {'missing_resource_paths': sorted(actual),
            'reported_missing_resource_paths': sorted(resources),
            'actual_missing_download_paths': sorted(missing_downloads),
            'download_candidates': download_candidates,
            'missing_resource_messages': counted(missing),
            'renderer_warnings': counted(renderer),
            'other_warnings': counted(other)}


def read_settings(path):
    if not path.is_file():
        return {}
    return dict(re.findall(r'^([A-Za-z0-9_]+)=(.*)$', path.read_text(errors='replace'), re.M))


def frame_count(path):
    if not path.is_file():
        return 0
    with path.open(newline='') as source:
        return sum(int(row.get('views', '0')) > 0 for row in csv.DictReader(source))


def smoke_case(release, files, renderer, map_name, frames, timeout, artifacts, keep_screenshots, available):
    label = renderer + '-' + map_name
    result = {'renderer': renderer, 'requested_map': map_name, 'requested_frames': frames}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='pp-standalone-', dir='/tmp') as temporary:
        isolated = Path(temporary)
        stage(release, files, isolated)
        command = [str(isolated / 'quake2'), '-portable', '-datadir', str(isolated)]
        settings = [('vid_renderer', renderer), ('s_openal', '0'), ('developer', '1'),
                    ('logfile', '2'), ('r_mode', '0'), ('vid_fullscreen', '0'),
                    ('cl_perf_frames', str(frames)), ('cl_perf_quit', '1'),
                    ('cl_perf_screenshot', '1')]
        for key, value in settings:
            command.extend(('+set', key, value))
        command.extend(('+map', map_name, '+cl_perf_start', label))
        result['command'] = command
        result['fresh_data_directory'] = str(isolated)
        case_dir = artifacts / label
        case_dir.mkdir(parents=True, exist_ok=True)
        console = case_dir / 'console.log'
        result['console_log'] = str(console)
        try:
            with console.open('w') as output:
                process = subprocess.Popen(command, cwd=isolated, env={**os.environ, **ENVIRONMENT},
                                           stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    result['returncode'] = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    result['timed_out'] = True
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        result['returncode'] = process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        result['returncode'] = process.wait()
        except OSError as error:
            result['launch_error'] = str(error)
            result['returncode'] = None
        log = console.read_text(errors='replace')
        result['console_sha256'] = digest(console)
        result.update(diagnostics(log, available))
        perf = isolated / 'baseq2/perf'
        captured_settings = read_settings(perf / (label + '-settings.txt'))
        result['captured_settings'] = captured_settings
        result['actual_map'] = captured_settings.get('map')
        result['actual_renderer'] = captured_settings.get('vid_renderer')
        result['rendering_backends_loaded'] = re.findall(r'Successfully loaded (ref_\w+\.so) as rendering backend', log)
        try:
            result['actual_complete_frames'] = frame_count(perf / (label + '-frames.csv'))
        except (ValueError, OSError, csv.Error) as error:
            result['capture_error'] = str(error)
            result['actual_complete_frames'] = 0
        stopped = re.findall(r'Performance capture stopped: (\d+) complete frames', log)
        result['console_complete_frames'] = int(stopped[-1]) if stopped else None
        result['gl_info'] = dict(re.findall(r'^(GL_VENDOR|GL_RENDERER|GL_VERSION): (.*)$', log, re.M))
        result['artifacts'] = []
        for suffix in ('-settings.txt', '-frames.csv', '-views.csv'):
            path = perf / (label + suffix)
            if path.is_file():
                destination = case_dir / path.name
                shutil.copy2(path, destination)
                result['artifacts'].append({'path': str(destination), 'sha256': digest(destination)})
        screenshots = sorted((isolated / 'baseq2/scrnshot').glob('*'))
        result['screenshots_generated'] = len(screenshots)
        if keep_screenshots:
            for screenshot in screenshots:
                if not screenshot.is_file():
                    continue
                destination = case_dir / screenshot.name
                shutil.copy2(screenshot, destination)
                result['artifacts'].append({'path': str(destination), 'sha256': digest(destination)})
        result['passed'] = (result['returncode'] == 0 and not result.get('timed_out')
                            and result['actual_map'] == f'maps/{map_name}.bsp'
                            and result['actual_renderer'] == renderer
                            and result['rendering_backends_loaded'][-1:] == [f'ref_{renderer}.so']
                            and result['actual_complete_frames'] == frames)
        result['seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, default=ROOT / 'release')
    parser.add_argument('--renderer', action='append', choices=('gl3', 'gl1', 'soft'), help='repeatable; default gl3')
    parser.add_argument('--map', action='append', dest='maps', help='repeatable; default all ten project maps')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=90, help='seconds per map')
    parser.add_argument('--output-dir', type=Path, help='retain report, logs, CSVs and screenshots here; otherwise retain report/logs/CSVs in a new /tmp directory')
    args = parser.parse_args()
    maps = list(dict.fromkeys(args.maps or DEFAULT_MAPS))
    renderers = list(dict.fromkeys(args.renderer or ('gl3',)))
    if args.frames <= 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('frames and timeout must be positive')
    for map_name in maps:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,55}', map_name):
            parser.error(f'invalid map name: {map_name!r}')
    release = args.release.resolve()
    try:
        files = release_files(release, renderers)
    except ValueError as error:
        parser.error(str(error))
    artifacts = (args.output_dir.resolve() if args.output_dir else
                 Path(tempfile.mkdtemp(prefix='pp-smoke-results-', dir='/tmp')))
    artifacts.mkdir(parents=True, exist_ok=True)
    report_path = artifacts / 'standalone-smoke.json'
    # Take one byte snapshot for the whole sweep. Subsequent builds of release/
    # cannot silently change the version used by later maps or invalidate hashes.
    with tempfile.TemporaryDirectory(prefix='pp-smoke-inputs-', dir='/tmp') as temporary:
        snapshot = Path(temporary)
        stage(release, files, snapshot, hardlink=False)
        files = [snapshot / path.relative_to(release) for path in files]
        available = available_asset_names(snapshot, files)
        report = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'release': str(release), 'host': platform.platform(),
                  'environment': ENVIRONMENT, 'report': str(report_path),
                  'scope': 'Fresh configuration, isolated project-only data, fixed-camera software-host map load/render checks; no stock PAKs or home assets. All maps use one initial byte snapshot. Warnings do not fail a completed capture. This does not verify combat, all dynamic sounds, performance on target hardware, or redistribution rights.',
                  'inputs': [{'path': path.relative_to(snapshot).as_posix(), 'bytes': path.stat().st_size,
                              'sha256': digest(path)} for path in files],
                  'available_asset_paths': len(available), 'cases': []}
        for renderer in renderers:
            for map_name in maps:
                result = smoke_case(snapshot, files, renderer, map_name, args.frames, args.timeout,
                                    artifacts, args.output_dir is not None, available)
                report['cases'].append(result)
                report['passed'] = all(case['passed'] for case in report['cases'])
                report['missing_resource_paths'] = sorted({name for case in report['cases']
                                                           for name in case['missing_resource_paths']})
                report['actual_missing_download_paths'] = sorted({name for case in report['cases']
                                                                  for name in case['actual_missing_download_paths']})
                report['replacement_backed_download_paths'] = sorted({item['reference'] for case in report['cases']
                                                                      for item in case['download_candidates']
                                                                      if item['resolved_candidates']})
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                print(f'{renderer} {map_name}: {"PASS" if result["passed"] else "FAIL"}, '
                      f'{result["actual_complete_frames"]}/{args.frames} frames, '
                      f'{len(result["missing_resource_paths"])} missing resources, '
                      f'exit {result["returncode"]}', flush=True)
    print(f'Report: {report_path}', flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
