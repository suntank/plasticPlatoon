/* Include once, in a renderer's main translation unit. */
#include <errno.h>
#include <inttypes.h>
#ifdef USE_SDL3
#include <SDL3/SDL.h>
#else
#include <SDL2/SDL.h>
#endif
pp_refperf_t pp_refperf;
cvar_t *r_perf;
uint64_t pp_static_vertex_total, pp_static_index_total;
static double pp_view_started;
static uint64_t pp_view_serial;

void PP_PerfInit(void)
{
	char *end;
	const char *saved = ri.Cvar_Get("r_perf_serial", "0", 0)->string;
	unsigned long long serial;
	/* Cvars outlive renderer DSOs. Read the string, not its float value, so
	 * serials remain exact across renderer reloads and beyond 2^24 views. */
	errno = 0;
	serial = strtoull(saved, &end, 10);
	pp_view_serial = saved[0] >= '0' && saved[0] <= '9' && !*end && !errno ? serial : 0;
	r_perf = ri.Cvar_Get("r_perf", "0", 0);
	memset(&pp_refperf, 0, sizeof(pp_refperf));
	pp_static_vertex_total = pp_static_index_total = 0;
}

double PP_PerfNow(void)
{
	if (!r_perf || !r_perf->value) return 0;
	return (double)SDL_GetPerformanceCounter() * 1000.0 / (double)SDL_GetPerformanceFrequency();
}
void PP_PerfBegin(void)
{
	if (!r_perf) PP_PerfInit();
	memset(&pp_refperf, 0, sizeof(pp_refperf));
	pp_view_started = PP_PerfNow();
}
void PP_PerfEnd(void)
{
	char value[64];
	if (!r_perf || !r_perf->value) return;
	pp_refperf.cpu_ms = PP_PerfNow() - pp_view_started;
#define PP_PUBLISH(field) do { snprintf(value, sizeof(value), "%.6f", (double)pp_refperf.field); ri.Cvar_Set("r_perf_" #field, value); } while (0)
	PP_PUBLISH(cpu_ms); PP_PUBLISH(visibility_ms); PP_PUBLISH(model_ms);
	PP_PUBLISH(draws); PP_PUBLISH(world_triangles); PP_PUBLISH(model_triangles);
	PP_PUBLISH(static_vertex_bytes); PP_PUBLISH(static_index_bytes);
	PP_PUBLISH(dynamic_vertex_bytes); PP_PUBLISH(dynamic_index_bytes);
	PP_PUBLISH(client_vertex_bytes); PP_PUBLISH(client_index_bytes);
	PP_PUBLISH(pose_vertices); PP_PUBLISH(pose_cache_hits); PP_PUBLISH(topology_builds);
	PP_PUBLISH(pvs_builds); PP_PUBLISH(pvs_hits); PP_PUBLISH(lightmap_bytes);
#undef PP_PUBLISH
	snprintf(value, sizeof(value), "%llu", (unsigned long long)pp_static_vertex_total);
	ri.Cvar_Set("r_perf_static_vertex_total", value);
	snprintf(value, sizeof(value), "%llu", (unsigned long long)pp_static_index_total);
	ri.Cvar_Set("r_perf_static_index_total", value);
	snprintf(value, sizeof(value), "%" PRIu64, ++pp_view_serial);
	ri.Cvar_Set("r_perf_serial", value);
}
