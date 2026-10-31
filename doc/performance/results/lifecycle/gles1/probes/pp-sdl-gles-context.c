#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    int accel = argc > 1 ? atoi(argv[1]) : 1;
    int minor = argc > 2 ? atoi(argv[2]) : 0;
    int depth = argc > 3 ? atoi(argv[3]) : 24;
    int stencil = argc > 4 ? atoi(argv[4]) : 8;
    if (SDL_Init(SDL_INIT_VIDEO) < 0) { printf("init: %s\n", SDL_GetError()); return 1; }
    SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, depth);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, stencil);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_ACCELERATED_VISUAL, accel);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 1);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, minor);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 0);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 0);
    SDL_Window *window = SDL_CreateWindow("context probe", 0, 0, 240, 240, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!window) { printf("window: %s\n", SDL_GetError()); SDL_Quit(); return 2; }
    SDL_GLContext context = SDL_GL_CreateContext(window);
    if (!context) { printf("context: %s\n", SDL_GetError()); SDL_DestroyWindow(window); SDL_Quit(); return 3; }
    const unsigned char *(*get_string)(unsigned) = SDL_GL_GetProcAddress("glGetString");
    printf("video=%s accel-request=%d depth=%d stencil=%d context=1.%d vendor=%s renderer=%s version=%s\n",
        SDL_GetCurrentVideoDriver(), accel, depth, stencil, minor,
        get_string(0x1f00), get_string(0x1f01), get_string(0x1f02));
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
