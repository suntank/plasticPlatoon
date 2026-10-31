#include "../../src/client/header/client.h"
#include <assert.h>
#include <limits.h>

client_static_t cls;
static int draws, image_w = 800, image_h = 400;
static int last_x, last_y, last_w, last_h;

struct image_s *Draw_FindPic(const char *name) { return (struct image_s *)1; }
void Draw_GetPicSize(int *w, int *h, const char *name) { *w = image_w; *h = image_h; }
void Draw_StretchPic(int x, int y, int w, int h, const char *name)
{
    draws++; last_x = x; last_y = y; last_w = w; last_h = h;
}
void Com_Printf(const char *fmt, ...) {}
void Com_Error(int code, const char *fmt, ...) { abort(); }

static void parse(cl_screen_image_t *image, const char *pic, int w, int h, int duration)
{
    byte data[256] = {0};
    size_t n = strlen(pic) + 1;
    sizebuf_t msg = {0};
    memcpy(data, pic, n);
    data[n++] = w & 255; data[n++] = (w >> 8) & 255;
    data[n++] = h & 255; data[n++] = (h >> 8) & 255;
    data[n++] = duration & 255; data[n++] = (duration >> 8) & 255;
    msg.data = data; msg.cursize = n;
    CL_ParseScreenImage(image, &msg);
    assert(msg.readcount == msg.cursize);
}

int main(void)
{
    cl_screen_image_t primary = {0}, secondary = {0};
    assert(svc_nop == 6 && svc_stufftext == 11 && svc_frame == 20);
    assert(svc_screen_image == 21);
    cls.realtime = 1000;
    parse(&primary, "/pics/primary.png", 0, 0, 5);
    parse(&secondary, "/pics/secondary.png", 100, 0, 10);
    assert(!strcmp(primary.pic, "/pics/primary.png"));
    assert(primary.endtime == 6000 && secondary.endtime == 11000);
    SCR_DrawScreenImageOverlay(&primary, 0, 120, 240, 120);
    assert(draws == 1 && last_x == 0 && last_y == 120 && last_w == 240 && last_h == 120);
    SCR_DrawScreenImageOverlay(&secondary, 0, 0, 240, 120);
    assert(draws == 2 && last_x == 70 && last_y == 35 && last_w == 100 && last_h == 50);
    cls.realtime = 6000;
    SCR_DrawScreenImageOverlay(&primary, 0, 0, 240, 120);
    assert(draws == 2);
    parse(&secondary, "", 0, 0, 0);
    assert(!secondary.pic[0] && primary.pic[0]);
    parse(&secondary, "/pics/oversized.png", 32767, 32767, 1);
    SCR_DrawScreenImageOverlay(&secondary, 10, 20, 240, 120);
    assert(last_x == 70 && last_y == 20 && last_w == 120 && last_h == 120);
    cls.realtime = INT_MAX - 500;
    parse(&primary, "/pics/wrap.png", 10, 10, 2);
    cls.realtime = INT_MIN + 500;
    SCR_DrawScreenImageOverlay(&primary, 0, 0, 100, 100);
    assert(draws == 4);
    cls.realtime = INT_MIN + 1500;
    SCR_DrawScreenImageOverlay(&primary, 0, 0, 100, 100);
    assert(draws == 4);
    {
        byte data[] = {'x', 0, 10};
        sizebuf_t msg = {0}; msg.data = data; msg.cursize = sizeof(data);
        CL_ParseScreenImage(&primary, &msg);
        assert(!primary.pic[0]);
    }
    puts("screen-image client protocol, isolation, bounds and expiry passed");
    return 0;
}
