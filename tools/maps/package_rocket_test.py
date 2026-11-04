#!/usr/bin/env python3
"""Package the verified rocket range and its required materials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-user", action="store_true", help="also install the archive in ~/.yq2/baseq2")
    args = parser.parse_args()
    source = ROOT / "maps/source/pp_rocket_test.map"
    bsp = ROOT / "baseq2/maps/pp_rocket_test.bsp"
    build = ROOT / "build/maps/pp_rocket_test"
    try:
        report = json.loads((build / "verification.json").read_text())
        if not (report.get("passed") and report.get("map_sha256") == sha(source)
                and report.get("bsp_sha256") == sha(bsp)):
            parser.error("Run generate_rocket_test.py --verify on this exact source/BSP before packaging")
        files = {"maps/pp_rocket_test.bsp": bsp,
                 "maps/pp_rocket_test.map": source,
                 "rocket_test.cfg": ROOT / "baseq2/rocket_test.cfg",
                 "rocket-test-readme.txt": ROOT / "maps/README-rocket-test.md"}
        from verify_sandkeep import parse_entities
        textures = {t for e in parse_entities(source.read_text()) for t in e["textures"]}
        for texture in textures:
            for suffix in ("wal", "png"):
                rel = f"textures/{texture}.{suffix}"
                files[rel] = ROOT / "baseq2" / rel
        missing = [str(path) for path in files.values() if not path.is_file()]
        if missing:
            parser.error("Missing package sources: " + ", ".join(missing))
        destinations = [ROOT / "baseq2", ROOT / "release/baseq2"]
        if args.install_user:
            destinations.append(Path.home() / ".yq2/baseq2")
        with tempfile.TemporaryDirectory(prefix="pp-rocket-package-") as temporary:
            archive = Path(temporary) / "operation-rocket-test.pk3"
            with ZipFile(archive,"w",ZIP_DEFLATED) as package:
                for name,path in sorted(files.items()):
                    info = ZipInfo(name,(1980,1,1,0,0,0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    package.writestr(info,path.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
            digest = sha(archive)
            for dest in destinations:
                dest.mkdir(parents=True, exist_ok=True)
                target = dest / archive.name
                if not target.exists() or sha(target) != digest:
                    staged = target.with_suffix(".pk3.tmp")
                    try:
                        shutil.copyfile(archive, staged)
                        staged.replace(target)
                    finally:
                        staged.unlink(missing_ok=True)
        manifest = dict(archive="operation-rocket-test.pk3", sha256=digest,
                        installed=[str(d / "operation-rocket-test.pk3") for d in destinations],
                        files={name:sha(path) for name,path in sorted(files.items())})
        (build / "package.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print(json.dumps({k:v for k,v in manifest.items() if k != "files"},indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
