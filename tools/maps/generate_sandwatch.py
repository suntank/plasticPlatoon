#!/usr/bin/env python3
"""Generate Operation Sandwatch using Sandkeep's editable brush vocabulary.

Vanilla Q2 entities implement the entire encounter, including save/load. No
engine patch, repeated spawn point, or wave that waits for the last straggler.
"""
from __future__ import annotations

import json
from pathlib import Path

import generate_sandkeep as g

ROOT = Path(__file__).resolve().parents[2]
PREP = 20
SURVIVAL = 480
WAVES = [
    (0, "NORTHWEST SCOUTS", 6),
    (75, "EASTERN RAIDERS", 8),
    (150, "WESTERN BREACH", 10),
    (225, "NORTHEAST GRENADIERS", 10),
    (300, "EASTERN SHOCK TROOPS", 12),
    (375, "WESTERN ARMORED COLUMN", 14),
]
LOCKERS = [
    (-480, "AUTO", 60, "RIFLE", ["weapon_machinegun"] + ["ammo_bullets"] * 8),
    (-240, "CLOSE", 135, "DOUBLE BARREL SHOTGUN", ["weapon_supershotgun"] + ["ammo_shells"] * 8),
    (0, "BOOM", 210, "GRENADE LAUNCHER", ["weapon_grenadelauncher"] + ["ammo_gl_rounds"] * 6),
    (240, "HEAVY", 285, "HEAVY MACHINEGUN", ["weapon_chaingun"] + ["ammo_bullets"] * 10),
    (480, "ROCKET", 360, "ROCKET LAUNCHER", ["weapon_rocketlauncher"] + ["ammo_rockets"] * 8),
]


def relay(name, target=None, delay=0, message=None, **kw):
    if target:
        kw["target"] = target
    if delay:
        kw["delay"] = delay
    if message:
        kw["message"] = message.replace("\n", "\\n")
    g.entity("trigger_relay", targetname=name, **kw)


def helptext(name, text):
    g.entity("target_help", targetname=name, spawnflags=1, message=text)


def shutter(name, lo, hi):
    # Move down into the sand; none of the trim is left hanging in the opening.
    g.entity("func_door", brushes=[g.box(lo, hi, "gate_wood")],
             targetname=name, angle=-2, speed=96, lip=2, wait=-1, sounds=1)


def north_sign(cx,y,z,name,width=224,height=112):
    x=cx-width/2
    sx,sy=width/256,height/128
    g.wb((x,y-4,z),(x+width,y,z+height),"trim",detail=True,
         face_overrides={3:dict(texture=name,scale=(sx,sy),shift=(-x/sx,(z+height)/sy))})


def signs():
    from generate_sandkeep_materials import panel, text, write_wal
    from platoon_palette import load_palette
    palette = load_palette()
    labels = {
        "sw_mission": ["OP SANDWATCH", "6 WAVES / 8 MIN", "TOUCH RADIO TO START"],
        "sw_radio": ["HOLD THE BASE", "20 SEC TO DEPLOY", "TOUCH CONTROL BELOW"],
        "sw_exit": ["EXTRACTION", "SURVIVE 8 MIN", "CLEAR ALL HOSTILES"],
        "sw_wave": ["DEPLOYMENT BAY", "HOSTILE APPROACH", "WATCH THE SHUTTERS"],
        "sw_ammo": ["RESUPPLY", "FRESH EACH WAVE", "SHARE WITH SQUAD"],
    }
    for _, label, at, _, _ in LOCKERS:
        labels["sw_" + label.lower()] = [label + " LOCKER", f"OPENS {at//60} MIN {at%60:02}", "AMMO AND WEAPON"]
    dest = ROOT / "baseq2/textures/sandkeep"
    dest.mkdir(parents=True, exist_ok=True)
    for name, lines in labels.items():
        im, draw = panel(color=(32, 62, 66), accent=(218, 191, 101))
        for y, line in zip((24, 56, 88), lines):
            text(draw, 128, y, line, 2, (230, 221, 180))
        im.save(dest / (name + ".png"))
        write_wal(dest / (name + ".wal"), "sandkeep/" + name, im, palette)


