/*
 * Plastic Platoon campaign progression and Mission Complete shop.
 * Distributed under the GNU General Public License, version 2 or later.
 */

#include <limits.h>

#include "../header/local.h"

#define QM_STAT_STEP 25
#define QM_STAT_BASE 100

static const int upgrade_prices[] = {100, 175, 250, 325};
static const char *const tier_names[] = {"0", "I", "II", "III", "IV"};
static const char *const upgrade_names[QM_UPGRADE_COUNT] = {
	"Reinforced Body", "Reinforced Vest", "Bandolier",
	"Demolition Pouch", "Heavy Ordnance Pack"
};

typedef struct
{
	const char *name;
	const char *label;
	int tag;
	int upgrade;
	int base;
	int step;
	int price;
} quartermaster_ammo_t;

/* Ammo sizes come from the same items that are picked up in the field. */
static const quartermaster_ammo_t ammo_stock[] = {
	{"Light Bullets", "Light", AMMO_LIGHT_BULLETS, QM_BANDOLIER, 150, 50, 10},
	{"Heavy Bullets", "Heavy", AMMO_BULLETS, QM_BANDOLIER, 200, 50, 12},
	{"Shells", "Shells", AMMO_SHELLS, QM_BANDOLIER, 50, 10, 10},
	{"Sniper Rounds", "Sniper", AMMO_SLUGS, QM_BANDOLIER, 15, 5, 15},
	{"Grenades", "Grenades", AMMO_GRENADES, QM_DEMOLITION, 4, 2, 8},
	{"Rockets", "Rockets", AMMO_ROCKETS, QM_ORDNANCE, 30, 3, 20},
	{"GL Ammo", "40mm", AMMO_GL_ROUNDS, QM_ORDNANCE, 30, 5, 15},
	{"Mortar Rounds", "Mortar", AMMO_MORTAR, QM_ORDNANCE, 6, 1, 18},
	{"Napalm", "Napalm", AMMO_CELLS, QM_ORDNANCE, 100, 0, 12}
};

enum
{
	QM_RESUPPLY_COUNT = 2 + ARRLEN(ammo_stock),
	QM_INPUT_UP = 1,
	QM_INPUT_DOWN = 2,
	QM_INPUT_TAB = 4,
	QM_INPUT_SELECT = 8
};

typedef struct
{
	const char *name;
	gitem_t *ammo;
	int current;
	int cap;
	int amount;
	int price;
} quartermaster_refill_t;

qboolean
QM_Campaign(void)
{
	return !deathmatch->value && !Q_strncasecmp(level.mapname, "pp_", 3);
}

qboolean
QM_IsOpen(void)
{
	return level.intermission_state == INTERMISSION_QUARTERMASTER &&
		level.time >= level.intermissiontime;
}

static qboolean
QM_IsPlayer(const edict_t *ent)
{
	return ent->inuse && ent->client && ent->client->pers.connected &&
		!ent->client->resp.spectator;
}

void
QM_AwardSprues(int amount, qboolean discovery)
{
	int i;

	if (!QM_Campaign() || level.intermissiontime || amount <= 0)
	{
		return;
	}

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *player = &g_edicts[i];
		quartermaster_progress_t *progress;

		if (!QM_IsPlayer(player))
		{
			continue;
		}

		progress = &player->client->quartermaster.progress;
		progress->sprues += Q_min(amount, INT_MAX - progress->sprues);
		if (discovery)
		{
			progress->discoveries_earned += Q_min(amount, INT_MAX - progress->discoveries_earned);
			gi.cprintf(player, PRINT_HIGH, "Squad found %d Sprues.\n", amount);
		}
		else
		{
			progress->kills_earned += Q_min(amount, INT_MAX - progress->kills_earned);
		}
	}
}

void
QM_KillReward(const edict_t *monster)
{
	int health = monster->max_health;
	int reward = 2;

	if (health >= 400)
	{
		reward = 15;
	}
	else if (health >= 100)
	{
		reward = 5;
	}

	QM_AwardSprues(reward, false);
}

static int
QM_Tier(const gclient_t *client, int upgrade)
{
	return Q_min(client->quartermaster.progress.tier[upgrade], ARRLEN(upgrade_prices));
}

