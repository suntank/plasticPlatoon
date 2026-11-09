/* Test actual startup selection code with a deterministic SDL backend stub. */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <SDL2/SDL.h>
#ifdef TEST_OLD_SDL_HEADERS
#undef SDL_HINT_VIDEODRIVER
#endif
#include "../../src/client/vid/glimp_sdl2.c"

static const char *wayland_env, *driver_env, *driver_hint;
static SDL_version runtime;
static int init_calls, hint_calls, clear_calls, fallback_logs;
static int native_result, default_result;
static SDL_bool allow_hint;
static char tried[2][32];

char *SDL_getenv(const char *name)
{
    if (!strcmp(name, "WAYLAND_DISPLAY")) return (char *)wayland_env;
    if (!strcmp(name, "SDL_VIDEODRIVER")) return (char *)driver_env;
    assert(!"Unexpected environment lookup");
    return NULL;
}
const char *SDL_GetHint(const char *name)
{ assert(!strcmp(name, "SDL_VIDEODRIVER")); return driver_hint; }
SDL_bool SDL_SetHintWithPriority(const char *name, const char *value, SDL_HintPriority priority)
{
    assert(!strcmp(name, "SDL_VIDEODRIVER") && priority == SDL_HINT_DEFAULT);
    ++hint_calls;
    if (allow_hint) driver_hint = value;
    return allow_hint;
}
void SDL_GetVersion(SDL_version *version) { *version = runtime; }
int SDL_Init(Uint32 flags)
{
    assert(flags == SDL_INIT_VIDEO && init_calls < 2);
    const char *driver = driver_env ? driver_env : driver_hint;
    snprintf(tried[init_calls++], sizeof(tried[0]), "%s", driver ? driver : "");
    return driver && !strcmp(driver, "wayland") ? native_result : default_result;
}
const char *SDL_GetError(void) { return "test backend unavailable"; }
void SDL_ClearError(void) { ++clear_calls; }
void Com_Printf(const char *format, ...) { (void)format; ++fallback_logs; }
static void reset(void)
{
    wayland_env = "wayland-0"; driver_env = driver_hint = NULL;
    runtime.major = 2; runtime.minor = 0; runtime.patch = 22;
    init_calls = hint_calls = clear_calls = fallback_logs = 0;
    native_result = default_result = 0;
    allow_hint = SDL_TRUE;
    memset(tried, 0, sizeof(tried));
}
int main(void)
{
    reset();
#ifdef TEST_OLD_SDL_HEADERS
    assert(InitVideoSubsystem() == 0);
    assert(init_calls == 1 && hint_calls == 0 && !tried[0][0]);
#else
    assert(InitVideoSubsystem() == 0);
    assert(init_calls == 1 && !strcmp(tried[0], "wayland") && hint_calls == 1);
    reset(); native_result = -1;
    assert(InitVideoSubsystem() == 0);
    assert(init_calls == 2 && !strcmp(tried[0], "wayland") && !tried[1][0]);
    assert(clear_calls == 1 && fallback_logs == 1 && hint_calls == 2);
    reset(); native_result = default_result = -1;
    assert(InitVideoSubsystem() == -1 && init_calls == 2);
    const char *explicit_drivers[] = {"x11", "wayland", "offscreen", "dummy", ""};
    for (unsigned i = 0; i < sizeof(explicit_drivers)/sizeof(*explicit_drivers); ++i)
    {
        reset(); driver_env = explicit_drivers[i];
        assert(InitVideoSubsystem() == 0 && init_calls == 1 && hint_calls == 0);
        assert(!strcmp(tried[0], explicit_drivers[i]));
        reset(); driver_hint = explicit_drivers[i];
        assert(InitVideoSubsystem() == 0 && init_calls == 1 && hint_calls == 0);
        assert(!strcmp(tried[0], explicit_drivers[i]));
    }
    reset(); driver_env = "wayland"; native_result = -1;
    assert(InitVideoSubsystem() == -1 && init_calls == 1 && hint_calls == 0);
    reset(); wayland_env = NULL;
    assert(InitVideoSubsystem() == 0 && hint_calls == 0 && !tried[0][0]);
    reset(); wayland_env = "";
    assert(InitVideoSubsystem() == 0 && hint_calls == 0 && !tried[0][0]);
    reset(); runtime.patch = 20;
    assert(InitVideoSubsystem() == 0 && hint_calls == 0 && !tried[0][0]);
    reset(); allow_hint = SDL_FALSE;
    assert(InitVideoSubsystem() == 0 && hint_calls == 1 && !tried[0][0]);
#endif
    puts("SDL2 native Wayland preference, fallback, explicit overrides and older SDL compatibility pass");
    return 0;
}
