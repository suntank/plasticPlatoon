/* Shared behavioral sound checks, linked against the real game module. */
static void
expect_insect_sound(const char *species, const char *event, int channel)
{
    char prefix[MAX_QPATH];
    snprintf(prefix, sizeof(prefix), "%s/%s_", species, event);
    assert(!strncmp(sounds[played_sound], prefix, strlen(prefix)));
    assert(sound_channel == channel);
    assert(sound_volume > 0 && sound_volume <= 1 && sound_offset == 0);
}

static void
check_insect_sounds(edict_t *(*spawn)(void), const char *species,
        int precached, const char *savepath)
{
    edict_t *insect, *enemy;
    mmove_t *move;
    cvar_t nightmare = {0};
    int first, calls, i, is_ant = !strcmp(species, "ant");
    float cooldown;

    sound_count = sound_calls = 0;
    insect = spawn();
    enemy = insect->enemy;
    assert(sound_count == precached + 1); /* Shared gib sound plus this species. */
    assert(sound_calls == 0);
    assert(insect->monsterinfo.idle && insect->monsterinfo.search);
    assert((insect->monsterinfo.sight != NULL) == is_ant);
    for (i = 1; i <= sound_count; ++i)
        assert(!strstr(sounds[i], "spider/sight"));

    /* Quiet idle variants use the existing engine idle/search callbacks. */
    insect->monsterinfo.idle(insect);
    assert(sound_calls == 0); /* No idle chatter over an active fight. */
    insect->enemy = NULL;
    insect->monsterinfo.idle(insect);
    expect_insect_sound(species, "idle", CHAN_VOICE);
    assert(sound_attenuation == ATTN_IDLE && sound_volume < 1);
    first = played_sound;
    insect->monsterinfo.search(insect);
    expect_insect_sound(species, "idle", CHAN_VOICE);
    assert(sound_calls == 2 && played_sound != first);

    /* Exercise real visual acquisition, including blocked sight and no
     * repeated alert when the same target is already acquired. */
    level.framenum = 100;
    level.sight_client = enemy;
    enemy->light_level = 128;
    calls = sound_calls;
    blocked_sight = 1;
    assert(!FindTarget(insect) && sound_calls == calls);
    blocked_sight = 0;
    assert(FindTarget(insect) && insect->enemy == enemy);
    assert(sound_calls == calls + is_ant);
    if (is_ant) {
        expect_insect_sound(species, "sight", CHAN_VOICE);
        first = played_sound;
        insect->monsterinfo.sight(insect, enemy);
        assert(played_sound != first);
    }
    calls = sound_calls;
    FindTarget(insect);
    assert(sound_calls == calls);

    /* Pain remains on its existing three-second debounce. Nightmare only
     * suppresses the animation, not the hurt sound. */
    insect->pain(insect, enemy, 1, 1);
    expect_insect_sound(species, "pain", CHAN_VOICE);
    first = played_sound;
    calls = sound_calls;
    level.time += 0.1f;
    insect->pain(insect, enemy, 1, 1);
    assert(sound_calls == calls);
    insect->monsterinfo.stand(insect);
    move = insect->monsterinfo.currentmove;
    nightmare.value = SKILL_HARDPLUS;
    skill = &nightmare;
    level.time += 3;
    insect->pain(insect, enemy, 1, 1);
    expect_insect_sound(species, "pain", CHAN_VOICE);
    assert(sound_calls == calls + 1 && played_sound != first);
    assert(insect->monsterinfo.currentmove == move);
    skill = &one;

    insect->monsterinfo.melee(insect);
    expect_insect_sound(species, "attack", CHAN_WEAPON);
    first = played_sound;
    insect->monsterinfo.melee(insect);
    assert(played_sound != first);
    assert(insect->monsterinfo.currentmove->firstframe == 32);

    /* Trace a flat floor and use the real movement AI, rather than calling
     * the sound helper directly. Both walk and run retain their distances. */
    solid_floor = 1;
    insect->groundentity = &g_edicts[0];
    insect->goalentity = enemy;
    VectorSet(enemy->s.origin, 2000, 0, 24);
    link_entity(enemy);
    insect->monsterinfo.walk(insect);
    move = insect->monsterinfo.currentmove;
    level.time = 50;
    calls = sound_calls;
    assert(!g_monsterfootsteps->value); /* Combat audio works by default. */
    move->frame[0].aifunc(insect, move->frame[0].dist);
    expect_insect_sound(species, "scuttle", CHAN_BODY);
    assert(sound_calls == calls + 1 && sound_volume < 1);
    assert(insect->s.origin[0] == 4);
    first = played_sound;
    cooldown = insect->last_move_time;
    assert(cooldown == 51.5f);
    insect->monsterinfo.run(insect);
    move = insect->monsterinfo.currentmove;
    for (i = 1; i <= 14; ++i) {
        level.time = 50 + i * 0.1f;
        move->frame[0].aifunc(insect, move->frame[0].dist);
    }
    assert(sound_calls == calls + 1);
    level.time = cooldown;
    move->frame[0].aifunc(insect, move->frame[0].dist);
    expect_insect_sound(species, "scuttle", CHAN_BODY);
    assert(sound_calls == calls + 2 && played_sound != first);
    assert(insect->s.origin[0] == 4 + 15 * 12);

    /* A stopped or blocked insect cannot repeatedly play a gait burst. */
    calls = sound_calls;
    level.time += 2;
    blocked_movement = 1;
    move->frame[0].aifunc(insect, move->frame[0].dist);
    assert(sound_calls == calls);
    blocked_movement = 0;
    insect->monsterinfo.aiflags |= AI_HOLD_FRAME;
    move->frame[0].aifunc(insect, 0);
    assert(sound_calls == calls);
    insect->monsterinfo.aiflags &= ~AI_HOLD_FRAME;
    insect->groundentity = NULL;
    move->frame[0].aifunc(insect, move->frame[0].dist);
    assert(sound_calls == calls);
    insect->groundentity = &g_edicts[0];
    insect->waterlevel = 2;
    move->frame[0].aifunc(insect, move->frame[0].dist);
    assert(sound_calls == calls);
    insect->waterlevel = 0;

    /* Patrol movement without a live target and standing still are quiet. */
    insect->monsterinfo.walk(insect);
    move = insect->monsterinfo.currentmove;
    insect->enemy = NULL;
    level.sight_client = NULL;
    level.sight_entity_framenum = 0;
    insect->monsterinfo.idle_time = level.time + 100;
    move->frame[0].aifunc(insect, move->frame[0].dist);
    assert(sound_calls == calls);
    insect->monsterinfo.stand(insect);
    move = insect->monsterinfo.currentmove;
    move->frame[0].aifunc(insect, 0);
    assert(sound_calls == calls);
    insect->enemy = enemy;

    /* Save/load retains callbacks and cadence without stale sound indices. */
    enemy->pain = NULL;
    cooldown = insect->last_move_time;
    WriteLevel(savepath);
    sound_count = 0; /* Simulate a freshly indexed server/map. */
    ReadLevel(savepath);
    insect = &g_edicts[2]; enemy = &g_edicts[1];
    assert(insect->last_move_time == cooldown);
    assert(insect->monsterinfo.idle && insect->monsterinfo.search);
    assert((insect->monsterinfo.sight != NULL) == is_ant);
    insect->monsterinfo.melee(insect);
    expect_insect_sound(species, "attack", CHAN_WEAPON);

    /* A save from before audio existed has the same layout and NULL hooks. */
    insect->monsterinfo.idle = insect->monsterinfo.search = NULL;
    insect->monsterinfo.sight = NULL;
    WriteLevel(savepath); ReadLevel(savepath);
    insect = &g_edicts[2]; enemy = &g_edicts[1];
    assert(insect->monsterinfo.idle && insect->monsterinfo.search);
    assert((insect->monsterinfo.sight != NULL) == is_ant);
    assert(insect->last_move_time == cooldown && insect->enemy == enemy);
    assert(insect->monsterinfo.currentmove->firstframe == 32);

    /* No newly triggered voices on a dead entity; no damage/animation changes
     * are asserted here because the original creature tests cover them. */
    calls = sound_calls;
    insect->health = 0;
    insect->enemy = NULL;
    insect->monsterinfo.idle(insect);
    insect->monsterinfo.melee(insect);
    if (is_ant) insect->monsterinfo.sight(insect, enemy);
    level.time += 3;
    insect->pain(insect, enemy, 1, 1);
    assert(sound_calls == calls);
    solid_floor = 0;
    puts("insect sound variants, sight/stealth, pain debounce, movement cadence and save/load passed");
}
