#!/usr/bin/env python3
"""Build the complete low-poly runtime tree from checked original source archives."""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import md2_assets as md2

ROOT = md2.ROOT
CONFIG = Path(__file__).with_name("platoon.json")
MANIFEST = Path(__file__).with_name("platoon-manifest.json")
CONVERTERS = ("build_platoon.py", "md2_assets.py", "md2_animation.py", "asset_sources.py")
CONVERSION_INPUTS = ("tools/assets/pickups.json", "tools/assets/pickup-manifest.json",
                     "src/client/refresh/constants/anorms.h")


def converter_hashes():
    return {name: md2.sha(Path(__file__).with_name(name).read_bytes()) for name in CONVERTERS}


def input_hashes():
    return {name: md2.sha((ROOT / name).read_bytes()) for name in CONVERSION_INPUTS}


def pickup_overrides(prior):
    """Keep corrected pickups paired with their audited models and textures."""
    if "source_archive" not in prior:
        return {}, {}
    originals, outputs = {}, {}
    for entry in prior["assets"]:
        path = entry["model"]
        originals[path] = md2.pickup_source_bytes(prior, "baseq2/" + path)
        raw = md2.pickup_source_bytes(prior, "baseq2/" + entry["texture_before"]["path"])
        originals[entry["texture_before"]["path"]] = raw
        originals[entry["texture_after"]["path"]] = raw
        output = (ROOT / "baseq2" / path).read_bytes()
        if md2.sha(output) != entry["after"]["sha256"]:
            raise ValueError(f"rebuild pickups with md2_assets.py before the full release: {path}")
        outputs[path] = output
    return originals, outputs


def read_source(raw, path):
    try:
        return md2.MD2.read(raw, source_compat=True), None
    except ValueError:
        if path != "players/soldier/w_hyperblaster.md2":
            raise
        from md2_animation import repair_stale_triangle_table
        fixed, report = repair_stale_triangle_table(raw, expected_sha256="7742a95495ed3db8699798671bf42b635f97cbb0a74df6472fd4964479bf3e9a")
        return fixed, report


def frame_view(model, frame):
    out = copy.copy(model)
    out.positions = model.positions[frame:frame + 1]
    out.normals = model.normals[frame:frame + 1]
    return out


def compare(source, result, before, after, destination, title):
    """Compare sampled action poses with identical cameras, framing and lighting."""
    frames = {0, len(source.positions) - 1}
    # Spread samples throughout the complete timeline, including death poses.
    frames.update(np.linspace(0, len(source.positions) - 1, min(8, len(source.positions)), dtype=int).tolist())
    # Include the first pose of each authored action prefix.
    import re
    groups = set()
    for i, name in enumerate(source.names):
        group = re.sub(rb"[0-9]+$", b"", name.split(b"\0")[0])
        if group not in groups:
            groups.add(group)
            frames.add(i)
    frames = sorted(frames)
    textures = [Image.open(io.BytesIO(d)) for d in (before, after)]
    tile, height = 144, 180
    canvas = Image.new("RGB", (tile * 8, 40 + height * len(frames)), (22, 25, 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), title + " | source / optimized at each angle; identical framing and light", fill="white")
    overlaps = []
    for row, frame in enumerate(frames):
        views = [frame_view(m, frame) for m in (source, result)]
        p = views[0].positions[0]
        centre = (p.min(axis=0) + p.max(axis=0)) / 2
        framing = centre, max(1e-6, np.linalg.norm(p - centre, axis=1).max())
        for col, angle in enumerate((25, 115, 205, 295)):
            masks = []
            for j in (0, 1):
                pic, mask = md2.raster(views[j], textures[j], angle, tile - 4, framing)
                canvas.paste(pic, (tile * (col * 2 + j), 40 + height * row))
                masks.append(mask)
            score = float((masks[0] & masks[1]).sum() / max(1, (masks[0] | masks[1]).sum()))
            overlaps.append(score)
            draw.text((tile * col * 2 + 3, 40 + height * row + tile),
                      f"frame {frame} | {angle} deg | IoU {score:.3f}", fill="white")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    return {"path": str(destination.relative_to(ROOT)), "sha256": md2.sha(destination.read_bytes()),
            "frames": frames, "angles": [25, 115, 205, 295], "pixels": tile - 4,
            "silhouette_iou_min": min(overlaps), "silhouette_iou_mean": float(np.mean(overlaps)),
            "note": "Offline asset comparison; all-pose collapse validation is separate from sampled visual review."}


