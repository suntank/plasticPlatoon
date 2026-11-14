#!/usr/bin/env python3
"""Build five optional distant pickup MD2s without rewriting close models/skins.

Generation needs the pinned tools/assets requirements. --verify is deliberately
standard-library-only so normal asset builds and the Pi can audit shipped LODs.
Original geometry comes exclusively from the audited source archives named by
pickup-lods.json. The two open ammo trays use a simple authored shape recipe;
the other silhouettes use independent reduction from their original inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("pickup-lods.json")
MANIFEST = Path(__file__).with_name("pickup-lods-manifest.json")
HEADER = struct.Struct("<17i")
HELPERS = ("tools/assets/md2_assets.py", "tools/assets/asset_sources.py",
           "src/client/refresh/constants/anorms.h")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or ".." in Path(relative).parts:
        raise ValueError("asset path escapes project: " + relative)
    return path


def decode(raw):
    """Audit MD2 layout, indices and GL topology without conversion libraries."""
    if len(raw) < HEADER.size:
        raise ValueError("truncated MD2")
    h = HEADER.unpack_from(raw)
    magic, version, sw, sh, stride, ns, nv, nt, nf, nc, frames, os, ot, of, ofr, oc, end = h
    if (magic, version) != (844121161, 8) or frames != 1 or not 0 < nv <= 2048:
        raise ValueError("expected a supported static MD2")
    if not (0 < ns <= 32 and 0 < nt <= 32767 and 0 < nf <= 4096 and nc > 0
            and sw > 0 and sh > 0 and stride == 40 + 4 * nv and end == len(raw)):
        raise ValueError("invalid MD2 sizes")
    previous = HEADER.size
    for start, length in ((os, ns * 64), (ot, nt * 4), (of, nf * 12),
                          (ofr, stride), (oc, nc * 4)):
        if start != previous or start + length > end:
            raise ValueError("invalid MD2 section offsets")
        previous = start + length
    if previous != end:
        raise ValueError("unaccounted MD2 trailing data")
    skins = [raw[os + i * 64:os + (i + 1) * 64].split(b"\0")[0].decode() for i in range(ns)]
    if any(not skin.startswith("models/items/") or ".." in skin or "\\" in skin for skin in skins):
        raise ValueError("unexpected pickup skin reference")
    scale = struct.unpack_from("<3f", raw, ofr)
    trans = struct.unpack_from("<3f", raw, ofr + 12)
    if any(not math.isfinite(v) for v in (*scale, *trans)) or min(scale) <= 0:
        raise ValueError("invalid MD2 quantization lattice")
    name = raw[ofr + 24:ofr + 40]
    positions = []
    for i in range(nv):
        x, y, z, normal = struct.unpack_from("<4B", raw, ofr + 40 + i * 4)
        if normal >= 162:
            raise ValueError("invalid MD2 normal")
        positions.append(tuple(v * s + t for v, s, t in zip((x, y, z), scale, trans)))
    triangles = []
    for i in range(nf):
        indices = struct.unpack_from("<6H", raw, of + 12 * i)
        if max(indices[:3]) >= nv or max(indices[3:]) >= nt:
            raise ValueError("MD2 triangle index out of range")
        a, b, c = (positions[j] for j in indices[:3])
        ab, ac = [b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)]
        cross = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
                 ab[0] * ac[1] - ab[1] * ac[0]]
        if sum(v * v for v in cross) <= 1e-24:
            raise ValueError("degenerate quantized MD2 triangle")
        triangles.append(indices[:3])
    commands, primitive_count, cursor = [], 0, oc
    while cursor + 4 <= end:
        count = struct.unpack_from("<i", raw, cursor)[0]
        cursor += 4
        if not count:
            break
        if abs(count) < 3 or cursor + abs(count) * 12 > end:
            raise ValueError("invalid GL strip/fan")
        primitive_count += 1
        values = [struct.unpack_from("<ffi", raw, cursor + i * 12) for i in range(abs(count))]
        cursor += abs(count) * 12
        if any(not math.isfinite(u) or not math.isfinite(v) or not 0 <= vertex < nv
               for u, v, vertex in values):
            raise ValueError("invalid GL UV or position index")
        for i in range(2, abs(count)):
            indices = (0, i - 1, i) if count < 0 else ((i - 2, i - 1, i) if i % 2 == 0 else (i - 1, i - 2, i))
            commands.append(tuple(values[j][2] for j in indices))
    else:
        raise ValueError("missing GL command terminator")
    oriented = lambda triangle: min(triangle, triangle[1:] + triangle[:1], triangle[2:] + triangle[:2])
    if cursor != end or Counter(map(oriented, triangles)) != Counter(map(oriented, commands)):
        raise ValueError("GL command topology differs from triangle table")
    return dict(sha256=sha(raw), file_bytes=len(raw), triangles=nf, position_vertices=nv,
                gl_primitives=primitive_count, frames=frames, skins=skins,
                skin_dimensions=[sw, sh], frame_name_hex=name.hex(),
                scale=list(scale), translation=list(trans),
                bounds=[[min(p[axis] for p in positions) for axis in range(3)],
                        [max(p[axis] for p in positions) for axis in range(3)]])


def inputs(config):
    archives = {}
    for key, entry in config["source_archives"].items():
        raw = checked_path(entry["path"]).read_bytes()
        if sha(raw) != entry["sha256"]:
            raise ValueError("pinned source archive changed: " + entry["path"])
        archives[key] = raw
    for spec in config["assets"]:
        canonical = checked_path("baseq2/" + spec["canonical"]).read_bytes()
        texture = checked_path("baseq2/" + spec["skin"]).read_bytes()
        if sha(canonical) != spec["canonical_sha256"] or sha(texture) != spec["skin_sha256"]:
            raise ValueError("canonical pickup or texture changed: " + spec["canonical"])
        with zipfile.ZipFile(io.BytesIO(archives[spec["source_archive"]])) as archive:
            original = archive.read("baseq2/" + spec["canonical"])
        if sha(original) != spec["source_sha256"]:
            raise ValueError("pinned original pickup changed: " + spec["canonical"])
        if spec["lod"] != spec["canonical"].replace("/tris.md2", "/lod1.md2"):
            raise ValueError("LOD output must be an additive sibling of tris.md2")
        yield spec, original, canonical, texture


def validate_pair(spec, canonical, lod):
    before, after = decode(canonical), decode(lod)
    for key in ("skins", "skin_dimensions", "scale", "translation", "frame_name_hex", "frames"):
        if before[key] != after[key]:
            raise ValueError("close/LOD frame identity or skin mismatch: " + key)
    if not 100 <= after["triangles"] <= 200 or after["triangles"] > spec["target_triangles"]:
        raise ValueError("distant pickup exceeds its authored 100-200 triangle budget")
    for axis in range(3):
        extent = before["bounds"][1][axis] - before["bounds"][0][axis]
        if after["bounds"][0][axis] < before["bounds"][0][axis] - extent * .05 or after["bounds"][1][axis] > before["bounds"][1][axis] + extent * .05:
            raise ValueError("LOD grows beyond the original pickup bounds")
    return before, after


def ammo_box(source, texture, texel):
    """Art-directed distant tray: retain open top/lid; remove subpixel bevels."""
    import numpy as np
    vertices, faces = [], []
    lo, hi = source.positions[0].min(axis=0), source.positions[0].max(axis=0)
    dimensions = hi - lo
    topology = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
                (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))

    def solid(points):
        points = np.array(points)
        offset = len(vertices)
        vertices.extend(points)
        # Quake II alias models use clockwise exterior winding.
        positive = np.linalg.det(np.array([points[1] - points[0], points[3] - points[0], points[4] - points[0]])) > 0
        faces.extend(tuple(offset + i for i in (face[::-1] if positive else face)) for face in topology)

    def panel(a, b):
        x, y, z = a
        X, Y, Z = b
        solid([lo + np.array(p) * dimensions for p in
               ((x, y, z), (X, y, z), (X, Y, z), (x, Y, z),
                (x, y, Z), (X, y, Z), (X, Y, Z), (x, Y, Z))])

    panel((0, 0, 0), (1, 1, .08))
    panel((0, 0, .08), (1, .06, .55))
    panel((0, .94, .08), (1, 1, .55))
    panel((0, .06, .08), (.06, .94, .55))
    panel((.94, .06, .08), (1, .94, .55))
    lid = ((0, .94, .52), (1, .94, .52), (1, .43, .98), (0, .43, .98),
           (0, .97, .55), (1, .97, .55), (1, .46, 1), (0, .46, 1))
    solid([lo + np.array(p) * dimensions for p in lid])
    for i in range(5):
        x = .16 + i * .17
        panel((x - .04, .25, .08), (x + .04, .65, .58))
    # At <=12 projected pixels, use an existing representative pigment texel.
    # Nearest-vertex UV transfer stretches atlas background across broad panels.
    # This constant UV keeps the original green without adding/changing skins.
    from PIL import Image
    image = Image.open(io.BytesIO(texture))
    if not (0 <= texel[0] < image.width and 0 <= texel[1] < image.height):
        raise ValueError("pigment texel outside original skin")
    uv = ((texel[0] + .5) / image.width, (texel[1] + .5) / image.height)
    return np.array(vertices), np.array(faces), np.tile(uv, (len(faces), 3, 1))


def review_pair(spec, full, lod, texture, destination):
    import numpy as np
    from PIL import Image, ImageDraw
    import md2_assets as md2
    tex = Image.open(io.BytesIO(texture))
    points = full.positions[0]
    centre = (points.min(axis=0) + points.max(axis=0)) / 2
    framing = centre, np.linalg.norm(points - centre, axis=1).max()
    canvas = Image.new("RGB", (1024, 300), (22, 25, 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), spec["classname"] + " | unchanged close model / distant LOD | identical camera, skin and light", fill="white")
    metrics = []
    for col, angle in enumerate((25, 115, 205, 295)):
        x = col * 256
        draw.text((x + 8, 25), str(angle) + " deg", fill="white")
        for j, model in enumerate((full, lod)):
            near, _ = md2.raster(model, tex, angle, 112, framing, cull_front=True)
            canvas.paste(near, (x + 8 + j * 120, 44))
            draw.text((x + 8 + j * 120, 160), str(len(model.faces)) + " triangles", fill="white")
        for row, pixels in enumerate((16, 12, 8)):
            views = [md2.raster(model, tex, angle, pixels, framing, cull_front=True) for model in (full, lod)]
            for j, (picture, _) in enumerate(views):
                canvas.paste(picture, (x + 8 + j * 120, 184 + row * 34))
                canvas.paste(picture.resize((pixels * 2, pixels * 2), Image.Resampling.NEAREST),
                             (x + 35 + j * 120, 182 + row * 34))
            a, b = [v[1] for v in views]
            metrics.append(dict(angle=angle, raster_pixels=pixels,
                                silhouette_iou=float((a & b).sum() / max(1, (a | b).sum()))))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    return dict(path=str(destination.relative_to(ROOT)), sha256=sha(destination.read_bytes()),
                note="Offline raster review; 16/12/8px native silhouettes plus 2x nearest enlargement. Near inspection intentionally shows LOD simplification; close rendering keeps canonical model.",
                metrics=metrics)


def build(config, review):
    import importlib.metadata
    import numpy as np
    import md2_assets as md2
    manifest = dict(schema=1, config_sha256=sha(CONFIG.read_bytes()),
                    generator_sha256=sha(Path(__file__).read_bytes()),
                    helper_sha256={name: sha(checked_path(name).read_bytes()) for name in HELPERS},
                    source_archives=config["source_archives"],
                    tools={name: importlib.metadata.version(name) for name in ("numpy", "Pillow", "pymeshlab")},
                    policy="Additive distant LODs only; canonical models, skins, frame lattice and gameplay are unchanged.", assets=[])
    for spec, original, canonical, texture in inputs(config):
        source = md2.MD2.read(original, source_compat=True)
        full = md2.MD2.read(canonical)
        if spec["recipe"] == "ammo_box":
            positions, faces, uvs = ammo_box(source, texture, spec["pigment_texel"])
        elif spec["recipe"] == "qem":
            positions, faces, uvs = md2.simplify(source, spec["target_triangles"], config["qem_parameters"])
        else:
            raise ValueError("unknown authored LOD recipe")
        data = md2.encode_static(source, positions, faces, uvs, full.skins)
        before, after = validate_pair(spec, canonical, data)
        # Validate the original lattice as well as the canonical close model.
        result = md2.MD2.read(data)
        if not np.array_equal(result.scales, source.scales) or not np.array_equal(result.translations, source.translations):
            raise ValueError("original pickup coordinate system changed")
        path = checked_path("baseq2/" + spec["lod"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entry = dict(classname=spec["classname"], canonical=spec["canonical"], lod=spec["lod"],
                     source_sha256=spec["source_sha256"], skin=spec["skin"], skin_sha256=spec["skin_sha256"],
                     recipe=spec["recipe"], design=spec["design"], before=before, after=after)
        if review:
            entry["offline_review"] = review_pair(spec, full, result, texture,
                checked_path("build/pi-four-player-20261112/pickup-lods-review/" + spec["classname"] + ".png"))
        manifest["assets"].append(entry)
        print(f"{spec['lod']}: {before['triangles']} -> {after['triangles']} triangles; {after['position_vertices']} positions", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def verify(config):
    manifest = json.loads(MANIFEST.read_text())
    if manifest["config_sha256"] != sha(CONFIG.read_bytes()) or manifest["generator_sha256"] != sha(Path(__file__).read_bytes()):
        raise ValueError("LOD config/generator changed; regenerate audited outputs")
    if manifest["helper_sha256"] != {name: sha(checked_path(name).read_bytes()) for name in HELPERS}:
        raise ValueError("LOD conversion helper changed; regenerate audited outputs")
    entries = {entry["lod"]: entry for entry in manifest["assets"]}
    if len(entries) != 5 or set(entries) != {spec["lod"] for spec in config["assets"]}:
        raise ValueError("expected exactly the five configured pickup LODs")
    for spec, _, canonical, _ in inputs(config):
        lod = checked_path("baseq2/" + spec["lod"]).read_bytes()
        before, after = validate_pair(spec, canonical, lod)
        entry = entries[spec["lod"]]
        if before != entry["before"] or after != entry["after"] or entry["skin_sha256"] != spec["skin_sha256"]:
            raise ValueError("pickup LOD/canonical/skin output drift: " + spec["lod"])
        print("verified " + spec["lod"], flush=True)
    print("Verified five additive pickup LODs, pinned sources, unchanged close models/skins, frame identities and GL topology.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="audit existing outputs using only the Python standard library")
    parser.add_argument("--review", action="store_true", help="generate fixed-camera near/far comparison PNGs while building")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if args.verify:
        verify(config)
    else:
        build(config, args.review)
        verify(config)


if __name__ == "__main__":
    main()
