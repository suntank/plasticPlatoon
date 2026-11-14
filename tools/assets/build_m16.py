#!/usr/bin/env python3
"""Build the simple-shape M16 and preserve the project's authored weapon poses.

Geometry is authored by m16_geometry.py. Existing archived weapons supply only
coordinate-system/animation references, never replacement topology. All new
models share one small diffuse atlas and keep the runtime's existing asset paths.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw

from asset_sources import source_bytes
from md2_assets import HEADER, IDENT, MD2, gl_strips, normal_table
from md2_animation import _st_table

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "baseq2"
MANIFEST = ROOT / "tools/assets/m16-manifest.json"
ORIGINALS = ROOT / "tools/assets/platoon-originals.json"
MATERIALS = ("plastic", "dark", "edge", "grip", "handguard", "magazine",
             "receiver", "bore", "hand", "cuff", "fingers", "palm")
COLORS = ((86, 123, 44), (48, 75, 29), (104, 144, 58), (67, 98, 36),
          (77, 111, 40), (68, 101, 37), (83, 119, 43), (10, 18, 8),
          (90, 126, 47), (48, 75, 29), (84, 118, 43), (70, 103, 38))
ATLAS_SIZE = 256
# The shipped soldier and original M16 have a plastic-value median of 43.
# The readable authoring palette above has median 118. Keep this conversion
# local to the new atlas: team-color variants preserve value before lighting,
# so a bright authoring atlas otherwise clips to neon green in the renderer.
ALBEDO_SCALE = 43.0 / 118.0
MODELS = {
    "models/weapons/g_machn/tris.md2": "pickup",
    "models/weapons/v_machn/tris.md2": "view",
    "players/soldier/w_machinegun.md2": "player",
    "players/soldier/weapon.md2": "player",
    "models/monsters/soldier/weapon_machinegun.md2": "enemy",
}
TEXTURES = ("models/weapons/g_machn/skin.png", "models/weapons/g_machn/skin_pickup.png",
            "models/weapons/v_machn/skin.png")
# These measured counts describe the actual shipped decimated files at review.
# Pose inputs come from the checked local archive, independently of Git history.
BASELINE_COUNTS = {
    "pickup": {"triangles": 800, "position_vertices": 396, "frames": 1, "file_bytes": 34752},
    "view": {"triangles": 1400, "position_vertices": 696, "frames": 1, "file_bytes": 57440},
    "player": {"triangles": 1398, "position_vertices": 695, "frames": 198, "file_bytes": 613672},
    "enemy": {"triangles": 1444, "position_vertices": 718, "frames": 475, "file_bytes": 1439876},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def texture_bytes():
    """A 4x4 atlas: modeled silhouette, painted grooves and finger divisions."""
    atlas = Image.new("RGB", (ATLAS_SIZE, ATLAS_SIZE), COLORS[0])
    for index, rgb in enumerate(COLORS):
        tile = Image.new("RGB", (64, 64))
        pixels = tile.load()
        for y in range(64):
            for x in range(64):
                shading = .93 + .10 * (1 - y / 63) + .025 * math.sin(x * math.pi / 63)
                pixels[x, y] = tuple(round(c * shading) for c in rgb)
        d = ImageDraw.Draw(tile)
        shadow = tuple(round(c * .72) for c in rgb)
        highlight = tuple(min(255, round(c * 1.15)) for c in rgb)
        if index == 3:  # Fine grip texture costs no additional geometry.
            for y in range(9, 59, 7):
                d.line((6, y, 57, y), fill=shadow, width=1)
        elif index == 4:
            for x in range(10, 58, 7):
                d.line((x, 8, x, 56), fill=shadow, width=2)
                d.line((x + 2, 8, x + 2, 56), fill=highlight, width=1)
        elif index == 5:
            for x in (16, 28, 40, 52):
                d.line((x, 8, x, 57), fill=shadow, width=2)
                d.line((x + 2, 8, x + 2, 57), fill=highlight, width=1)
        elif index == 6:
            d.rectangle((11, 17, 52, 44), outline=shadow, width=1)
            d.line((12, 16, 52, 16), fill=highlight)
            for x, y in ((15, 47), (48, 47), (25, 12)):
                d.ellipse((x - 1, y - 1, x + 1, y + 1), fill=shadow)
        elif index == 7:
            d.rectangle((0, 0, 63, 63), fill=rgb)
        elif index in (10, 11):
            # Mitten mesh: the diffuse art supplies finger separations.
            for y in (20, 32, 44):
                d.line((12, y, 54, y + 1), fill=shadow, width=2)
                d.line((13, y + 2, 52, y + 3), fill=highlight, width=1)
        atlas.paste(tile, (index % 4 * 64, index // 4 * 64))
    atlas = atlas.point([round(value * ALBEDO_SCALE) for value in range(256)] * 3)
    out = io.BytesIO()
    atlas.save(out, format="PNG", compress_level=9)
    return out.getvalue()


def atlas_uvs(mesh):
    local = np.asarray(mesh["uvs"], dtype=np.float64)
    if local.shape != (len(mesh["faces"]), 3, 2) or not np.isfinite(local).all():
        raise ValueError("mesh needs finite local triangle-corner UVs")
    if local.min() < -1e-8 or local.max() > 1 + 1e-8:
        raise ValueError("local atlas UVs must be in [0, 1]")
    ids = np.array([MATERIALS.index(name) for name in mesh["materials"]])
    origins = np.column_stack((ids % 4, ids // 4)) * 64
    return (origins[:, None, :] + 4.5 + np.clip(local, 0, 1) * 55) / ATLAS_SIZE


def vertex_normals(vertices, faces):
    """Area-weighted normals, with hard edges authored as split vertices."""
    crossed = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]],
                       vertices[faces[:, 2]] - vertices[faces[:, 0]])
    result = np.zeros_like(vertices, dtype=np.float64)
    for corner in range(3):
        np.add.at(result, faces[:, corner], crossed)
    lengths = np.linalg.norm(result, axis=1)
    if np.any(lengths < 1e-12):
        raise ValueError("unused vertices or canceling geometric normals")
    return result / lengths[:, None]


def placement(role):
    """Uniform-scale transforms measured against the reviewed original meshes.

    Matrices use row vectors: new_point = canonical_point @ matrix + offset.
    Pickup faces -X; player/enemy rifle has the original slight holding yaw.
    """
    if role == "pickup":
        scale, degrees = (36.09209579229355 + 36.38828659057617) / 100, 180.
        offset = np.array([36.09209579229355, -.25, 20.35])
    elif role == "view":
        scale, degrees = (56.49812462925911 + 9.061456233263016) / 100, 0.
        offset = np.array([-9.061456233263016, -7.95, -5.77833774])
    else:
        degrees = 1.4
        scale = (31.443956270813942 + .43617725372314453) / (100 * math.cos(math.radians(degrees)))
        offset = np.array([-.43617725372314453, -4.5 - 100 * scale * math.sin(math.radians(degrees)), 15.68863792])
    angle = math.radians(degrees)
    rotation = np.array([[math.cos(angle), math.sin(angle), 0.],
                         [-math.sin(angle), math.cos(angle), 0.], [0., 0., 1.]])
    return rotation * scale, offset, rotation


def rigid_transforms(source):
    reference = source.positions[0]
    center = reference.mean(axis=0)
    base = reference - center
    rotations, offsets, errors = [], [], []
    for pose in source.positions:
        target = pose.mean(axis=0)
        u, _, vt = np.linalg.svd(base.T @ (pose - target))
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u[:, -1] *= -1
            rotation = u @ vt
        offset = target - center @ rotation
        errors.append(float(np.sqrt(np.mean(np.sum((reference @ rotation + offset - pose) ** 2, axis=1)))))
        rotations.append(rotation)
        offsets.append(offset)
    if max(errors) > .12:
        raise ValueError("source rifle is not rigid enough for reviewed pose transfer")
    return np.asarray(rotations), np.asarray(offsets), np.asarray(errors)


def encode_md2(positions, normals, ccw_faces, uvs, skins, names):
    """Encode a compact MD2, converting outward CCW to Quake front-cull winding."""
    positions = np.asarray(positions, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    ccw_faces = np.asarray(ccw_faces, dtype=np.int32)
    if not 0 < positions.shape[1] <= 2048 or not 0 < len(names) <= 512:
        raise ValueError("MD2 vertex/frame budget exceeded")
    if positions.shape != normals.shape or positions.shape[0] != len(names):
        raise ValueError("pose, normal and frame-name dimensions disagree")
    faces, uvs = ccw_faces[:, [0, 2, 1]], np.asarray(uvs)[:, [0, 2, 1]]
    st, st_faces = _st_table(uvs, (ATLAS_SIZE, ATLAS_SIZE))
    triangle_data = np.column_stack((faces, st_faces)).astype("<u2").tobytes()
    skin_data = bytearray()
    for skin in skins:
        value = skin.encode("ascii")
        if len(value) >= 64 or b"\0" in value:
            raise ValueError("invalid MD2 skin path")
        skin_data += value.ljust(64, b"\0")
    frames, worst_error, minimum_area = bytearray(), 0., float("inf")
    normal_lookup = normal_table()
    for frame_number, (points, directions, name) in enumerate(zip(positions, normals, names)):
        minimum = points.min(axis=0).astype("<f4")
        scale = np.maximum((points.max(axis=0) - minimum) / 255, 1e-8).astype("<f4")
        packed = np.clip(np.rint((points - minimum) / scale), 0, 255).astype(np.uint8)
        restored = packed.astype(np.float64) * scale + minimum
        triangle_points = restored[ccw_faces]
        crossed = np.cross(triangle_points[:, 1] - triangle_points[:, 0], triangle_points[:, 2] - triangle_points[:, 0])
        areas = np.linalg.norm(crossed, axis=1)
        minimum_area = min(minimum_area, float(areas.min()))
        if np.any(areas < 1e-10):
            raise ValueError(f"MD2 quantization collapsed geometry in frame {frame_number}, triangles {np.flatnonzero(areas < 1e-10).tolist()}; enlarge the thin feature")
        ideal = np.cross(points[ccw_faces[:, 1]] - points[ccw_faces[:, 0]], points[ccw_faces[:, 2]] - points[ccw_faces[:, 0]])
        if np.any(np.sum(crossed * ideal, axis=1) <= 0):
            raise ValueError(f"MD2 quantization inverted a triangle in frame {frame_number}: {np.flatnonzero(np.sum(crossed * ideal, axis=1) <= 0).tolist()}")
        # Symmetric faces can be equidistant from two MD2 normals. BLAS
        # rounding differs across CPUs; choose the first tied table entry.
        scores = directions @ normal_lookup.T
        tied = scores >= scores.max(axis=1, keepdims=True) - 1e-12
        normal_ids = np.argmax(tied, axis=1).astype(np.uint8)
        packed = np.column_stack((packed, normal_ids)).astype(np.uint8)
        raw_name = name if isinstance(name, bytes) else name.encode("ascii")
        frames += struct.pack("<6f", *scale, *minimum) + raw_name[:16].ljust(16, b"\0") + packed.tobytes()
        worst_error = max(worst_error, float(np.linalg.norm(restored - points, axis=1).max()))
    commands = gl_strips(faces, uvs)
    sections = (bytes(skin_data), st, triangle_data, bytes(frames), commands)
    offsets, cursor = [], HEADER.size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    header = HEADER.pack(IDENT, 8, ATLAS_SIZE, ATLAS_SIZE, 40 + positions.shape[1] * 4,
                         len(skins), positions.shape[1], len(st) // 4, len(faces),
                         len(commands) // 4, len(names), *offsets, cursor)
    output = header + b"".join(sections)
    parsed = MD2.read(output)
    if parsed.names != [n[:16].ljust(16, b"\0") if isinstance(n, bytes) else n.encode("ascii")[:16].ljust(16, b"\0") for n in names]:
        raise AssertionError("frame names changed during export")
    return output, {"max_vertex_quantization_error": float(f"{worst_error:.12g}"),
                    "minimum_quantized_double_triangle_area": float(f"{minimum_area:.12g}"),
                    "all_frames_nondegenerate": True, "outward_normals_clockwise_triangles": True}


def build_assets():
    from m16_geometry import build_m16
    from build_soldier_height import transform_model, CONFIG as HEIGHT_CONFIG

    originals = json.loads(ORIGINALS.read_text())
    meshes = {detail: build_m16(detail=detail) for detail in ("world", "view")}
    outputs = {path: texture_bytes() for path in TEXTURES}
    manifest = {"schema": 1, "generator": "tools/assets/build_m16.py",
                "generator_sha256": sha(Path(__file__).read_bytes()),
                "geometry_sha256": sha((ROOT / "tools/assets/m16_geometry.py").read_bytes()),
                "source_archive": originals["source_archive"],
                "method": "authored primitives; archived rigid animation poses; no decimation",
                "comparison_baseline": "reviewed shipped outputs at 7b30465800c9aa479d4e231010772e49a4358559",
                "atlas": {"size": [ATLAS_SIZE, ATLAS_SIZE], "tiles": list(MATERIALS), "inset_pixels": 4,
                          "albedo_scale": ALBEDO_SCALE,
                          "sha256": sha(outputs[TEXTURES[0]])}, "models": [], "textures": list(TEXTURES)}
    for path, role in MODELS.items():
        source = MD2.read(source_bytes(originals, "baseq2/" + path), source_compat=True)
        mesh = meshes["view" if role == "view" else "world"]
        vertices, faces = np.asarray(mesh["vertices"], float), np.asarray(mesh["faces"], np.int32)
        normals = np.asarray(mesh["normals"] if "normals" in mesh else vertex_normals(vertices, faces), float)
        matrix, offset, rotation = placement(role)
        posed, directions = vertices @ matrix + offset, normals @ rotation
        fit_report = None
        if role in ("player", "enemy"):
            rotations, offsets, errors = rigid_transforms(source)
            positions = np.asarray([posed @ r + t for r, t in zip(rotations, offsets)])
            normal_poses = np.asarray([directions @ r for r in rotations])
            names = source.names
            fit_report = {"frames": len(names), "rms_median": float(f"{np.median(errors):.12g}"),
                          "rms_max": float(f"{errors.max():.12g}"), "source_frame_names_preserved": True}
        else:
            # Both first-person paths force static frame zero for the M16.
            # One frame retains the renderer's precomputed static_xyz cache;
            # procedural code owns raising, recoil, bobbing and sight movement.
            frames = 1
            positions = np.repeat(posed[None, :, :], frames, axis=0)
            normal_poses = np.repeat(directions[None, :, :], frames, axis=0)
            names = [source.names[0]] * frames
        skin = TEXTURES[2] if role == "view" else TEXTURES[1] if role == "pickup" else TEXTURES[0]
        try:
            raw, validation = encode_md2(positions, normal_poses, faces, atlas_uvs(mesh), [skin], names)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        outputs[path] = raw
        after = MD2.read(raw).stats()
        # Frame names remain in the MD2 itself; avoid repeating hundreds in JSON.
        after.pop("frame_names")
        anchors = {name: (np.asarray(value) @ matrix + offset).tolist()
                   for name, value in mesh.get("anchors", {}).items()}
        manifest["models"].append({"path": path, "role": role, "baseline": BASELINE_COUNTS[role],
                                    "after": after, "pose_transfer": fit_report, "validation": validation,
                                    "canonical_matrix": matrix.tolist(), "canonical_offset": offset.tolist(),
                                    "anchors_frame0": anchors, "parts": mesh.get("parts", [])})
    normal = "models/monsters/soldier/weapon_machinegun.md2"
    tall = "models/monsters/soldier/tall/weapon_machinegun.md2"
    height = json.loads(HEIGHT_CONFIG.read_text())
    outputs[tall] = transform_model(outputs[normal], height["scale"], height["foot_z"])
    stats = MD2.read(outputs[tall]).stats()
    stats.pop("frame_names")
    manifest["models"].append({"path": tall, "role": "enemy_tall", "baseline": BASELINE_COUNTS["enemy"],
                                "after": stats, "derived_from": normal,
                                "uniform_scale": height["scale"], "foot_z": height["foot_z"]})
    manifest["files"] = [{"path": path, "bytes": len(raw), "sha256": sha(raw)}
                         for path, raw in sorted(outputs.items())]
    return outputs, manifest


def generate():
    """Return every owned file, including its manifest, without mutating disk."""
    assets, manifest = build_assets()
    outputs = {BASE / path: raw for path, raw in assets.items()}
    outputs[MANIFEST] = (json.dumps(manifest, indent=2) + "\n").encode()
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="rebuild and compare without writing")
    parser.add_argument("--output", type=Path, default=BASE, help="baseq2 output directory")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    assets, manifest = build_assets()
    outputs = {args.output / path: raw for path, raw in assets.items()}
    outputs[args.manifest] = (json.dumps(manifest, indent=2) + "\n").encode()
    for path, raw in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError("M16 output differs from reproducible build: " + str(path))
        elif not path.is_file() or path.read_bytes() != raw:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    for model in manifest["models"]:
        print(f"{model['path']}: {model['baseline']['triangles']} -> {model['after']['triangles']} triangles, "
              f"{model['after']['position_vertices']} vertices, {model['after']['frames']} frames")
    print("Verified M16 assets" if args.verify else "Built M16 assets; regenerate height/color/muzzle/package derivatives next")


if __name__ == "__main__":
    main()
