#!/usr/bin/env python3
"""Audit Quake II MAP sources and IBSP38 visibility without external packages."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct

DETAIL = 0x08000000
LUMPS = ('entities planes vertexes visibility nodes texinfo faces lighting '
         'leafs leaffaces leafbrushes edges surfedges models brushes brushsides '
         'pop areas areaportals').split()
SIZES = dict(planes=20, vertexes=12, nodes=28, texinfo=76, faces=20,
             leafs=28, leaffaces=2, leafbrushes=2, edges=4, surfedges=4,
             models=48, brushes=12, brushsides=4, areas=8, areaportals=8)

def map_inventory(path):
    data = Path(path).read_bytes()
    entities, brushes, current, brush, depth = [], [], None, None, 0
    for lineno, line in enumerate(data.decode('utf-8-sig').splitlines(), 1):
        line = line.split('//', 1)[0].strip()
        if not line:
            continue
        if line == '{':
            depth += 1
            if depth == 1:
                current = {'keys': {}, 'brushes': []}
            elif depth == 2:
                brush = []
            else:
                raise ValueError(f'unsupported nesting at line {lineno}')
        elif line == '}':
            if depth == 2:
                current['brushes'].append(brush)
                brushes.append((current, brush))
            elif depth == 1:
                entities.append(current)
            else:
                raise ValueError(f'unbalanced closing brace at line {lineno}')
            depth -= 1
        elif depth == 1:
            m = re.fullmatch(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s+"(.*)"', line)
            if m:
                current['keys'][m[1]] = m[2]
        elif depth == 2 and line.startswith('('):
            m = re.match(r'(?:\(\s*[^)]+\)\s*){3}(\S+)\s+(.*)', line)
            if not m:
                raise ValueError(f'malformed brush face at line {lineno}')
            texture, tail = m.groups()
            plain = re.sub(r'\[[^]]*\]', '', tail).split()
            minimum = 3 if '[' in tail else 5
            contents = int(plain[minimum], 0) if len(plain) >= minimum + 3 else 0
            brush.append({'texture': texture, 'contents': contents})
    if depth:
        raise ValueError('unbalanced MAP braces')
    classes = Counter(e['keys'].get('classname', '') for e in entities)
    textures = Counter(f['texture'] for _, b in brushes for f in b)
    sand = [b for _, b in brushes if b and 'sand' in Counter(f['texture'] for f in b).most_common(1)[0][0].rsplit('/', 1)[-1].lower()]
    return {
        'source': Path(path).name, 'sha256': hashlib.sha256(data).hexdigest(),
        'entities': len(entities), 'brushes': len(brushes),
        'world_brushes': sum(len(e['brushes']) for e in entities if e['keys'].get('classname') == 'worldspawn'),
        'detail_brushes': sum(any(f['contents'] & DETAIL for f in b) for _, b in brushes),
        'source_faces': sum(len(b) for _, b in brushes),
        'pickups': sum(v for k, v in classes.items() if k.startswith(('item_', 'weapon_', 'ammo_'))),
        'initial_monsters': sum(v for k, v in classes.items() if k.startswith('monster_')),
        'spawners': classes['target_spawner'], 'timers': classes['func_timer'], 'placed_lights': classes['light'],
        'sand_brushes': len(sand),
        'sand_detail': sum(any(f['contents'] & DETAIL for f in b) for b in sand),
        'sand_structural': sum(not any(f['contents'] & DETAIL for f in b) for b in sand),
        'classes': dict(sorted(classes.items())), 'textures': dict(sorted(textures.items())),
        'player_starts': [e['keys'] for e in entities if e['keys'].get('classname', '').startswith('info_player')],
        'timer_settings': [e['keys'] for e in entities if e['keys'].get('classname') == 'func_timer'],
    }

def decompress_vis(data, offset, size):
    if offset == -1:
        return b'\xff' * size
    if offset < 0 or offset >= len(data):
        raise ValueError('visibility offset outside lump')
    out = bytearray()
    while len(out) < size:
        if offset >= len(data):
            raise ValueError('truncated visibility row')
        value = data[offset]
        offset += 1
        if value:
            out.append(value)
        else:
            if offset >= len(data) or not data[offset]:
                raise ValueError('invalid visibility zero run')
            out.extend(bytes(data[offset]))
            offset += 1
        if len(out) > size:
            raise ValueError('visibility row overflow')
    return bytes(out)

def bsp_inventory(path, require_release=False):
    raw = Path(path).read_bytes()
    if len(raw) < 160 or struct.unpack_from('<4si', raw) != (b'IBSP', 38):
        raise ValueError('expected Quake II IBSP version 38')
    lumps, info, spans = {}, {}, []
    for i, name in enumerate(LUMPS):
        start, size = struct.unpack_from('<ii', raw, 8 + i * 8)
        if start < 0 or size < 0 or start + size > len(raw):
            raise ValueError(f'{name} lump outside BSP')
        if size and start < 160:
            raise ValueError(f'{name} overlaps BSP header')
        if size:
            if any(start < end and start + size > begin for begin, end, _ in spans):
                raise ValueError(f'{name} overlaps another BSP lump')
            spans.append((start, start + size, name))
        if name in SIZES and size % SIZES[name]:
            raise ValueError(f'invalid {name} lump size')
        lumps[name] = raw[start:start + size]
        info[name] = {'bytes': size}
        if name in SIZES:
            info[name]['count'] = size // SIZES[name]
    vis, clusters, visible = lumps['visibility'], 0, []
    if vis:
        if len(vis) < 4:
            raise ValueError('truncated visibility header')
        clusters, = struct.unpack_from('<i', vis)
        if clusters < 1 or 4 + 8 * clusters > len(vis):
            raise ValueError('invalid visibility cluster table')
        for cluster in range(clusters):
            for kind in range(2):
                offset, = struct.unpack_from('<i', vis, 4 + 8 * cluster + 4 * kind)
                if require_release and offset == -1:
                    raise ValueError('release BSP has missing visibility rows')
                if offset != -1 and offset < 4 + 8 * clusters:
                    raise ValueError('visibility offset overlaps cluster table')
                row = decompress_vis(vis, offset, (clusters + 7) // 8)
                if kind == 0:
                    visible.append(sum(bool(row[i >> 3] & (1 << (i & 7))) for i in range(clusters)))
        for i in range(0, len(lumps['leafs']), 28):
            cluster, = struct.unpack_from('<h', lumps['leafs'], i + 4)
            if cluster < -1 or cluster >= clusters:
                raise ValueError('leaf references invalid visibility cluster')
    if require_release and (not vis or not lumps['lighting']):
        raise ValueError('release BSP requires nonempty validated VIS and baked lighting lumps')
    return {'source': Path(path).name, 'sha256': hashlib.sha256(raw).hexdigest(),
            'file_bytes': len(raw), 'lumps': info, 'clusters': clusters,
            'pvs_visible_clusters_mean': sum(visible) / len(visible) if visible else None,
            'pvs_visible_clusters_max': max(visible) if visible else None,
            'pvs_visible_fraction_mean': sum(visible) / (clusters * clusters) if visible else None,
            'release_lumps_present': bool(vis and lumps['lighting'])}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path', type=Path)
    p.add_argument('--require-release', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = bsp_inventory(a.path, a.require_release) if a.path.suffix == '.bsp' else map_inventory(a.path)
    text = json.dumps(result, indent=2) + '\n'
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text)
    else:
        print(text, end='')

if __name__ == '__main__':
    main()
