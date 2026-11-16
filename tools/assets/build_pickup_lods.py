#!/usr/bin/env python3
"""Build five optional distant pickup MD2s without rewriting close models/skins.

Generation needs the pinned tools/assets requirements. --verify is deliberately
standard-library-only so normal asset builds and the Pi can audit shipped LODs.
Ammo, health and armor LODs use their exact authored low-poly meshes. Historical
reduction recipes remain available only for older audited configurations.
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
AUTHORED_RECIPES = {"authored_ammo": ("ammo", "build_ammo"),
                    "authored_health": ("health", "build_health"),
                    "authored_armor": ("armor", "build_armor")}


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
    owned = authored_inventories(config)
    for spec in config["assets"]:
        canonical = checked_path("baseq2/" + spec["canonical"]).read_bytes()
        texture = checked_path("baseq2/" + spec["skin"]).read_bytes()
        if sha(canonical) != spec["canonical_sha256"] or sha(texture) != spec["skin_sha256"]:
            raise ValueError("canonical pickup or texture changed: " + spec["canonical"])
        if spec["recipe"] in AUTHORED_RECIPES:
            for name in (spec["canonical"], spec["lod"], spec["skin"]):
                if name not in owned[spec["recipe"]]:
                    raise ValueError("authored owner omits configured LOD input/output: " + name)
            original = canonical
        else:
            with zipfile.ZipFile(io.BytesIO(archives[spec["source_archive"]])) as archive:
                original = archive.read("baseq2/" + spec["canonical"])
            if sha(original) != spec["source_sha256"]:
                raise ValueError("pinned original pickup changed: " + spec["canonical"])
        if spec["lod"] != spec["canonical"].replace("/tris.md2", "/lod1.md2"):
            raise ValueError("LOD output must be an additive sibling of tris.md2")
        yield spec, original, canonical, texture


def owner_inventory(config, recipe):
    """Audit the owning generator and outputs without importing its toolchain."""
    kind, _ = AUTHORED_RECIPES[recipe]
    owner = config[recipe]
    manifest = json.loads(checked_path(owner["manifest"]).read_text())
    if manifest["generator"] != owner["generator"]:
        raise ValueError("unexpected authored " + kind + " generator")
    for name, expected in manifest["dependencies_sha256"].items():
        if sha(checked_path("tools/assets/" + name).read_bytes()) != expected:
            raise ValueError(kind + " generator changed; run " + owner["generator"])
    inventory = {entry["path"]: entry for entry in manifest["files"]}
    ownership = json.loads(checked_path("tools/assets/platoon.json").read_text())["procedural_replacements"][kind]
    if len(inventory) != len(manifest["files"]) or set(ownership["models"] + ownership["textures"]) != set(inventory):
        raise ValueError(kind + " owner manifest differs from registered outputs")
    for name, entry in inventory.items():
        raw = checked_path("baseq2/" + name).read_bytes()
        if sha(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
            raise ValueError("stale authored " + kind + " output: " + name)
    return inventory


def ammo_inventory(config):
    return owner_inventory(config, "authored_ammo")


def authored_inventories(config):
    recipes = {spec["recipe"] for spec in config["assets"]} & AUTHORED_RECIPES.keys()
    return {recipe: ammo_inventory(config) if recipe == "authored_ammo" else owner_inventory(config, recipe)
            for recipe in recipes}


def validate_pair(spec, canonical, lod):
    before, after = decode(canonical), decode(lod)
    for key in ("skins", "skin_dimensions", "scale", "translation", "frame_name_hex", "frames"):
        if before[key] != after[key]:
            raise ValueError("close/LOD frame identity or skin mismatch: " + key)
    if spec["recipe"] in AUTHORED_RECIPES:
        if canonical != lod:
            raise ValueError("authored pickup must keep the exact close mesh at distance")
        if not 0 < after["triangles"] <= spec["target_triangles"]:
            raise ValueError("authored pickup exceeds its triangle budget")
    elif not 100 <= after["triangles"] <= 200 or after["triangles"] > spec["target_triangles"]:
        raise ValueError("distant pickup exceeds its authored 100-200 triangle budget")
    for axis in range(3):
        extent = before["bounds"][1][axis] - before["bounds"][0][axis]
        if after["bounds"][0][axis] < before["bounds"][0][axis] - extent * .05 or after["bounds"][1][axis] > before["bounds"][1][axis] + extent * .05:
            raise ValueError("LOD grows beyond the original pickup bounds")
    return before, after


def record(spec, canonical, lod):
    before, after = validate_pair(spec, canonical, lod)
    entry = dict(classname=spec["classname"], canonical=spec["canonical"], lod=spec["lod"],
                 skin=spec["skin"], skin_sha256=spec["skin_sha256"], recipe=spec["recipe"],
                 design=spec["design"], before=before, after=after)
    if spec["recipe"] not in AUTHORED_RECIPES:
        entry["source_sha256"] = spec["source_sha256"]
    else:
        entry["owner_manifest"] = "tools/assets/" + AUTHORED_RECIPES[spec["recipe"]][0] + "-manifest.json"
    return entry


def manifest_header(config, tools):
    return dict(schema=1, config_sha256=sha(CONFIG.read_bytes()),
                generator_sha256=sha(Path(__file__).read_bytes()),
                helper_sha256={name: sha(checked_path(name).read_bytes()) for name in HELPERS},
                source_archives=config["source_archives"], tools=tools,
                policy="Authored ammo, health and armor retain identical close/distant meshes. Skins, frame identity and gameplay are preserved.", assets=[])


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
    packages = ("numpy", "Pillow") + (("pymeshlab",) if any(spec["recipe"] == "qem" for spec in config["assets"]) else ())
    manifest = manifest_header(config, {name: importlib.metadata.version(name) for name in packages})
    authored = {}
    for spec, original, canonical, texture in inputs(config):
        source = md2.MD2.read(original, source_compat=True)
        full = md2.MD2.read(canonical)
        if spec["recipe"] in AUTHORED_RECIPES:
            recipe = spec["recipe"]
            if recipe not in authored:
                import importlib
                authored[recipe], _ = importlib.import_module(AUTHORED_RECIPES[recipe][1]).build_assets()
            if authored[recipe][spec["canonical"]] != canonical:
                raise ValueError("regenerate authored pickups before their LOD manifest")
            data = authored[recipe][spec["lod"]]
        elif spec["recipe"] == "ammo_box":
            positions, faces, uvs = ammo_box(source, texture, spec["pigment_texel"])
        elif spec["recipe"] == "qem":
            positions, faces, uvs = md2.simplify(source, spec["target_triangles"], config["qem_parameters"])
        else:
            raise ValueError("unknown authored LOD recipe")
        if spec["recipe"] not in AUTHORED_RECIPES:
            data = md2.encode_static(source, positions, faces, uvs, full.skins)
        entry = record(spec, canonical, data)
        before, after = entry["before"], entry["after"]
        # Validate the original lattice as well as the canonical close model.
        result = md2.MD2.read(data)
        if not np.array_equal(result.scales, source.scales) or not np.array_equal(result.translations, source.translations):
            raise ValueError("original pickup coordinate system changed")
        path = checked_path("baseq2/" + spec["lod"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if review:
            entry["offline_review"] = review_pair(spec, full, result, texture,
                checked_path("build/pi-four-player-20261112/pickup-lods-review/" + spec["classname"] + ".png"))
        manifest["assets"].append(entry)
        print(f"{spec['lod']}: {before['triangles']} -> {after['triangles']} triangles; {after['position_vertices']} positions", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def refresh_authored(config):
    """Register owned pickups while requiring unchanged legacy LOD bytes.

    This audit-only operation needs no reduction tools. It cannot bless a new
    legacy shape, skin, source or recipe; those need a full generation.
    """
    previous = json.loads(MANIFEST.read_text())
    # The owner has already authenticated generator dependencies and every
    # output. Adopt only authored hash pins, never legacy sources or budgets.
    inventories = authored_inventories(config)
    config = json.loads(json.dumps(config))
    for spec in config["assets"]:
        if spec["recipe"] in AUTHORED_RECIPES:
            inventory = inventories[spec["recipe"]]
            spec["canonical_sha256"] = inventory[spec["canonical"]]["sha256"]
            spec["skin_sha256"] = inventory[spec["skin"]]["sha256"]
    old = {entry["lod"]: entry for entry in previous["assets"]}
    expected = {spec["lod"] for spec in config["assets"]}
    if set(old) != expected or previous["source_archives"] != config["source_archives"]:
        raise ValueError("authored refresh cannot change the legacy LOD inventory or sources")
    records = []
    for spec, _, canonical, _ in inputs(config):
        lod = checked_path("baseq2/" + spec["lod"]).read_bytes()
        entry = record(spec, canonical, lod)
        if spec["recipe"] not in AUTHORED_RECIPES:
            if any(old[spec["lod"]].get(key) != value for key, value in entry.items()):
                raise ValueError("authored refresh cannot change legacy LOD: " + spec["lod"])
            entry = old[spec["lod"]]
        records.append(entry)
    CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    tools = {name: version for name, version in previous["tools"].items()
             if name != "pymeshlab" or any(spec["recipe"] == "qem" for spec in config["assets"])}
    manifest = manifest_header(config, tools)
    manifest["assets"] = records
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
        expected = record(spec, canonical, lod)
        entry = entries[spec["lod"]]
        if any(entry.get(key) != value for key, value in expected.items()):
            raise ValueError("pickup LOD/canonical/skin output drift: " + spec["lod"])
        print("verified " + spec["lod"], flush=True)
    print("Verified five pickup LODs, authored ammo/health/armor identity, pinned sources, skins, frame identities and GL topology.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="audit existing outputs using only the Python standard library")
    mode.add_argument("--refresh-authored", action="store_true", help="register owner-verified authored outputs and preserve any legacy LODs")
    parser.add_argument("--review", action="store_true", help="generate fixed-camera near/far comparison PNGs while building")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if args.verify:
        verify(config)
    elif args.refresh_authored:
        refresh_authored(config)
        verify(json.loads(CONFIG.read_text()))
    else:
        build(config, args.review)
        verify(config)


if __name__ == "__main__":
    main()
