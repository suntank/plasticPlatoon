/* Shared production relay/door fixture for vehicle death-target regressions. */
/* g_func.c keeps its movement states private. */
enum { OBJECTIVE_GATE_BOTTOM = 1, OBJECTIVE_GATE_UP = 2 };

extern void SP_trigger_relay(edict_t *self);
extern void SP_func_door(edict_t *self);

static void objective_setmodel(edict_t *ent, char *name)
{
    (void)name;
    VectorSet(ent->mins, -160, 8, 0);
    VectorSet(ent->maxs, 160, 56, 192);
    VectorSubtract(ent->maxs, ent->mins, ent->size);
}

static edict_t *objective_gate(edict_t *vehicle)
{
    edict_t *relay = G_Spawn(), *gate = G_Spawn();
    vehicle->deathtarget = "vehicle_down";
    relay->classname = "trigger_relay";
    relay->targetname = "vehicle_down";
    relay->target = "vehicle_gate";
    SP_trigger_relay(relay);
    gate->classname = "func_door";
    gate->targetname = "vehicle_gate";
    gate->model = "*1";
    gate->wait = -1;
    gate->speed = 80;
    gate->sounds = 1;
    VectorSet(gate->s.angles, 0, -1, 0);
    gi.setmodel = objective_setmodel;
    SP_func_door(gate);
    gate->think(gate); /* Finish normal named-door setup. */
    assert(gate->moveinfo.state == OBJECTIVE_GATE_BOTTOM);
    return gate;
}

static void assert_objective_opens(edict_t *gate)
{
    assert(gate->moveinfo.state == OBJECTIVE_GATE_UP);
    assert(gate->moveinfo.wait == -1);
    if (gate->velocity[2] == 0)
        gate->think(gate); /* Run the scheduled Move_Begin. */
    assert(gate->velocity[2] > 0);
}
