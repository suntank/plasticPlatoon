#include "../../src/game/header/local.h"
#include <assert.h>

extern void Pmove(pmove_t *pm);
extern game_export_t *GetGameAPI(game_import_t *import);

void Com_DPrintf(const char *format, ...) {}

static cvar_t vars[128];
static int var_count, retries;
static const char *command;
static qboolean block_reach, block_first_pad;
static edict_t *patient, *medic, *third, *objective;

static cvar_t *
Cvar(const char *name, const char *value, int flags)
{
	for (int i = 0; i < var_count; ++i)
		if (!strcmp(vars[i].name, name))
			return &vars[i];
	assert(var_count < ARRLEN(vars));
	cvar_t *var = &vars[var_count++];
	var->name = (char *)name;
	var->string = (char *)value;
	var->value = atof(value);
	var->flags = flags;
	return var;
}

static void
Print(const char *format, ...)
{
}

static void
Broadcast(int priority, const char *format, ...)
{
	if (!strncmp(format, "Squad wiped.", 12))
		++retries;
}

static void
Link(edict_t *ent)
{
	VectorAdd(ent->s.origin, ent->mins, ent->absmin);
	VectorAdd(ent->s.origin, ent->maxs, ent->absmax);
}

static void
Unlink(edict_t *ent)
{
}

static int
Index(char *name)
{
	return name != NULL;
}

static void
Config(int index, char *value)
{
}

static void
WriteInt(int value)
{
}

static void
WriteString(char *value)
{
}

static void
WriteVector(vec3_t value)
{
}

static void
Multicast(vec3_t origin, multicast_t type)
{
}

static void
Unicast(edict_t *ent, qboolean reliable)
{
}

static void
Sound(edict_t *ent, int channel, int index, float volume, float attenuation, float offset)
{
}

static int
Contents(vec3_t point)
{
	return 0;
}

static trace_t
Trace(vec3_t start, vec3_t mins, vec3_t maxs, vec3_t end, edict_t *pass, int mask)
{
	trace_t trace = {.fraction = 1};
	VectorCopy(end, trace.endpos);
	if (mins && start[2] + mins[2] >= 0 && end[2] + mins[2] < 0)
	{
		trace.fraction = (start[2] + mins[2]) / (start[2] - end[2]);
		trace.endpos[2] = -mins[2];
		trace.plane.normal[2] = 1;
		trace.ent = world;
		trace.contents = CONTENTS_SOLID;
	}
	if ((block_reach && mask == MASK_SOLID) ||
		(block_first_pad && start[0] == 300 && VectorCompare(start, end)))
	{
		trace.fraction = 0;
		trace.startsolid = true;
		trace.ent = world;
	}
	return trace;
}

static int
BoxEdicts(vec3_t mins, vec3_t maxs, edict_t **list, int count, int type)
{
	if (objective)
	{
		list[0] = objective;
		return 1;
	}
	return 0;
}

static void
TouchObjective(edict_t *ent, edict_t *other, cplane_t *plane, csurface_t *surface)
{
	++ent->count;
}

static char *
Arg(int index)
{
	return (char *)command;
}

static void
Start(int players)
{
	memset(&level, 0, sizeof(level));
	memset(g_edicts, 0, game.maxentities * sizeof(*g_edicts));
	memset(game.clients, 0, game.maxclients * sizeof(*game.clients));
	globals.num_edicts = game.maxclients + 1;
	coop->value = 1;
	deathmatch->value = 0;
	block_reach = block_first_pad = false;
	objective = NULL;
	retries = 0;
	strcpy(level.mapname, "pp_coop_test");
	level.framenum = 80;
	level.time = 8;
	world->inuse = true;
	world->classname = "worldspawn";
	for (int i = 1; i <= players; ++i)
	{
		edict_t *start = G_Spawn();
		start->classname = i == 1 ? "info_player_start" : "info_player_coop";
		VectorSet(start->s.origin, (i - 1) * 56, 0, 24);
		edict_t *ent = &g_edicts[i];
		G_InitEdict(ent);
		ent->client = &game.clients[i - 1];
		InitClientPersistant(ent->client);
		InitClientResp(ent->client);
		PutClientInServer(ent);
		ent->s.origin[2] = 24;
		ent->groundentity = world;
	}
	patient = &g_edicts[1];
	medic = &g_edicts[2];
	third = &g_edicts[3];
}

static void
Damage(edict_t *ent, int amount)
{
	T_Damage(ent, world, world, vec3_origin, ent->s.origin, vec3_origin,
		amount, 0, DAMAGE_NO_ARMOR, MOD_TRIGGER_HURT);
}

static void
Input(edict_t *ent, int buttons)
{
	usercmd_t cmd = {.buttons = buttons, .msec = 100};
	ClientThink(ent, &cmd);
}

static void
Tick(edict_t *user, int buttons, int frames)
{
	for (int i = 0; i < frames; ++i)
	{
		if (user)
			Input(user, buttons);
		++level.framenum;
		level.time = level.framenum * FRAMETIME;
		Coop_RescueFrame();
	}
}

