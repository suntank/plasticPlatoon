/* Exercise production projectile spawns, player/monster callers and impacts.
 * Only engine I/O and damage recipients are stubbed; firing code is real. */
#include <assert.h>
#include <stdarg.h>
#include "../../src/game/player/weapon.c"

game_import_t gi;
game_export_t globals;
game_locals_t game;
level_locals_t level;
edict_t *g_edicts;
static edict_t entities[64];
static gclient_t client;
static cvar_t zero, one = {.value=1}, normal_skill = {.value=SKILL_MEDIUM};
cvar_t *deathmatch=&zero, *coop=&zero, *dmflags=&zero, *skill=&normal_skill;
cvar_t *aimfix=&zero, *maxclients=&one;
static char models[32][MAX_QPATH], sounds[32][MAX_QPATH];
static int model_count, sound_count, links, sound_calls;
static int bytes[16], byte_count, short_value, multicasts;
static int direct_calls, direct_damage, direct_mod, splash_calls, splash_mod;
static float splash_damage, splash_radius;
static edict_t *splash_ignore, *damage_attacker;
static qboolean mine_target_visible, mine_same_team;

qboolean CanDamage(edict_t *target, edict_t *inflictor) { return mine_target_visible; }
qboolean OnSameTeam(edict_t *one, edict_t *two) { return mine_same_team; }
static int point_contents(vec3_t origin) { return 0; }
static int mine_targets(vec3_t mins, vec3_t maxs, edict_t **list, int max, int area)
{
    assert(area == AREA_SOLID && max >= 2);
    list[0] = &entities[1];
    list[1] = &entities[2];
    return 2;
}

int randk(void) { return 16384; }
float frandk(void) { return .5f; }
float crandk(void) { return 0.f; }
qboolean infront(edict_t *a, edict_t *b) { (void)a; (void)b; return true; }
void ThrowDebris(edict_t *e, char *name, float speed, vec3_t origin)
{ (void)e; (void)name; (void)speed; (void)origin; }
void T_Damage(edict_t *target, edict_t *inflictor, edict_t *attacker,
    vec3_t direction, vec3_t point, vec3_t normal, int damage, int knockback, int flags, int mod)
{
    (void)target; (void)inflictor; (void)direction; (void)point; (void)normal; (void)knockback; (void)flags;
    ++direct_calls; direct_damage=damage; direct_mod=mod; damage_attacker=attacker;
}
void T_RadiusDamage(edict_t *e, edict_t *attacker, float damage, edict_t *ignore, float radius, int mod)
{
    (void)e; ++splash_calls; splash_damage=damage; splash_radius=radius;
    splash_ignore=ignore; splash_mod=mod; damage_attacker=attacker;
}
static int index_name(char names[32][MAX_QPATH], int *count, char *name)
{
    for (int i=1;i<=*count;++i) if (!strcmp(names[i],name)) return i;
    assert(*count<31); snprintf(names[++*count],MAX_QPATH,"%s",name); return *count;
}
static int model_index(char *name) { return index_name(models,&model_count,name); }
static int sound_index(char *name) { return index_name(sounds,&sound_count,name); }
static void sound_effect(edict_t *e,int channel,int sound,float volume,float attenuation,float offset)
{ (void)e;(void)channel;(void)sound;(void)volume;(void)attenuation;(void)offset;++sound_calls; }
static void link_entity(edict_t *e) { ++links; ++e->linkcount; }
static void unlink_entity(edict_t *e) { (void)e; }
static void write_byte(int value) { assert(byte_count<16); bytes[byte_count++]=value; }
static void write_short(int value) { short_value=value; }
static void write_position(vec3_t value) { (void)value; }
static void multicast(vec3_t point,multicast_t destination) { (void)point;(void)destination;++multicasts; }
static trace_t trace_world(vec3_t start,vec3_t mins,vec3_t maxs,vec3_t end,edict_t *pass,int mask)
{ trace_t tr={0};(void)start;(void)mins;(void)maxs;(void)pass;(void)mask;tr.fraction=1;VectorCopy(end,tr.endpos);return tr; }
static YQ2_ATTR_NORETURN void error(const char *format,...)
{ va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);abort(); }

