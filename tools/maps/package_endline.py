#!/usr/bin/env python3
"""Install the exact verified End of the Line build and original dependencies."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
from zipfile import ZipFile, ZIP_DEFLATED

from verify_sandkeep import parse_entities

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-user", action="store_true", help="Also install in ~/.yq2/baseq2")
    args = parser.parse_args()
    source = ROOT / "maps/source/pp_endline.map"
    bsp = ROOT / "baseq2/maps/pp_endline.bsp"
    report = json.loads((ROOT / "build/maps/pp_endline/verification.json").read_text())
    if not (report["passed"] and report.get("map_sha256") == sha(source) and report.get("bsp_sha256") == sha(bsp)):
        raise SystemExit("Verify this exact source and compiled BSP before packaging")
    base = ROOT / "baseq2"
    files = {"maps/pp_endline.map": source, "maps/pp_endline.bsp": bsp,
             "maps/README-endline.md": ROOT / "maps/README-endline.md",
             "maps/endline-LICENSE.txt": ROOT / "LICENSE",
             "maps/endline-ASSET-LICENSE.md": ROOT / "ASSET-LICENSE.md",
             "maps/endline-materials.json": ROOT / "tools/maps/endline-materials.json",
             "maps/endline-audio.json": ROOT / "tools/maps/endline-audio.json"}
    for p in base.glob("endline_*.cfg"):
        files[p.name] = p
    # Include exact existing material dependencies and complete button animation
    # chains. Never package another mission or an unrelated texture directory.
    pending = list({t for e in parse_entities(source.read_text()) for t in e["textures"]})
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        if name.split("/")[0] not in ("endline", "sandbox", "sandkeep", "bedroom"):
            raise SystemExit("Unexpected material namespace: " + name)
        wal = base / "textures" / (name + ".wal")
        data = wal.read_bytes()
        next_name = struct.unpack_from("<32s", data, 56)[0].split(b"\0")[0].decode()
        if next_name:
            pending.append(next_name)
        for suffix in (".wal", ".png", ".tga"):
            path = base / "textures" / (name + suffix)
            if path.is_file():
                files[path.relative_to(base).as_posix()] = path
    for path in sorted((base / "sound/endline").glob("*.wav")):
        files[path.relative_to(base).as_posix()] = path
    for path in sorted((base / "env").glob("sandkeep*")):
        files[path.relative_to(base).as_posix()] = path
    archive = ROOT / "build/maps/pp_endline/operation-endline.pk3"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for name, path in sorted(files.items()):
            output.write(path, name)
    destinations = [base, ROOT / "release/baseq2"]
    if args.install_user:
        destinations.append(Path.home() / ".yq2/baseq2")
    for dest in destinations:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, dest / archive.name)
        for path in base.glob("endline_*.cfg"):
            if dest != base:
                shutil.copy2(path, dest / path.name)
    (base / "maps/pp_endline.map").write_bytes(source.read_bytes())
    manifest = dict(archive_sha256=sha(archive), source_sha256=sha(source), bsp_sha256=sha(bsp),
                    installed=[str(d / archive.name) for d in destinations],
                    files={name: sha(path) for name, path in sorted(files.items())})
    (ROOT / "build/maps/pp_endline/package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k:v for k,v in manifest.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
