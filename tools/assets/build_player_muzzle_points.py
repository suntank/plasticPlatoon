#!/usr/bin/env python3
"""Generate player weapon muzzle attachments from reviewed MD2 barrel-rim vertices.

Markers retain the same vertex identities through every authored pose. The
client interpolates them exactly like the held mesh; they are model-space XYZ,
not eye-relative offsets. No first-person model, tuning or geometry is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'src/client/header/player_muzzle_points.h'
REPORT = ROOT / 'tools/assets/player-muzzle-points.json'
REVIEW = ROOT / 'tools/assets/review/player-muzzle-points.png'
# Reviewed front-rim vertex identities, pinned to the current optimized mesh.
# The <=0.13-unit X slab covers the quantized barrel lip, not the rear sights.
# Double-barrel shotgun intentionally uses the center of the paired openings.
SELECTORS = {'w_bfg.md2': {'sha256': 'bd4b45055a3ba4d59baaae850816927cb53e9f5fd56b39b69cc84488842b32c4',
               'vertices': [328, 443, 458, 569]},
 'w_blaster.md2': {'sha256': 'e9ef32e21870c9f30b987d28c18478a5871fc9e5ff5b4c7c1b24de917dce94f8',
                   'vertices': [127,
                                128,
                                178,
                                184,
                                194,
                                195,
                                214,
                                215,
                                217,
                                231,
                                238,
                                240,
                                249,
                                250,
                                252,
                                254,
                                279,
                                280,
                                289,
                                324,
                                325,
                                326,
                                334,
                                349,
                                351,
                                358,
                                360,
                                369,
                                390,
                                391,
                                412,
                                413,
                                422,
                                439,
                                452,
                                453,
                                460,
                                461,
                                465,
                                474,
                                486,
                                492,
                                494,
                                495,
                                542,
                                554,
                                564,
                                566,
                                576,
                                587,
                                589,
                                595,
                                602,
                                624]},
 'w_chaingun.md2': {'sha256': '4e061cc055f001f86e4be9b348f7566778913ee50a7d5f7d66e90470316eeed8',
                    'vertices': [230, 231, 249, 297, 321, 323, 354, 399, 403, 477, 482, 523]},
 'w_glauncher.md2': {'sha256': '464aef9819300433b656fd5a5d7db70032e1967689eaca26596a3551927175e1',
                     'vertices': [144, 145, 189, 226, 296, 301, 360, 383, 506, 525, 537, 550, 587]},
 'w_hyperblaster.md2': {'sha256': 'e40b6d06c18850dcf019d17a8bb48d2d1dca455a1114bfad97c4c75d6e4a1d34',
                        'vertices': [58, 64, 95, 96, 147, 156, 192]},
 'w_machinegun.md2': {'sha256': 'f516f09bc3fe5f8e165a2e8818a29c8127631ec61fd9ecfc937a8ffaa826ef72',
                      'vertices': [223, 259, 260, 375, 400, 469]},
 'w_railgun.md2': {'sha256': '4240cc88896bfa0fc8a0501cc73c10f75ff683b31c1b515c3646d757c7801bfc',
                   'vertices': [354, 439, 535, 618, 671, 679, 719, 758, 764, 854, 859, 870, 934, 1188]},
 'w_rlauncher.md2': {'sha256': 'ed73d6194eee3af276000032290ca2854262e800a90330ffbb5e871227f99f04',
                     'vertices': [114,
                                  156,
                                  222,
                                  266,
                                  272,
                                  319,
                                  322,
                                  340,
                                  352,
                                  394,
                                  411,
                                  425,
                                  446,
                                  447,
                                  516,
                                  586,
                                  587]},
 'w_shotgun.md2': {'sha256': '74b73f5eaa477c64737ce56243d6a54b95dd4d49315eec273216ebf3a4716125',
                   'vertices': [161, 208, 211, 212, 269, 297, 333, 347, 377, 394, 396, 409, 470, 539]},
 'w_sshotgun.md2': {'sha256': '0e835341e2300376d88d51a6380d6f84ebfe2e9569cffec0b65a094bdfc9a55b',
                    'vertices': [17,
                                 22,
                                 24,
                                 27,
                                 61,
                                 82,
                                 142,
                                 195,
                                 219,
                                 251,
                                 283,
                                 284,
                                 287,
                                 331,
                                 343,
                                 359,
                                 434,
                                 490,
                                 499,
                                 501,
                                 502,
                                 514,
                                 523,
                                 550,
                                 558,
                                 634,
                                 683,
                                 686,
                                 687,
                                 688,
                                 724]},
 'weapon.md2': {'sha256': 'f516f09bc3fe5f8e165a2e8818a29c8127631ec61fd9ecfc937a8ffaa826ef72',
                'vertices': [223, 259, 260, 375, 400, 469]}}


def load_model(path: Path, expected_hash: str):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError(f'{path}: source changed; inspect barrel rim before updating attachment vertices')
    h = struct.unpack_from('<17i', raw)
    if h[0] != 844121161 or h[1] != 8 or h[10] != 198:
        raise ValueError(f'{path}: expected player MD2 with 198 frames')
    if h[16] != len(raw) or h[4] != 40 + h[6] * 4:
        raise ValueError(f'{path}: invalid MD2 layout')
    frames, names = [], []
    for frame in range(h[10]):
        offset = h[14] + frame * h[4]
        scale_translate = struct.unpack_from('<6f', raw, offset)
        names.append(raw[offset + 24:offset + 40].split(b'\0', 1)[0].decode('ascii'))
        verts = []
        for vertex in range(h[6]):
            packed = raw[offset + 40 + vertex * 4:offset + 44 + vertex * 4]
            verts.append(tuple(packed[a] * scale_translate[a] + scale_translate[a + 3] for a in range(3)))
        frames.append(verts)
    triangles = [struct.unpack_from('<3H', raw, h[13] + face * 12) for face in range(h[8])]
    return frames, names, triangles


def generate(root=ROOT):
    entries = []
    header = [
        '/* Generated by tools/assets/build_player_muzzle_points.py; do not edit.',
        ' * Model-space muzzle centers track reviewed barrel-rim vertices in all poses.',
        ' * Regenerate after intentional model edits and visual attachment review. */',
        '#ifndef PP_PLAYER_MUZZLE_POINTS_H', '#define PP_PLAYER_MUZZLE_POINTS_H', '',
        'typedef struct {', '\tconst char *filename;', '\tconst float (*points)[3];',
        '\tint num_frames;', '} pp_player_muzzle_model_t;', '',
    ]
    for filename, selector in SELECTORS.items():
        path = root / 'baseq2/players/soldier' / filename
        frames, names, triangles = load_model(path, selector['sha256'])
        selected = selector['vertices']
        if not selected or len(selected) != len(set(selected)) or any(i < 0 or i >= len(frames[0]) for i in selected):
            raise ValueError(f'{filename}: invalid marker vertex selection')
        front = max(v[0] for v in frames[0])
        if any(front - frames[0][i][0] > .130001 for i in selected):
            raise ValueError(f'{filename}: selected vertex is no longer on the reviewed barrel rim')
        points = [[sum(vertices[i][axis] for i in selected) / len(selected) for axis in range(3)] for vertices in frames]
        symbol = 'pp_muzzle_' + filename.removesuffix('.md2')
        entries.append(dict(filename=filename, source_sha256=selector['sha256'], vertices=selected,
                            symbol=symbol, frames=len(frames), points=points, names=names))
        if filename == 'weapon.md2':
            machinegun = next(e for e in entries if e['filename'] == 'w_machinegun.md2')
            if points != machinegun['points']:
                raise ValueError('fallback weapon no longer matches machinegun; review separately')
            entries[-1]['symbol'] = machinegun['symbol']
            continue
        header += [f'/* {filename} SHA256 {selector["sha256"]} */',
                   f'static const float {symbol}[{len(points)}][3] = {{']
        for frame, point in enumerate(points):
            header.append('\t{' + ', '.join(f'{v:.6f}f' for v in point) + f'}}, /* {frame}: {names[frame]} */')
        header += ['};', '']
    header += ['static const pp_player_muzzle_model_t pp_player_muzzle_models[] = {']
    for entry in entries:
        header.append(f'\t{{"{entry["filename"]}", {entry["symbol"]}, {entry["frames"]}}},')
    header += ['};', '#define PP_PLAYER_MUZZLE_MODEL_COUNT (sizeof(pp_player_muzzle_models) / sizeof(pp_player_muzzle_models[0]))', '', '#endif', '']
    report = dict(schema=1, space='MD2 model-local XYZ (X forward, Y left, Z up); interpolate before entity transform',
                  method='Mean of fixed, visually reviewed front barrel-rim vertex identities through all 198 frames',
                  frame_groups={'standing':[0,39], 'running':[40,45], 'standing_attack':[46,53], 'crouch_idle':[135,153], 'crouch_walk':[154,159], 'crouch_attack':[160,168]},
                  models=[{k:v for k,v in entry.items() if k not in ('symbol','names','points')} |
                          {'sample_points':{str(i):[round(v,6) for v in entry['points'][i]] for i in (0,40,46,47,135,154,160,161)}} for entry in entries])
    return '\n'.join(header), json.dumps(report, indent=2) + '\n', entries


def review(destination=REVIEW, root=ROOT):
    """Side and top orthographic plots show actual faces and tracked marker poses."""
    from PIL import Image, ImageDraw
    _, _, entries = generate(root)
    entries = [e for e in entries if e['filename'] != 'weapon.md2']
    width, cellw, rowh = 1200, 400, 235
    image = Image.new('RGB', (width, 55 + len(entries) * rowh), '#182128')
    draw = ImageDraw.Draw(image)
    draw.text((12, 10), 'Third-person held weapons | red = tracked muzzle center | side (X/Z) and top (X/Y) | same scale', fill='white')
    for row, entry in enumerate(entries):
        frames, names, faces = load_model(root / 'baseq2/players/soldier' / entry['filename'], entry['source_sha256'])
        for col, frame in enumerate((0,46,160)):
            vertices, marker = frames[frame], entry['points'][frame]
            top, left = 55 + row * rowh, col * cellw
            draw.text((left + 8, top + 5), f'{entry["filename"]}  {frame}: {names[frame]}', fill='white')
            for view, axis in enumerate((2,1)):
                centerz = 20 if axis == 2 and frame < 135 else 3 if axis == 2 else 0
                cy = top + (90 if view == 0 else 190)
                def project(v): return (left + 105 + v[0] * 7, cy - (v[axis] - centerz) * 7)
                for face in sorted(faces, key=lambda face:sum(vertices[i][1 if axis==2 else 2] for i in face), reverse=axis==2):
                    draw.polygon([project(vertices[i]) for i in face], fill='#497948', outline='#345a35')
                x,y=project(marker)
                draw.ellipse((x-4,y-4,x+4,y+4),outline='#ff615f',width=2)
                draw.line((x-7,y,x+7,y),fill='#ff615f',width=1)
                draw.line((x,y-7,x,y+7),fill='#ff615f',width=1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify generated header/report without modifying them')
    parser.add_argument('--review', action='store_true', help='render the geometry audit contact sheet')
    args = parser.parse_args()
    header, report, entries = generate()
    for path, expected in ((HEADER,header),(REPORT,report)):
        if args.check:
            if not path.is_file() or path.read_text() != expected:
                raise SystemExit(f'{path}: stale generated attachment data')
        else:
            path.write_text(expected)
    if args.review: review()
    print(f'{"Verified" if args.check else "Generated"} muzzle points for {len(entries)} held models, 198 frames each.')


if __name__ == '__main__': main()
