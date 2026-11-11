/* Check approved runtime WAVs with the engine's real decoder, without SDL. */
#include "../../src/client/header/client.h"
#include "../../src/client/sound/header/local.h"
#include <assert.h>
#include <stdarg.h>

void Com_Printf(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
}

YQ2_ATTR_NORETURN void Com_Error(int code, const char *fmt, ...)
{
    va_list args;
    (void)code;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    abort();
}

int main(int argc, char **argv)
{
    int i;
    assert(argc == 19);
    for (i = 1; i < argc; ++i) {
        FILE *file = fopen(argv[i], "rb");
        long length;
        byte *bytes;
        wavinfo_t info;
        assert(file);
        assert(!fseek(file, 0, SEEK_END));
        length = ftell(file);
        assert(length > 0 && length < 200000);
        rewind(file);
        bytes = malloc((size_t)length);
        assert(bytes && fread(bytes, 1, (size_t)length, file) == (size_t)length);
        fclose(file);
        info = GetWavinfo(argv[i], bytes, (int)length);
        assert(info.channels == 1 && info.width == 2 && info.rate == 48000);
        assert(info.loopstart == -1 && info.samples > 20000 && info.samples <= 57600);
        assert(info.dataofs >= 44 && info.dataofs + info.samples * info.width <= length);
        free(bytes);
    }
    puts("engine WAV decoder: all 18 insect effects are valid spatial mono PCM16 one-shots");
    return 0;
}