static edict_t *reset(qboolean player)
{
    memset(entities,0,sizeof(entities)); memset(&client,0,sizeof(client));
    memset(&level,0,sizeof(level)); memset(&game,0,sizeof(game));
    memset(&globals,0,sizeof(globals));
    game.maxclients=1;game.maxentities=64;game.clients=&client;
    g_edicts=entities;globals.num_edicts=10;level.time=20;level.framenum=200;
    for (int i=0;i<10;++i) { entities[i].inuse=true;entities[i].s.number=i; }
    entities[1].client=player?&client:NULL;
    entities[1].viewheight=22;entities[1].health=100;
    entities[1].flags=FL_NOTARGET; /* Avoid incidental player-noise objects. */
    client.ammo_index=7;client.pers.inventory[7]=20;client.pers.hand=RIGHT_HANDED;
    is_quad=false;is_silenced=0;deathmatch=&zero;coop=&zero;dmflags=&zero;
    links=sound_calls=byte_count=multicasts=0;short_value=-1;
    direct_calls=splash_calls=0;damage_attacker=NULL;
    return &entities[1];
}
static edict_t *last_projectile(void)
{
    assert(globals.num_edicts==11);return &entities[10];
}
static void near(float actual,float expected)
{ if(fabsf(actual-expected)>=.001f)fprintf(stderr,"expected %.6f, got %.6f\n",expected,actual);assert(fabsf(actual-expected)<.001f); }
static void assert_common(edict_t *e,edict_t *owner,const char *path,int movement,int effect)
{
    assert(e->inuse&&e->owner==owner&&e->touch&&e->think&&e->linkcount==1);
    assert(e->movetype==movement&&e->solid==SOLID_BBOX&&e->clipmask==MASK_SHOT);
    assert(e->s.effects==(unsigned)effect&&!strcmp(models[e->s.modelindex],path));
    assert(e->s.frame==0&&VectorLength(e->mins)==0&&VectorLength(e->maxs)==0);
}
static void assert_flash(int kind) { assert(byte_count==2&&bytes[0]==svc_muzzleflash&&bytes[1]==kind&&short_value==1&&multicasts==1); }

