/* Optional asynchronous desktop timer queries, shared by GL1 and GL3.
 * A full ring drops a sample; it never waits for the GPU or calls glFinish.
 * ES paths report unsupported until disjoint-query handling is implemented.
 */
#define PP_GPU_QUERY_SLOTS 16
#define PP_TIME_ELAPSED 0x88BF
#define PP_QUERY_RESULT 0x8866
#define PP_QUERY_AVAILABLE 0x8867
static struct { GLuint query; qboolean pending; uint64_t serial; } pp_gpu_slots[PP_GPU_QUERY_SLOTS];
static int pp_gpu_active = -1;
static qboolean pp_gpu_initialized;
static uint64_t pp_gpu_completed;
static cvar_t *r_perf_gpu;
#if !defined(YQ2_GL1_GLES) && !defined(YQ2_GL3_GLES)
static void (APIENTRY *pp_gen_queries)(GLsizei, GLuint *);
#endif
static void (APIENTRY *pp_delete_queries)(GLsizei, const GLuint *);
static void (APIENTRY *pp_begin_query)(GLenum, GLuint);
static void (APIENTRY *pp_end_query)(GLenum);
static void (APIENTRY *pp_query_available)(GLuint, GLenum, GLuint *);
static void (APIENTRY *pp_query_result)(GLuint, GLenum, uint64_t *);

static void PP_GPUTimerInit(void)
{
	memset(pp_gpu_slots, 0, sizeof(pp_gpu_slots));
	pp_gpu_active = -1;
	pp_gpu_completed = 0;
	pp_gpu_initialized = false;
#if !defined(YQ2_GL1_GLES) && !defined(YQ2_GL3_GLES)
	pp_gen_queries = NULL;
#endif
	pp_delete_queries = NULL;
	pp_begin_query = NULL;
	pp_end_query = NULL;
	pp_query_available = NULL;
	pp_query_result = NULL;
	/* Results describe one context and must not survive a restart, even if
	 * the next renderer has diagnostics or timer queries disabled. */
	ri.Cvar_Set("r_perf_gpu_supported", "0");
	ri.Cvar_Set("r_perf_gpu_serial", "0");
	ri.Cvar_Set("r_perf_gpu_ms", "-1");
}

static void PP_GPUTimerBegin(void)
{
	if (!r_perf || !r_perf->value) return;
	if (!r_perf_gpu) r_perf_gpu = ri.Cvar_Get("r_perf_gpu", "0", 0);
	if (!r_perf_gpu->value) return;
	if (!pp_gpu_initialized)
	{
		pp_gpu_initialized = true;
		ri.Cvar_Set("r_perf_gpu_supported", "0");
		ri.Cvar_Set("r_perf_gpu_serial", "0");
		ri.Cvar_Set("r_perf_gpu_ms", "-1");
#if !defined(YQ2_GL1_GLES) && !defined(YQ2_GL3_GLES)
		if (!SDL_GL_ExtensionSupported("GL_ARB_timer_query") &&
			!SDL_GL_ExtensionSupported("GL_EXT_timer_query")) return;
#define PP_QUERY_PROC(dst, name, signature) do { \
		dst = (signature)SDL_GL_GetProcAddress(name); \
		if (!dst) dst = (signature)SDL_GL_GetProcAddress(name "ARB"); \
} while (0)
		PP_QUERY_PROC(pp_gen_queries, "glGenQueries", void (APIENTRY *)(GLsizei, GLuint *));
		PP_QUERY_PROC(pp_delete_queries, "glDeleteQueries", void (APIENTRY *)(GLsizei, const GLuint *));
		PP_QUERY_PROC(pp_begin_query, "glBeginQuery", void (APIENTRY *)(GLenum, GLuint));
		PP_QUERY_PROC(pp_end_query, "glEndQuery", void (APIENTRY *)(GLenum));
		PP_QUERY_PROC(pp_query_available, "glGetQueryObjectuiv", void (APIENTRY *)(GLuint, GLenum, GLuint *));
#undef PP_QUERY_PROC
		pp_query_result = (void (APIENTRY *)(GLuint, GLenum, uint64_t *))SDL_GL_GetProcAddress("glGetQueryObjectui64v");
		if (!pp_query_result) pp_query_result = (void (APIENTRY *)(GLuint, GLenum, uint64_t *))SDL_GL_GetProcAddress("glGetQueryObjectui64vEXT");
		if (!pp_gen_queries || !pp_delete_queries || !pp_begin_query || !pp_end_query || !pp_query_available || !pp_query_result)
		{ pp_query_result = NULL; return; }
		for (int i = 0; i < PP_GPU_QUERY_SLOTS; ++i) pp_gen_queries(1, &pp_gpu_slots[i].query);
		ri.Cvar_Set("r_perf_gpu_supported", "1");
#endif
	}
	if (!pp_query_result) return;
	for (int i = 0; i < PP_GPU_QUERY_SLOTS; ++i)
	{
		if (!pp_gpu_slots[i].pending) continue;
		GLuint available = 0;
		pp_query_available(pp_gpu_slots[i].query, PP_QUERY_AVAILABLE, &available);
		if (available)
		{
			uint64_t ns;
			pp_query_result(pp_gpu_slots[i].query, PP_QUERY_RESULT, &ns);
			if (pp_gpu_slots[i].serial > pp_gpu_completed)
			{
				char value[64];
				pp_gpu_completed = pp_gpu_slots[i].serial;
				snprintf(value, sizeof(value), "%.6f", ns / 1000000.0);
				ri.Cvar_Set("r_perf_gpu_ms", value);
				snprintf(value, sizeof(value), "%" PRIu64, pp_gpu_completed);
				ri.Cvar_Set("r_perf_gpu_serial", value);
			}
			pp_gpu_slots[i].pending = false;
		}
	}
	for (int i = 0; i < PP_GPU_QUERY_SLOTS; ++i)
	{
		if (pp_gpu_slots[i].pending) continue;
		pp_gpu_active = i;
		pp_gpu_slots[i].serial = pp_view_serial + 1;
		pp_begin_query(PP_TIME_ELAPSED, pp_gpu_slots[i].query);
		break;
	}
}
static void PP_GPUTimerEnd(void)
{
	if (pp_gpu_active < 0) return;
	pp_end_query(PP_TIME_ELAPSED);
	pp_gpu_slots[pp_gpu_active].pending = true;
	pp_gpu_active = -1;
}
static void PP_GPUTimerShutdown(void)
{
	PP_GPUTimerEnd();
	if (pp_delete_queries)
		for (int i = 0; i < PP_GPU_QUERY_SLOTS; ++i)
			if (pp_gpu_slots[i].query) pp_delete_queries(1, &pp_gpu_slots[i].query);
	PP_GPUTimerInit();
}
