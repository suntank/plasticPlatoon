/* Per-view CPU and workload counters. No GPU synchronization is performed. */
#ifndef PP_REF_PERF_H
#define PP_REF_PERF_H
#include <stdint.h>
typedef struct
{
	double cpu_ms, visibility_ms, model_ms;
	uint64_t draws, world_triangles, model_triangles;
	uint64_t static_vertex_bytes, static_index_bytes;
	uint64_t dynamic_vertex_bytes, dynamic_index_bytes;
	uint64_t client_vertex_bytes, client_index_bytes;
	uint64_t pose_vertices, pose_cache_hits, topology_builds, pvs_builds, pvs_hits, lightmap_bytes;
} pp_refperf_t;
extern pp_refperf_t pp_refperf;
extern cvar_t *r_perf;
extern uint64_t pp_static_vertex_total, pp_static_index_total;
void PP_PerfInit(void);
void PP_PerfBegin(void);
void PP_PerfEnd(void);
double PP_PerfNow(void);
#define PP_PERF(field, amount) do { if (r_perf && r_perf->value) pp_refperf.field += (amount); } while (0)
#endif