static int
Progress(edict_t *ent)
{
	Coop_RescueStats(ent);
	return ent->client->ps.stats[STAT_COOP_REVIVE];
}

static void
CheckRevives(void)
{
	Start(3);
	patient->health = patient->max_health = 125;
	Damage(patient, 600);
	assert(patient->health == 0 && !patient->deadflag);
	assert(patient->client->coop_rescue.bleedout_frame == level.framenum + 250);
	int deadline = patient->client->coop_rescue.bleedout_frame;
	gitem_t *weapon = patient->client->pers.weapon;
	objective = G_Spawn();
	objective->classname = "trigger_once";
	objective->touch = TouchObjective;
	usercmd_t crawl = {.forwardmove = 400, .upmove = 400, .buttons = BUTTON_ATTACK, .msec = 100};
	crawl.angles[YAW] = ANGLE2SHORT(90);
	ClientThink(patient, &crawl);
	assert(patient->s.origin[1] > 0 && patient->s.origin[1] <= 6.125f);
	assert(patient->s.origin[2] == 24 && patient->client->ps.pmove.pm_flags & PMF_DUCKED);
	assert(patient->client->ps.viewangles[YAW] == 90 && !patient->client->ps.gunindex);
	assert(patient->client->pers.weapon == weapon && !patient->client->weapon_thunk);
	assert(!objective->count);
	edict_t *nearby = objective;
	objective = NULL;
	command = "weapnext";
	ClientCommand(patient);
	assert(!patient->client->newweapon);
	edict_t *loot = G_Spawn();
	loot->item = FindItem("Sprues");
	Touch_Item(loot, patient, NULL, NULL);
	assert(patient->client->quartermaster.progress.sprues == 0);

	Tick(medic, BUTTON_USE, 7);
	int progress = Progress(medic);
	assert(progress > 1 && Progress(patient) == progress && Progress(third) == 0);
	Input(medic, 0);
	assert(!Progress(patient));

	Tick(medic, BUTTON_USE, 6);
	assert(Progress(patient) > 1);
	Damage(patient, 10);
	Tick(medic, BUTTON_USE, 5);
	assert(!Progress(patient));
	Tick(medic, 0, 1);
	Tick(medic, BUTTON_USE, 5);
	Damage(medic, 5);
	Tick(medic, BUTTON_USE, 5);
	assert(!Progress(medic));

	Tick(medic, 0, 1);
	Tick(medic, BUTTON_USE, 5);
	medic->s.origin[0] = 100;
	Tick(medic, BUTTON_USE, 1);
	assert(!Progress(patient));
	medic->s.origin[0] = 56;
	Tick(medic, 0, 1);
	block_reach = true;
	Tick(medic, BUTTON_USE, 5);
	assert(!Progress(patient));
	Tick(medic, 0, 1);
	block_reach = false;
	assert(patient->client->coop_rescue.bleedout_frame == deadline);
	Tick(medic, BUTTON_USE, 20);
	assert(patient->health == 0 && Progress(patient) > 1);
	Tick(medic, BUTTON_USE, 1);
	assert(patient->health == 37 && !Coop_IsIncapacitated(patient));
	assert(!Progress(patient) && !Progress(medic) && patient->client->pers.weapon == weapon);
	objective = nearby;
	Input(patient, 0);
	assert(objective->count == 1);
}

static edict_t *
Checkpoint(const char *name, const char *pads)
{
	edict_t *checkpoint = G_Spawn();
	checkpoint->targetname = (char *)name;
	checkpoint->target = (char *)pads;
	SP_target_platoon_checkpoint(checkpoint);
	return checkpoint;
}

static void
Pad(const char *pads, int x)
{
	edict_t *pad = G_Spawn();
	pad->classname = "info_notnull";
	pad->targetname = (char *)pads;
	VectorSet(pad->s.origin, x, 0, 24);
}

static void
BleedOut(edict_t *ent)
{
	Damage(ent, 500);
	Tick(NULL, 0, 249);
	assert(ent->client->coop_rescue.bleedout_frame);
	Tick(NULL, 0, 1);
	assert(ent->client->coop_rescue.awaiting_redeploy);
}