static void test_spawn_and_orientation(void)
{
    vec3_t start={10,20,30},dir={0,1,0};edict_t *owner,*e;
    owner=reset(true);fire_rocket(owner,start,dir,117,650,120,120);e=last_projectile();
    assert_common(e,owner,"models/objects/rocket/tris.md2",MOVETYPE_FLYMISSILE,EF_ROCKET);
    assert(!strcmp(e->classname,"rocket")&&!strcmp(sounds[e->s.sound],"weapons/rockfly.wav"));
    near(e->s.angles[YAW],90);near(e->s.angles[PITCH],0);near(e->velocity[1],650);
    near(e->s.origin[0],10);near(e->s.origin[1],20);near(e->s.origin[2],30);
    near(e->nextthink,32);assert(e->think==G_FreeEdict&&e->dmg==117&&e->radius_dmg==120);near(e->dmg_radius,120);
    owner=reset(false);fire_grenade(owner,start,dir,120,600,2.5f,160);e=last_projectile();
    assert_common(e,owner,"models/objects/grenade/tris.md2",MOVETYPE_BOUNCE,EF_GRENADE);
    assert(!strcmp(e->classname,"grenade")&&e->spawnflags==0);
    near(e->velocity[1],600);near(e->velocity[2],200);near(e->nextthink,22.5f);
    assert(e->dmg==120);near(e->dmg_radius,160);
    for(int axis=0;axis<3;++axis) near(e->avelocity[axis],300);
    owner=reset(false);fire_grenade2(owner,start,dir,125,500,1.5f,165,false);e=last_projectile();
    assert_common(e,owner,"models/objects/grenade2/tris.md2",MOVETYPE_BOUNCE,EF_GRENADE);
    assert(!strcmp(e->classname,"hgrenade")&&e->spawnflags==1&&sound_calls==1);
    assert(!strcmp(sounds[e->s.sound],"weapons/hgrenc1b.wav"));near(e->nextthink,21.5f);
    near(e->velocity[1],500);near(e->velocity[2],200);
    owner=reset(false);fire_mortar(owner,start,dir,500,650,10,480);e=last_projectile();
    assert_common(e,owner,"models/objects/grenade/tris.md2",MOVETYPE_BOUNCE,EF_GRENADE);
    assert(!strcmp(e->classname,"mortar")&&e->dmg==500);near(e->dmg_radius,480);
    near(e->velocity[1],650);near(e->velocity[2],650);near(e->nextthink,30);
    for(int axis=0;axis<3;++axis) near(e->avelocity[axis],300);
    puts("PASS projectile spawns: authored model paths, +X rocket orientation, velocities, point bounds, spin, effects, reports and fuses");
}
static void test_player_and_monster_callers(void)
{
    vec3_t start={10,20,30},dir={1,0,0};edict_t *owner,*e;
    for(int aimed=0;aimed<2;++aimed) {
        owner=reset(true);client.weapon_state.ads_active=aimed;client.ps.gunframe=5;
        Weapon_RocketLauncher_Fire(owner);e=last_projectile();assert_flash(MZ_ROCKET);
        near(e->velocity[0],650);near(e->dmg,110);near(e->dmg_radius,120);assert(e->radius_dmg==120);
        assert(client.pers.inventory[7]==19&&client.ps.gunframe==6);
        near(e->s.origin[1],aimed?0:-8);
        owner=reset(true);client.weapon_state.ads_active=aimed;client.ps.gunframe=6;
        weapon_grenadelauncher_fire(owner);e=last_projectile();assert_flash(MZ_GRENADE);
        near(e->velocity[0],aimed?900:600);near(e->velocity[2],200);near(e->nextthink,22.5f);
        assert(e->dmg==120&&client.pers.inventory[7]==19&&client.ps.gunframe==7);
        owner=reset(true);client.weapon_state.ads_active=aimed;client.ps.gunframe=9;
        weapon_bfg_fire(owner);e=last_projectile();assert_flash(MZ_BFG);
        near(e->velocity[0],aimed?975:650);near(e->velocity[2],650);near(e->nextthink,30);
        assert(e->dmg==500&&client.pers.inventory[7]==19&&client.ps.gunframe==10);
        near(client.v_dmg_pitch,-40);
    }
    owner=reset(true);deathmatch=&one;weapon_bfg_fire(owner);assert(last_projectile()->dmg==200);
    owner=reset(true);is_quad=true;Weapon_RocketLauncher_Fire(owner);assert(last_projectile()->dmg==440&&last_projectile()->radius_dmg==480);
    owner=reset(true);dmflags=&(cvar_t){.value=DF_INFINITE_AMMO};weapon_grenadelauncher_fire(owner);assert(client.pers.inventory[7]==20);
    owner=reset(true);client.pers.inventory[7]=0;weapon_bfg_fire(owner);assert(globals.num_edicts==10&&client.ps.gunframe==1);
    owner=reset(true);client.grenade_time=level.time+1;weapon_grenade_fire(owner,true);e=last_projectile();
    assert_common(e,owner,"models/objects/grenade2/tris.md2",MOVETYPE_BOUNCE,EF_GRENADE);
    assert(e->spawnflags==3&&e->dmg==125&&client.pers.inventory[7]==19);near(e->velocity[0],666);near(e->nextthink,21);
    owner=reset(false);monster_fire_rocket(owner,start,dir,60,450,MZ2_SOLDIER_ROCKET);e=last_projectile();
    assert_common(e,owner,"models/objects/rocket/tris.md2",MOVETYPE_FLYMISSILE,EF_ROCKET);
    assert(e->dmg==60&&e->radius_dmg==60);near(e->dmg_radius,80);near(e->velocity[0],450);
    assert(bytes[0]==svc_muzzleflash2&&bytes[1]==MZ2_SOLDIER_ROCKET);
    owner=reset(false);monster_fire_grenade(owner,start,dir,50,600,MZ2_GUNNER_GRENADE_1);e=last_projectile();
    assert_common(e,owner,"models/objects/grenade/tris.md2",MOVETYPE_BOUNCE,EF_GRENADE);
    assert(e->dmg==50);near(e->dmg_radius,90);near(e->nextthink,22.5f);
    assert(bytes[0]==svc_muzzleflash2&&bytes[1]==MZ2_GUNNER_GRENADE_1);
    puts("PASS production callers: player hip/ADS speed, ammo, quad, recoil and monster rocket/grenade routing preserved");
}
static void test_contacts_fuses_and_explosions(void)
{
    vec3_t start={0,0,0},dir={1,0,0};edict_t target={.takedamage=DAMAGE_YES};
    cplane_t plane={.normal={0,0,1}};csurface_t sky={.flags=SURF_SKY};
    edict_t *owner=reset(false);fire_rocket(owner,start,dir,117,650,120,120);edict_t *e=last_projectile();
    e->touch(e,owner,&plane,NULL);assert(e->inuse&&!direct_calls&&!splash_calls);
    e->touch(e,&target,&plane,NULL);assert(!e->inuse&&direct_calls==1&&direct_damage==117&&direct_mod==MOD_ROCKET);
    assert(splash_calls==1&&splash_mod==MOD_R_SPLASH&&splash_damage==120&&splash_radius==120&&splash_ignore==&target&&damage_attacker==owner);
    assert(bytes[0]==svc_temp_entity&&bytes[1]==TE_ROCKET_EXPLOSION);
    owner=reset(false);fire_rocket(owner,start,dir,117,650,120,120);e=last_projectile();e->waterlevel=1;
    e->touch(e,&target,NULL,NULL);assert(bytes[1]==TE_ROCKET_EXPLOSION_WATER&&direct_mod==MOD_ROCKET);
    owner=reset(false);fire_rocket(owner,start,dir,117,650,120,120);e=last_projectile();e->touch(e,&target,&plane,&sky);
    assert(!e->inuse&&!direct_calls&&!splash_calls&&!byte_count);
    for(int hand=0;hand<2;++hand) for(int grounded=0;grounded<2;++grounded) for(int water=0;water<2;++water) {
        owner=reset(false);
        if(hand)fire_grenade2(owner,start,dir,125,500,1,165,false);else fire_grenade(owner,start,dir,120,600,2.5f,160);
        e=last_projectile();e->touch(e,&entities[0],NULL,NULL);assert(e->inuse&&sound_calls>=1&&!splash_calls);
        e->groundentity=grounded?&entities[0]:NULL;e->waterlevel=water;e->think(e);
        assert(!e->inuse&&splash_calls==1&&splash_mod==(hand?MOD_HG_SPLASH:MOD_G_SPLASH));
        assert(bytes[1]==(grounded?(water?TE_GRENADE_EXPLOSION_WATER:TE_GRENADE_EXPLOSION):(water?TE_ROCKET_EXPLOSION_WATER:TE_ROCKET_EXPLOSION)));
    }
    owner=reset(false);fire_grenade2(owner,start,dir,125,500,0,165,true);e=last_projectile();
    assert(!e->inuse&&splash_mod==MOD_HELD_GRENADE&&links==0);
    owner=reset(false);fire_grenade(owner,start,dir,120,600,2.5f,160);e=last_projectile();e->touch(e,&target,NULL,NULL);
    assert(direct_calls==1&&direct_damage==120&&direct_mod==MOD_GRENADE&&splash_mod==MOD_G_SPLASH);
    owner=reset(false);fire_mortar(owner,start,dir,500,650,10,480);e=last_projectile();e->touch(e,owner,NULL,NULL);assert(e->inuse);
    e->touch(e,&target,NULL,NULL);assert(!e->inuse&&direct_damage==500&&direct_mod==MOD_BFG_BLAST);
    assert(splash_damage==500&&splash_radius==480&&splash_mod==MOD_BFG_BLAST&&bytes[1]==TE_MORTAR_EXPLOSION);
    puts("PASS impacts/fuses: owner and sky handling, bouncing, direct/splash damage, cooked/held grenades, water and mortar explosions");
}

