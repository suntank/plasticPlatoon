#!/usr/bin/env python3
"""Build Garden Ghost with a private coordinate-safe compile copy and full VIS/RAD."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
from build_endline import prepare_assets
from prepare_garden_runtime import prepare

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tool',default=str(Path.home()/'q2tools/build/q2tool'))
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--edited-source',action='store_true',help='Build the manually edited mission; report original-preservation drift')
    p.add_argument('--output-dir',type=Path,default=ROOT/'baseq2/maps')
    a=p.parse_args();source=prepare(a.edited_source);assets=ROOT/'build/garden-infiltration-compile-assets'
    candidate=ROOT/'build/garden-infiltration-candidate/maps'
    prepare_assets(source,assets)
    command=[sys.executable,str(ROOT/'tools/performance/compile_map.py'),'--source',str(source),
             '--tool',a.tool,'--basedir',str(assets),'--profile','release','--rad-subdiv','128',
             '--rad-ambient','16','--threads',str(a.threads),'--build-dir',str(ROOT/'build/garden-infiltration-runtime-build'),
             '--output-dir',str(candidate)]
    subprocess.run(command,check=True)
    verify=[sys.executable,str(ROOT/'tools/maps/verify_garden_infiltration.py'),'--bsp',str(candidate/'pp_garden_infiltration.bsp')]
    if a.edited_source: verify.append('--edited-source')
    subprocess.run(verify,check=True)
    # A failed mission audit must never replace the last playable BSP.
    a.output_dir.mkdir(parents=True,exist_ok=True)
    staged=a.output_dir/'pp_garden_infiltration.bsp.tmp'
    shutil.copy2(candidate/'pp_garden_infiltration.bsp',staged)
    staged.replace(a.output_dir/'pp_garden_infiltration.bsp')


if __name__=='__main__': main()