static int
QM_StockCap(const quartermaster_ammo_t *stock, int tier)
{
	return stock->base + tier * stock->step;
}

int
QM_AmmoCap(const gclient_t *client, int ammo_tag)
{
	int i;

	if (QM_Campaign())
	{
		for (i = 0; i < ARRLEN(ammo_stock); ++i)
		{
			const quartermaster_ammo_t *stock = &ammo_stock[i];
			if (stock->tag == ammo_tag)
			{
				return QM_StockCap(stock, QM_Tier(client, stock->upgrade));
			}
		}
	}

	return 0;
}

int
QM_ArmorCap(const gclient_t *client)
{
	if (!QM_Campaign())
	{
		return 0;
	}

	return QM_STAT_BASE + QM_Tier(client, QM_ARMOR) * QM_STAT_STEP;
}

void
QM_ClampStock(edict_t *ent)
{
	int i;
	int *inventory = ent->client->pers.inventory;
	int armor;

	if (!QM_Campaign())
	{
		return;
	}

	for (i = 0; i < ARRLEN(ammo_stock); ++i)
	{
		const quartermaster_ammo_t *stock = &ammo_stock[i];
		gitem_t *item = FindItem(stock->name);
		int index = ITEM_INDEX(item);

		inventory[index] = Q_min(inventory[index],
			QM_StockCap(stock, QM_Tier(ent->client, stock->upgrade)));
	}

	armor = ArmorIndex(ent);
	if (armor)
	{
		inventory[armor] = Q_min(inventory[armor], QM_ArmorCap(ent->client));
	}
}

static quartermaster_refill_t
QM_Refill(edict_t *ent, int row)
{
	quartermaster_refill_t refill = {0};
	int bundle = QM_STAT_STEP;
	int price = 15;

	if (row == QM_HEALTH)
	{
		refill.name = "Health";
		refill.current = ent->health;
		refill.cap = ent->max_health;
	}
	else if (row == QM_ARMOR)
	{
		refill.name = "Armor";
		refill.current = QM_ArmorPoints(ent);
		refill.cap = QM_ArmorCap(ent->client);
	}
	else
	{
		const quartermaster_ammo_t *stock = &ammo_stock[row - 2];
		refill.name = stock->label;
		refill.ammo = FindItem(stock->name);
		refill.current = ent->client->pers.inventory[ITEM_INDEX(refill.ammo)];
		refill.cap = QM_AmmoCap(ent->client, stock->tag);
		bundle = refill.ammo->quantity;
		price = stock->price;
	}

	refill.amount = Q_max(0, Q_min(bundle, refill.cap - refill.current));
	refill.price = (price * refill.amount + bundle - 1) / bundle;
	return refill;
}

static const char *
QM_BuyUpgrade(edict_t *ent, int upgrade)
{
	quartermaster_progress_t *progress = &ent->client->quartermaster.progress;
	int tier = QM_Tier(ent->client, upgrade);

	if (tier == ARRLEN(upgrade_prices))
	{
		return "Already at Tier IV";
	}
	if (progress->sprues < upgrade_prices[tier])
	{
		return "You need more Sprues";
	}

	progress->sprues -= upgrade_prices[tier];
	progress->tier[upgrade]++;
	if (upgrade == QM_HEALTH)
	{
		ent->max_health += QM_STAT_STEP;
		ent->health += QM_STAT_STEP;
	}
	else if (upgrade == QM_ARMOR)
	{
		QM_AddArmor(ent, QM_STAT_STEP);
	}
	return "Upgrade equipped";
}

static const char *
QM_BuyRefill(edict_t *ent, int row)
{
	quartermaster_progress_t *progress = &ent->client->quartermaster.progress;
	quartermaster_refill_t refill = QM_Refill(ent, row);

	if (!refill.amount)
	{
		return "Already full";
	}
	if (progress->sprues < refill.price)
	{
		return "You need more Sprues";
	}

	if (refill.ammo)
	{
		if (!Add_Ammo(ent, refill.ammo, refill.amount))
		{
			return "Already full";
		}
	}
	else if (row == QM_HEALTH)
	{
		ent->health += refill.amount;
	}
	else
	{
		QM_AddArmor(ent, refill.amount);
	}

	progress->sprues -= refill.price;
	return "Resupply received";
}

