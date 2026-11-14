/* Include only from gl1_main.c after perf_impl.h. GL1 and GLES1 share this.
 * CPU scope times include preparation and driver submission, not GPU completion.
 * HUD/menu submission is outside RenderFrame and excluded from these per-view data.
 */
static cvar_t *r_drawprofile;
int pp_drawprofile_active;
static int dp_category, dp_inline;
static unsigned dp_flush_reason;
static double dp_started;
static uint64_t dp_draws[DP_CLASSES], dp_flushes[8], dp_inline_draws[256];
static double dp_ms[DP_CLASSES], dp_inline_ms[256];
static double dp_world_metrics[DPW_METRICS];
static uint64_t dp_world_flushes[8], dp_total_draws;
static const char *const dp_world_names[] = {"world_mark_ms", "brush_light_ms", "brush_light_models", "brush_light_surface_tests", "brush_light_dlight_tests", "lm_regen_ms", "lm_regen_runs", "lm_atlases_scanned", "lm_surfaces_scanned", "lm_changed_surfaces", "lm_build_ms", "lm_build_calls", "lm_build_texels", "lm_upload_ms", "lm_upload_calls", "lm_upload_bytes", "world_chain_ms", "world_chain_draws", "world_blend_ms", "world_blend_draws", "world_sky_ms", "world_sky_draws", "world_alpha_ms", "world_alpha_draws", "world_visible_surfaces", "mtex_enabled", "lm_copy_enabled", "lm_atlas_count", "lm_static_ms", "lm_dynamic_ms", "lm_pack_ms", "lm_style_layers", "lm_style_texels", "lm_fullbright_texels", "lm_dynamic_surfaces", "lm_dynamic_light_tests", "lm_dynamic_light_hits", "lm_dynamic_light_passes", "lm_dynamic_texel_tests", "lm_upload_setup_ms", "lm_regen_useful_texels", "lm_regen_rect_texels", "lm_regen_upload_texels"};
static const char *const dp_class_names[] = {"world", "inline", "pickup", "npc_body", "npc_held", "player_body", "player_held", "viewweapon", "alias_other", "sprite", "effects", "other"};
static const char *const dp_flush_names[] = {"type", "color", "lightmap", "flags", "alpha", "vbo", "capacity", "explicit"};
static double DP_Now(void)
{
    return (double)SDL_GetPerformanceCounter() * 1000.0 / SDL_GetPerformanceFrequency();
}
double PP_DPClock(void) { return pp_drawprofile_active ? DP_Now() : 0; }
uint64_t PP_DPTotalDraws(void) { return pp_drawprofile_active ? dp_total_draws : 0; }
void PP_DPAddWorld(int metric, double value)
{
    if (pp_drawprofile_active && metric >= 0 && metric < DPW_METRICS) dp_world_metrics[metric] += value;
}
void PP_DPBegin(void)
{
    if (!r_drawprofile) r_drawprofile = ri.Cvar_Get("r_drawprofile", "0", 0);
    pp_drawprofile_active = r_drawprofile->value != 0;
    dp_category = DP_OTHER; dp_inline = -1; dp_started = 0; dp_flush_reason = 0;
    memset(dp_draws, 0, sizeof(dp_draws)); memset(dp_ms, 0, sizeof(dp_ms));
    memset(dp_flushes, 0, sizeof(dp_flushes));
    memset(dp_world_metrics, 0, sizeof(dp_world_metrics));
    if (pp_drawprofile_active) {
        dp_world_metrics[DPW_MTEX_ENABLED] = gl_config.multitexture != 0;
        dp_world_metrics[DPW_LM_COPY_ENABLED] = gl_config.lightmapcopies != 0;
    }
    memset(dp_world_flushes, 0, sizeof(dp_world_flushes)); dp_total_draws = 0;
    memset(dp_inline_draws, 0, sizeof(dp_inline_draws)); memset(dp_inline_ms, 0, sizeof(dp_inline_ms));
}
void PP_DPEnter(int category, const char *model)
{
    if (!pp_drawprofile_active) return;
    dp_category = category; dp_inline = -1;
    if (category == DP_INLINE && model && model[0] == '*') {
        int index = atoi(model + 1);
        if (index > 0 && index < 256) dp_inline = index;
    }
    dp_started = DP_Now();
}
void PP_DPLeave(void)
{
    if (!pp_drawprofile_active || !dp_started) return;
    double elapsed = DP_Now() - dp_started;
    dp_ms[dp_category] += elapsed;
    if (dp_inline >= 0) dp_inline_ms[dp_inline] += elapsed;
    dp_started = 0; dp_category = DP_OTHER; dp_inline = -1;
}
void PP_DPDraw(void)
{
    if (!pp_drawprofile_active) return;
    ++dp_draws[dp_category]; ++dp_total_draws;
    if (dp_inline >= 0) ++dp_inline_draws[dp_inline];
}
void PP_DPSetFlush(unsigned reasons) { dp_flush_reason = reasons; }
void PP_DPFlush(void)
{
    if (pp_drawprofile_active) {
        unsigned reasons = dp_flush_reason ? dp_flush_reason : DP_FLUSH_EXPLICIT;
        for (int i = 0; i < 8; ++i) if (reasons & (1U << i)) {
            ++dp_flushes[i];
            if (dp_category == DP_WORLD) ++dp_world_flushes[i];
        }
    }
    dp_flush_reason = 0;
}
static void DP_Publish(const char *name, double value)
{
    char key[96], text[64];
    snprintf(key, sizeof(key), "r_perf_dp_%s", name);
    snprintf(text, sizeof(text), "%.6f", value);
    ri.Cvar_Set(key, text);
}
void PP_DPEnd(void)
{
    if (!pp_drawprofile_active && (!r_perf || !r_perf->value)) return;
    DP_Publish("enabled", pp_drawprofile_active);
    if (!pp_drawprofile_active) return;
    PP_DPLeave();
    char name[80];
    for (int i = 0; i < DP_CLASSES; ++i) {
        snprintf(name, sizeof(name), "%s_draws", dp_class_names[i]); DP_Publish(name, dp_draws[i]);
        snprintf(name, sizeof(name), "%s_ms", dp_class_names[i]); DP_Publish(name, dp_ms[i]);
    }
    for (int i = 0; i < 8; ++i) {
        snprintf(name, sizeof(name), "flush_%s", dp_flush_names[i]); DP_Publish(name, dp_flushes[i]);
    }
    for (int i = 0; i < DPW_METRICS; ++i) DP_Publish(dp_world_names[i], dp_world_metrics[i]);
    for (int i = 0; i < 8; ++i) {
        snprintf(name, sizeof(name), "world_flush_%s", dp_flush_names[i]); DP_Publish(name, dp_world_flushes[i]);
    }
    int selected[4] = {-1,-1,-1,-1};
    for (int rank = 0; rank < 4; ++rank) {
        for (int i = 1; i < 256; ++i) {
            int used = 0;
            for (int j = 0; j < rank; ++j) used |= selected[j] == i;
            if (!used && (dp_inline_ms[i] || dp_inline_draws[i]) &&
                (selected[rank] < 0 || dp_inline_ms[i] > dp_inline_ms[selected[rank]])) selected[rank] = i;
        }
        int index = selected[rank];
        snprintf(name, sizeof(name), "inline_top%d_model", rank); DP_Publish(name, index);
        snprintf(name, sizeof(name), "inline_top%d_draws", rank); DP_Publish(name, index >= 0 ? dp_inline_draws[index] : 0);
        snprintf(name, sizeof(name), "inline_top%d_ms", rank); DP_Publish(name, index >= 0 ? dp_inline_ms[index] : 0);
    }
    pp_drawprofile_active = 0;
}
int PP_DPEntity(const entity_t *entity, const model_t *model)
{
    if (!pp_drawprofile_active) return DP_OTHER;
    const char *name = model ? model->name : "";
    if (entity->flags & RF_BEAM) return DP_EFFECTS;
    if (!model) return DP_OTHER;
    if (model->type == mod_brush) return DP_INLINE;
    if (model->type == mod_sprite) return DP_SPRITE;
    if (model->type != mod_alias) return DP_OTHER;
    if (entity->flags & RF_WEAPONMODEL) return DP_VIEWWEAPON;
    if (PP_PickupLODPath(name)) return DP_PICKUP;
    if (!strncmp(name, "players/", 8)) {
        const char *base = strrchr(name, '/');
        return base && (strstr(base, "weapon") || !strncmp(base, "/w_", 3)) ? DP_PLAYER_HELD : DP_PLAYER_BODY;
    }
    if (!strncmp(name, "models/monsters/", 16))
        return strstr(name, "/weapon_") ? DP_NPC_HELD : DP_NPC_BODY;
    if (!strncmp(name, "models/weapons/g_", 17) && (entity->flags & RF_PP_ENEMY_COLOR)) return DP_NPC_HELD;
    return DP_ALIAS_OTHER;
}
