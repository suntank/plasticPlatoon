#!/usr/bin/env python3
"""Summarize complete display-frame captures; never convert per-view work to FPS."""
import argparse
import csv
import json
from pathlib import Path
import statistics

def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    at = (len(values) - 1) * fraction
    lo, hi = int(at), min(int(at) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (at - lo)

def summarize(path, warmup=120):
    with Path(path).open(newline='') as f:
        all_rows = list(csv.DictReader(f))
    rows = [r for r in all_rows[warmup:] if float(r['frame_ms']) > 0]
    if not rows:
        raise ValueError(f'{path}: no timed frames remain after warmup={warmup}')
    result = {'capture': str(path), 'warmup_frames': warmup, 'frames': len(rows), 'metrics': {}}
    for key in rows[0]:
        if key == 'frame':
            continue
        values = [float(r[key]) for r in rows if r[key] and float(r[key]) >= 0]
        if values:
            result['metrics'][key] = dict(median=statistics.median(values),
                p95=percentile(values, .95), p99=percentile(values, .99),
                maximum=max(values), mean=statistics.mean(values), minimum=min(values))
    times = [float(r['frame_ms']) for r in rows]
    result['over_33_333_ms_percent'] = 100 * sum(x > 1000 / 30 for x in times) / len(times)
    result['elapsed_seconds'] = sum(times) / 1000
    for key in ('rss_kib', 'server_edicts', 'monsters', 'dead_monsters', 'active_particles'):
        if key in rows[0] and float(rows[0][key]) >= 0:
            result[key + '_first_last'] = [float(rows[0][key]), float(rows[-1][key])]
    viewfile = Path(path).with_name(Path(path).name.replace('-frames.csv', '-views.csv'))
    if viewfile.exists():
        with viewfile.open(newline='') as f:
            views = list(csv.DictReader(f))
        # Delayed query results can be published on several views. Count each
        # originating renderer serial once, and only if its original frame survived warmup.
        retained_frames = {int(r['frame']) for r in rows}
        origin_frames = {int(v['renderer_serial']): int(v['frame']) for v in views
                         if v.get('renderer_serial') and float(v.get('renderer_counters') or 0) > 0}
        gpu = {}
        for v in views:
            serial = int(v.get('gpu_origin_serial') or 0)
            value = float(v.get('gpu_ms') or -1)
            if serial > 0 and value >= 0 and origin_frames.get(serial, -1) in retained_frames:
                gpu[serial] = value
        if gpu:
            result['gpu_view_samples'] = len(gpu)
            result['gpu_view_ms'] = {'median': statistics.median(gpu.values()), 'p95': percentile(gpu.values(), .95)}
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('captures', nargs='+', type=Path)
    p.add_argument('--warmup', type=int, default=120)
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    if a.warmup < 0:
        p.error('--warmup must be nonnegative')
    results = [summarize(path, a.warmup) for path in a.captures]
    print('| Capture | Frames | Median complete frame ms | P95 ms | P99 ms | >33.3 ms |')
    print('|---|---:|---:|---:|---:|---:|')
    for r in results:
        m = r['metrics']['frame_ms']
        print(f"| {Path(r['capture']).stem} | {r['frames']} | {m['median']:.3f} | {m['p95']:.3f} | {m['p99']:.3f} | {r['over_33_333_ms_percent']:.1f}% |")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(results, indent=2) + '\n')

if __name__ == '__main__':
    main()