def build(args):
    config = json.loads(CONFIG.read_text())
    prior = json.loads((ROOT / config["pickup_manifest"]).read_text())
    pickups = {a["model"]: a for a in prior["assets"]}
    params = json.loads(Path(__file__).with_name("pickups.json").read_text())["parameters"]
    originals = {p.removeprefix("baseq2/"): raw for p, raw in md2.source_files(config).items()
                 if Path(p).suffix.lower() in (".md2", ".png")
                 and not p.startswith("baseq2/players/male/")}
    overrides, pickup_outputs = pickup_overrides(prior)
    originals.update(overrides)
    textures = {}
    for path, raw in originals.items():
        if not path.endswith(".png"):
            continue
        limit = config["world_texture_size"]
        if path.startswith("models/weapons/v_"):
            limit = config["view_texture_size"]
        if path.startswith("sprites/"):
            limit = config["sprite_texture_size"]
        textures[path] = md2.resize_texture(raw, limit)
    manifest = {"schema": 1, "source_archive": config["source_archive"], "config_sha256": md2.sha(CONFIG.read_bytes()),
                "converter_sha256": converter_hashes(),
                "conversion_inputs_sha256": input_hashes(),
                "tools": {p: importlib.metadata.version(p) for p in ("numpy", "Pillow", "pymeshlab")},
                "models": [], "textures": []}
    if "source_archive" in prior:
        manifest["pickup_source_archive"] = prior["source_archive"]
    previous = json.loads(args.manifest.read_text()) if args.pickups_only else None
    for path, raw in originals.items():
        if not path.endswith(".md2") or (args.only and args.only not in path):
            continue
        if args.pickups_only and path not in pickups:
            manifest["models"].append(next(entry for entry in previous["models"] if entry["path"] == path))
            continue
        source, repair = read_source(raw, path)
        skins = source.skins
        valid = [s for s in skins if s in originals or (ROOT / "baseq2" / s).is_file()]
        if skins and not valid:
            raise ValueError(f"No valid skin for {path}: {skins}")
        skins = [s if s in valid else valid[0] for s in skins]
        report = {}
        if path in pickups:
            data = pickup_outputs.get(path, raw)
            method = "Texture-aware pickup simplification from audited local originals"
        elif len(source.positions) == 1:
            default = config["view_triangles"] if path.startswith("models/weapons/v_") else config["static_triangles"]
            target = config["targets"].get(path, default)
            if len(source.faces) > target:
                p, f, uv = md2.simplify(source, target, params)
                data = md2.encode_static(source, p, f, uv, skins)
                method = "Texture-aware quadric simplification, source-surface normal transfer"
            else:
                # Low-poly gibs need no additional geometric loss.
                from md2_animation import encode_vertex_subset
                used = np.unique(source.faces)
                data = encode_vertex_subset(source, used, np.searchsorted(used, source.faces), source.uvs, skins=skins)
                method = "Compact frame stride and deterministic strips; original geometry retained"
        else:
            from md2_animation import simplify_shared, encode_vertex_subset
            target = math.ceil(len(source.faces) * config["animated_ratio"])
            ids, f, uv, report = simplify_shared(source, target, max_displacement_ratio=config["animated_max_displacement_ratio"])
            data = encode_vertex_subset(source, ids, f, uv, skins=skins)
            method = "One endpoint-collapse topology shared across every original animation frame"
        result = md2.MD2.read(data)
        entry = {"path": path, "input_sha256": md2.sha(raw), "before": source.stats(), "after": result.stats(),
                 "method": method, "collapse_validation": report}
        if path in pickups:
            entry["local_original"] = pickups[path]["before"]
        if repair:
            entry["source_repair"] = repair
        if args.review and path not in pickups:
            skin = skins[0]
            before = originals[skin] if skin in originals else (ROOT / "baseq2" / skin).read_bytes()
            after = textures.get(skin, before)
            entry["review"] = compare(source, result, before, after,
                                      ROOT / "tools/assets/review" / (path.replace("/", "_") + ".png"), path)
        if args.write:
            (ROOT / "baseq2" / path).write_bytes(data)
        manifest["models"].append(entry)
        print(f"{path}: {len(source.faces)} -> {len(result.faces)} triangles, {len(source.positions)} frames", flush=True)
    if not args.only:
        for path, data in textures.items():
            manifest["textures"].append({"path": path, "before": md2.texture_stats(originals[path]),
                                         "after": md2.texture_stats(data)})
            if args.write and (not args.pickups_only or path in overrides):
                (ROOT / "baseq2" / path).write_bytes(data)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")


def verify(args):
    manifest = json.loads(args.manifest.read_text())
    assert manifest["config_sha256"] == md2.sha(CONFIG.read_bytes()), "optimization configuration changed"
    assert manifest["converter_sha256"] == converter_hashes(), "conversion tools changed"
    assert manifest["conversion_inputs_sha256"] == input_hashes(), "conversion inputs changed"
    prior = json.loads((ROOT / json.loads(CONFIG.read_text())["pickup_manifest"]).read_text())
    overrides, _ = pickup_overrides(prior)
    for entry in manifest["models"]:
        path = entry["path"]
        raw = overrides[path] if path in overrides else md2.source_bytes(manifest, "baseq2/" + path)
        assert md2.sha(raw) == entry["input_sha256"], path
        out = md2.MD2.read((ROOT / "baseq2" / path).read_bytes())
        assert out.stats() == entry["after"], path
        assert out.names == read_source(raw, path)[0].names, path
        assert out.header[4] == 40 + out.header[6] * 4, path
        if "review" in entry:
            review = entry["review"]
            assert md2.sha((ROOT / review["path"]).read_bytes()) == review["sha256"], path
    for entry in manifest["textures"]:
        assert md2.texture_stats((ROOT / "baseq2" / entry["path"]).read_bytes()) == entry["after"], entry["path"]
    print(f"Verified {len(manifest['models'])} MD2 models and {len(manifest['textures'])} PNG textures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--pickups-only", action="store_true", help="refresh corrected pickups while retaining other converted models")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    (build if args.command == "build" else verify)(args)
