#!/usr/bin/env python3
"""Rebuild the optional Pi actor overlay from reviewed, hash-pinned topology.

Canonical high-detail models are inputs only. The accepted animated topology
uses the same selected original vertices in every frame, preserving packed
coordinates, normals, names, skins and quantization. Static view-gun cleanup
removes only faces covered by the bound first-person visibility certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

import numpy as np

from md2_assets import HEADER, MD2
from md2_animation import encode_vertex_subset
from verify_m16_runtime import verify as verify_m16
from verify_pistol_runtime import verify as verify_pistol

ROOT = Path(__file__).resolve().parents[2]
RECIPE = Path(__file__).with_name('pi-actor-models.json')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_path(name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.md2':
        raise ValueError('Invalid model path: ' + name)
    path = ROOT / 'baseq2' / relative
    if not path.resolve().is_relative_to((ROOT / 'baseq2').resolve()):
        raise ValueError('Model escapes canonical asset tree')
    return path


def ordered_commands(source, keep):
    """Retain original primitive/triangle/UV order, including strip parity."""
    raw = source.data
    cursor = source.header[15]
    end = cursor + 4 * source.header[9]
    output = bytearray()
    face = 0
    def emit(count, vertices):
        output.extend(struct.pack('<i', count))
        output.extend(b''.join(vertices))
    while cursor + 4 <= end:
        count = struct.unpack_from('<i', raw, cursor)[0]
        cursor += 4
        if not count:
            break
        vertices = [raw[cursor + 12*i:cursor + 12*(i+1)] for i in range(abs(count))]
        cursor += 12 * abs(count)
        mask = list(keep[face:face + abs(count) - 2])
        face += abs(count) - 2
        if all(mask):
            emit(count, vertices)
            continue
        start = None
        for index, value in enumerate(mask + [False]):
            if value and start is None:
                start = index
            if value or start is None:
                continue
            length = index - start
            if count < 0:
                emit(-(length + 2), [vertices[0]] + vertices[start+1:start+length+2])
            else:
                if start % 2:
                    emit(-3, [vertices[start+1], vertices[start], vertices[start+2]])
                    start += 1
                    length -= 1
                if length:
                    emit(length + 2, vertices[start:start+length+2])
            start = None
    if cursor != end or face != len(keep):
        raise ValueError('Incomplete original GL command stream')
    output.extend(struct.pack('<i', 0))
    return bytes(output)


def remove_hidden_faces(source, removed):
    if source.header[10] != 1:
        raise ValueError('First-person removal requires a static source')
    ids = np.asarray(removed, dtype=np.int32)
    if len(ids) == 0 or len(set(map(int, ids))) != len(ids) or ids.min() < 0 or ids.max() >= len(source.faces):
        raise ValueError('Invalid removed-face set')
    points = source.positions[0, source.faces[ids]]
    normal = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    if not np.all(np.sum(normal * points[:, 0], axis=1) + 29 * np.linalg.norm(normal, axis=1) < -1e-7):
        raise ValueError('A removed face fails the 29-unit visibility certificate')
    keep = np.ones(len(source.faces), dtype=bool)
    keep[ids] = False
    h, raw = source.header, source.data
    skins = raw[h[11]:h[11] + 64*h[5]]
    st = raw[h[12]:h[12] + 4*h[7]]
    frames = raw[h[14]:h[14] + h[4]*h[10]]
    values = np.frombuffer(st, dtype='<i2').reshape(-1, 2)
    lookup = {tuple(map(int, row)): i for i, row in reversed(list(enumerate(values)))}
    triangles = bytearray()
    for face, uv in zip(source.faces[keep], source.uvs[keep]):
        keys = np.rint(uv * np.asarray(h[2:4]) - .5).astype(int)
        indices = [lookup[tuple(map(int, key))] for key in keys]
        triangles.extend(struct.pack('<6H', *map(int, face), *indices))
    commands = ordered_commands(source, keep)
    sections = [skins, st, bytes(triangles), frames, commands]
    offsets, cursor = [], HEADER.size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    result = HEADER.pack(*h[:8], int(keep.sum()), len(commands)//4, h[10], *offsets, cursor) + b''.join(sections)
    decoded = MD2.read(result)
    np.testing.assert_array_equal(decoded.faces, source.faces[keep])
    np.testing.assert_array_equal(decoded.uvs, source.uvs[keep])
    np.testing.assert_array_equal(decoded.positions, source.positions)
    np.testing.assert_array_equal(decoded.normals, source.normals)
    return result


def build(recipe_path):
    # The old accepted topology is only valid for its original decimated
    # inputs. Authored replacements already have lower budgets and must come
    # from the main package, including the height builder's tall M16 variant.
    verify_m16()
    verify_pistol()
    authored = json.loads((ROOT / 'tools/assets/m16-manifest.json').read_text())
    authored_models = {model['path'] for model in authored['models']}
    pistol = json.loads((ROOT / 'tools/assets/pistol-manifest.json').read_text())
    authored_models.update(model['path'] for model in pistol['models'])
    recipe_raw = recipe_path.read_bytes()
    recipe = json.loads(recipe_raw)
    if recipe.get('schema') != 1 or not recipe.get('models'):
        raise ValueError('Missing accepted topology recipe')
    quality_raw = (ROOT / recipe['quality']['path']).read_bytes()
    quality = json.loads(quality_raw)
    if (sha(quality_raw) != recipe['quality']['sha256'] or
            quality.get('schema') != 1 or quality.get('passed') is not True):
        raise ValueError('Accepted model quality receipt missing or changed')
    expected_models = {m['path']: {k: m[k] for k in ('source_sha256', 'output_sha256')}
                       for m in recipe['models']}
    if len(expected_models) != len(recipe['models']) or quality.get('models') != expected_models:
        raise ValueError('Quality receipt does not bind the exact replacement set')
    proof_path = ROOT / recipe['first_person_proof']['path']
    proof_raw = proof_path.read_bytes()
    proof = json.loads(proof_raw)
    if (sha(proof_raw) != recipe['first_person_proof']['sha256'] or
            not all(proof.get(k) is True for k in ('passed', 'analytic_passed', 'pixel_exact')) or
            proof.get('analytic_bound_units', 0) < 29):
        raise ValueError('First-person proof missing, changed or incomplete')
    members, models = {}, []
    for spec in recipe['models']:
        name = spec['path']
        if name in authored_models:
            continue
        if name in members:
            raise ValueError('Duplicate model')
        raw = source_path(name).read_bytes()
        if sha(raw) != spec['source_sha256']:
            raise ValueError('Canonical model changed: ' + name)
        source = MD2.read(raw)
        if spec['kind'] == 'animated_subset':
            result = encode_vertex_subset(source, np.asarray(spec['source_vertices'], dtype=np.int32),
                np.asarray(spec['faces'], dtype=np.int32), np.asarray(spec['uvs'], dtype=np.float64))
        elif spec['kind'] == 'first_person_hidden':
            if proof['models'].get(name) != {k: spec[k] for k in ('source_sha256', 'output_sha256')}:
                raise ValueError('First-person proof does not bind this model')
            result = remove_hidden_faces(source, spec['removed_faces'])
        else:
            raise ValueError('Unknown topology recipe kind')
        if sha(result) != spec['output_sha256']:
            raise ValueError('Regenerated output differs from accepted model: ' + name)
        output = MD2.read(result)
        if (output.header[8] >= source.header[8] or output.names != source.names or
                output.skins != source.skins or output.header[2:4] != source.header[2:4]):
            raise ValueError('Triangle reduction/animation/skin contract failed')
        members[name] = result
        models.append(dict(path=name, source_sha256=spec['source_sha256'], output_sha256=sha(result),
            triangles_before=source.header[8], triangles_after=output.header[8],
            vertices_before=source.header[6], vertices_after=output.header[6], frames=output.header[10],
            kind=spec['kind']))
    manifest = dict(schema=1, profile='Pi Zero 2 W, four 120x120 views',
        generator_sha256=sha(Path(__file__).read_bytes()), recipe_sha256=sha(recipe_raw),
        first_person_proof_sha256=sha(proof_raw), models=models,
        canonical_replacements_omitted=sorted(authored_models & set(expected_models)),
        quality=recipe['quality'], canonical_high_detail_assets_unchanged=True)
    members['actor-models-manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue(), manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, default=RECIPE)
    parser.add_argument('--output', type=Path, default=ROOT/'build/assets/pi-actor-models.pkz')
    parser.add_argument('--verify', action='store_true', help='Check existing pack against exact regeneration')
    args = parser.parse_args()
    data, manifest = build(args.recipe)
    if args.verify:
        if args.output.read_bytes() != data:
            raise ValueError('Existing Pi model pack differs from exact regeneration')
    else:
        if args.output.resolve().is_relative_to((ROOT/'baseq2').resolve()):
            raise ValueError('Build outside canonical baseq2; install the Pi overlay explicitly')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        staged = args.output.with_suffix('.pkz.tmp')
        staged.write_bytes(data)
        staged.replace(args.output)
    print(json.dumps(dict(path=str(args.output), sha256=sha(data), models=len(manifest['models']),
        triangles_before=sum(m['triangles_before'] for m in manifest['models']),
        triangles_after=sum(m['triangles_after'] for m in manifest['models'])), indent=2))


if __name__ == '__main__':
    main()
