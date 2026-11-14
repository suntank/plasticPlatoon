#!/usr/bin/env python3
"""Analyze isolated run_pi_suite.py output trees without modifying captures.

Examples:
  python3 tools/performance/analyze_pi_four_player.py build/pi-results
  python3 tools/performance/analyze_pi_four_player.py build/pi-results --output report.json
  python3 tools/performance/analyze_pi_four_player.py build/pi-results --output report.md --json report.json

Frame timing is for the complete display. Screenshots taken by the suite before
cl_perf_start are outside these CSV intervals. CPU phase times can be nested;
they must not be added to estimate frame time.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import re
import statistics
import sys


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def values(rows, key, positive=False):
    result = [number(row.get(key)) for row in rows]
    return [value for value in result if value is not None and
            (value > 0 if positive else value >= 0)]


def percentile(data, fraction):
    if not data:
        return None
    ordered = sorted(data)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def stats(data):
    if not data:
        return None
    return dict(mean=statistics.mean(data), median=statistics.median(data),
                p95=percentile(data, .95), p99=percentile(data, .99),
                minimum=min(data), maximum=max(data))


def read_json(path, fallback, warnings):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        warnings.append(f'{path}: {error}')
        return fallback


def read_csv(path, warnings):
    try:
        with path.open(newline='') as stream:
            return list(csv.DictReader(stream))
    except (OSError, csv.Error) as error:
        warnings.append(f'{path}: {error}')
        return []


def read_text(path):
    try:
        return path.read_text(errors='replace')
    except OSError:
        return ''


def kib_field(text, key):
    match = re.search(r'^' + re.escape(key) + r':\s*(\d+)\s+kB\s*$', text, re.M)
    return int(match[1]) if match else None


def vm_counter(text, key):
    match = re.search(r'^' + re.escape(key) + r'\s+(\d+)\s*$', text, re.M)
    return int(match[1]) if match else None


def process_accounting(text):
    # comm (field 2) can itself contain spaces and parentheses. The final ')'
    # terminates it; the remaining fields start at state (field 3).
    try:
        prefix, tail = text.rsplit(')', 1)
        fields = tail.split()
        pid = int(prefix.split('(', 1)[0].strip())
        result = dict(pid=pid, start_ticks=int(fields[19]),
                      cpu_ticks=int(fields[11]) + int(fields[12]),
                      minor_faults=int(fields[7]), major_faults=int(fields[9]))
        return result if pid > 0 and all(value >= 0 for value in result.values()) else None
    except (ValueError, IndexError):
        return None


def process_ticks(text):
    reading = process_accounting(text)
    return (reading['pid'], reading['start_ticks'], reading['cpu_ticks']) if reading else None


def telemetry_summary(samples, clock_ticks=None):
    available, swap, rss, temps, clocks, flags, cpu_samples = [], [], [], [], [], [], []
    swap_samples, fault_samples = [], []
    vm_samples = {key: [] for key in ('pswpin', 'pswpout', 'oom_kill', 'pgmajfault')}
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        mem = kib_field(str(sample.get('mem', '')), 'MemAvailable')
        process_swap = kib_field(str(sample.get('status', '')), 'VmSwap')
        process_rss = kib_field(str(sample.get('status', '')), 'VmRSS')
        if mem is not None:
            available.append(mem / 1024)
        if process_swap is not None:
            swap.append(process_swap / 1024)
        if process_rss is not None:
            rss.append(process_rss / 1024)
        match = re.search(r'temp=([\d.]+)', str(sample.get('temp', '')))
        if match and number(match[1]) is not None:
            temps.append(float(match[1]))
        match = re.search(r'throttled=(0x[\da-fA-F]+)', str(sample.get('throttled', '')))
        if match:
            flags.append(int(match[1], 16))
        clock = number(sample.get('cpu_khz'))
        if clock is not None:
            clocks.append(clock / 1000)
        timestamp = number(sample.get('time'))
        accounting = process_accounting(str(sample.get('proc_stat', '')))
        if process_swap is not None and timestamp is not None:
            identity = (accounting['pid'], accounting['start_ticks']) if accounting else None
            swap_samples.append((timestamp, process_swap / 1024, identity))
        for key in vm_samples:
            value = vm_counter(str(sample.get('vm', '')), key)
            if value is not None and timestamp is not None:
                vm_samples[key].append((timestamp, value))
        if timestamp is not None and accounting is not None:
            cpu_samples.append((timestamp, (accounting['pid'], accounting['start_ticks'], accounting['cpu_ticks'])))
            fault_samples.append((timestamp, accounting))
    combined = 0
    for flag in flags:
        combined |= flag
    deltas, intervals, regressions = {}, {}, []
    for key, readings in vm_samples.items():
        readings.sort()
        valid = len(readings) >= 2 and readings[-1][0] > readings[0][0]
        regression = any(right[1] < left[1] for left, right in zip(readings, readings[1:]))
        if regression:
            regressions.append(key)
        deltas[key] = readings[-1][1] - readings[0][1] if valid and not regression else None
        intervals[key] = readings[-1][0] - readings[0][0] if valid else None
    cpu_samples.sort()
    swap_samples.sort(key=lambda item: item[0])
    fault_samples.sort(key=lambda item: item[0])
    process_faults = {}
    for key in ('minor_faults', 'major_faults'):
        total, observed, valid_intervals, skipped, regressed = 0, 0, 0, 0, 0
        for (before_time, before), (after_time, after) in zip(fault_samples, fault_samples[1:]):
            if (before['pid'], before['start_ticks']) != (after['pid'], after['start_ticks']) or after_time <= before_time:
                skipped += 1
                continue
            if after[key] < before[key]:
                regressed += 1
                continue
            total += after[key] - before[key]
            observed += after_time - before_time
            valid_intervals += 1
        process_faults[key] = dict(delta=total if valid_intervals else None,
                                  observed_wall_seconds=observed if valid_intervals else None,
                                  valid_intervals=valid_intervals, skipped_identity_or_time_intervals=skipped,
                                  counter_regressions=regressed)
    swap_delta = (swap_samples[-1][1] - swap_samples[0][1]
                  if len(swap_samples) >= 2 and swap_samples[-1][0] > swap_samples[0][0]
                  and swap_samples[0][2] is not None
                  and all(sample[2] == swap_samples[0][2] for sample in swap_samples) else None)
    swap_io = [deltas[key] for key in ('pswpin', 'pswpout')]
    swap_io_observed = (True if any(value is not None and value > 0 for value in swap_io)
                        else False if all(value is not None for value in swap_io) else None)
    cpu_percentages, cpu_seconds, cpu_wall = [], 0, 0
    if clock_ticks is not None:
        for (previous_time, previous), (current_time, current) in zip(cpu_samples, cpu_samples[1:]):
            elapsed = current_time - previous_time
            delta = current[2] - previous[2]
            # Only join samples from the same PID and start time. CPU accounting
            # resets and a restarted process must never create a negative load.
            if previous[:2] != current[:2] or elapsed <= 0 or delta < 0:
                continue
            seconds = delta / clock_ticks
            cpu_seconds += seconds
            cpu_wall += elapsed
            cpu_percentages.append(100 * seconds / elapsed)
    return dict(samples=len(samples),
                memory_available_min_mib=min(available) if available else None,
                process_swap_max_mib=max(swap) if swap else None,
                process_swap_min_mib=min(swap) if swap else None,
                process_swap_first_mib=swap_samples[0][1] if swap_samples else None,
                process_swap_last_mib=swap_samples[-1][1] if swap_samples else None,
                process_swap_delta_mib=swap_delta,
                process_rss_max_mib=max(rss) if rss else None,
                temperature_max_c=max(temps) if temps else None,
                temperature_min_c=min(temps) if temps else None,
                cpu_min_mhz=min(clocks) if clocks else None,
                cpu_max_mhz=max(clocks) if clocks else None,
                throttled_samples=len(flags),
                throttled_flags_observed=[hex(flag) for flag in sorted(set(flags))],
                throttled_flags_or=hex(combined) if flags else None,
                current_throttle_or_undervoltage=bool(combined & 0xf) if flags else None,
                historical_throttle_or_undervoltage=bool(combined & 0xf0000) if flags else None,
                system_vm_counter_deltas=dict(pswpin_pages=deltas['pswpin'],
                    pswpout_pages=deltas['pswpout'], oom_kills=deltas['oom_kill'],
                    major_faults=deltas['pgmajfault']),
                system_vm_counter_observed_seconds=intervals,
                system_vm_counter_regressions=regressions,
                process_page_faults=dict(accounting='Own process minflt/majflt, excluding child counters; only increasing-time samples with the same PID and starttime are joined.',
                    **process_faults),
                resource_flags=dict(process_has_swapped_pages=max(swap) > 0 if swap else None,
                    process_swap_grew=swap_delta > 0 if swap_delta is not None else None,
                    system_swap_io_observed=swap_io_observed,
                    process_major_faults_observed=(process_faults['major_faults']['delta'] > 0
                        if process_faults['major_faults']['delta'] is not None else None),
                    system_major_faults_observed=deltas['pgmajfault'] > 0 if deltas['pgmajfault'] is not None else None,
                    oom_kills_observed=deltas['oom_kill'] > 0 if deltas['oom_kill'] is not None else None,
                    current_throttle_or_undervoltage=bool(combined & 0xf) if flags else None),
                resource_limits='System VM counters include other processes. Process VmSwap includes cold swapped pages and does not establish active stalls. Major faults include file-backed paging, not only swap. Sample windows and peaks need not cover the full capture; no CPU/GPU-exclusive bottleneck is inferred.',
                process_cpu=dict(clock_ticks_per_second=clock_ticks,
                    clock_ticks_source='explicit --clock-ticks argument' if clock_ticks is not None else 'unavailable; not assumed from analysis host',
                    accounting='100 percent is one fully occupied CPU core; utime + stime, excluding child processes',
                    interval_samples=len(cpu_percentages), observed_wall_seconds=cpu_wall,
                    cpu_seconds=cpu_seconds if cpu_percentages else None,
                    mean_percent_of_one_core=100 * cpu_seconds / cpu_wall if cpu_wall else None,
                    interval_percent_of_one_core=stats(cpu_percentages)))


def settings_from(path):
    settings = {}
    for line in read_text(path).splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', key):
                settings[key] = value.strip()
    return settings


def driver_state_summary(text):
    def reject_constant(value):
        raise ValueError(f'non-finite JSON number {value}')

    decoder = json.JSONDecoder(parse_constant=reject_constant)
    snapshots, malformed = [], []
    for match in re.finditer(r'PP_TEST_STATE\s*', text):
        line = text.count('\n', 0, match.start()) + 1
        try:
            payload, _ = decoder.raw_decode(text[match.end():].lstrip())
            if not isinstance(payload, dict) or not isinstance(payload.get('slots'), list):
                raise ValueError('expected an object with a slots list')
            slots = payload['slots']
            indices = [slot.get('slot') for slot in slots if isinstance(slot, dict)]
            all_four = len(slots) == 4 and sorted(indices) == [0, 1, 2, 3]
            # ca_active is enum value 4 in this instrumented engine. Requiring
            # explicit 0/1 fields avoids treating missing values or -1 as ready.
            ready = all_four and all(slot.get('active') == 1 and
                slot.get('device_connected') == 1 and slot.get('menu_open') == 0 and
                (number(slot.get('connection')) or 0) >= 4 and
                slot.get('snapshot') == 1 for slot in slots)
            attack_commands = all_four and all(isinstance(slot.get('cmd_buttons'), int) and
                bool(slot['cmd_buttons'] & 1) for slot in slots)
            attack_held = all_four and all(slot.get('attack_down') == 1 for slot in slots)
            snapshots.append(dict(line=line, state=payload, all_four_ready=ready,
                all_four_attack_cmd=attack_commands, all_four_attack_held=attack_held))
        except (ValueError, TypeError) as error:
            malformed.append(dict(line=line, error=str(error),
                text=text[match.end():].split('\n', 1)[0][:240]))
    return dict(state_snapshots=snapshots, state_snapshot_count=len(snapshots),
                state_snapshot_parse_errors=malformed,
                all_four_ready_snapshots=sum(snapshot['all_four_ready'] for snapshot in snapshots),
                all_four_attack_cmd_snapshots=sum(snapshot['all_four_attack_cmd'] for snapshot in snapshots),
                all_four_attack_held_snapshots=sum(snapshot['all_four_attack_held'] for snapshot in snapshots),
                all_four_ready_and_attack_cmd_snapshots=sum(snapshot['all_four_ready'] and
                    snapshot['all_four_attack_cmd'] for snapshot in snapshots),
                virtual_pad_counts_observed=sorted({snapshot['state']['virtual_pads'] for snapshot in snapshots
                    if isinstance(snapshot['state'].get('virtual_pads'), int)}))


def log_summary(path):
    text = read_text(path)
    lines = text.splitlines()
    pattern = re.compile(r'PP_TEST_ERROR|EGL_BAD_[A-Z_]+|EGL_NOT_INITIALIZED|\b(error|fatal|failed|failure|out of memory|oom|overflow|no free edicts)\b', re.I)
    errors = Counter(line.strip() for line in lines if pattern.search(line))
    driver_errors = Counter(line.strip() for line in lines if 'PP_TEST_ERROR' in line)
    backend = [line.strip() for line in lines if re.search(
        r'GL_(VENDOR|RENDERER|VERSION)|SDL.*(video|driver)|OpenGL.*(version|renderer)|Broadcom|VC4|llvmpipe|softpipe',
        line, re.I)]
    return dict(path=str(path), error_like_lines=[dict(line=line, count=count)
                for line, count in errors.items()], error_like_count=sum(errors.values()),
                driver_ready='PP_TEST_READY' in text,
                driver_error_lines=[dict(line=line, count=count) for line, count in driver_errors.items()],
                driver_error_count=sum(driver_errors.values()),
                backend_lines=list(dict.fromkeys(backend)), **driver_state_summary(text))


def analyze_capture(path, session, plan, warmup, clock_ticks=None):
    warnings = []
    label = path.name[:-len('-frames.csv')]
    session_dir = path.parents[3]
    all_rows = read_csv(path, warnings)
    rows = [row for row in all_rows[warmup:] if (number(row.get('frame_ms')) or 0) > 0]
    frame_ids = {row.get('frame') for row in rows}
    all_views = read_csv(path.with_name(label + '-views.csv'), warnings)
    views = [view for view in all_views if view.get('frame') in frame_ids]
    view_counts = Counter(view.get('frame') for view in views)
    settings = settings_from(path.with_name(label + '-settings.txt'))
    telemetry = read_json(session_dir / (label + '-telemetry.json'), [], warnings)
    if not isinstance(telemetry, list):
        warnings.append('Telemetry JSON is not a list')
        telemetry = []
    expected_players = session.get('players', plan.get('players'))
    expected_map = session.get('map', plan.get('map'))
    dm = bool(plan.get('dm', False))
    expected_modes = dict(coop=0 if dm or expected_players == 1 else 1,
                          deathmatch=int(dm), maxclients=expected_players,
                          ss_players=expected_players if expected_players != 1 else 0)
    mode_checks = {key: number(settings.get(key)) == value
                   for key, value in expected_modes.items() if value is not None}
    if expected_players == 1:
        mode_checks.pop('ss_players', None)
    if expected_map:
        mode_checks['map'] = settings.get('map') == f'maps/{expected_map}.bsp'
    if not rows:
        warnings.append('No positive complete-frame intervals remain after warmup')
    dimensions = sorted({(view.get('slot'), view.get('width'), view.get('height')) for view in views})
    observed_counts = sorted(set(values(rows, 'views')))
    incomplete = sum(view_counts[frame] != expected_players for frame in frame_ids) if expected_players else None
    if incomplete:
        warnings.append(f'{incomplete} timed frames have an unexpected number of view rows')
    if any(not match for match in mode_checks.values()):
        warnings.append('Actual settings do not match all requested mode checks')
    times = values(rows, 'frame_ms', positive=True)
    rss = values(rows, 'rss_kib')
    metrics = {key: stats(values(rows, key)) for key in (
        'server_ms', 'simulation_ms', 'snapshot_send_ms', 'client_update_ms',
        'prepare_ms', 'submit_ms', 'present_ms', 'cpu_ms', 'visibility_ms', 'model_ms',
        'draws', 'world_triangles', 'model_triangles', 'lightmap_bytes', 'server_edicts',
        'monsters', 'dead_monsters', 'active_particles', 'prepared_particles',
        'particles_created', 'projectiles_by_effect')}
    metrics = {key: value for key, value in metrics.items() if value is not None}
    return dict(capture=f'{session_dir.name}/{label}', source=str(path),
                requested_map=expected_map, requested_players=expected_players,
                requested_mode='deathmatch' if dm else 'coop' if expected_players and expected_players > 1 else 'singleplayer',
                total_frames=len(all_rows), warmup_frames_excluded=min(warmup, len(all_rows)),
                timed_frames=len(rows), excluded_nonpositive_or_invalid_intervals=len(all_rows[warmup:]) - len(rows),
                elapsed_timed_seconds=sum(times) / 1000,
                throughput_fps=1000 / statistics.mean(times) if times else None,
                frame_ms=stats(times),
                over_33_333_ms_percent=100 * sum(value > 1000 / 30 for value in times) / len(times) if times else None,
                over_50_ms_percent=100 * sum(value > 50 for value in times) / len(times) if times else None,
                rss_peak_mib=max(rss) / 1024 if rss else None,
                total_view_rows=len(all_views), timed_view_rows=len(views),
                complete_timed_view_frames=len(frame_ids) - incomplete if incomplete is not None else None,
                unexpected_view_row_frames=incomplete, observed_views_per_frame=observed_counts,
                framebuffers=sorted({(row.get('width'), row.get('height')) for row in rows}),
                viewports=[dict(slot=slot, width=width, height=height) for slot, width, height in dimensions],
                submitted_particles_max=max(values(views, 'particles'), default=None),
                submitted_lights_max=max(values(views, 'lights'), default=None),
                settings=settings, mode_checks=mode_checks,
                actual_modes_match_requested=all(mode_checks.values()) if mode_checks else None,
                metrics=metrics, telemetry=telemetry_summary(telemetry, clock_ticks), warnings=warnings)


def analyze_root(root, warmup, clock_ticks=None):
    warnings = []
    metadata = read_json(root / 'metadata.json', {}, warnings)
    plan = read_json(root / 'plan.json', [], warnings)
    if not isinstance(metadata, dict):
        metadata = {}
        warnings.append('Metadata JSON is not an object')
    if not isinstance(plan, list):
        plan = []
        warnings.append('Plan JSON is not a list')
    sessions = {session['label']: session for session in metadata.get('sessions', [])
                if isinstance(session, dict) and isinstance(session.get('label'), str)}
    plans = {session['label']: session for session in plan
             if isinstance(session, dict) and isinstance(session.get('label'), str)}
    captures, logs = [], {}
    # The copied runtime may contain historic captures. Only suite session save
    # directories belong to this run; never recursively include runtime/baseq2.
    for path in sorted(root.glob('*/saves/baseq2/perf/*-frames.csv')):
        session_dir = path.parents[3]
        captures.append(analyze_capture(path, sessions.get(session_dir.name, {}),
                                        plans.get(session_dir.name, {}), warmup, clock_ticks))
        if session_dir.name not in logs:
            logs[session_dir.name] = log_summary(session_dir / 'engine.log')
    # Context/startup failures can leave a log before the first capture exists.
    # Include these attempted sessions rather than silently dropping failures.
    for label in sorted(sessions):
        if Path(label).name != label or label in ('.', '..'):
            warnings.append(f'Ignoring invalid session directory label: {label!r}')
            continue
        log_path = root / label / 'engine.log'
        if label not in logs and log_path.is_file():
            logs[label] = log_summary(log_path)
    capture_counts = Counter(capture['capture'].split('/', 1)[0] for capture in captures)
    for label, log in logs.items():
        log['capture_count'] = capture_counts[label]
        log['no_frame_captures'] = not capture_counts[label]
    return dict(root=str(root), system=metadata.get('system'), device=metadata.get('device'),
                started=metadata.get('started'), ended=metadata.get('ended'),
                run_error=metadata.get('error'), shell_restored=metadata.get('shell_restored'),
                save_hashes_unchanged=metadata.get('save_hashes_unchanged'),
                package_hashes_unchanged=metadata.get('package_hashes_unchanged'),
                session_count=len(set(sessions) | set(logs)), logged_session_count=len(logs),
                sessions_without_captures=sorted(label for label in sessions if not capture_counts[label]),
                captures=captures, logs=logs, warnings=warnings)


def fmt(value, digits=1):
    return f'{value:.{digits}f}' if value is not None else 'n/a'


def markdown(report):
    lines = [f'First {report["warmup_frames"]} frames of each capture excluded; FPS uses complete-display mean frame time.',
             'Screenshots occur before capture. CPU phase columns may overlap and must not be summed.', '',
             '| Capture | Frames | FPS | Median ms | P95 ms | P99 ms | >33.3 ms | >50 ms | RSS MiB | Views |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for run in report['runs']:
        for capture in run['captures']:
            timing = capture['frame_ms'] or {}
            dimensions = sorted({f'{v["width"]}×{v["height"]}' for v in capture['viewports']})
            views = ','.join(str(int(v)) for v in capture['observed_views_per_frame']) + ' @ ' + ','.join(dimensions)
            lines.append('| ' + ' | '.join((capture['capture'], str(capture['timed_frames']),
                fmt(capture['throughput_fps']), fmt(timing.get('median')), fmt(timing.get('p95')),
                fmt(timing.get('p99')), fmt(capture['over_33_333_ms_percent']) + '%',
                fmt(capture['over_50_ms_percent']) + '%', fmt(capture['rss_peak_mib']), views)) + ' |')
    lines += ['', '| Capture | Server ms | Simulation ms | Submit ms | Present ms | Draws | World tris | Model tris | Min available MiB | Max swap MiB | Max °C | Modes |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for run in report['runs']:
        for capture in run['captures']:
            metrics = capture['metrics']
            telemetry = capture['telemetry']
            means = [fmt(metrics.get(key, {}).get('mean')) for key in (
                'server_ms', 'simulation_ms', 'submit_ms', 'present_ms', 'draws', 'world_triangles', 'model_triangles')]
            lines.append('| ' + ' | '.join([capture['capture']] + means + [
                fmt(telemetry['memory_available_min_mib']), fmt(telemetry['process_swap_max_mib']),
                fmt(telemetry['temperature_max_c']), 'pass' if capture['actual_modes_match_requested'] else 'CHECK']) + ' |')
        lines.append('')
        lines.append(f'Run `{run["root"]}`: shell restored={run["shell_restored"]}; '
                     f'saves unchanged={run["save_hashes_unchanged"]}; package unchanged={run["package_hashes_unchanged"]}.')
        if run['run_error']:
            lines.append(f'Run error: {run["run_error"]}')
        for label, log in run['logs'].items():
            if log['no_frame_captures']:
                lines.append(f'Log `{label}`: no frame captures; session startup or rendering failed before timing, or capture did not begin.')
            if log['error_like_count']:
                lines.append(f'Log `{label}`: {log["error_like_count"]} error-like lines; inspect JSON for text and counts.')
            if log['driver_ready'] or log['state_snapshot_count'] or log['driver_error_count']:
                lines.append(f'Driver `{label}`: {log["state_snapshot_count"]} state snapshots; '
                             f'all four active/connected/unpaused/valid in {log["all_four_ready_snapshots"]}; '
                             f'all four attack command bits in {log["all_four_attack_cmd_snapshots"]}; '
                             f'driver errors {log["driver_error_count"]}; '
                             f'malformed state snapshots {len(log["state_snapshot_parse_errors"])}.')
        for capture in run['captures']:
            telemetry = capture['telemetry']
            flags = telemetry['throttled_flags_observed']
            vm = telemetry['system_vm_counter_deltas']
            cpu = telemetry['process_cpu']
            faults = telemetry['process_page_faults']
            lines.append(f'`{capture["capture"]}`: throttling flags {", ".join(flags) or "unavailable"}; '
                         f'complete view frames {capture["complete_timed_view_frames"]}/{capture["timed_frames"]}; '
                         f'max particles/view {fmt(capture["submitted_particles_max"], 0)}, '
                         f'max projectiles {fmt(capture["metrics"].get("projectiles_by_effect", {}).get("maximum"), 0)}.')
            lines.append(f'Process CPU {fmt(cpu["mean_percent_of_one_core"])}% of one core '
                         f'(clock ticks/s: {fmt(cpu["clock_ticks_per_second"], 0)}); '
                         f'system swap-in/out delta {fmt(vm["pswpin_pages"], 0)}/{fmt(vm["pswpout_pages"], 0)} pages; '
                         f'process/system major faults {fmt(faults["major_faults"]["delta"], 0)}/{fmt(vm["major_faults"], 0)}; '
                         f'process VmSwap min/max {fmt(telemetry["process_swap_min_mib"])}/{fmt(telemetry["process_swap_max_mib"])} MiB '
                         f'(sample-window change {fmt(telemetry["process_swap_delta_mib"])} MiB); '
                         f'system OOM-kill delta {fmt(vm["oom_kills"], 0)}.')
            for warning in capture['warnings']:
                lines.append(f'Warning: `{capture["capture"]}`: {warning}')
        lines += ['Warning: ' + warning for warning in run['warnings']]
    lines.append('Resource observations: system VM counters include other processes; swapped pages and major faults do not alone identify the cause of stalls.')
    return '\n'.join(lines) + '\n'


def write_output(path, content):
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    else:
        sys.stdout.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('roots', type=Path, nargs='+', help='suite output directories containing metadata.json')
    parser.add_argument('--warmup', type=int, default=10, help='exclude this many initial CSV rows (default: 10)')
    parser.add_argument('--clock-ticks', type=int, help='target CLK_TCK (getconf CLK_TCK on the Pi), required for process CPU percentages')
    parser.add_argument('--format', choices=('json', 'markdown', 'both'), help='default: infer .json output, otherwise Markdown')
    parser.add_argument('--output', type=Path, help='write selected format here instead of stdout')
    parser.add_argument('--json', type=Path, help='also write complete structured JSON here')
    args = parser.parse_args()
    if args.warmup < 0:
        parser.error('--warmup must be nonnegative')
    if args.clock_ticks is not None and args.clock_ticks <= 0:
        parser.error('--clock-ticks must be positive')
    for root in args.roots:
        if not root.is_dir():
            parser.error(f'not a directory: {root}')
    report = dict(warmup_frames=args.warmup, fps_definition='1000 / mean positive complete-display frame_ms',
                  timings_include_screenshots=False,
                  runs=[analyze_root(root.resolve(), args.warmup, args.clock_ticks) for root in args.roots])
    encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
    output_format = args.format or ('json' if args.output and args.output.suffix.lower() == '.json' else 'markdown')
    rendered = encoded if output_format == 'json' else markdown(report)
    if output_format == 'both':
        rendered += '\n```json\n' + encoded + '```\n'
    write_output(args.output, rendered)
    if args.json:
        write_output(args.json, encoded)


if __name__ == '__main__':
    main()
