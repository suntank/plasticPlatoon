#!/usr/bin/env python3
"""Extract measured Temple geometry from the public n64decomp/007 C records.

Inputs are downloaded C records, not a ROM. Only geometry, vertex light values,
portal connectivity and navigation measurements are retained; no texture pixels,
audio, executable game code, or compressed display lists enter the output.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REVISION = "c4356466796c697dfd298010b9bed261f9ed8c6a"
SOURCE_ROOT = f"https://raw.githubusercontent.com/n64decomp/007/{SOURCE_REVISION}/assets/obseg/"


def arrays(text):
    result = {}
    for name, body in re.findall(r"u32 (\w+)\[\] = \{(.*?)\};", text, re.S):
        raw = b"".join(struct.pack(">I", int(n, 16))
                       for n in re.findall(r"0x([0-9A-Fa-f]+)", body))
        result[name] = zlib.decompress(raw[2:], -15) if raw[:2] == b"\x11\x72" else raw
    return result


def mesh(bg):
    data = arrays(bg)
    origins = {int(i): [int(float(v)) for v in (x, y, z)]
               for i, x, y, z in re.findall(
                   r"\{&point_table_binary_(\d+),[^\n]*?, ([\d.-]+), ([\d.-]+), ([\d.-]+)\}", bg)}
    rooms = []
    for room_id, origin in sorted(origins.items()):
        if room_id == 26:  # Empty terminator room.
            continue
        raw = data[f"point_table_binary_{room_id}"]
        vertices, colors = [], []
        if len(raw) % 16:
            raise ValueError(f"room {room_id}: invalid Vtx byte count")
        for offset in range(0, len(raw), 16):
            local = struct.unpack_from(">3h", raw, offset)
            vertices.append([a+b for a, b in zip(local, origin)])
            colors.append(list(raw[offset+12:offset+16]))
        dl = data[f"pri_mapping_binary_{room_id}"]
        cache = [None]*16
        triangles, textures = [], []
        texture_id = None
        def emit(indices):
            if len(set(indices)) != 3:
                return
            indices = [cache[i] for i in indices]
            if any(i is None or i >= len(vertices) for i in indices):
                raise ValueError(f"room {room_id}: invalid vertex-cache reference")
            a, b, c = (vertices[i] for i in indices)
            ab, ac = ([b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)])
            cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            if not any(cross):
                return
            triangles.append(indices)
            textures.append(texture_id)
        for offset in range(0, len(dl)-7, 8):
            w0, w1 = struct.unpack_from(">II", dl, offset)
            opcode = w0 >> 24
            if opcode == 0x04:  # Original F3D G_VTX: n-1 high nibble, v0 low.
                count, start = ((w0 >> 20) & 15)+1, (w0 >> 16) & 15
                address = w1 & 0xFFFFFF
                if address % 16 or start+count > 16:
                    raise ValueError(f"room {room_id}: unsupported G_VTX")
                cache[start:start+count] = range(address//16, address//16+count)
            elif opcode == 0xB1:  # GE custom TRI4, include original winding.
                for t in range(4):
                    emit([(w1 >> (t*8)) & 15, (w1 >> (t*8+4)) & 15,
                          (w0 >> (t*4)) & 15])
            elif opcode == 0xBF:  # Original F3D TRI1 stores index * 10.
                emit([((w1 >> s) & 255)//10 for s in (16, 8, 0)])
            elif opcode == 0xC0:
                texture_id = w1 & 0xFFF
            elif opcode == 0xB8:
                break
        rooms.append(dict(id=room_id, origin=origin, vertices=vertices,
                          vertex_colors=colors, triangles=triangles,
                          triangle_texture_ids=textures))
    return rooms


def portals(bg):
    connections = {int(i): [int(a, 16), int(b, 16)] for i, a, b in re.findall(
        r"\{&portal_(\d+), 0x([\da-fA-F]+), 0x([\da-fA-F]+),", bg)}
    output = []
    for i, body in re.findall(r"struct portal_4_point portal_(\d+) = \{(.*?)\};", bg):
        values = [float(n) for n in body.split(",")[4:]]
        output.append(dict(id=int(i), rooms=connections[int(i)],
                           vertices=[[int(v) for v in values[j:j+3]] for j in range(0, 12, 3)]))
    return output


def stan_tiles(stan):
    output = []
    for idx, body in re.findall(r"StandTile tile_(\d+) = \{(.*?)\n\};", stan, re.S):
        header = re.match(r"\s*0x([\da-fA-F]+), 0x([\da-fA-F]+),", body)
        if not header:
            continue
        points = [[int(x), int(y), int(z)] for x, y, z in re.findall(
            r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*0x[\da-fA-F]+\}", body)]
        if len(points) < 3:
            continue
        neighbors = [int(n, 16) for n in re.findall(
            r"\{\s*-?\d+,\s*-?\d+,\s*-?\d+,\s*0x([\da-fA-F]+)\}", body)]
        output.append(dict(id=int(idx), name=header[1], room=int(header[2], 16),
                           vertices=points, neighbor_offsets=neighbors))
    return output


def pads(setup, tiles):
    block = setup.split("PadRecord padlist[] = {", 1)[1].split("\n};", 1)[0]
    output = []
    for pos, up, look, name in re.findall(r'\{ \{([^}]+)\}, \{([^}]+)\}, \{([^}]+)\}, "([^\"]+)"', block):
        values = lambda text: [float(n.strip().rstrip("f")) for n in text.split(",")]
        output.append(dict(id=len(output), position=values(pos), up=values(up),
                           look=values(look), tile_name=name))
    by_name = {}
    for tile in tiles:
        key = int(tile['name'], 16)
        by_name[f'p{key >> 8}a{(key & 255) or ""}'] = tile
    for pad in output:
        tile = by_name[pad['tile_name']]
        a, b, c = tile['vertices'][:3]
        ab, ac = ([b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)])
        normal = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
        x, _, z = pad['position']
        floor = a[1]-(normal[0]*(x-a[0])+normal[2]*(z-a[2]))/normal[1]
        pad.update(room=tile['room'], tile=tile['id'], floor_y=floor,
                   floor_position=[x, floor, z])
    return output


def bound_pads(setup):
    block = setup.split('BoundPadRecord pad3dlist[] = {', 1)[1].split('\n};', 1)[0]
    vector = r'\{\s*([^{}]+)\}'
    pattern = vector+r',\s*'+vector+r',\s*'+vector+r',\s*"([^"]+)",\s*0,\s*'+vector
    values = lambda text: [float(n.strip().rstrip('f')) for n in text.split(',')]
    output = []
    for position, up, look, tile_name, bounds in re.findall(pattern, block):
        position, up, look, bounds = (values(v) for v in (position, up, look, bounds))
        normal = [up[1]*look[2]-up[2]*look[1], up[2]*look[0]-up[0]*look[2], up[0]*look[1]-up[1]*look[0]]
        corners = [[position[i]+normal[i]*a+up[i]*b+look[i]*c for i in range(3)]
                   for a, b, c in itertools.product(bounds[:2], bounds[2:4], bounds[4:])]
        output.append(dict(id=len(output), position=position, up=up, look=look,
                           tile_name=tile_name, local_bounds=bounds,
                           world_min=[round(min(p[i] for p in corners), 4) for i in range(3)],
                           world_max=[round(max(p[i] for p in corners), 4) for i in range(3)]))
    return output


def props(setup):
    block = setup.split('s32 propDefs[] = {', 1)[1].split('\n};', 1)[0]
    output = []
    for kind, idx, body in re.findall(r'/\* Type = (\w+); index = (\d+) \*/\s*(.*?)(?=/\*|$)', block, re.S):
        pair = re.search(r'_mkword\(\d+, _mkshort\(0, \d+\)\), _mkword\((\d+), (\d+)\)', body)
        if pair is None:
            continue
        model, pad = map(int, pair.groups())
        record = dict(id=int(idx), kind=kind, model=model, pad=pad)
        if kind == 'Collectable':
            item = re.search(r'_mkword\(_mkshort\((0x[\da-fA-F]+), 0xff\)', body)
            if item:
                record['item'] = int(item[1], 16)
                if 0xf0 <= record['item'] <= 0xf7:
                    record['weapon_slot'] = record['item']-0xf0
        output.append(record)
    return output


def spawn_pad_ids(setup):
    block = setup.split('s32 intro[] = {', 1)[1].split('\n};', 1)[0]
    return [int(v) for v in re.findall(r'Type = Spawn; index = \d+ \*/\s*_mkword\(0, _mkshort\(0, 0\)\), (\d+), 0', block)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, default=ROOT/"build/temple-reference")
    parser.add_argument("--output", type=Path, default=ROOT/"tools/maps/temple_layout.json")
    args = parser.parse_args()
    files = {"bg": ("temple-bg.c", "bg/bg_dish_all_p.c"),
             "stan": ("temple-stan.c", "stan/Tbg_dish_all_p_stanZ.c"),
             "setup": ("temple-setup.c", "setup/Ump_setupdishZ.c")}
    texts = {key: (args.reference_dir/name).read_text() for key, (name, _) in files.items()}
    tiles = stan_tiles(texts['stan'])
    rooms = mesh(texts['bg'])
    result = dict(schema_version=1, level="GoldenEye 007 (N64) multiplayer Temple",
                  coordinate_system="Original BG/STAN units, right-handed Y-up. Mesh vertices are room-local vertices plus room origins.",
                  source_level_scale=0.47142857,
                  source_revision=SOURCE_REVISION,
                  sources=[dict(url=SOURCE_ROOT+remote, sha256=hashlib.sha256((args.reference_dir/local).read_bytes()).hexdigest())
                           for local, remote in files.values()],
                  rooms=rooms, portals=portals(texts["bg"]),
                  stan_tiles=tiles, pads=pads(texts["setup"], tiles),
                  bound_pads=bound_pads(texts['setup']), props=props(texts['setup']),
                  spawn_pad_ids=spawn_pad_ids(texts['setup']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"))+"\n")
    print(f"{args.output}: {len(result['rooms'])} rooms, {sum(len(r['triangles']) for r in result['rooms'])} triangles, "
          f"{len(result['stan_tiles'])} navigation tiles, {len(result['portals'])} portals, {len(result['pads'])} pads")


if __name__ == "__main__":
    main()
