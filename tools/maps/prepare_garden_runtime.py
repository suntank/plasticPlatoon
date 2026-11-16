#!/usr/bin/env python3
"""Re-center a private compile copy; preserve authored Garden geometry and UVs."""
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
DELTA=(-3200,-2000,0)
POINT=re.compile(r'\(\s*([^()]+?)\s*\)')
BASEAXES=[((0,0,1),(1,0,0),(0,-1,0)),((0,0,-1),(1,0,0),(0,-1,0)),
          ((1,0,0),(0,1,0),(0,0,-1)),((-1,0,0),(0,1,0),(0,0,-1)),
          ((0,1,0),(1,0,0),(0,0,-1)),((0,-1,0),(1,0,0),(0,0,-1))]


def axes(points,rotation,scales):
    a,b,c=points; u=[a[i]-b[i] for i in range(3)];v=[c[i]-b[i] for i in range(3)]
    n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    _,s,t=max(BASEAXES,key=lambda entry:sum(n[i]*entry[0][i] for i in range(3)))
    sv=next(i for i in range(3) if s[i]);tv=next(i for i in range(3) if t[i])
    sinv=math.sin(math.radians(rotation));cosv=math.cos(math.radians(rotation))
    result=[]
    for row,scale in zip((s,t),scales):
        row=list(row);row[sv],row[tv]=cosv*row[sv]-sinv*row[tv],sinv*row[sv]+cosv*row[tv]
        result.append([v/scale for v in row])
    return result


def moved(text):
    return ' '.join(format(Decimal(v)+d,'f') for v,d in zip(text.split(),DELTA))


def prepare(edited_source=False):
    source=ROOT/'maps/source/pp_garden_infiltration.map';text=source.read_text();lines=[];faces=0;origins=0
    worldspawns=0;normalized=0
    for raw in text.splitlines(True):
        line=raw.lstrip()
        if re.fullmatch(r'\s*"classname"\s+"worldspawn"\s*',raw):
            worldspawns+=1
            if edited_source and worldspawns>1:
                # Editors can leave detached terrain containers labelled as
                # worldspawn. func_group is compiler-only world geometry;
                # preserve every brush instead of spawning extra worlds.
                raw='"classname" "func_group"\n';normalized+=1
                line=raw
        if line.startswith('('):
            matches=list(POINT.finditer(raw));assert len(matches)==3
            points=[list(map(float,m[1].split())) for m in matches]
            tail=raw[matches[-1].end():].split(); assert '[' not in tail
            # This compiler parses classic shifts/rotation as integers. Match
            # its actual projection rather than the editor's ideal float UVs.
            rotation=math.trunc(float(tail[3]));scales=list(map(float,tail[4:6]));vectors=axes(points,rotation,scales)
            for i in range(2):
                tail[1+i]=str(round(math.trunc(float(tail[1+i]))-sum(vectors[i][j]*DELTA[j] for j in range(3))))
            raw=' '.join('( '+moved(m[1])+' )' for m in matches)+' '+' '.join(tail)+'\n';faces+=1
        elif line.startswith('"origin"'):
            m=re.fullmatch(r'\s*"origin"\s+"([^"]+)"\s*',raw);assert m
            raw='"origin" "'+moved(m[1])+'"\n';origins+=1
        lines.append(raw)
    output=ROOT/'build/maps/pp_garden_infiltration/runtime-source/pp_garden_infiltration.map'
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(''.join(lines))
    design=ROOT/'build/maps/pp_garden_infiltration/design.json'
    authoring_design=ROOT/'maps/source/pp_garden_infiltration.design.json'
    d=json.loads((authoring_design if authoring_design.is_file() else design).read_text());d['runtime_translation']=list(DELTA);d['runtime_source']=str(output)
    design.write_text(json.dumps(d,indent=2)+'\n')
    receipt={'reason':'Quake II signed 16-bit eighth-unit player coordinates must remain within +/-4096; a rigid translation preserves all shapes, distances and texture alignment.',
             'translation':DELTA,'authored_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
             'runtime_source_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'translated_faces':faces,'translated_origins':origins,
             'normalized_worldspawn_containers':normalized,'edited_source':edited_source}
    (output.parent/'translation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
    return output


if __name__=='__main__': prepare()
