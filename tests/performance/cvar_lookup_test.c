/* Exercise the production lookup cache, including alias warning semantics. */
#include <assert.h>
#include <stdarg.h>
#include "../../src/common/cvar.c"

static unsigned warnings;
void *Z_Malloc(int size) { void *p=calloc(1,size); assert(p); return p; }
void Z_Free(void *p) { free(p); }
char *CopyString(const char *s) { return strdup(s); }
void Com_Printf(const char *fmt,...) { if (strstr(fmt,"deprecated")) ++warnings; }
void Cmd_RemoveCommand(const char *name) { (void)name; }

int main(void)
{
    cvar_lookup_cache=Cvar_Get("cvar_lookup_cache","1",0);
    cvar_t *vars[2048]; char name[64];
    for (unsigned i=0;i<2048;++i) {
        snprintf(name,sizeof(name),"lookup_test_%04u",i);
        vars[i]=Cvar_Get(name,"12.5",CVAR_ARCHIVE); assert(vars[i]);
    }
    for (int enabled=0;enabled<2;++enabled) {
        cvar_lookup_cache->value=enabled;
        for (unsigned pass=0;pass<4;++pass)
        for (unsigned i=0;i<2048;++i) {
            snprintf(name,sizeof(name),"lookup_test_%04u",i);
            assert(Cvar_FindVar(name)==vars[i]); assert(Cvar_FindVar(name)==vars[i]);
            assert(Cvar_VariableValue(name)==12.5f);
            assert(!strcmp(Cvar_VariableString(name),"12.5"));
        }
        assert(!Cvar_FindVar("LOOKUP_TEST_0000"));
        snprintf(name,sizeof(name),"created_after_miss_%d",enabled);
        assert(!Cvar_FindVar(name));
        cvar_t *newvar=Cvar_Get(name,"7",0);
        assert(Cvar_FindVar(name)==newvar);
        /* Aliases retain the original warning on every lookup, even warm. */
        cvar_t *canonical=Cvar_Get("r_drawentities","1",0);
        for (unsigned i=0;i<10;++i) {
            unsigned before=warnings;
            assert(Cvar_FindVar("gl_drawentities")==canonical);
            assert(warnings==before+1);
            assert(Cvar_FindVar("r_drawentities")==canonical);
        }
        assert(Cvar_Get("lookup_test_0000","3",CVAR_USERINFO)==vars[0]);
        assert(!strcmp(vars[0]->string,"12.5"));
        assert(vars[0]->flags&CVAR_USERINFO);
    }
    Cvar_Fini(); assert(!cvar_vars && !cvar_lookup_cache);
    for (unsigned i=0;i<CVAR_LOOKUP_SLOTS;++i) assert(!cvar_lookup_slots[i]);
    cvar_t *again=Cvar_Get("lookup_test_0000","99",0);
    assert(Cvar_FindVar("lookup_test_0000")==again);
    assert(Cvar_VariableValue("lookup_test_0000")==99);
    Cvar_Fini();
    puts("PASS production cvar lookup: on/off, 2048 variables/collisions, case, miss/create, aliases/warnings, flags/defaults and teardown/reinit");
}
