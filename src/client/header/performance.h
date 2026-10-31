/* Opt-in complete-display-frame diagnostics. GPL-2.0-or-later. */
#ifndef CL_PERFORMANCE_H
#define CL_PERFORMANCE_H

void CL_PerfInit(void);
void CL_PerfShutdown(void);
int CL_PerfEnabled(void);
void CL_PerfAddServer(long long usec);
void CL_PerfAddSimulation(long long usec);
void CL_PerfAddSnapshot(long long usec);
void CL_PerfAddClient(long long usec);
void CL_PerfBeginDisplay(void);
void CL_PerfEndDisplay(void);
void CL_PerfBeginPrepare(void);
void CL_PerfEndPrepare(void);
void CL_PerfBeginView(int slot);
/* The argument points to a refdef_t; opaque here for server-only includes. */
void CL_PerfEndView(int slot, const void *refdef);
void CL_PerfBeginPresent(void);
void CL_PerfEndPresent(void);

#endif
