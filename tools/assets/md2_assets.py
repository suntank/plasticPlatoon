#!/usr/bin/env python3
"""Reproducible static MD2 pickup conversion, validation and visual review.

Read sources from the pinned git commit, never from a previously simplified output.
Geometry changes are deliberately restricted to single-frame models. Wedge UVs,
the original MD2 quantization lattice, coordinate system and frame name survive.
The original sources remain recoverable with `git show SOURCE_COMMIT:path`.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
HEADER = struct.Struct("<17i")
IDENT = 844121161  # IDP2
NORMALS_PATH = "src/client/refresh/constants/anorms.h"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_bytes(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)


def normal_table() -> np.ndarray:
    return np.array([
        [float(v) for v in row.split(",")]
        for row in re.findall(r"\{\s*([\d.eE+\-,\s]+)\}",
                              (ROOT / NORMALS_PATH).read_text())
    ], dtype=np.float64)


@dataclass
class MD2:
    data: bytes
    header: tuple[int, ...]
    skins: list[str]
    faces: np.ndarray
    uvs: np.ndarray
    positions: np.ndarray
    normals: np.ndarray
    scales: np.ndarray
    translations: np.ndarray
    names: list[bytes]
    command_primitives: int
    command_triangles: int

    @classmethod
    def read(cls, data: bytes, *, source_compat: bool = False) -> "MD2":
        if len(data) < HEADER.size:
            raise ValueError("truncated MD2 header")
        h = HEADER.unpack_from(data)
        ident, version, sw, sh, framesize, ns, nv, nt, nf, nc, nframes, os, ot, of, ofr, oc, end = h
        if (ident, version) != (IDENT, 8):
            raise ValueError("expected MD2 IDP2 version 8")
        if not (0 < nv <= 2048 and 0 < nt <= 32767 and 0 < nf <= 4096
                and 0 < nframes <= 512 and 0 <= ns <= 32):
            raise ValueError("MD2 counts exceed supported loader limits")
        if sw <= 0 or not 0 < sh <= 480 or framesize < 40 + 4 * nv:
            raise ValueError("invalid skin dimensions or frame stride")
        sections = [(os, 64 * ns), (ot, 4 * nt), (of, 12 * nf),
                    (ofr, framesize * nframes), (oc, 4 * nc)]
        previous_end = HEADER.size
        for offset, length in sections:
            if offset < previous_end or offset + length > end or end > len(data):
                raise ValueError("invalid MD2 section offset or length")
            previous_end = offset + length
        skins = [data[os + i * 64:os + (i + 1) * 64].split(b"\0")[0].decode("utf-8") for i in range(ns)]
        table = np.frombuffer(data, dtype="<u2", count=nf * 6, offset=of).reshape(nf, 6)
        if table[:, :3].max() >= nv or table[:, 3:].max() >= nt:
            raise ValueError("triangle references outside position/UV arrays")
        positions, normals, scales, translations, names = [], [], [], [], []
        for i in range(nframes):
            off = ofr + i * framesize
            scale = np.array(struct.unpack_from("<3f", data, off))
            trans = np.array(struct.unpack_from("<3f", data, off + 12))
            if not np.isfinite(np.r_[scale, trans]).all() or (scale <= 0).any():
                raise ValueError("nonfinite or nonpositive frame scale")
            verts = np.frombuffer(data, dtype=np.uint8, count=nv * 4, offset=off + 40).reshape(nv, 4)
            if verts[:, 3].max() >= 162:
                raise ValueError("invalid MD2 normal index")
            positions.append(verts[:, :3] * scale + trans)
            normals.append(verts[:, 3].copy())
            scales.append(scale)
            translations.append(trans)
            names.append(data[off + 24:off + 40])
        # Use authoritative GL command UVs, not rounded software-renderer STs.
        faces, uvs = [], []
        cursor, command_end, primitives = oc, oc + nc * 4, 0
        while cursor + 4 <= command_end:
            count = struct.unpack_from("<i", data, cursor)[0]
            cursor += 4
            if count == 0:
                break
            primitives += 1
            if abs(count) < 3 or cursor + abs(count) * 12 > command_end:
                raise ValueError("invalid or truncated strip/fan")
            values = [struct.unpack_from("<ffi", data, cursor + i * 12) for i in range(abs(count))]
            cursor += abs(count) * 12
            for i in range(2, abs(count)):
                ids = (0, i - 1, i) if count < 0 else ((i - 2, i - 1, i) if i % 2 == 0 else (i - 1, i - 2, i))
                faces.append([values[j][2] for j in ids])
                uvs.append([[values[j][0], values[j][1]] for j in ids])
        else:
            raise ValueError("missing GL command terminator")
        if cursor != command_end:
            raise ValueError("GL commands contain uncounted trailing words")
        faces = np.array(faces, dtype=np.int32)
        uvs = np.array(uvs, dtype=np.float64)
        command_triangles = len(faces)
        if faces.min() < 0 or faces.max() >= nv or not np.isfinite(uvs).all():
            raise ValueError("GL commands disagree with MD2 counts")
        canonical = lambda f: min(tuple(f), tuple(np.roll(f, 1)), tuple(np.roll(f, 2)))
        if source_compat and len(faces) > nf:
            # Five original exporters duplicated one or two existing triangles
            # in the GL stream. Only exact oriented position+UV duplicates may
            # be repaired, never silently missing or different topology.
            needed = Counter(map(canonical, table[:, :3]))
            seen, keep = set(), []
            for i, (face, coords) in enumerate(zip(faces, uvs)):
                key = canonical(face)
                corners = tuple((int(v), struct.pack("<2f", *uv)) for v, uv in zip(face, coords))
                signature = min(corners, corners[1:] + corners[:1], corners[2:] + corners[:2])
                if needed[key] > 0:
                    needed[key] -= 1
                    keep.append(i)
                    seen.add(signature)
                elif signature not in seen:
                    raise ValueError("source GL stream contains an unknown extra triangle")
            faces, uvs = faces[keep], uvs[keep]
        if Counter(map(canonical, faces)) != Counter(map(canonical, table[:, :3])):
            raise ValueError("GL command topology/winding differs from triangle table")
        return cls(data, h, skins, faces, uvs, np.array(positions), np.array(normals),
                   np.array(scales), np.array(translations), names, primitives, command_triangles)

    def stats(self) -> dict:
        render_verts = {(int(v), *struct.pack("<2f", *uv)) for f, u in zip(self.faces, self.uvs) for v, uv in zip(f, u)}
        return {
            "triangles": len(self.faces), "position_vertices": self.positions.shape[1],
            "render_vertices": len(render_verts), "frames": len(self.positions),
            "frame_names": [n.split(b"\0")[0].decode("ascii", errors="replace") for n in self.names],
            "skin_references": self.skins, "skin_coordinate_dimensions": list(self.header[2:4]),
            "gl_command_primitives": self.command_primitives,
            "gl_command_triangles": self.command_triangles,
            "duplicate_gl_triangles": self.command_triangles - len(self.faces),
            "unused_bytes_per_frame": self.header[4] - 40 - 4 * self.header[6],
            "file_bytes": len(self.data), "sha256": sha(self.data),
            "bounds": [self.positions.min(axis=(0, 1)).tolist(), self.positions.max(axis=(0, 1)).tolist()]
        }


def gl_strips(faces: np.ndarray, uvs: np.ndarray) -> bytes:
    """Deterministic greedy strips with exact float32 UV seam matching.

    This avoids turning every triangle into a separate legacy GL1 draw. Triangle
    table and GL stream topology/winding are verified by MD2.read afterwards.
    """
    keys, values, triangles = {}, [], []
    for face, coords in zip(faces, uvs):
        triangle = []
        for index, uv in zip(face, coords):
            packed = struct.pack("<ffi", float(uv[0]), float(uv[1]), int(index))
            if packed not in keys:
                keys[packed] = len(values)
                values.append(packed)
            triangle.append(keys[packed])
        triangles.append(tuple(triangle))
    adjacency = defaultdict(list)
    for i, t in enumerate(triangles):
        for j in range(3):
            adjacency[(t[j], t[(j + 1) % 3])].append((i, t[(j + 2) % 3]))
    remaining = set(range(len(triangles)))
    result = bytearray()
    while remaining:
        start = min(remaining)
        best_path, best_ids = None, None
        for rotation in range(3):
            t = triangles[start]
            path = list(t[rotation:] + t[:rotation])
            used = {start}
            while True:
                edge = (path[-1], path[-2]) if len(path) % 2 else (path[-2], path[-1])
                candidates = [(i, v) for i, v in adjacency.get(edge, []) if i in remaining and i not in used]
                if not candidates:
                    break
                i, v = min(candidates)
                used.add(i)
                path.append(v)
            if best_path is None or len(path) > len(best_path):
                best_path, best_ids = path, used
        result += struct.pack("<i", len(best_path))
        for v in best_path:
            result += values[v]
        remaining -= best_ids
    result += struct.pack("<i", 0)
    return bytes(result)


def sample_source_normals(source: MD2, points: np.ndarray) -> np.ndarray:
    """Transfer smooth source normals from the closest original triangle surface.

    Recomputing area-weighted normals on a coarser mesh makes the toy's smooth
    plastic unnecessarily faceted. Barycentric transfer preserves that authored
    shading, then quantizes to Quake's exact 162-normal lookup table.
    """
    triangles = source.positions[0, source.faces]
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    ab, ac = b - a, c - a
    d00, d01, d11 = np.sum(ab * ab, axis=1), np.sum(ab * ac, axis=1), np.sum(ac * ac, axis=1)
    den = d00 * d11 - d01 * d01
    safe_den = np.where(abs(den) > 1e-20, den, 1)
    vectors = normal_table()[source.normals[0, source.faces]]
    result = []
    for p in points:
        ap = p - a
        d20, d21 = np.sum(ap * ab, axis=1), np.sum(ap * ac, axis=1)
        v = (d11 * d20 - d01 * d21) / safe_den
        w = (d00 * d21 - d01 * d20) / safe_den
        bary = np.column_stack([1 - v - w, v, w])
        projection = a + v[:, None] * ab + w[:, None] * ac
        distances = np.sum((projection - p) ** 2, axis=1)
        distances[(bary < 0).any(axis=1) | (abs(den) <= 1e-20)] = np.inf
        for i, j in ((0, 1), (1, 2), (2, 0)):
            start = triangles[:, i]
            edge = triangles[:, j] - start
            t = np.clip(np.sum((p - start) * edge, axis=1) / np.maximum(np.sum(edge * edge, axis=1), 1e-30), 0, 1)
            edge_dist = np.sum((start + t[:, None] * edge - p) ** 2, axis=1)
            closer = edge_dist < distances
            distances[closer] = edge_dist[closer]
            bary[closer] = 0
            bary[closer, i] = 1 - t[closer]
            bary[closer, j] = t[closer]
        nearest = int(np.argmin(distances))
        normal = bary[nearest] @ vectors[nearest]
        normal /= max(np.linalg.norm(normal), 1e-30)
        result.append(normal)
    return np.argmax(np.asarray(result) @ normal_table().T, axis=1).astype(np.uint8)


def encode_static(source: MD2, positions: np.ndarray, faces: np.ndarray,
                  uvs: np.ndarray, skins: list[str]) -> bytes:
    if len(source.positions) != 1:
        raise ValueError("independent simplification of animated models is prohibited")
    # Preserve the exact origin, scale and orientation of the original frame.
    scale, trans = source.scales[0], source.translations[0]
    q = np.clip(np.rint((positions - trans) / scale), 0, 255).astype(np.uint8)
    positions = q.astype(np.float64) * scale + trans
    # Quantization can collapse exceptionally tiny triangles. Remove them before
    # generating normals, the triangle table and commands from the same topology.
    crossed = np.cross(positions[faces[:, 1]] - positions[faces[:, 0]],
                       positions[faces[:, 2]] - positions[faces[:, 0]])
    valid = np.linalg.norm(crossed, axis=1) > 1e-12
    faces, uvs, crossed = faces[valid], uvs[valid], crossed[valid]
    used = np.unique(faces)
    remap = np.full(len(q), -1, dtype=np.int32)
    remap[used] = np.arange(len(used))
    faces, q = remap[faces], q[used]
    normals = sample_source_normals(source, positions[used])
    # Keep logical MD2 skin dimensions independent of replacement PNG resolution.
    # GL UVs remain float32; the ST table is the nearest software-renderer texel.
    sw, sh = source.header[2:4]
    uvkeys, st, stfaces = {}, [], []
    for coords in uvs:
        indices = []
        for uv in coords:
            key = tuple(np.rint(uv * [sw, sh] - 0.5).astype(int))
            if not all(-32768 <= x <= 32767 for x in key):
                raise ValueError("software UV coordinate overflow")
            if key not in uvkeys:
                uvkeys[key] = len(st)
                st.append(key)
            indices.append(uvkeys[key])
        stfaces.append(indices)
    skins_raw = b""
    for skin in skins:
        raw = skin.encode("utf-8")
        if len(raw) >= 64:
            raise ValueError("skin reference exceeds MD2's 63-byte limit")
        skins_raw += raw.ljust(64, b"\0")
    uv_raw = np.asarray(st, dtype="<i2").tobytes()
    triangle_raw = np.column_stack([faces, stfaces]).astype("<u2").tobytes()
    vertex_raw = np.column_stack([q, normals]).astype(np.uint8).tobytes()
    frame_raw = struct.pack("<6f", *scale, *trans) + source.names[0] + vertex_raw
    cmd_raw = gl_strips(faces, uvs)
    offsets, cursor = [], HEADER.size
    for section in (skins_raw, uv_raw, triangle_raw, frame_raw, cmd_raw):
        offsets.append(cursor)
        cursor += len(section)
    header = HEADER.pack(IDENT, 8, sw, sh, len(frame_raw), len(skins), len(q),
                         len(st), len(faces), len(cmd_raw) // 4, 1, *offsets, cursor)
    data = header + skins_raw + uv_raw + triangle_raw + frame_raw + cmd_raw
    result = MD2.read(data)
    if result.names != source.names or not np.array_equal(result.scales, source.scales) or not np.array_equal(result.translations, source.translations):
        raise AssertionError("frame identity or quantization lattice changed")
    return data


def simplify(model: MD2, target: int, params: dict) -> tuple:
    if len(model.positions) != 1:
        raise ValueError("only single-frame pickups may be simplified")
    import pymeshlab
    meshes = pymeshlab.MeshSet()
    # OBJ+MTL import supplies per-wedge material indices. PyMeshLab's ndarray
    # constructor leaves them unset, which texture-aware decimation rejects.
    # Quadric texture error uses UV coordinates, not image pixels.
    with tempfile.TemporaryDirectory(prefix="pp-md2-") as directory:
        path = Path(directory)
        Image.new("RGB", (1, 1), "white").save(path / "slot.png")
        (path / "input.mtl").write_text("newmtl skin\nmap_Kd slot.png\n")
        lines = ["mtllib input.mtl"]
        lines += ["v %.17g %.17g %.17g" % tuple(p) for p in model.positions[0]]
        lines += ["vt %.17g %.17g" % tuple(uv) for uv in model.uvs.reshape(-1, 2)]
        lines += ["usemtl skin"]
        lines += ["f " + " ".join(f"{int(v) + 1}/{i * 3 + j + 1}" for j, v in enumerate(f))
                  for i, f in enumerate(model.faces)]
        (path / "input.obj").write_text("\n".join(lines) + "\n")
        meshes.load_new_mesh(str(path / "input.obj"))
        if not np.allclose(meshes.current_mesh().wedge_tex_coord_matrix(), model.uvs.reshape(-1, 2), atol=1e-7):
            raise ValueError("MeshLab OBJ bridge changed UVs")
        meshes.apply_filter("meshing_decimation_quadric_edge_collapse_with_texture",
                            targetfacenum=target, **params)
        mesh = meshes.current_mesh()
        mesh.compact()
        return mesh.vertex_matrix(), mesh.face_matrix(), mesh.wedge_tex_coord_matrix().reshape(-1, 3, 2)


def texture_stats(data: bytes) -> dict:
    image = Image.open(io.BytesIO(data))
    w, h = image.size
    # Engine upload expands RGB and RGBA to four bytes per texel. PNG compression
    # changes disk/download size, never this decoded memory estimate.
    base = w * h * 4
    mip = 0
    while True:
        mip += w * h * 4
        if w == h == 1:
            break
        w, h = max(1, w // 2), max(1, h // 2)
    return {"dimensions": list(image.size), "mode": image.mode, "file_bytes": len(data),
            "decoded_rgba_bytes": base, "rgba_mip_chain_bytes": mip, "sha256": sha(data)}


def resize_texture(data: bytes, maximum: int) -> bytes:
    image = Image.open(io.BytesIO(data))
    if max(image.size) <= maximum:
        return data
    size = tuple(max(1, round(x * maximum / max(image.size))) for x in image.size)
    # RGBA resize uses Pillow's premultiplied-alpha Lanczos path.
    image = image.resize(size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()


def raster(model: MD2, texture: Image.Image, angle: float, size: int,
           framing: tuple, elevation: float = 22.5) -> tuple[Image.Image, np.ndarray]:
    """Small deterministic orthographic asset review rasterizer, not a game capture.

    Uses MD2 GL float UVs and indexed normals, bilinear texels, z-buffering and a
    fixed light. Identical camera/framing/light for before/after; no auto-refitting.
    """
    angle, elevation = math.radians(angle), math.radians(elevation)
    forward = np.array([math.cos(angle) * math.cos(elevation), math.sin(angle) * math.cos(elevation), math.sin(elevation)])
    right = np.array([-math.sin(angle), math.cos(angle), 0])
    up = np.cross(forward, right)
    centre, radius = framing
    pos = model.positions[0] - centre
    coords = np.column_stack([pos @ right, -(pos @ up), pos @ forward])
    coords[:, :2] = coords[:, :2] / radius * size * 0.43 + size / 2
    zbuffer = np.full((size, size), -np.inf)
    colour = np.zeros((size, size, 3), dtype=np.float64) + [30, 34, 40]
    tex = np.array(texture.convert("RGBA"), dtype=np.float64)
    height, width = tex.shape[:2]
    vn = normal_table()[model.normals[0]]
    light = np.array([-.4, -.5, .85]); light /= np.linalg.norm(light)
    light_values = .45 + .55 * np.maximum(vn @ light, 0)
    for face, uv in zip(model.faces, model.uvs):
        points = coords[face]
        x0, y0 = np.maximum(np.floor(points[:, :2].min(axis=0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(points[:, :2].max(axis=0)).astype(int), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        x, y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        a, b, c = points
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        w1 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        z = w0 * a[2] + w1 * b[2] + w2 * c[2]
        region = np.s_[y0:y1 + 1, x0:x1 + 1]
        inside &= z > zbuffer[region]
        if not inside.any():
            continue
        u = (w0 * uv[0, 0] + w1 * uv[1, 0] + w2 * uv[2, 0]) * width - .5
        v = (w0 * uv[0, 1] + w1 * uv[1, 1] + w2 * uv[2, 1]) * height - .5
        # MD2 skins repeat, matching the renderer's GL_REPEAT upload policy.
        ix, iy = np.floor(u).astype(int), np.floor(v).astype(int)
        fx, fy = (u - ix)[..., None], (v - iy)[..., None]
        rgba = ((tex[iy % height, ix % width] * (1 - fx) + tex[iy % height, (ix + 1) % width] * fx) * (1 - fy)
                + (tex[(iy + 1) % height, ix % width] * (1 - fx) + tex[(iy + 1) % height, (ix + 1) % width] * fx) * fy)
        shade = w0 * light_values[face[0]] + w1 * light_values[face[1]] + w2 * light_values[face[2]]
        # Opaque alias models use texture RGB, matching their normal render path.
        values = rgba[..., :3] * shade[..., None]
        colour[region][inside] = values[inside]
        zbuffer[region][inside] = z[inside]
    return Image.fromarray(np.clip(np.rint(colour), 0, 255).astype(np.uint8)), np.isfinite(zbuffer)


def review(source: MD2, result: MD2, before: bytes, after: bytes, path: Path, title: str) -> dict:
    textures = [Image.open(io.BytesIO(before)), Image.open(io.BytesIO(after))]
    p = source.positions[0]
    centre = (p.min(axis=0) + p.max(axis=0)) * .5
    radius = np.linalg.norm(p - centre, axis=1).max()
    framing = (centre, radius)
    angles = (25, 115, 205, 295)
    canvas = Image.new("RGB", (4 * 240, 2 * 330 + 55), (22, 25, 30))
    draw = ImageDraw.Draw(canvas)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 15) if font_path.exists() else ImageFont.load_default()
    smallfont = ImageFont.truetype(str(font_path), 12) if font_path.exists() else ImageFont.load_default()
    draw.text((14, 10), title, font=font, fill="white")
    draw.text((14, 32), "Same camera, framing and light. Top: source. Bottom: optimized. 48 px + 224 px inspection.", font=smallfont, fill="#c2c8d0")
    masks = [[], []]
    for row, model in enumerate((source, result)):
        for col, angle in enumerate(angles):
            high, _ = raster(model, textures[row], angle, 448, framing)
            low, mask = raster(model, textures[row], angle, 48, framing)
            masks[row].append(mask)
            x, y = col * 240 + 8, row * 330 + 60
            canvas.paste(high.resize((224, 224), Image.Resampling.LANCZOS), (x, y))
            canvas.paste(low, (x, y + 231))
            draw.text((x + 58, y + 232), f"{angle} degrees", font=smallfont, fill="#c2c8d0")
            draw.text((x + 58, y + 250), f"{len(model.faces):,} triangles", font=smallfont, fill="white")
            draw.text((x, y + 286), f"Texture {textures[row].width} x {textures[row].height}", font=smallfont, fill="#c2c8d0")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, optimize=False)
    overlaps = [float((a & b).sum() / max(1, (a | b).sum())) for a, b in zip(*masks)]
    return {"comparison": str(path.relative_to(ROOT)), "comparison_sha256": sha(path.read_bytes()), "inspection_pixels": 224,
            "coverage_pixels": 48, "angles_degrees": list(angles),
            "silhouette_iou_at_48px": overlaps,
            "note": "Offline rasterizer review; silhouette IoU is a screening metric, not visual equivalence proof."}


def build(args) -> None:
    config = json.loads(args.config.read_text())
    ref = config["source_commit"]
    subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], cwd=ROOT, check=True)
    if args.map:
        map_data = args.map.read_bytes()
        if sha(map_data) != config["source_map_sha256"]:
            raise ValueError("map hash differs from the inventoried supplied sandbox source")
        counts = Counter(re.findall(r'"classname"\s+"([^"]+)"', map_data.decode("utf-8")))
        for spec in config["assets"]:
            if counts[spec["classname"]] != spec["instances"]:
                raise ValueError(f"instance count changed for {spec['classname']}")
    manifest = {
        "schema": 1, "source_commit": ref, "source_map_sha256": config["source_map_sha256"],
        "tools": {"python": sys.version.split()[0], **{name: importlib.metadata.version(name) for name in ("numpy", "Pillow", "pymeshlab")}},
        "algorithm": config["algorithm"], "parameters": config["parameters"],
        "normal_policy": "closest source surface, barycentric normal transfer, nearest of 162 MD2 normals",
        "converter_sha256": sha(Path(__file__).read_bytes()), "assets": []
    }
    selected = [s for s in config["assets"] if not args.only or args.only in s["model"]]
    for spec in selected:
        path = "baseq2/" + spec["model"]
        source = MD2.read(source_bytes(ref, path), source_compat=True)
        texture = source_bytes(ref, "baseq2/" + source.skins[0])
        vertices, faces, uv = simplify(source, spec["triangles"], config["parameters"])
        skin = spec.get("output_skin", source.skins[0])
        # Invalid exporter-added extra skin slots are replaced with the real skin,
        # preserving slot count while making every registered slot loadable.
        skin_refs = [skin] * len(source.skins)
        data = encode_static(source, vertices, faces, uv, skin_refs)
        result = MD2.read(data)
        new_texture = resize_texture(texture, spec["texture_size"])
        record = {"model": spec["model"], "classname": spec["classname"],
                  "sandbox_instances": spec["instances"], "target_triangles": spec["triangles"],
                  "before": source.stats(), "after": result.stats(),
                  "texture_before": {"path": source.skins[0], **texture_stats(texture)},
                  "texture_after": {"path": skin, **texture_stats(new_texture)}}
        if args.write:
            (ROOT / path).write_bytes(data)
            (ROOT / "baseq2" / skin).write_bytes(new_texture)
        if args.review:
            image_path = ROOT / "doc/performance/asset-comparisons" / (spec["model"].replace("/tris.md2", "").replace("/", "_") + ".png")
            record["visual_review"] = review(source, result, texture, new_texture, image_path, spec["model"])
        manifest["assets"].append(record)
        print(f"{spec['model']}: {len(source.faces)} -> {len(result.faces)} triangles; "
              f"{record['texture_before']['dimensions']} -> {record['texture_after']['dimensions']}", flush=True)
    manifest["totals"] = {
        "sandbox_instances": sum(a["sandbox_instances"] for a in manifest["assets"]),
        "triangles_before": sum(a["before"]["triangles"] for a in manifest["assets"]),
        "triangles_after": sum(a["after"]["triangles"] for a in manifest["assets"]),
        "instance_weighted_triangles_before": sum(a["before"]["triangles"] * a["sandbox_instances"] for a in manifest["assets"]),
        "instance_weighted_triangles_after": sum(a["after"]["triangles"] * a["sandbox_instances"] for a in manifest["assets"])
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")


def verify(args) -> None:
    manifest = json.loads(args.manifest.read_text())
    if sha(Path(__file__).read_bytes()) != manifest["converter_sha256"]:
        raise ValueError("converter changed; regenerate the manifest with the current tool")
    for entry in manifest["assets"]:
        path = ROOT / "baseq2" / entry["model"]
        model = MD2.read(path.read_bytes())
        if model.stats() != entry["after"]:
            raise ValueError(f"MD2 output drift: {entry['model']}")
        original = source_bytes(manifest["source_commit"], "baseq2/" + entry["model"])
        if len(original) != entry["before"]["file_bytes"]:
            raise ValueError("source length changed")
        if sha(original) != entry["before"]["sha256"]:
            raise ValueError("source hash changed")
        original_texture = source_bytes(manifest["source_commit"], "baseq2/" + entry["texture_before"]["path"])
        if sha(original_texture) != entry["texture_before"]["sha256"]:
            raise ValueError("source texture hash changed")
        tex = entry["texture_after"]
        actual = texture_stats((ROOT / "baseq2" / tex["path"]).read_bytes())
        if actual != {k: v for k, v in tex.items() if k != "path"}:
            raise ValueError(f"texture output drift: {tex['path']}")
        # No coordinate-system change or altered frame compression is permitted.
        old = MD2.read(original, source_compat=True)
        assert np.array_equal(old.scales, model.scales)
        assert np.array_equal(old.translations, model.translations)
        assert old.names == model.names
        if "visual_review" in entry:
            review_data = entry["visual_review"]
            if sha((ROOT / review_data["comparison"]).read_bytes()) != review_data["comparison_sha256"]:
                raise ValueError("comparison image drift")
        print(f"verified {entry['model']}")
    print(f"Validated {len(manifest['assets'])} models, textures, source hashes and frame identities.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--manifest", type=Path, default=ROOT / "doc/performance/assets-manifest.json")
    b = sub.add_parser("build", parents=[common])
    b.add_argument("--config", type=Path, default=Path(__file__).with_name("pickups.json"))
    b.add_argument("--map", type=Path)
    b.add_argument("--only", help="model path substring for a review experiment")
    b.add_argument("--write", action="store_true", help="install validated MD2/PNG output in baseq2")
    b.add_argument("--review", action="store_true", help="render comparable four-angle inspection sheets")
    b.set_defaults(func=build)
    v = sub.add_parser("verify", parents=[common]); v.set_defaults(func=verify)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
