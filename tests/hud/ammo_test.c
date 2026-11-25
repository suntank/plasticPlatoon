/* Exercise the real game status builder across ammo-less and finite weapons. */
#include "../../src/game/header/local.h"
#include <assert.h>

static cvar_t zero;
static int image_index(char *name)
{
    assert(name && name[0]);
    if (!strcmp(name, PP_SPRUES_ICON)) return 2;
    if (!strcmp(name, "a_throwable_mine")) return 3;
    return 1;
}
static void config_string(int index, char *value) { (void)index; (void)value; }

static void test_mine_resupply(edict_t *player)
{
    gclient_t *client = player->client;
    gitem_t *mines = FindItemByClassname("ammo_prox_mines");
    assert(mines && mines->quantity == 2);
    int index = ITEM_INDEX(mines);
    quartermaster_t *shop = &client->quartermaster;
    const usercmd_t release = {0}, buy = {.buttons = BUTTON_ATTACK};

    Q_strlcpy(level.mapname, "pp_quartermaster_test", sizeof(level.mapname));
    level.intermission_state = INTERMISSION_QUARTERMASTER;
    player->inuse = client->pers.connected = true;
    shop->progress.sprues = 500;
    QM_Enter(player);
    QM_Shortcut(player, "2");
    QM_Shortcut(player, "down"); /* armor */
    QM_Shortcut(player, "down"); /* grenades */
    QM_Shortcut(player, "down"); /* mines */
    QM_Input(player, &release);
    QM_Input(player, &buy);
    assert(shop->progress.sprues == 375 && client->pers.inventory[index] == 2);
    assert(QM_AmmoCap(client, AMMO_PROX_MINES) == 4);

    QM_Shortcut(player, "1");
    for (int i = 0; i < QM_DEMOLITION; i++) QM_Shortcut(player, "down");
    QM_Input(player, &release);
    QM_Input(player, &buy);
    assert(shop->progress.sprues == 275 && shop->progress.tier[QM_DEMOLITION] == 1);
    assert(QM_AmmoCap(client, AMMO_PROX_MINES) == 6 && QM_AmmoCap(client, AMMO_GRENADES) == 6);
    assert(Add_Ammo(player, mines, 99) && client->pers.inventory[index] == 6);

    assert(PP_SelectedThrowable(client) == FindItem("Grenades"));
    client->weapon_state.selected_throwable = AMMO_THROWABLE_MINE;
    G_SetStats(player);
    assert(client->ps.stats[STAT_GRENADES] == 6 && client->ps.stats[STAT_GRENADE_ICON] == 3);
    puts("Mine resupply, shared Demolition Pouch upgrade, inventory cap and selected-item HUD passed");
}

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

    Q_strlcpy(level.mapname, "PP_QUARTERMASTER_TEST", sizeof(level.mapname));
    G_SetStats(&player);
    assert(client.ps.stats[STAT_SPRUES_ICON] == 2);
    assert(!client.ps.stats[STAT_SPRUES_LOW] && !client.ps.stats[STAT_SPRUES_HIGH]);
    client.quartermaster.progress.sprues = 0x1234fedc;
    G_SetStats(&player);
    assert((unsigned short)client.ps.stats[STAT_SPRUES_LOW] == 0xfedc);
    assert(client.ps.stats[STAT_SPRUES_HIGH] == 0x1234);
    level.mapname[0] = '\0';
    G_SetStats(&player);
    assert(!client.ps.stats[STAT_SPRUES_ICON] && !client.ps.stats[STAT_SPRUES_LOW] &&
        !client.ps.stats[STAT_SPRUES_HIGH]);
    puts("Sprues HUD displays zero and full wallet balances on campaign maps");
    test_mine_resupply(&player);
    return 0;
}
