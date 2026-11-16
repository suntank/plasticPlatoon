/* Reuse the native game fixture for the distinct Sandkeep boss. */
extern void SP_monster_boss2(edict_t *);
extern void Boss2Rocket(edict_t *);
extern void Boss2MachineGun(edict_t *);
extern void boss2_reattack_mg(edict_t *);
extern mmove_t boss2_move_attack_rocket, boss2_move_attack_mg, boss2_move_attack_post_mg;

static edict_t *new_boss(void)
{
    edict_t *self = new_helicopter();
    memset(&g_edicts[2], 0, (game.maxentities-2)*sizeof(*g_edicts));
    globals.num_edicts = 3; level.total_monsters = 0;
    G_InitEdict(self); self->classname = "monster_boss2";
    VectorSet(self->s.origin, 0, 0, 128);
    SP_monster_boss2(self);
    self->enemy = self->goalentity = &g_edicts[1];
    return self;
}

static void test_boss_helicopter(const char *filename)
{
    edict_t *self = new_boss();
    assert(self->health == 4000 && self->max_health == 4000 && self->mass == 1800);
    assert(self->s.renderfx & RF_PP_ENEMY_COLOR);
    assert(!strcmp(models[self->s.modelindex], "models/monsters/plastic_boss/body.md2"));
    assert(!strcmp(models[self->s.modelindex2], "models/monsters/plastic_boss/main_rotor.md2"));
    mmove_t *move = self->monsterinfo.currentmove;
    self->health -= 8; self->pain(self, self->enemy, 0, 8);
    assert(self->monsterinfo.currentmove == move); /* Small hits cannot stagger-lock it. */
    self->health = 1999; self->pain(self, self->enemy, 0, 8);
    assert(self->s.skinnum == 1 && self->monsterinfo.currentmove == move);
    self->pain(self, self->enemy, 0, 80);
    assert(self->monsterinfo.currentmove != move);

    /* Both native cannons fire; cover, lost targets and close rocket range are respected. */
    self = new_boss(); Boss2MachineGun(self); assert(bullet_rays == 2);
    blocked_shots = 1; Boss2MachineGun(self); Boss2Rocket(self);
    assert(bullet_rays == 2 && !rockets()); blocked_shots = 0;
    blocked_sight = 1; Boss2Rocket(self); assert(!rockets()); blocked_sight = 0;
    self->enemy = NULL; Boss2MachineGun(self); Boss2Rocket(self); assert(!rockets());
    self->enemy = &g_edicts[1]; self->enemy->s.origin[0] = 100;
    Boss2Rocket(self); assert(!rockets());

    for (int phase = 0; phase < 2; phase++) {
        self = new_boss();
        self->health = phase ? 2000 : 4000;
        self->monsterinfo.currentmove = &boss2_move_attack_rocket;
        self->s.frame = -1;
        float first = 0, second = 0;
        for (int i = 0; i < 24 && self->monsterinfo.currentmove == &boss2_move_attack_rocket; i++) {
            tick(self);
            if (!first && rockets() >= 4) first = level.time;
            if (!second && rockets() >= 8) second = level.time;
        }
        assert(rockets() == (phase ? 8 : 4));
        assert(first > 10.9f); /* Wind-up is retained. */
        if (phase) assert(second-first > .55f && second-first < .65f);
        assert(self->monsterinfo.attack_finished > level.time);
        for (int i = 3; i < globals.num_edicts; i++) if (g_edicts[i].inuse && g_edicts[i].owner == self) {
            edict_t *r = &g_edicts[i];
            assert(r->dmg == 65 && fabsf(VectorLength(r->velocity)-650) < .1f);
        }
    }
    self = new_boss(); self->count = 2;
    self->monsterinfo.currentmove = &boss2_move_attack_mg;
    boss2_reattack_mg(self);
    assert(self->monsterinfo.currentmove == &boss2_move_attack_post_mg);
    assert(self->monsterinfo.attack_finished > level.time);

    /* Save an older fight halfway through its salvo: refresh only media, no heal/reset. */
    self = new_boss(); self->health = 1700;
    self->monsterinfo.currentmove = &boss2_move_attack_rocket;
    self->s.frame = boss2_move_attack_rocket.firstframe + 13;
    self->s.modelindex = model_index("models/monsters/boss2/tris.md2");
    self->s.modelindex2 = model_index("models/monsters/boss2/propeller.md2");
    WriteLevel(filename); ReadLevel(filename); self = &g_edicts[2];
    assert(self->health == 1700 && self->monsterinfo.currentmove == &boss2_move_attack_rocket);
    assert(self->s.frame == boss2_move_attack_rocket.firstframe + 13);
    assert(!strcmp(models[self->s.modelindex], "models/monsters/plastic_boss/body.md2"));
    assert(!strcmp(models[self->s.modelindex2], "models/monsters/plastic_boss/main_rotor.md2"));

    self = new_boss(); edict_t *gate = objective_gate(self);
    kill_helicopter(self);
    assert_objective_opens(gate); /* Sandkeep's boss_down chain is still fired. */
    assert(self->deadflag == DEAD_DEAD && !(self->flags & FL_FLY));
    for (int i = 0; i < 40 && self->inuse; i++) tick(self);
    assert(!self->inuse && explosions >= 5 && level.killed_monsters == 1);

    self = new_boss(); kill_helicopter(self);
    while (self->inuse && self->s.modelindex2) tick(self);
    assert(self->inuse && !self->s.modelindex2);
    WriteLevel(filename); ReadLevel(filename); self = &g_edicts[2];
    assert(!self->s.modelindex2 && self->deadflag == DEAD_DEAD);
    for (int i = 0; i < 15 && self->inuse; i++) tick(self);
    assert(!self->inuse);
    unlink(filename);
    puts("boss gunship: health, phases, wind-up, bounded bursts, cover safety, old saves, objective and crash passed");
}
