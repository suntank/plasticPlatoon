#!/usr/bin/env python3
"""Package the verified helicopter range and its original replacement assets.

The game module, client, main Plastic Platoon asset pack and original Q2 data
remain runtime prerequisites. No original game PAK data is redistributed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
SOUNDS = tuple(f"m60{i}.wav" for i in range(1,6)) + ("m60end.wav",)
MODELS = ("models/monsters/plastic_helicopter/body.md2",
          "models/monsters/plastic_helicopter/main_rotor.md2",
          "models/monsters/plastic_helicopter/tail_rotor.md2",
          "models/objects/rocket/tris.md2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_skins(path):
    """Read MD2 skin dependencies instead of assuming an unrelated stock skin."""
    raw = path.read_bytes()
    if len(raw) < 68:
        raise ValueError(f"Short MD2 header: {path}")
    header = struct.unpack_from("<17i",raw)
    if header[0:2] != (844121161,8):
        raise ValueError(f"Unsupported MD2: {path}")
    count, offset = header[5], header[11]
    if count <= 0 or offset < 68 or offset+count*64 > len(raw):
        raise ValueError(f"Invalid MD2 skin table: {path}")
    for i in range(count):
        rel = raw[offset+i*64:offset+(i+1)*64].split(b"\0",1)[0].decode("ascii")
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"Unsafe MD2 skin reference in {path}: {rel!r}")
        yield rel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-user",action="store_true",
                        help="also install the archive in ~/.yq2/baseq2")
    args = parser.parse_args()
    source = ROOT / "maps/source/pp_helicopter_test.map"
    bsp = ROOT / "baseq2/maps/pp_helicopter_test.bsp"
    build = ROOT / "build/maps/pp_helicopter_test"
    try:
        report = json.loads((build / "verification.json").read_text())
        if not (report.get("passed") and report.get("map_sha256") == sha(source)
                and report.get("bsp_sha256") == sha(bsp)):
            parser.error("Run generate_helicopter_test.py --verify on this exact source/BSP before packaging")
        files = {"maps/pp_helicopter_test.bsp":bsp,
                 "maps/pp_helicopter_test.map":source,
                 "helicopter_test.cfg":ROOT / "baseq2/helicopter_test.cfg",
                 "helicopter-test-readme.txt":ROOT / "maps/README-helicopter-test.md"}
        from verify_sandkeep import parse_entities
        textures = {t for e in parse_entities(source.read_text()) for t in e["textures"]}
        for texture in textures:
            for suffix in ("wal","png"):
                rel = f"textures/{texture}.{suffix}"
                files[rel] = ROOT / "baseq2" / rel
        for rel in MODELS:
            path = ROOT / "baseq2" / rel
            files[rel] = path
            for skin in model_skins(path):
                files[skin] = ROOT / "baseq2" / skin
        files.update((f"sound/weapons/{name}",ROOT / "baseq2/sound/weapons" / name)
                     for name in SOUNDS)
        missing = [str(path) for path in files.values() if not path.is_file()]
        if missing:
            parser.error("Missing package sources: " + ", ".join(missing))
        destinations = [ROOT / "baseq2",ROOT / "release/baseq2"]
        if args.install_user:
            destinations.append(Path.home() / ".yq2/baseq2")
        with tempfile.TemporaryDirectory(prefix="pp-helicopter-package-") as temporary:
            archive = Path(temporary) / "operation-helicopter-test.pk3"
            with ZipFile(archive,"w",ZIP_DEFLATED) as package:
                for name,path in sorted(files.items()):
                    info = ZipInfo(name,(1980,1,1,0,0,0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    package.writestr(info,path.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
            digest = sha(archive)
            for dest in destinations:
                dest.mkdir(parents=True,exist_ok=True)
                target = dest / archive.name
                if not target.exists() or sha(target) != digest:
                    staged = target.with_suffix(".pk3.tmp")
                    try:
                        shutil.copyfile(archive,staged)
                        staged.replace(target)
                    finally:
                        staged.unlink(missing_ok=True)
        manifest = dict(archive="operation-helicopter-test.pk3",sha256=digest,
                        installed=[str(d / "operation-helicopter-test.pk3") for d in destinations],
                        files={name:sha(path) for name,path in sorted(files.items())})
        (build / "package.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print(json.dumps({k:v for k,v in manifest.items() if k != "files"},indent=2))
    except (OSError,ValueError,UnicodeError,struct.error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