def arena():
    g.wb((-1600,-1600,-192),(1600,1600,0),"sand")
    g.wb((-1600,-1600,768),(1600,1600,800),"sky")
    for lo, hi in [((-1600,-1600,0),(-1536,1600,320)),
                   ((1536,-1600,0),(1600,1600,320)),
                   ((-1536,1536,0),(1536,1600,320)),
                   ((-1536,-1600,0),(1536,-1536,320))]:
        g.wb(lo,hi,"wood")
        g.wb((lo[0],lo[1],320),(hi[0],hi[1],800),"sky")
    for x in (-1536,1488):
        g.wb((x,-1536,296),(x+48,1536,328),"wood_end",detail=True)
        for y in range(-1408,1500,384):
            g.wb((x+12,y,328),(x+36,y+24,332),"iron",detail=True)
    # Low, broken breastworks allow enemies and defenders to move around both
    # ends. The three broad approaches connect to a complete circuit of cover.
    for x, X in [(-656,-224),(224,656)]:
        g.wb((x,400,0),(X,448,64))
        g.crenels_x(x,X,400,64,depth=48,step=144)
    for x in (-672,624):
        for y,Y in [(-624,-304),(64,352)]:
            g.wb((x,y,0),(x+48,Y,88))
    g.tower(-576,352,72,112)
    g.tower(576,352,72,112)
    # Roofed command bunker, with two through entrances and a north firing gap.
    for x in (-240,208):
        for y,Y in [(-224,-96),(64,192)]:
            g.wb((x,y,0),(x+32,Y,128))
        g.wb((x,-96,96),(x+32,64,128))
    g.wb((-240,160,0),(-80,192,128))
    g.wb((80,160,0),(240,192,128))
    g.wb((-80,160,96),(80,192,128))
    g.wb((-240,-224,0),(240,-192,128))
    g.wb((-256,-240,128),(256,208,152),"wood")
    # Sixteen-unit risers meet the roof exactly; no jumping is required.
    for i in range(1,10):
        g.wb((-80,-528+(i-1)*32,0),(80,-528+i*32,min(i*16,152)),"sand",detail=True)
    g.wb((-80,-240,0),(80,-208,152),"sand",detail=True)
    for x,X in [(-256,-80),(80,256)]:
        g.wb((x,-240,152),(X,-216,192),detail=True)
    for x in (-256,232):
        g.wb((x,-216,152),(x+24,208,192),detail=True)
    g.wb((-256,184,152),(-64,208,192),detail=True)
    g.wb((64,184,152),(256,208,192),detail=True)
    g.ceiling_lamp(0,-16,120,450,"0.72 0.88 1")
    g.console(0,112,0,"radio","deploy")
    g.panel(0,106,160,"sw_radio")
    # Flag and aerial are visual rally points for players arriving in co-op.
    g.wb((176,-144,152),(192,-128,440),"wood",detail=True)
    g.wb((192,-142,352),(320,-134,424),"plastic_green_smooth",detail=True)
    g.wb((-200,-152,152),(-192,-144,384),"iron",detail=True)
    g.wb((-248,-152,344),(-144,-144,352),"iron",detail=True)
    # Starter supplies on both flanks: weapons stay for other co-op players;
    # finite ammunition and health are shared as in Sandkeep.
    for x in (-416,416):
        g.pickup("weapon_shotgun",x,-336)
        g.pickup("item_armor_jacket",x,-432)
        for dx in (-48,48):
            for y in (-272,-368,-464):
                g.pickup("ammo_shells",x+dx,y)
    for x,y in [(-128,-32),(128,-32),(-384,160),(384,160)]:
        g.pickup("item_health_large",x,y)
    for x,y in [(0,-608),(-112,-608),(112,-608),(0,-656)]:
        g.entity("info_player_start" if (x,y)==(0,-608) else "info_player_coop",(x,y,24),angle=90)
    g.panel(-880,-1200,32,"sw_mission")
    # Toy-scale silhouettes sit clear of the enemy approach centerlines.
    for x,y,yaw in [(-864,352,18),(864,352,-15),(-480,800,-12),(480,800,10)]:
        g.rotated_box(x,y,112,112,0,112,yaw,letters=True)
    g.tipped_bucket(-976,-1152,144,208)
    g.garden_spade(1120,-1200)
    for x,y in [(-864,-64),(864,-64),(-240,656),(240,656)]:
        g.shaped_mound(x,y,128,96,48)
    g.spool(-848,-416,72,48)
    g.spool(848,-416,72,48)
    for x,y in [(-1152,896),(1152,896),(-1120,-1392),(1120,-1392)]:
        g.light(x,y,256,600)
    for x,y in [(-448,0),(448,0),(0,640),(0,-1104)]:
        g.light(x,y,288,700)


