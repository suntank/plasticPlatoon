#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <stdio.h>

int main(void)
{
    PFNEGLGETPLATFORMDISPLAYEXTPROC platform = (void*)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay display = platform(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    EGLint major, minor;
    if (!eglInitialize(display, &major, &minor)) { printf("init failed: %#x\n", eglGetError()); return 1; }
    printf("EGL %d.%d %s, APIs %s\n", major, minor, eglQueryString(display,EGL_VENDOR),eglQueryString(display,EGL_CLIENT_APIS));
    eglBindAPI(EGL_OPENGL_ES_API);
    for (int version = 1; version <= 3; ++version) {
        EGLint attrs[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, version == 1 ? EGL_OPENGL_ES_BIT : EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE };
        EGLConfig config;
        EGLint configs;
        if (!eglChooseConfig(display, attrs, &config, 1, &configs) || !configs) { printf("config v%d failed: %#x\n", version, eglGetError()); continue; }
        EGLint context_attrs[] = { EGL_CONTEXT_CLIENT_VERSION, version, EGL_NONE };
        EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attrs);
        printf("context v%d=%p error=%#x\n", version, context, eglGetError());
        if (context) {
            eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, context);
            const unsigned char *(*get_string)(unsigned) = (void*)eglGetProcAddress("glGetString");
            printf("renderer=%s version=%s\n", get_string(0x1f01), get_string(0x1f02));
            eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            eglDestroyContext(display,context);
        }
    }
    eglTerminate(display);
}
