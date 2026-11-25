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
	const char *portrait;
	int tag;
	int upgrade;
	int base;
	int step;
	int price;
} quartermaster_ammo_t;

/* Ammo sizes come from the same items that are picked up in the field. */
static const quartermaster_ammo_t ammo_stock[] = {
	{"Light Bullets", "Light", "light", AMMO_LIGHT_BULLETS, QM_BANDOLIER, 150, 50, 10},
	{"Heavy Bullets", "Heavy", "heavy", AMMO_BULLETS, QM_BANDOLIER, 200, 50, 25},
	{"Shells", "Shells", "shells", AMMO_SHELLS, QM_BANDOLIER, 50, 10, 40},
	{"Sniper Rounds", "Sniper", "sniper", AMMO_SLUGS, QM_BANDOLIER, 15, 5, 65},
	{"GL Ammo", "40mm", "gl", AMMO_GL_ROUNDS, QM_ORDNANCE, 30, 5, 90},
	{"Grenades", "Grenades", "grenades", AMMO_GRENADES, QM_DEMOLITION, 4, 2, 110},
	{"Proximity Mines", "Mines", "mines", AMMO_PROX_MINES, QM_DEMOLITION, 4, 2, 125},
	{"Rockets", "Rockets", "rockets", AMMO_ROCKETS, QM_ORDNANCE, 30, 3, 180},
	{"Napalm", "Napalm", "napalm", AMMO_CELLS, QM_ORDNANCE, 100, 0, 225},
	{"Mortar Rounds", "Mortar", "mortar", AMMO_MORTAR, QM_ORDNANCE, 6, 1, 300}
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
		(!ent->client->resp.spectator || ent->client->coop_rescue.awaiting_redeploy);
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
		refill.name = stock->name;
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

/* SpawnEntities rebuilds this catalog from the mission even on a save load. */
static byte mission_weapons[MAX_ITEMS];

void
QM_ClearMapWeapons(void)
{
	memset(mission_weapons, 0, sizeof(mission_weapons));
}

void
QM_RecordMapWeapon(const gitem_t *item)
{
	if (QM_Campaign() && (item->flags & IT_WEAPON) && item->pickup)
	{
		mission_weapons[ITEM_INDEX(item)] = true;
	}
}

static int
QM_WeaponOffers(const edict_t *ent, gitem_t **offers)
{
	int count = 0;

	for (int i = 1; i < game.num_items; i++)
	{
		if (mission_weapons[i] && ent->client->pers.inventory[i] <= 0)
		{
			offers[count++] = GetItemByIndex(i);
		}
	}
	return count;
}

static int
QM_WeaponPrice(const gitem_t *weapon)
{
	switch (weapon->weapmodel)
	{
		case WEAP_SHOTGUN:
		case WEAP_SMG:
		case WEAP_KNIFE:
			return 175;
		case WEAP_SUPERSHOTGUN:
		case WEAP_MACHINEGUN:
			return 200;
		case WEAP_GRENADELAUNCHER:
		case WEAP_ROCKETLAUNCHER:
		case WEAP_HYPERBLASTER:
		case WEAP_BFG:
			return 250;
		default:
			return 225;
	}
}

static int
QM_WeaponAmmo(const edict_t *ent, const gitem_t *ammo)
{
	if (!ammo)
	{
		return 0;
	}
	return Q_clamp(QM_AmmoCap(ent->client, ammo->tag) -
		ent->client->pers.inventory[ITEM_INDEX(ammo)], 0, ammo->quantity);
}

static const char *
QM_BuyWeapon(edict_t *ent, gitem_t *weapon)
{
	quartermaster_progress_t *progress = &ent->client->quartermaster.progress;
	int price = QM_WeaponPrice(weapon);
	gitem_t *ammo = FindItem(weapon->ammo);
	int amount = QM_WeaponAmmo(ent, ammo);

	if (progress->sprues < price)
	{
		return "Need more Sprues";
	}

	ent->client->pers.inventory[ITEM_INDEX(weapon)] = 1;
	progress->sprues -= price;
	if (amount)
	{
		Add_Ammo(ent, ammo, amount);
	}
	return va("%s acquired", weapon->pickup_name);
}

static int
QM_ResupplyRows(const edict_t *ent, int *refills)
{
	qboolean available[ARRLEN(ammo_stock)] = {0};
	int rows = 2;

	refills[0] = QM_HEALTH;
	refills[1] = QM_ARMOR;

	for (int i = 1; i < game.num_items; i++)
	{
		if (ent->client->pers.inventory[i] > 0)
		{
			const gitem_t *weapon = GetItemByIndex(i);

			if ((weapon->flags & IT_WEAPON) && weapon->ammo)
			{
				for (int n = 0; n < ARRLEN(ammo_stock); n++)
				{
					if (!Q_stricmp(weapon->ammo, ammo_stock[n].name))
					{
						available[n] = true;
						break;
					}
				}
			}
		}
	}

	for (int i = 0; i < ARRLEN(ammo_stock); i++)
	{
		/* Throwables can be used with any loadout. */
		if (available[i] || ammo_stock[i].upgrade == QM_DEMOLITION)
		{
			refills[rows++] = i + 2;
		}
	}
	return rows;
}

static int
QM_ShopRows(const edict_t *ent, gitem_t **offers, int *refills)
{
	switch (ent->client->quartermaster.page)
	{
		case QM_PAGE_WEAPONS:
			return QM_WeaponOffers(ent, offers);
		case QM_PAGE_RESUPPLY:
			return QM_ResupplyRows(ent, refills);
		default:
			return QM_UPGRADE_COUNT;
	}
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
	qboolean maxed = tier == ARRLEN(upgrade_prices);
	int i, shown = 0;
	char line[40] = "";

	if (upgrade == QM_HEALTH || upgrade == QM_ARMOR)
	{
		int cap = upgrade == QM_HEALTH ? ent->max_health : QM_ArmorCap(ent->client);
		if (maxed)
		{
			QM_LayoutLine(layout, 155, va("Capacity   %d", cap), false);
		}
		else
		{
			QM_LayoutLine(layout, 155, va("Capacity   %d -> %d", cap, cap + QM_STAT_STEP),
				false);
			QM_LayoutLine(layout, 167, va("+%d %s on purchase", QM_STAT_STEP,
				upgrade == QM_HEALTH ? "health" : "armor"), false);
		}
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

		if (maxed)
		{
			Com_sprintf(change, sizeof(change), "%s %d", stock->label, QM_StockCap(stock, tier));
		}
		else
		{
			Com_sprintf(change, sizeof(change), "%s %d>%d", stock->label,
				QM_StockCap(stock, tier), QM_StockCap(stock, tier + 1));
		}
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
	char layout[1024];
	gitem_t *offers[MAX_ITEMS];
	int refills[QM_RESUPPLY_COUNT];
	int rows = QM_ShopRows(ent, offers, refills);
	qboolean weapons = shop->page == QM_PAGE_WEAPONS;
	qboolean resupply = shop->page == QM_PAGE_RESUPPLY;
	int focus = Q_clamp(shop->row, 0, rows);
	int first = weapons ? Q_clamp(focus - QM_WEAPON_VISIBLE_ROWS + 1, 0,
		Q_max(0, rows - QM_WEAPON_VISIBLE_ROWS)) : 0;
	int last = weapons ? Q_min(rows, first + QM_WEAPON_VISIBLE_ROWS) : rows;
	qboolean has_unaffordable = false;
	int i;

	/* The themed client uses the page and equipped tiers to decorate the
	 * standard layout. Older clients skip these tokens and draw the strings. */
	if (weapons)
	{
		Com_sprintf(layout, sizeof(layout), "quartermaster qmweap %s xv 16 ",
			focus < rows ? offers[focus]->classname : "-");
	}
	else if (resupply)
	{
		Q_strlcpy(layout, "quartermaster qmres xv 16 ", sizeof(layout));
	}
	else
	{
		char tiers[QM_UPGRADE_COUNT + 1];

		for (i = 0; i < QM_UPGRADE_COUNT; i++)
		{
			tiers[i] = '0' + QM_Tier(ent->client, i);
		}
		tiers[i] = '\0';
		Com_sprintf(layout, sizeof(layout), "quartermaster qmup %s xv 16 ", tiers);
	}

	QM_LayoutLine(layout, 16, "MISSION COMPLETE  /  QUARTERMASTER", true);
	QM_LayoutLine(layout, 32, va("%d Sprues", progress->sprues), true);
	QM_LayoutLine(layout, 44, va("Earned  %d combat  +  %d found",
		progress->kills_earned, progress->discoveries_earned), false);
	if (weapons)
	{
		QM_LayoutLine(layout, 61, rows > QM_WEAPON_VISIBLE_ROWS ?
			va("WEAPONS %d-%d/%d", first + 1, last, rows) : "WEAPONS", true);
	}
	else
	{
		QM_LayoutLine(layout, 61, resupply ? "Upgrades [RESUPPLY] Weapons" :
			"[UPGRADES] Resupply Weapons", true);
	}

	for (i = first; i < last; ++i)
	{
		char line[42];
		char marker = focus == i ? '>' : ' ';
		int price = 0;

		if (weapons)
		{
			price = QM_WeaponPrice(offers[i]);
			Com_sprintf(line, sizeof(line), "%c %-26.26s %4d", marker,
				offers[i]->pickup_name, price);
		}
		else if (resupply)
		{
			quartermaster_refill_t refill = QM_Refill(ent, refills[i]);

			if (refill.amount)
			{
				price = refill.price;
				Com_sprintf(line, sizeof(line), "%c %-13s %4d/%-3d +%3d %4d",
					marker, refill.name, refill.current, refill.cap, refill.amount,
					price);
			}
			else
			{
				Com_sprintf(line, sizeof(line), "%c %-13s %4d/%-3d   FULL",
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

		QM_LayoutLine(layout, 78 + (i - first) * (resupply || weapons ? 10 : 13), line,
			focus == i);
	}

	if (weapons)
	{
		if (!rows)
		{
			QM_LayoutLine(layout, 155, "No missed weapons this mission", false);
		}
		else if (focus < rows)
		{
			gitem_t *ammo = FindItem(offers[focus]->ammo);
			int amount = QM_WeaponAmmo(ent, ammo);

			if (amount)
			{
				QM_LayoutLine(layout, 155, va("Includes %d %s", amount, ammo->pickup_name), false);
			}
			else if (ammo)
			{
				QM_LayoutLine(layout, 155, va("%s stock full", ammo->pickup_name), false);
			}
		}
	}
	else if (!resupply && focus < rows)
	{
		QM_UpgradePreview(ent, layout, focus);
	}

	QM_LayoutLine(layout, 192, va("%c %-15s Squad ready %d/%d",
		focus == rows ? '>' : ' ', shop->ready ? "Unready" : "Ready",
		shop->ready_count, shop->squad_size), focus == rows);
	if (shop->feedback[0] || has_unaffordable)
	{
		QM_LayoutLine(layout, 206, shop->feedback[0] ? shop->feedback :
			"* Need more Sprues", false);
	}
	QM_LayoutLine(layout, 220, "UP/DOWN ROW  JUMP TAB  FIRE SELECT", false);
	Q_strlcat(layout, "qmweapons ", sizeof(layout));
	if (resupply && focus < rows)
	{
		int supply = refills[focus];
		const char *portrait = supply == QM_HEALTH ? "health" :
			supply == QM_ARMOR ? "armor" : ammo_stock[supply - 2].portrait;

		Q_strlcat(layout, va("qmsupply %s ", portrait), sizeof(layout));
	}

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

static void
QM_Move(quartermaster_t *shop, int rows, int direction, int page)
{
	if (shop->ready)
	{
		return;
	}

	shop->feedback[0] = '\0';
	if (page >= 0)
	{
		shop->page = page;
		shop->row = 0;
	}
	else
	{
		shop->row = (Q_clamp(shop->row, 0, rows) + direction + rows + 1) % (rows + 1);
	}
	shop->redraw = true;
}

void
QM_Shortcut(edict_t *ent, const char *action)
{
	quartermaster_t *shop = &ent->client->quartermaster;

	if (!QM_IsOpen() || !QM_IsPlayer(ent) || shop->ready)
	{
		return;
	}

	if (!strcmp(action, "prev") || !strcmp(action, "next"))
	{
		int page = (shop->page + QM_PAGE_COUNT + (!strcmp(action, "prev") ? -1 : 1))
			% QM_PAGE_COUNT;

		QM_Move(shop, 0, 0, page);
	}
	else if (action[0] >= '1' && action[0] <= '3' && !action[1])
	{
		QM_Move(shop, 0, 0, action[0] - '1');
	}
	else if (!strcmp(action, "up") || !strcmp(action, "down"))
	{
		gitem_t *offers[MAX_ITEMS];
		int refills[QM_RESUPPLY_COUNT];
		int rows = QM_ShopRows(ent, offers, refills);

		QM_Move(shop, rows, !strcmp(action, "up") ? -1 : 1, -1);
	}
}

void
QM_Input(edict_t *ent, const usercmd_t *cmd)
{
	quartermaster_t *shop = &ent->client->quartermaster;
	gitem_t *offers[MAX_ITEMS];
	int refills[QM_RESUPPLY_COUNT];
	int rows;
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

	rows = QM_ShopRows(ent, offers, refills);
	shop->row = Q_clamp(shop->row, 0, rows);
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
			const char *result;

			switch (shop->page)
			{
				case QM_PAGE_WEAPONS:
				{
					gitem_t *weapon = offers[shop->row];

					result = QM_BuyWeapon(ent, weapon);
					if (ent->client->pers.inventory[ITEM_INDEX(weapon)])
					{
						shop->row = Q_min(shop->row, Q_max(0, rows - 2));
					}
					break;
				}
				case QM_PAGE_RESUPPLY:
					result = QM_BuyRefill(ent, refills[shop->row]);
					break;
				default:
					result = QM_BuyUpgrade(ent, shop->row);
					break;
			}
			Q_strlcpy(shop->feedback, result, sizeof(shop->feedback));
		}
	}
	else if (pressed & QM_INPUT_TAB)
	{
		QM_Move(shop, rows, 0, (shop->page + 1) % QM_PAGE_COUNT);
	}
	else
	{
		QM_Move(shop, rows, (pressed & QM_INPUT_UP) ? -1 : 1, -1);
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
