#!/usr/bin/env python3
"""Retarget an existing held M60 or rocket launcher to all 475 soldier frames.

Both player weapons share the enemy attachment's first-frame grip coordinates.
The enemy's machinegun is a rigid object, so a least-squares rigid transform per
frame transfers its authored motion to the M60 without changing the body mesh.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw

from md2_assets import HEADER, IDENT, MD2, ROOT, normal_table, raster, sha


MOTION = "models/monsters/soldier/weapon_machinegun.md2"
WEAPON = "players/soldier/w_chaingun.md2"
BODY = "models/monsters/soldier/tris.md2"
OUTPUT = "models/monsters/soldier/weapon_heavy.md2"
REPORT = ROOT / "tools/assets/heavy-gunner-manifest.json"
REVIEW = ROOT / "tools/assets/review/heavy-gunner.png"
SOURCES = {
    MOTION: "c44c70b25c3edc1f65cfcdf9195a2163f7751efd63ebe07fcad05c655a6ba022",
    WEAPON: "4e061cc055f001f86e4be9b348f7566778913ee50a7d5f7d66e90470316eeed8",
    BODY: "9363f8d2fcb22c0d738ddf12f33a7e873ecb30f7badc8d704ecc565c812a2f05",
}


def load(path: str) -> MD2:
    data = (ROOT / "baseq2" / path).read_bytes()
    if sha(data) != SOURCES[path]:
        raise ValueError(f"source changed; review the attachment fit before updating its hash: {path}")
    return MD2.read(data)


def build() -> tuple[bytes, dict]:
    motion, weapon, body = load(MOTION), load(WEAPON), load(BODY)
    if motion.names != body.names:
        raise ValueError("body and attachment animation frames disagree")
    reference = motion.positions[0]
    centre = reference.mean(axis=0)
    centred = reference - centre
    m60 = weapon.positions[0]
    table = normal_table()
    base_normals = table[weapon.normals[0]]
    frames = bytearray()
    fit_errors, quantization_errors = [], []
    for frame, target in enumerate(motion.positions):
        destination = target.mean(axis=0)
        u, _, vt = np.linalg.svd(centred.T @ (target - destination))
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u[:, -1] *= -1
            rotation = u @ vt
        fitted = centred @ rotation + destination
        error = float(np.linalg.norm(fitted - target, axis=1).max())
        if error > .15:
            raise ValueError(f"weapon motion is no longer rigid at frame {frame}: {error}")
        fit_errors.append(error)
        positions = (m60 - centre) @ rotation + destination
        # Store the exact float32 scale/translation that the MD2 loader will use.
        translation = positions.min(axis=0).astype("<f4")
        scale = (np.maximum(np.ptp(positions, axis=0), .001) / 255).astype("<f4")
        quantized = np.clip(np.rint((positions - translation) / scale), 0, 255).astype(np.uint8)
        quantization_errors.append(float(np.linalg.norm(quantized * scale + translation - positions,
                                                        axis=1).max()))
        normals = np.argmax((base_normals @ rotation) @ table.T, axis=1).astype(np.uint8)
        frames.extend(struct.pack("<6f16s", *scale, *translation, motion.names[frame]))
        frames.extend(np.column_stack((quantized, normals)).astype(np.uint8).tobytes())
    # Preserve the M60 topology, UVs, skin references and draw strips byte for byte.
    wh = weapon.header
    sections = (weapon.data[wh[11]:wh[12]], weapon.data[wh[12]:wh[13]],
                weapon.data[wh[13]:wh[14]], bytes(frames), weapon.data[wh[15]:wh[16]])
    offsets, cursor = [], HEADER.size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    header = HEADER.pack(IDENT, 8, *wh[2:4], 40 + wh[6] * 4,
                         *wh[5:10], motion.header[10], *offsets, cursor)
    data = header + b"".join(sections)
    result = MD2.read(data)
    if result.names != body.names or result.skins != weapon.skins:
        raise AssertionError("retargeting changed the frame correspondence or M60 skin")
    np.testing.assert_array_equal(result.faces, weapon.faces)
    np.testing.assert_array_equal(result.uvs, weapon.uvs)
    report = {
        "schema": 1,
        "model": OUTPUT,
        "sources": SOURCES,
        "method": "Rigid least-squares transfer of enemy attachment motion onto held M60 frame zero",
        "frames": result.header[10],
        "position_vertices": result.header[6],
        "triangles": result.header[8],
        "skin_references": result.skins,
        "max_source_rigid_fit_error_units": round(max(fit_errors), 8),
        "max_output_quantization_error_units": round(max(quantization_errors), 8),
        "sha256": sha(data),
        "bytes": len(data),
    }
    return data, report


def review(data: bytes) -> None:
    """Render the real body and M60 together, including deployed and death poses."""
    body, weapon = load(BODY), MD2.read(data)
    atlas = Image.new("RGB", (512, 256))
    for i, model in enumerate((body, weapon)):
        atlas.paste(Image.open(ROOT / "baseq2" / model.skins[0]).convert("RGB"), (i * 256, 0))
    buv, wuv = body.uvs.copy(), weapon.uvs.copy()
    buv[..., 0] *= .5
    wuv[..., 0] = wuv[..., 0] * .5 + .5
    faces = np.concatenate((body.faces, weapon.faces + body.header[6]))
    uv = np.concatenate((buv, wuv))
    positions = np.concatenate((body.positions, weapon.positions), axis=1)
    normals = np.concatenate((body.normals, weapon.normals), axis=1)
    sheet = Image.new("RGB", (960, 5 * 300 + 35), (22, 25, 30))
    draw = ImageDraw.Draw(sheet)
    label = "rocket launcher" if WEAPON.endswith("w_rlauncher.md2") else "M60"
    draw.text((12, 10), f"Enemy soldier + retargeted {label} (offline asset review)", fill="white")
    for row, (frame, label) in enumerate(((0, "standing"), (33, "crouched fire"),
                                        (45, "duck"), (270, "walk"), (474, "death"))):
        model = replace(body, faces=faces, uvs=uv, positions=positions[frame:frame + 1],
                        normals=normals[frame:frame + 1])
        # Same framing in each row makes the crouched silhouette easy to inspect.
        framing = (np.array([12., 0., 0.]), 40.)
        for col, angle in enumerate((25, 115, 205, 295)):
            image, _ = raster(model, atlas, angle, 240, framing)
            sheet.paste(image, (col * 240, 35 + row * 300))
            draw.text((col * 240 + 10, 35 + row * 300 + 246),
                      f"{label}: frame {frame}, {angle} degrees", fill="#c2c8d0")
    sheet.save(REVIEW)


def main() -> None:
    global WEAPON, OUTPUT, REPORT, REVIEW
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weapon", choices=("m60", "rocket"), default="m60")
    parser.add_argument("--verify", action="store_true", help="compare generated model and manifest without writing")
    parser.add_argument("--review", action="store_true", help="also render body/attachment review sheet")
    args = parser.parse_args()
    if args.weapon == "rocket":
        WEAPON = "players/soldier/w_rlauncher.md2"
        OUTPUT = "models/monsters/soldier/weapon_rocket.md2"
        REPORT = ROOT / "tools/assets/rocket-soldier-manifest.json"
        REVIEW = ROOT / "tools/assets/review/rocket-soldier.png"
        SOURCES.pop("players/soldier/w_chaingun.md2", None)
        SOURCES[WEAPON] = "ed73d6194eee3af276000032290ca2854262e800a90330ffbb5e871227f99f04"
    data, report = build()
    if args.weapon == "rocket":
        report["method"] = report["method"].replace("M60", "rocket launcher")
    path = ROOT / "baseq2" / OUTPUT
    if args.verify:
        if path.read_bytes() != data or json.loads(REPORT.read_text()) != report:
            raise ValueError("heavy gunner model or manifest differs from the reproducible build")
    else:
        path.write_bytes(data)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
    if args.review:
        review(data)
    print(f"{'Verified' if args.verify else 'Built'} {OUTPUT}: {report['frames']} frames, "
          f"{report['triangles']} triangles; max motion fit error {report['max_source_rigid_fit_error_units']} units")


if __name__ == "__main__":
    main()
