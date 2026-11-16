/* Test-only display-completion timestamps with renderer counters disabled.
 * No frame-time formatting, allocations or file I/O during a capture. */
#define _GNU_SOURCE
#include <SDL.h>
#include <dlfcn.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint64_t stamps[16384];
static volatile sig_atomic_t request;
static unsigned count, sequence;
static int active, enabled;
static char prefix[PATH_MAX-32];
static struct sigaction previous_start, previous_stop;

static void control(int signo) { request=signo==SIGUSR1?1:2; }

__attribute__((constructor)) static void initialize(void)
{
    const char *path=getenv("PP_SWAP_OBSERVER_PATH");
    if (!path || path[0]!='/' || strlen(path)>=sizeof(prefix)) return;
    strcpy(prefix,path); memset(stamps,0,sizeof(stamps));
    sigaction(SIGUSR1,NULL,&previous_start); sigaction(SIGUSR2,NULL,&previous_stop);
    if (previous_start.sa_handler!=SIG_DFL || previous_stop.sa_handler!=SIG_DFL) return;
    struct sigaction action={0}; action.sa_handler=control; action.sa_flags=SA_RESTART;
    sigemptyset(&action.sa_mask);
    sigaction(SIGUSR1,&action,NULL); sigaction(SIGUSR2,&action,NULL); enabled=1;
}

void SDL_GL_SwapWindow(SDL_Window *window)
{
    static void (*swap)(SDL_Window *);
    if (!swap) { swap=dlsym(RTLD_NEXT,"SDL_GL_SwapWindow"); if (!swap) abort(); }
    swap(window);
    if (!enabled) return;
    if (request==1) { count=0; active=1; request=0; }
    if (request==2) {
        active=0; request=0;
        char name[PATH_MAX]; snprintf(name,sizeof(name),"%s-%u.csv",prefix,++sequence);
        FILE *file=fopen(name,"wx");
        if (file) {
            fputs("completion_ns\n",file);
            for (unsigned i=0;i<count;++i) fprintf(file,"%llu\n",(unsigned long long)stamps[i]);
            fclose(file);
        }
    }
    if (active && count<sizeof(stamps)/sizeof(stamps[0])) {
        struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
        stamps[count++]=(uint64_t)t.tv_sec*1000000000u+t.tv_nsec;
    }
}

__attribute__((destructor)) static void finalize(void)
{
    if (enabled) { sigaction(SIGUSR1,&previous_start,NULL); sigaction(SIGUSR2,&previous_stop,NULL); }
}