static void
QM_LayoutLine(char *layout, int y, const char *line, qboolean highlight)
{
	char command[96];

	Com_sprintf(command, sizeof(command), "yv %d %s \"%s\" ",
		y, highlight ? "string2" : "string", line);
	Q_strlcat(layout, command, 1024);
}

static void
QM_UpgradePreview(edict_t *ent, char *layout, int upgrade)
{
	int tier = QM_Tier(ent->client, upgrade);
	int i, shown = 0;
	char line[40] = "";

	if (tier == ARRLEN(upgrade_prices))
	{
		QM_LayoutLine(layout, 155, "Tier IV equipped", false);
		return;
	}

	if (upgrade == QM_HEALTH || upgrade == QM_ARMOR)
	{
		int cap = upgrade == QM_HEALTH ? ent->max_health : QM_ArmorCap(ent->client);
		QM_LayoutLine(layout, 155, va("Capacity   %d -> %d", cap, cap + QM_STAT_STEP),
			false);
		QM_LayoutLine(layout, 167, va("+%d %s on purchase", QM_STAT_STEP,
			upgrade == QM_HEALTH ? "health" : "armor"), false);
		return;
	}

	for (i = 0; i < ARRLEN(ammo_stock); ++i)
	{
		const quartermaster_ammo_t *stock = &ammo_stock[i];
		char change[24];

		if (stock->upgrade != upgrade || !stock->step)
		{
			continue;
		}

		Com_sprintf(change, sizeof(change), "%s %d>%d", stock->label,
			QM_StockCap(stock, tier), QM_StockCap(stock, tier + 1));
		if (shown % 2)
		{
			Q_strlcat(line, "   ", sizeof(line));
		}
		Q_strlcat(line, change, sizeof(line));
		if (shown++ % 2)
		{
			QM_LayoutLine(layout, 155 + (shown - 2) / 2 * 12, line, false);
			line[0] = '\0';
		}
	}

	if (line[0])
	{
		QM_LayoutLine(layout, 155 + shown / 2 * 12, line, false);
	}
}

static void
QM_SendLayout(edict_t *ent)
{
	const quartermaster_t *shop = &ent->client->quartermaster;
	const quartermaster_progress_t *progress = &shop->progress;
	char layout[1024] = "quartermaster xv 16 ";
	int rows = shop->page ? QM_RESUPPLY_COUNT : QM_UPGRADE_COUNT;
	qboolean has_unaffordable = false;
	int i;

	QM_LayoutLine(layout, 16, "MISSION COMPLETE  /  QUARTERMASTER", true);
	QM_LayoutLine(layout, 32, va("%d Sprues", progress->sprues), true);
	QM_LayoutLine(layout, 44, va("Earned  %d combat  +  %d found",
		progress->kills_earned, progress->discoveries_earned), false);
	QM_LayoutLine(layout, 61, shop->page ? " Upgrades [RESUPPLY] ADD  COST" :
		"[UPGRADES] Resupply     TIER   COST", true);

	for (i = 0; i < rows; ++i)
	{
		char line[42];
		char marker = shop->row == i ? '>' : ' ';
		int price = 0;

		if (shop->page)
		{
			quartermaster_refill_t refill = QM_Refill(ent, i);

			if (refill.amount)
			{
				price = refill.price;
				Com_sprintf(line, sizeof(line), "%c %-9s %4d/%-3d +%3d %4d",
					marker, refill.name, refill.current, refill.cap, refill.amount,
					price);
			}
			else
			{
				Com_sprintf(line, sizeof(line), "%c %-9s %4d/%-3d   FULL",
					marker, refill.name, refill.current, refill.cap);
			}
		}
		else
		{
			int tier = QM_Tier(ent->client, i);

			if (tier == ARRLEN(upgrade_prices))
			{
				Com_sprintf(line, sizeof(line), "%c %-20s    IV   MAX", marker,
					upgrade_names[i]);
			}
			else
			{
				price = upgrade_prices[tier];
				Com_sprintf(line, sizeof(line), "%c %-20s %3s>%-3s %4d", marker,
					upgrade_names[i], tier_names[tier], tier_names[tier + 1],
					price);
			}
		}

		if (price > progress->sprues)
		{
			Q_strlcat(line, " *", sizeof(line));
			has_unaffordable = true;
		}

		QM_LayoutLine(layout, 78 + i * (shop->page ? 10 : 13), line,
			shop->row == i);
	}

	if (!shop->page && shop->row < rows)
	{
		QM_UpgradePreview(ent, layout, shop->row);
	}

	QM_LayoutLine(layout, 192, va("%c %-15s Squad ready %d/%d",
		shop->row == rows ? '>' : ' ', shop->ready ? "Unready" : "Ready",
		shop->ready_count, shop->squad_size), shop->row == rows);
	if (shop->feedback[0] || has_unaffordable)
	{
		QM_LayoutLine(layout, 206, shop->feedback[0] ? shop->feedback :
			"* Need more Sprues", false);
	}
	QM_LayoutLine(layout, 220, "UP/DOWN ROW  JUMP TAB  FIRE SELECT", false);

	gi.WriteByte(svc_layout);
	gi.WriteString(layout);
	gi.unicast(ent, true);
}

