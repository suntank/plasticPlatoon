/* Verify the actual HUD drawing stays inside the handheld framebuffer. */
#include "../../src/client/cl_screen.c"
#include <assert.h>

client_static_t cls;
client_state_t cl;
viddef_t viddef;

static cvar_t hud_scale, compact_hud;
static int draws, icon_x[4], icon_y[4], last_x, last_y, last_w, last_h;
static qboolean check_bounds;
static qboolean check_text_bounds;
static int text_rows, text_y, text_length;
static char rendered_text[1024];

void Draw_GetPicSize(int *w, int *h, const char *name)
{
    if (!strcmp(name, "help")) { *w = 256; *h = 192; }
    else if (!strcmp(name, "field_3")) { *w = 50; *h = 24; }
    else if (!strncmp(name, "num_", 4) || !strncmp(name, "anum_", 5)) { *w = 16; *h = 24; }
    else { *w = 32; *h = 32; }
}

void Draw_PicScaled(int x, int y, const char *name, float scale)
{
    int w, h, index = -1;
    Draw_GetPicSize(&w, &h, name);
    w = (int)(w * scale); h = (int)(h * scale);
    ++draws;
    last_x = x; last_y = y; last_w = w; last_h = h;
    if (check_bounds)
        assert(x >= 0 && y >= 0 && x + w <= viddef.width && y + h <= viddef.height);
    if (!strcmp(name, "i_health")) index = 0;
    if (!strcmp(name, "i_jacketarmor")) index = 1;
    if (!strcmp(name, "a_bullets")) index = 2;
    if (!strcmp(name, "a_grenades")) index = 3;
    if (index >= 0) { icon_x[index] = x; icon_y[index] = y; }
}

void Draw_CharScaled(int x, int y, int c, float scale)
{
    if (check_text_bounds)
        assert(x >= 24 && x + 8 * scale <= 216 && y >= 36 && y + 8 * scale <= 112);
    if (!text_rows || y != text_y)
    {
        if (text_length) rendered_text[text_length++] = ' ';
        ++text_rows;
        text_y = y;
    }
    assert(text_length + 1 < sizeof(rendered_text));
    rendered_text[text_length++] = c & 0x7f;
    rendered_text[text_length] = 0;
}
void DrawStringScaled(int x, int y, const char *s, float scale) {}
void DrawAltStringScaled(int x, int y, const char *s, float scale) {}
void Com_DPrintf(const char *fmt, ...) {}
void Com_Printf(const char *fmt, ...) {}

static void setup(int width, int height)
{
    memset(&cl, 0, sizeof(cl));
    memset(icon_x, -1, sizeof(icon_x));
    draws = 0;
    text_rows = text_length = 0;
    rendered_text[0] = 0;
    viddef.width = width; viddef.height = height;
    cls.state = ca_active;
    cl.refresh_prepped = true;
    scr_initialized = true;
    r_hudscale = &hud_scale;
    scr_gamebird_hud = &compact_hud;
    hud_scale.value = 1;
    compact_hud.value = 1;
    cl.frame.playerstate.stats[STAT_HEALTH] = -99;
    cl.frame.playerstate.stats[STAT_ARMOR] = 0;
    cl.frame.playerstate.stats[STAT_AMMO] = 999;
    cl.frame.playerstate.stats[STAT_GRENADES] = 999;
    cl.frame.playerstate.stats[STAT_GRENADE_ICON] = 4;
    cl.frame.playerstate.stats[STAT_FLASHES] = 7;
    Q_strlcpy(cl.configstrings[CS_IMAGES + 4], "a_grenades", MAX_QPATH);
}

int main(void)
{
    setup(240, 240);
    check_bounds = true;
    SCR_DrawStats();
    assert(draws > 10);
    assert(icon_x[1] - icon_x[0] == 80 && icon_x[2] - icon_x[1] == 80);
    assert(icon_y[0] == icon_y[1] && icon_y[1] == icon_y[2]);
    assert(icon_y[0] > 200 && icon_y[3] == 4 && icon_x[3] > 200);
    /* Ammo-less pistol leaves its column empty, without a zero or flash. */
    setup(240, 240);
    cl.frame.playerstate.stats[STAT_AMMO] = -1;
    SCR_DrawStats();
    assert(icon_x[0] >= 0 && icon_x[1] >= 0 && icon_x[2] == -1);
    /* An actually empty ammo-consuming weapon still displays zero ammo. */
    setup(240, 240);
    cl.frame.playerstate.stats[STAT_AMMO] = 0;
    SCR_DrawStats();
    assert(icon_x[2] >= 0);
    hud_scale.value = 0;
    draws = 0;
    SCR_DrawStats();
    assert(draws == 0);

    setup(320, 240);
    SCR_DrawStats();
    assert(icon_x[0] >= 0 && icon_x[2] + 32 <= 320 && icon_y[3] == 4);

    setup(240, 240);
    SCR_ExecuteLayoutString("xv 32 yv 8 picn help");
    assert(last_x == 24 && last_y == 36 && last_w == 192 && last_h == 144);
    check_text_bounds = true;
    SCR_ExecuteLayoutString("xv 0 yv 24 cstring2 \"Mission 01: Operation Sandstorm\" "
        "xv 0 yv 54 cstring2 \"Infiltrate Sandcastle One via the broken wall or drainage pipe. Destroy its communications radio.\"");
    assert(text_rows >= 4 && text_y + 6 <= 112);
    assert(strstr(rendered_text, "Mission 01: Operation Sandstorm"));
    assert(strstr(rendered_text, "Infiltrate Sandcastle One via the broken wall or drainage pipe. Destroy its communications radio."));
    text_rows = text_length = 0;
    SCR_ExecuteLayoutString("xv 0 yv 54 cstring \"ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLM\"");
    assert(text_rows == 3);
    check_text_bounds = false;
    compact_hud.value = 0;
    check_bounds = false;
    SCR_ExecuteLayoutString("xv 32 yv 8 picn help");
    assert(last_x == -8 && last_y == 8 && last_w == 256 && last_h == 192);
    text_rows = text_length = 0;
    SCR_ExecuteLayoutString("xv 0 yv 54 cstring2 \"Infiltrate Sandcastle One via the broken wall or drainage pipe. Destroy its communications radio.\"");
    assert(text_rows == 1);
    puts("Game Bird HUD bounds, stat columns, grenade placement and word-wrapped mission help passed");
    return 0;
}