static void test_proximity_mine(void)
{
    const pp_throwable_params_t params = {.speed = 650, .arm_delay_sec = 0.5f, .radius = 160};
    vec3_t start = {0, 0, 0}, dir = {1, 0, 0};
    const vec3_t normals[] = {{0, 0, 1}, {0, 1, 0}, {0, 0, -1}};
    gclient_t guest = {0};
    gi.pointcontents = point_contents;
    gi.BoxEdicts = mine_targets;

    for (int i = 0; i < ARRLEN(normals); ++i)
    {
        edict_t *owner = reset(true);
        assert(fire_proximity_mine(owner, start, dir, &params, 150));
        edict_t *mine = last_projectile();
        near(mine->velocity[0], 650);
        assert(mine->movetype == MOVETYPE_TOSS && mine->clipmask == MASK_SOLID);
        assert(!strcmp(models[mine->s.modelindex], PP_PROX_MINE_MODEL));
        cplane_t plane = {0};
        vec3_t facing;
        VectorCopy(normals[i], plane.normal);
        mine->touch(mine, &entities[0], &plane, NULL);
        AngleVectors(mine->s.angles, facing, NULL, NULL);
        near(DotProduct(facing, plane.normal), 1);
        near(DotProduct(mine->s.origin, plane.normal), 0.5f);
        assert(mine->solid == SOLID_NOT && mine->movetype == MOVETYPE_NONE && !mine->touch);

        edict_t *target = &entities[2];
        target->health = 100;
        target->takedamage = DAMAGE_AIM;
        target->svflags = SVF_MONSTER;
        mine_target_visible = true;
        mine->think(mine);
        assert(mine->inuse && !mine->s.skinnum && !splash_calls);

        level.time = mine->delay;
        target->monsterinfo.aiflags = AI_GOOD_GUY;
        mine->think(mine);
        assert(mine->inuse && mine->s.skinnum == 1);
        target->monsterinfo.aiflags = 0;
        mine_target_visible = false;
        mine->think(mine);
        assert(mine->inuse);
        mine_target_visible = true;
        target->client = &guest;
        coop = &one;
        mine->think(mine);
        assert(mine->inuse);
        if (i == 0)
        {
            coop = &zero;
            deathmatch = &one;
            mine_same_team = true;
            mine->think(mine);
            assert(mine->inuse);
            mine_same_team = false;
        }
        else
        {
            target->client = NULL;
        }
        VectorSet(target->s.origin, 140, 0, 0);
        mine->think(mine);
        assert(mine->inuse);
        VectorClear(target->s.origin);
        mine->think(mine);
        assert(!mine->inuse && splash_calls == 1 && !direct_calls);
        assert(splash_mod == MOD_PROX_MINE && damage_attacker == owner);
        near(splash_radius, 160);
    }

    edict_t *owner = reset(true);
    assert(fire_proximity_mine(owner, start, dir, &params, 150));
    edict_t *mine = last_projectile();
    edict_t *door = &entities[3];
    door->solid = SOLID_BSP;
    cplane_t wall = {.normal = {1, 0, 0}};
    mine->touch(mine, door, &wall, NULL);
    VectorSet(door->s.origin, 100, 200, 0);
    door->s.angles[YAW] = 90;
    mine->think(mine);
    near(mine->s.origin[0], 100);
    near(mine->s.origin[1], 200.5f);
    near(mine->s.angles[YAW], 90);
    PP_RemoveOwnedMines(owner);
    assert(!mine->inuse);
    puts("PASS proximity mines: surface alignment, moving brushes, arming, hostile-only detection, occlusion and cleanup");
}

int main(void)
{
    gi.modelindex=model_index;gi.soundindex=sound_index;gi.sound=sound_effect;
    gi.linkentity=link_entity;gi.unlinkentity=unlink_entity;gi.trace=trace_world;gi.error=error;
    gi.WriteByte=write_byte;gi.WriteShort=write_short;gi.WritePosition=write_position;gi.multicast=multicast;
    test_spawn_and_orientation();test_player_and_monster_callers();test_contacts_fuses_and_explosions();
    test_proximity_mine();
    return 0;
}