def armory():
    for x, label, at, weapon, items in LOCKERS:
        left,right=x-112,x+112
        g.wb((left,-992,0),(left+16,-704,144))
        g.wb((right-16,-992,0),(right,-704,144))
        g.wb((left+16,-992,0),(right-16,-976,144))
        g.wb((left,-992,144),(right,-704,168),"wood")
        name="locker_"+label.lower()
        shutter(name,(left+16,-728,0),(right-16,-712,144))
        # South-facing signs are readable from the rear supply lane.
        north_sign(x,-704,176,"sw_"+label.lower())
        g.ceiling_lamp(x,-848,136,320)
        for index,item in enumerate(items):
            g.pickup(item,x-64+(index%3)*64,-776-(index//3)*56)
        relay("deploy",name,PREP+at,
              f"{weapon} UNLOCKED\n{label} locker open in the rear supply row.")
    north_sign(0,-992,176,"sw_ammo",width=256,height=128)
    for wave,(at,_,_) in enumerate(WAVES,1):
        for i,(item,x,y) in enumerate([
            ("ammo_shells",-360,-1120),("ammo_shells",-240,-1120),
            ("ammo_bullets",-120,-1120),("ammo_bullets",0,-1120),
            ("ammo_bullets",120,-1120),("item_health_large",240,-1120),
            ("item_health_large",360,-1120),("item_armor_combat",480,-1120),
        ]):
            # This game's SpawnItem clears ITEM_TRIGGER_SPAWN. Use the stock
            # spawner instead, well above reachable player hulls (its use does
            # a KillBox), and let the supplies fall onto the open sand strip.
            # Previous waves' uncollected supplies remain available below.
            g.entity("target_spawner",(x,y,640),target=item,targetname=f"supply_{wave}")
        relay("deploy",f"supply_{wave}",PREP+at+30)


def bay(wave, cx, cy, yaw):
    """Rotate a north-facing sealed deployment room around its center.

    Each room is used exactly once and opens AFTER its monsters materialize.
    Closed future rooms prevent players entering a later spawn's KillBox.
    """
    import math
    c,s=round(math.cos(math.radians(yaw))),round(math.sin(math.radians(yaw)))
    def p(x,y,z):
        return (cx+x*c-y*s,cy+x*s+y*c,z)
    def b(lo,hi):
        points=[p(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
        return tuple(min(v[i] for v in points) for i in range(3)),tuple(max(v[i] for v in points) for i in range(3))
    for lo,hi in [((-352,-240,0),(-320,240,224)),((320,-240,0),(352,240,224)),
                  ((-320,208,0),(320,240,224)),((-320,-240,0),(-240,-208,224)),
                  ((240,-240,0),(320,-208,224)),((-240,-240,160),(240,-208,224)),
                  ((-352,-240,224),(352,240,256))]:
        g.wb(*b(lo,hi),"sand_wall")
    shutter(f"bay_{wave}",*b((-240,-232,0),(240,-216,160)))
    g.ceiling_lamp(cx,cy,216,550)
    at,label,count=WAVES[wave-1]
    remaining=SURVIVAL-at
    relay("deploy",f"wave_{wave}",PREP+at,
          f"WAVE {wave} / 6 - {label}\nHold the base. {remaining//60}:{remaining%60:02} remaining.")
    # The first spawn tick completes before the door can expose the room.
    relay(f"wave_{wave}",f"bay_{wave}",1)
    g.entity("target_speaker",(0,0,192),targetname=f"wave_{wave}",
             noise="world/klaxon1.wav",attenuation=-1,volume=.65,spawnflags=4)
    helptext(f"wave_{wave}",f"Wave {wave}/6: {label}. Hold until 8:00, then clear survivors and extract south.")
    # Distinct combat points force every attacker toward the outpost even if
    # the radio operator has moved behind cover. No enemy waits inside a bay.
    for i in range(count+2):
        x=-192+(i%4)*128
        y=-112+(i//4)*80
        kind=("monster_soldier_light" if i%3 else "monster_soldier")
        if wave>=2 and i%3==0:
            kind="monster_soldier_ss"
        if wave>=4 and i%4==0:
            kind="monster_gunner"
        if wave==6 and i==0:
            kind="monster_tank"
        # Base count - 2 on easy, base on medium, base + 2 on hard/nightmare.
        skill=0 if i<count-2 else (256 if i<count else 768)
        g.entity(kind,p(x,y,32),angle=(270+yaw)%360,
                 spawnflags=2|skill,targetname=f"wave_{wave}",
                 combattarget=f"rally_{wave}_{i}",deathtarget="hostile_down")
        rx,ry=p(x*.6,-500,24)[:2]
        # One-use point_combat belongs to exactly one enemy.
        g.entity("point_combat",(rx,ry,24),targetname=f"rally_{wave}_{i}")


def encounter():
    # Starting is a physical, single-use radio button. Prep is outside the
    # survival clock; wave 1 is time zero for all subsequent unlocks.
    relay("deploy",message="OPERATION SANDWATCH\n20 seconds to prepare.\nSix waves. Hold for eight minutes.")
    helptext("deploy","Prepare for 20 seconds. Six waves over eight minutes. Weapon lockers open before each escalation.")
    for wave,args in enumerate([(-736,1280,0),(1280,640,270),(-1280,640,90),
                                 (736,1280,0),(1280,-640,270),(-1280,-640,90)],1):
        bay(wave,*args)
    for skill,count in [(1536,48),(1280,60),(768,72)]:
        g.entity("trigger_counter",targetname="hostile_down",count=count,
                 spawnflags=skill|1,target="all_clear")
    relay("all_clear","victory_check",message="ALL SIX WAVES CLEARED\nHold position until the survival clock expires.")
    relay("deploy","time_survived",PREP+SURVIVAL,
          "EIGHT MINUTES SURVIVED\nClear any remaining attackers.\nExtraction opens when the base is secure.")
    relay("time_survived","victory_check")
    helptext("time_survived","Eight minutes survived. Eliminate remaining hostiles to unlock the southern extraction bunker.")
    for at,remaining in [(60,7),(120,6),(180,5),(240,4),(360,2),(420,1)]:
        relay("deploy",f"minute_{remaining}",PREP+at)
        relay(f"minute_{remaining}",message=f"HOLD THE BASE\n{remaining} minute{'s' if remaining!=1 else ''} remaining.")
    g.entity("trigger_counter",targetname="victory_check",count=2,spawnflags=1,target="victory")
    # Delay completion messaging so it wins over the clock or last-kill text.
    relay("victory","extract_open",1,"BASE SECURED\nSix waves defeated.\nSouthern extraction bunker is open!")
    helptext("extract_open","Base secured. Move to the southern extraction bunker to finish the mission.")
    g.entity("target_goal",targetname="extract_open")
    # Extraction is sealed by geometry and a mover, not an always-live trigger
    # in open space. Returning co-op players can always reach the finish.
    g.wb((-208,-1536,0),(-176,-1232,192))
    g.wb((176,-1536,0),(208,-1232,192))
    g.wb((-208,-1536,192),(208,-1232,224),"wood")
    shutter("extract_open",(-176,-1264,0),(176,-1248,192))
    north_sign(0,-1232,240,"sw_exit",width=256,height=128)
    g.ceiling_lamp(0,-1408,184,450,"0.6 1 0.65")
    g.trigger((-160,-1504,0),(160,-1360,96),"mission_complete")
    g.entity("target_changelevel",targetname="mission_complete",map="*pp_sandwatch")
    g.entity("info_player_intermission",(0,-1104,480),angles="28 90 0")


def main():
    g.WORLD.clear()
    g.ENTITIES.clear()
    signs()
    arena()
    armory()
    encounter()
    out=ROOT/"maps/source/pp_sandwatch.map"
    out.write_text('// Operation Sandwatch: generated editable Q2 MAP.\n'
                   '{\n"classname" "worldspawn"\n"message" "Operation Sandwatch"\n'
                   '"sky" "sandkeep"\n"sounds" "0"\n'+''.join(g.WORLD)+'}\n'+''.join(g.ENTITIES))
    schedule={"map":"pp_sandwatch","prep_seconds":PREP,"survival_seconds":SURVIVAL,
              "waves":[{"wave":i,"at":at,"label":label,"easy":n-2,"medium":n,"hard":n+2}
                       for i,(at,label,n) in enumerate(WAVES,1)],
              "unlocks":[{"at":at,"locker":label,"weapon":weapon} for _,label,at,weapon,_ in LOCKERS]}
    dest=ROOT/"build/maps/pp_sandwatch/schedule.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(schedule,indent=2)+'\n')
    print(f"{out}: {len(g.WORLD)} world brushes, {len(g.ENTITIES)} entities")


if __name__=="__main__":
    main()