static void
CheckRedeploy(void)
{
	Start(3);
	edict_t *old = Checkpoint("old", "old_pads");
	edict_t *next = Checkpoint("next", "next_pads");
	Pad("old_pads", 200);
	Pad("next_pads", 300);
	Pad("next_pads", 350);
	old->use(old, world, medic);
	gclient_t *client = patient->client;
	int ammo = ITEM_INDEX(FindItem("Light Bullets"));
	client->pers.inventory[ammo] = 17;
	client->quartermaster.progress.sprues = 30;
	client->quartermaster.progress.tier[QM_HEALTH] = 1;
	patient->max_health = 125;
	BleedOut(patient);
	assert(client->chase_target == medic && client->resp.spectator);
	Input(patient, BUTTON_ATTACK);
	assert(client->chase_target == medic);
	old->use(old, world, medic);
	assert(client->coop_rescue.awaiting_redeploy);
	Coop_RescueStats(patient);
	assert(client->ps.stats[STAT_COOP_RESCUE] == COOP_RESCUE_WAITING);
	QM_AwardSprues(5, false);
	assert(client->quartermaster.progress.sprues == 35);

	ClientDisconnect(medic);
	Tick(NULL, 0, 1);
	assert(client->chase_target == third);
	block_first_pad = true;
	next->use(next, world, third);
	assert(patient->s.origin[0] == 350 && patient->health == 125 && !client->resp.spectator);
	assert(!client->chase_target && client->pers.inventory[ammo] == 17);
	assert(client->quartermaster.progress.sprues == 35 &&
		client->quartermaster.progress.tier[QM_HEALTH] == 1);

	BleedOut(patient);
	next->use(next, world, third);
	assert(client->coop_rescue.awaiting_redeploy);
	edict_t *exit = G_Spawn();
	exit->map = "pp_next_mission";
	BeginIntermission(exit);
	assert(QM_IsOpen());
	assert(patient->health == 125 && !Coop_IsIncapacitated(patient) && !client->resp.spectator);
	assert(!QM_Frame() && client->quartermaster.squad_size == 2);
	for (int i = 0; i < 2; ++i)
	{
		edict_t *ent = i == 0 ? patient : third;
		usercmd_t up = {.forwardmove = 200};
		Input(ent, 0);
		ClientThink(ent, &up);
		Input(ent, BUTTON_ATTACK);
	}
	assert(QM_Frame());
	SaveClientData();
	assert(client->pers.health == 125 && client->pers.inventory[ammo] == 17);
	InitClientResp(client);
	PutClientInServer(patient);
	assert(Coop_IsStanding(patient) && patient->max_health == 125);
	assert(client->pers.inventory[ammo] == 17);
	assert(client->quartermaster.progress.sprues == 35);
}

static void
CheckWipesAndDisconnects(void)
{
	Start(3);
	Damage(patient, 500);
	Tick(medic, BUTTON_USE, 8);
	assert(Progress(patient) > 1);
	ClientDisconnect(medic);
	Tick(NULL, 0, 1);
	assert(!Progress(patient) && !retries);
	Damage(third, 500);
	Tick(NULL, 0, 1);
	assert(retries == 1 && Coop_IsStanding(patient) && Coop_IsStanding(third));

	Start(3);
	Damage(patient, 500);
	Damage(medic, 500);
	Tick(NULL, 0, 1);
	assert(!retries && Coop_IsIncapacitated(patient) && Coop_IsIncapacitated(medic));
	Damage(third, 500);
	Tick(NULL, 0, 1);
	assert(retries == 1 && Coop_IsStanding(patient) && Coop_IsStanding(medic) && Coop_IsStanding(third));

	Start(2);
	BleedOut(patient);
	ClientDisconnect(medic);
	Tick(NULL, 0, 1);
	assert(retries == 1 && Coop_IsStanding(patient));

	Start(3);
	Damage(patient, 500);
	Tick(medic, BUTTON_USE, 8);
	ClientDisconnect(patient);
	Tick(medic, BUTTON_USE, 1);
	assert(!Progress(medic) && !retries);
	BleedOut(third);
	ClientDisconnect(third);
	Tick(NULL, 0, 1);
	assert(!retries && Coop_IsStanding(medic));
}

int
main(void)
{
	game_import_t imports = {
		.bprintf = Broadcast, .dprintf = Print, .sound = Sound, .argv = Arg,
		.configstring = Config, .modelindex = Index, .soundindex = Index, .imageindex = Index,
		.WriteByte = WriteInt, .WriteShort = WriteInt, .WriteString = WriteString,
		.WritePosition = WriteVector, .WriteDir = WriteVector,
		.unicast = Unicast, .multicast = Multicast, .linkentity = Link, .unlinkentity = Unlink,
		.trace = Trace, .pointcontents = Contents, .BoxEdicts = BoxEdicts, .Pmove = Pmove, .cvar = Cvar
	};
	GetGameAPI(&imports);
	maxclients = Cvar("maxclients", "4", 0);
	deathmatch = Cvar("deathmatch", "0", 0);
	coop = Cvar("coop", "1", 0);
	dmflags = Cvar("dmflags", "0", 0);
	skill = Cvar("skill", "1", 0);
	sv_gravity = Cvar("sv_gravity", "800", 0);
	game.maxentities = 96;
	game.maxclients = 4;
	game.clients = calloc(game.maxclients, sizeof(*game.clients));
	g_edicts = calloc(game.maxentities, sizeof(*g_edicts));
	InitItems();
	Coop_RescueInit();
	CheckRevives();
	CheckRedeploy();
	CheckWipesAndDisconnects();
	coop->value = 0;
	assert(!Coop_RescueActive());
	coop->value = deathmatch->value = 1;
	assert(!Coop_RescueActive());
	deathmatch->value = 0;
	strcpy(level.mapname, "base1");
	assert(!Coop_RescueActive());
	puts("Campaign rescue, interruption, checkpoint, mission exit, disconnect and wipe passed");
	free(game.clients);
	free(g_edicts);
	return 0;
}
