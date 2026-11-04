#!/usr/bin/env python3
"""Check the actual Sandwatch BSP, wave graph, supply gates and walking hulls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

from verify_sandkeep import (BSP, MONSTER_MASK, PLAYER_MASK, PLAYER_MAXS,
                            PLAYER_MINS, SOLID, parse_entities, vec)

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bsp',type=Path,default=ROOT/'build/sandwatch-candidate/maps/pp_sandwatch.bsp')
    p.add_argument('--output',type=Path,default=ROOT/'build/maps/pp_sandwatch/verification.json')
    a=p.parse_args()
    source=ROOT/'maps/source/pp_sandwatch.map'
    entities=parse_entities(source.read_text())
    bsp=BSP(a.bsp)
    keys=[e['keys'] for e in entities]
    byname=defaultdict(list)
    errors=[]
    def require(condition,message):
        if not condition:
            errors.append(message)
    for k in keys:
        if k.get('targetname'):
            byname[k['targetname']].append(k)
    normalize=lambda es: Counter(tuple(sorted((k,v) for k,v in e['keys'].items() if k!='model' and not k.startswith('_')))
                                  for e in es if e['keys'].get('classname') not in ('worldspawn','light'))
    require(normalize(entities)==normalize(bsp.entities),'Source and compiled gameplay entities differ')
    require(bsp.lumps['visibility'] and bsp.lumps['lighting'],'Missing VIS or lightmaps')
    for k in keys:
        for field in ('target','deathtarget','combattarget','killtarget'):
            if k.get(field) and not (field=='target' and k['classname']=='target_spawner'):
                require(k[field] in byname,f"Unresolved {field}: {k[field]}")
    buttons=[k for k in keys if k['classname']=='func_button']
    require(len(buttons)==1 and buttons[0].get('target')=='deploy' and buttons[0].get('wait')=='-1',
            'Mission radio must start the schedule exactly once')
    schedule=defaultdict(list)
    for k in byname['deploy']:
        if k.get('target'):
            schedule[k['target']].append(float(k.get('delay',0)))
    for i,at in enumerate((20,95,170,245,320,395),1):
        require(schedule[f'wave_{i}']==[at],f'Wave {i} start is not {at}s after radio')
        delayed=[k for k in byname[f'wave_{i}'] if k['classname']=='trigger_relay']
        require(len(delayed)==1 and delayed[0].get('delay')=='1' and delayed[0].get('target')==f'bay_{i}',
                f'Bay {i} must open after its monsters spawn')
    for label,at in [('auto',80),('close',155),('boom',230),('heavy',305),('rocket',380)]:
        require(schedule['locker_'+label]==[at],f'Incorrect unlock time for {label}')
    require(schedule['time_survived']==[500],'Survival clock must run 480s after 20s prep')
    for i,at in enumerate((50,125,200,275,350,425),1):
        require(schedule[f'supply_{i}']==[at],f'Missing wave {i} resupply')
        require(len(byname[f'supply_{i}'])==8,f'Wave {i} supply count changed')
        require(all(k['classname']=='target_spawner' and vec(k['origin'])[2]>=640 for k in byname[f'supply_{i}']),
                f'Supply {i} must be spawned above reachable player hulls')
    difficulty=[]
    for skill,expected in enumerate((48,60,72)):
        active=[k for k in keys if not int(k.get('spawnflags',0))&(256<<skill)]
        monsters=[k for k in active if k['classname'].startswith('monster_')]
        counters=[k for k in active if k.get('targetname')=='hostile_down']
        require(len(monsters)==expected and len(counters)==1 and int(counters[0]['count'])==expected,
                f'Difficulty {skill}: kill counter does not match {expected} attackers')
        require(all(k.get('deathtarget')=='hostile_down' and int(k['spawnflags'])&2 for k in monsters),
                f'Difficulty {skill}: enemies must spawn only when triggered and count on death')
        for i in range(1,7):
            require(any(k.get('targetname')==f'wave_{i}' for k in monsters),f'Difficulty {skill}: empty wave {i}')
        difficulty.append({'skill':skill,'enemies':len(monsters)})
    gate=byname['victory_check']
    require(len(gate)==1 and gate[0].get('count')=='2' and gate[0].get('target')=='victory',
            'Victory must require both survival time and all kills')
    inputs=[k.get('targetname') for k in keys if k.get('target')=='victory_check']
    require(sorted(inputs)==['all_clear','time_survived'],'Victory has unexpected or missing inputs')
    # Every start, attacker and pickup gets its own actual compiled hull check.
    placements=0
    monsters=[]
    for k in keys:
        cls=k['classname']
        if cls=='target_spawner':
            origin=vec(k['origin'])
            landing=(origin[0],origin[1],16)
            hit=bsp.collision(landing,(-15,)*3,(15,)*3,SOLID)
            require(not hit,f"Supply landing at {landing} intersects {hit}")
            placements+=1
            continue
        if cls.startswith('info_player_') and cls!='info_player_intermission':
            mins,maxs,mask=PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK
        elif cls.startswith('monster_'):
            mins,maxs,mask=PLAYER_MINS,PLAYER_MAXS,MONSTER_MASK
            if cls=='monster_tank':
                mins,maxs=(-32,-32,-16),(32,32,72)
            monsters.append((k,mins,maxs))
        elif cls.startswith(('ammo_','weapon_','item_')):
            mins,maxs,mask=(-15,)*3,(15,)*3,SOLID
        else:
            continue
        hit=bsp.collision(vec(k['origin']),mins,maxs,mask)
        require(not hit,f"{cls} at {k['origin']} intersects {hit}")
        placements+=1
    for n,(k,mins,maxs) in enumerate(monsters):
        o=vec(k['origin'])
        for other,omin,omax in monsters[n+1:]:
            q=vec(other['origin'])
            require(not all(o[j]+mins[j]<q[j]+omax[j] and q[j]+omin[j]<o[j]+maxs[j] for j in range(3)),
                    f"Overlapping enemy spawns at {o} / {q}")
    routes=[]
    def route(name,points,opened=(),must_block=False):
        hits=[]
        previous=None
        for start,end in zip(points,points[1:]):
            steps=max(1,math.ceil(math.dist(start,end)/8))
            for i in range(steps+1):
                point=tuple(start[j]+(end[j]-start[j])*i/steps for j in range(3))
                hit=bsp.collision(point,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,opened)
                if hit and previous:
                    for dz in range(1,19):
                        lifted=(point[0],point[1],point[2]+dz)
                        if lifted[2]>previous[2]+18.03125:
                            break
                        if not bsp.collision(lifted,PLAYER_MINS,PLAYER_MAXS,PLAYER_MASK,opened):
                            point,hit=lifted,None
                            break
                if hit:
                    if len(hits)<3:
                        hits.append({'point':point,'hit':hit})
                else:
                    previous=point
        require(bool(hits) if must_block else not hits,f'Route {name} failed: {hits}')
        routes.append({'name':name,'blocked':bool(hits),'expected_blocked':must_block,'hits':hits})
    route('roof stairs',[(0,-608,24),(0,-552,24)]+[(0,-528+i*32,24+min((i+1)*16,152)) for i in range(10)]+[(0,-96,176)])
    route('command west entrance',[(-416,-96,24),(-128,-16,24),(0,32,24)])
    route('command east entrance',[(416,-96,24),(128,-16,24),(0,32,24)])
    route('north approach',[(0,960,24),(0,448,24),(0,256,24),(0,224,24)])
    route('east approach',[(960,-240,24),(720,-240,24),(512,-128,24),(320,-128,24)])
    route('west approach',[(-960,-240,24),(-720,-240,24),(-512,-128,24),(-320,-128,24)])
    route('rear resupply circuit',[(416,-608,24),(416,-656,24),(736,-656,24),(736,-1120,24),(0,-1120,24)])
    for label,x in [('auto',-480),('close',-240),('boom',0),('heavy',240),('rocket',480)]:
        points=[(x,-656,24),(x,-864,24)]
        route(label+' locked',points,must_block=True)
        route(label+' open',points,('locker_'+label,))
    for i,(outside,inside) in enumerate([((-736,960,24),(-736,1280,24)),((960,640,24),(1280,640,24)),
                                         ((-960,640,24),(-1280,640,24)),((736,960,24),(736,1280,24)),
                                         ((960,-640,24),(1280,-640,24)),((-960,-640,24),(-1280,-640,24))],1):
        route(f'bay {i} sealed',[outside,inside],must_block=True)
        route(f'bay {i} released',[outside,inside],(f'bay_{i}',))
    route('extraction locked',[(0,-1168,24),(0,-1456,24)],must_block=True)
    route('extraction open',[(0,-1168,24),(0,-1456,24)],('extract_open',))
    log=(ROOT/'build/maps/pp_sandwatch/bsp.log').read_text()
    require(not re.search(r'\bwarning\b|\bleaked\b|unbounded',log,re.I),'BSP compiler emitted geometry warnings')
    report={'passed':not errors,'errors':errors,'map_sha256':sha(source),'bsp_sha256':sha(a.bsp),
            'difficulty':difficulty,'placement_hulls':placements,'routes':routes}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='routes'},indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__':
    main()
