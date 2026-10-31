/* Exercise the production diagnostic state without requiring a GL context. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef int qboolean;
enum { false = 0, true = 1 };
typedef unsigned int GLuint, GLenum;
typedef int GLsizei;
#define APIENTRY
#define YQ2_GL1_GLES
typedef struct { char name[64], string[96]; float value; } cvar_t;
static cvar_t cvars[64];
static size_t cvar_count;

static cvar_t *TestGet(const char *name, const char *value, int flags)
{
	(void)flags;
	for (size_t i = 0; i < cvar_count; ++i)
		if (!strcmp(cvars[i].name, name)) return &cvars[i];
	assert(cvar_count < sizeof(cvars) / sizeof(cvars[0]));
	cvar_t *out = &cvars[cvar_count++];
	snprintf(out->name, sizeof(out->name), "%s", name);
	snprintf(out->string, sizeof(out->string), "%s", value);
	out->value = strtof(value, NULL);
	return out;
}
static void TestSet(const char *name, const char *value)
{
	cvar_t *out = TestGet(name, value, 0);
	snprintf(out->string, sizeof(out->string), "%s", value);
	out->value = strtof(value, NULL);
}
static struct {
	cvar_t *(*Cvar_Get)(const char *, const char *, int);
	void (*Cvar_Set)(const char *, const char *);
} ri = { TestGet, TestSet };

#include "../src/client/refresh/perf.h"
#include "../src/client/refresh/perf_impl.h"
#include "../src/client/refresh/gpu_timer_impl.h"

static unsigned int queries_begun, queries_ended, queries_deleted;
static void MockBegin(GLenum target, GLuint query)
{
	assert(target == PP_TIME_ELAPSED && query == 42);
	++queries_begun;
}
static void MockEnd(GLenum target)
{
	assert(target == PP_TIME_ELAPSED);
	++queries_ended;
}
static void MockDelete(GLsizei count, const GLuint *query)
{
	assert(count == 1 && *query == 42);
	++queries_deleted;
}
static void MockAvailable(GLuint query, GLenum what, GLuint *available)
{
	assert(query == 42 && what == PP_QUERY_AVAILABLE);
	*available = 1;
}
static void MockResult(GLuint query, GLenum what, uint64_t *ns)
{
	assert(query == 42 && what == PP_QUERY_RESULT);
	*ns = 2000000;
}
static void AssertValue(const char *name, const char *expected)
{
	assert(!strcmp(TestGet(name, "", 0)->string, expected));
}

int main(void)
{
	TestSet("r_perf", "1");
	TestSet("r_perf_gpu", "0");
	TestSet("r_perf_serial", "4294967297");
	TestSet("r_perf_gpu_supported", "1");
	TestSet("r_perf_gpu_serial", "4294967297");
	TestSet("r_perf_gpu_ms", "5.5");
	PP_PerfInit();
	PP_GPUTimerInit();
	assert(pp_view_serial == UINT64_C(4294967297));
	AssertValue("r_perf_gpu_supported", "0");
	AssertValue("r_perf_gpu_serial", "0");
	AssertValue("r_perf_gpu_ms", "-1");
	PP_PerfBegin();
	PP_GPUTimerBegin();
	PP_GPUTimerEnd();
	PP_PerfEnd();
	AssertValue("r_perf_serial", "4294967298");

	/* A DSO reload discards static state, while engine cvars survive. */
	pp_view_serial = 0;
	PP_PerfInit();
	assert(pp_view_serial == UINT64_C(4294967298));
	PP_PerfBegin();
	PP_PerfEnd();
	AssertValue("r_perf_serial", "4294967299");

	/* A pending GPU sample uses the next preserved serial, then publishes
	 * that exact origin only after availability is reported. */
	TestSet("r_perf_gpu", "1");
	pp_gpu_initialized = true;
	pp_gpu_slots[0].query = 42;
	pp_begin_query = MockBegin;
	pp_end_query = MockEnd;
	pp_delete_queries = MockDelete;
	pp_query_available = MockAvailable;
	pp_query_result = MockResult;
	PP_PerfBegin();
	PP_GPUTimerBegin();
	assert(pp_gpu_slots[0].serial == UINT64_C(4294967300));
	PP_GPUTimerEnd();
	PP_PerfEnd();
	PP_PerfBegin();
	PP_GPUTimerBegin();
	AssertValue("r_perf_gpu_serial", "4294967300");
	AssertValue("r_perf_gpu_ms", "2.000000");
	PP_GPUTimerShutdown();
	assert(queries_begun == 2 && queries_ended == 2 && queries_deleted == 1);
	AssertValue("r_perf_gpu_supported", "0");
	AssertValue("r_perf_gpu_serial", "0");
	AssertValue("r_perf_gpu_ms", "-1");
	assert(!pp_query_result && !pp_gpu_completed && pp_gpu_active == -1);

	/* Even a diagnostics-disabled GLES context clears old desktop results. */
	TestSet("r_perf", "0");
	TestSet("r_perf_gpu_supported", "1");
	PP_PerfInit();
	PP_GPUTimerInit();
	AssertValue("r_perf_gpu_supported", "0");
	uint64_t before = pp_view_serial;
	PP_PerfBegin();
	PP_GPUTimerBegin();
	PP_GPUTimerEnd();
	PP_PerfEnd();
	assert(pp_view_serial == before);

	const char *invalid[] = { "", "-1", "12.5", "abc", "18446744073709551616" };
	for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
		TestSet("r_perf_serial", invalid[i]);
		PP_PerfInit();
		assert(pp_view_serial == 0);
	}
	puts("renderer diagnostic restart/query lifecycle: PASS");
	return 0;
}