void
QM_Enter(edict_t *ent)
{
	quartermaster_t *shop = &ent->client->quartermaster;
	quartermaster_progress_t progress = shop->progress;

	memset(shop, 0, sizeof(*shop));
	shop->progress = progress;
	shop->input = ~0u;
	shop->redraw = true;
	ent->client->showscores = false;
	ent->client->showinventory = false;
	ent->client->showhelp = false;
	ent->takedamage = DAMAGE_NO;
}

void
QM_Input(edict_t *ent, const usercmd_t *cmd)
{
	quartermaster_t *shop = &ent->client->quartermaster;
	int rows = shop->page ? QM_RESUPPLY_COUNT : QM_UPGRADE_COUNT;
	unsigned int input = 0;
	unsigned int pressed;

	if (cmd->forwardmove > 80)
	{
		input |= QM_INPUT_UP;
	}
	else if (cmd->forwardmove < -80)
	{
		input |= QM_INPUT_DOWN;
	}
	if (cmd->upmove > 80)
	{
		input |= QM_INPUT_TAB;
	}
	if (cmd->buttons & BUTTON_ATTACK)
	{
		input |= QM_INPUT_SELECT;
	}

	pressed = input & ~shop->input;
	shop->input = input;
	if (!pressed)
	{
		return;
	}

	if (pressed & QM_INPUT_SELECT)
	{
		if (shop->row == rows)
		{
			shop->ready = !shop->ready;
			Q_strlcpy(shop->feedback, shop->ready ? "Waiting for the squad" : "",
				sizeof(shop->feedback));
		}
		else if (!shop->ready)
		{
			const char *result = shop->page ? QM_BuyRefill(ent, shop->row) :
				QM_BuyUpgrade(ent, shop->row);
			Q_strlcpy(shop->feedback, result, sizeof(shop->feedback));
		}
	}
	else if (!shop->ready)
	{
		shop->feedback[0] = '\0';
		if (pressed & QM_INPUT_TAB)
		{
			shop->page = !shop->page;
			shop->row = 0;
		}
		else
		{
			shop->row = (shop->row + ((pressed & QM_INPUT_UP) ? rows : 1)) % (rows + 1);
		}
	}
	shop->redraw = true;
}

qboolean
QM_Frame(void)
{
	int i, ready = 0, players = 0;

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *player = &g_edicts[i];

		if (QM_IsPlayer(player))
		{
			++players;
			ready += player->client->quartermaster.ready;
		}
	}

	if (players > 0 && ready == players)
	{
		return true;
	}

	for (i = 1; i <= game.maxclients; ++i)
	{
		edict_t *player = &g_edicts[i];
		quartermaster_t *shop;

		if (!QM_IsPlayer(player))
		{
			continue;
		}

		shop = &player->client->quartermaster;
		if (shop->redraw || shop->ready_count != ready || shop->squad_size != players)
		{
			shop->redraw = false;
			shop->ready_count = ready;
			shop->squad_size = players;
			QM_SendLayout(player);
		}
	}

	return false;
}
