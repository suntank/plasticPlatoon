#include "../../src/client/refresh/color_pic_cache.h"
#include <assert.h>
#include <stdio.h>

static int released[128], frees;

static void release(void *ptr)
{
	int index = (int)((int *)ptr - released);
	assert(index >= 0 && index < 128 && !released[index]);
	released[index] = 1;
	++frees;
}

int main(void)
{
	pp_color_pic_cache_t cache = {0};
	int i, player, live;
	assert(PP_IsColorADSPicture("pics/colors/ads_machinegun_blue.png"));
	assert(!PP_IsColorADSPicture("pics/ads_machinegun.png"));
	assert(!PP_IsColorADSPicture("models/weapons/v_machn/colors/tris_blue.png"));
	/* Four simultaneous players stay resident as many other variants cycle. */
	for (i = 0; i < 100; i++)
	{
		for (player = 0; player < 4; player++)
			PP_TouchColorPicture(&cache, &released[player], "pics/colors/ads_active.png", release);
		PP_TouchColorPicture(&cache, &released[i + 4], "pics/colors/ads_other.png", release);
		for (player = 0; player < 4; player++) assert(!released[player]);
		live = 0;
		for (player = 0; player < 128; player++)
			if (player <= i + 4 && !released[player]) live++;
		assert(live <= PP_COLOR_PIC_LIMIT);
	}
	assert(frees == 104 - PP_COLOR_PIC_LIMIT);
	i = frees;
	PP_TouchColorPicture(&cache, &released[120], "pics/unrelated.png", release);
	PP_TouchColorPicture(&cache, NULL, "pics/colors/ads_missing.png", release);
	assert(frees == i && !released[120]);
	puts("Colored ADS pictures stay bounded while four player colors remain independent");
	return 0;
}
