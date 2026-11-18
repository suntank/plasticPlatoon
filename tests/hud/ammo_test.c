/* Exercise the real game status builder across ammo-less and finite weapons. */
#include "../../src/game/header/local.h"
#include <assert.h>

static cvar_t zero;
static int image_index(char *name) { assert(name && name[0]); return 1; }
static void config_string(int index, char *value) { (void)index; (void)value; }

int main(void)
{
    edict_t player = {0};
    gclient_t client = {0};
    deathmatch = coop = dmflags = &zero;
    gi.imageindex = image_index;
    gi.configstring = config_string;
    InitItems();
    SetItemNames();
    gitem_t *pistol = FindItem("Pistol");
    gitem_t *smg = FindItem("SMG");
    gitem_t *rifle = FindItem("Rifle");
    gitem_t *knife = FindItem("Knife");
    gitem_t *light = FindItem("Light Bullets");
    gitem_t *heavy = FindItem("Heavy Bullets");
    assert(pistol && smg && rifle && knife && light && heavy);
    assert(FindItem("Bullets") == heavy);
    assert(FindItem(pistol->ammo) == light && FindItem(smg->ammo) == light);
    assert(FindItem(rifle->ammo) == heavy);
    player.client = &client;
    player.health = 100;
    client.pers.health = 100;
    client.pers.selected_item = -1;
    client.pers.max_bullets = 999;
    client.pers.weapon = pistol;
    client.ammo_index = ITEM_INDEX(light);
    assert(light->quantity == 50 && Add_Ammo(&player, light, light->quantity));
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == 50 && client.ps.stats[STAT_AMMO_ICON]);
    assert(client.pers.inventory[ITEM_INDEX(heavy)] == 0);

    client.pers.weapon = smg;
    assert(Add_Ammo(&player, light, 975));
    assert(!Add_Ammo(&player, light, light->quantity));
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == 999 && client.ps.stats[STAT_AMMO_ICON]);

    client.pers.weapon = rifle;
    client.ammo_index = ITEM_INDEX(heavy);
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == 0 && client.ps.stats[STAT_AMMO_ICON]);

    client.pers.weapon = knife;
    client.ammo_index = 0;
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == -1 && !client.ps.stats[STAT_AMMO_ICON]);
    puts("Shared Light Bullets HUD and pickup cap, separate Heavy Bullets, and knife HUD passed");
    return 0;
}
