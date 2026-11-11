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
    gitem_t *pistol, *rifle, *bullets;
    int ammo_index;

    deathmatch = coop = dmflags = &zero;
    gi.imageindex = image_index;
    gi.configstring = config_string;
    InitItems();
    SetItemNames();
    pistol = FindItem("Pistol");
    rifle = FindItem("Rifle");
    bullets = FindItem("Bullets");
    assert(pistol && rifle && bullets);
    ammo_index = ITEM_INDEX(bullets);
    player.client = &client;
    player.health = 100;
    client.pers.health = 100;
    client.pers.selected_item = -1;
    client.pers.weapon = pistol;

    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == -1 && !client.ps.stats[STAT_AMMO_ICON]);
    /* A previous weapon's ammo index cannot revive a pistol ammo readout. */
    client.ammo_index = ammo_index;
    client.pers.inventory[ammo_index] = 34;
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == -1 && !client.ps.stats[STAT_AMMO_ICON]);

    client.pers.weapon = rifle;
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == 34 && client.ps.stats[STAT_AMMO_ICON]);
    client.pers.inventory[ammo_index] = 0;
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == 0 && client.ps.stats[STAT_AMMO_ICON]);
    client.pers.weapon = pistol;
    G_SetStats(&player);
    assert(client.ps.stats[STAT_AMMO] == -1 && !client.ps.stats[STAT_AMMO_ICON]);
    puts("Pistol ammo hidden and finite weapon/empty ammo status passed");
    return 0;
}
