#!/usr/bin/env python3
"""Package a verified Nightlight build and install only this mission's files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-user', action='store_true',
                        help='also install the archive in ~/.yq2/baseq2')
    args = parser.parse_args()
    bsp = ROOT / "build/nightlight-release/maps/pp_bedroom.bsp"
    source = ROOT / "maps/source/pp_bedroom.map"
    report = json.loads((ROOT / "build/maps/pp_bedroom/verification.json").read_text())
    if not (report["passed"] and report["map_sha256"] == sha(source) and report["bsp_sha256"] == sha(bsp)):
        raise SystemExit("Verify the exact source and BSP before packaging")
    files = {"maps/pp_bedroom.bsp":bsp,"maps/pp_bedroom.map":source,
             "maps/README-bedroom.md":ROOT/"maps/README-bedroom.md"}
    for name in ("bedroom_solo.cfg","bedroom_coop.cfg"):
        files[name] = ROOT / "baseq2" / name
    files.update((p.relative_to(ROOT/"baseq2").as_posix(),p)
                 for p in (ROOT/"baseq2/textures/bedroom").iterdir() if p.is_file())
    archive = ROOT / "build/maps/pp_bedroom/operation-nightlight.pk3"
    with ZipFile(archive,"w",compression=ZIP_DEFLATED) as z:
        for name,path in sorted(files.items()):
            z.write(path,name)
    # The archive contains only original mission assets; no stock game data.
    destinations = [ROOT/"baseq2",ROOT/"release/baseq2"]
    if args.install_user:
        destinations.append(Path.home()/".yq2/baseq2")
    for dest in destinations:
        dest.mkdir(parents=True,exist_ok=True)
        shutil.copy2(archive,dest/archive.name)
    (ROOT/"baseq2/maps").mkdir(exist_ok=True)
    shutil.copy2(bsp,ROOT/"baseq2/maps/pp_bedroom.bsp")
    manifest = dict(archive=str(archive),sha256=sha(archive),
                    installed=[str(d/archive.name) for d in destinations],
                    files={n:sha(p) for n,p in files.items()})
    (ROOT/"build/maps/pp_bedroom/package.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k != "files"},indent=2))


if __name__ == "__main__":
    main()
