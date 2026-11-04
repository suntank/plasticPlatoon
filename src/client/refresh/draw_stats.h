/* Count every actual draw while r_perf is enabled. Called only by renderers. */
#ifndef PP_DRAW_STATS_H
#define PP_DRAW_STATS_H
static inline void PP_DrawArrays(GLenum mode, GLint first, GLsizei count)
{
	PP_PERF(draws, 1);
	glDrawArrays(mode, first, count);
}
static inline void PP_DrawElements(GLenum mode, GLsizei count, GLenum type, const void *indices)
{
	PP_PERF(draws, 1);
	glDrawElements(mode, count, type, indices);
}
#endif
