#ifndef PP_COLOR_PIC_CACHE_H
#define PP_COLOR_PIC_CACHE_H

#include <stdint.h>
#include <string.h>

/* Full-size ADS pictures are large. Four local players need four concurrent
 * variants; eight keeps those plus recent switches without unbounded growth.
 * Only picture names are retained by the client, so evicted images reload on
 * their next draw. Model/weapon skin pointers are never part of this cache. */
#define PP_COLOR_PIC_LIMIT 8
typedef struct
{
	void *images[PP_COLOR_PIC_LIMIT];
	uint64_t used[PP_COLOR_PIC_LIMIT], clock;
} pp_color_pic_cache_t;

static inline int
PP_IsColorADSPicture(const char *name)
{
	return name && !strncmp(name, "pics/colors/ads_", 16);
}

static inline void
PP_TouchColorPicture(pp_color_pic_cache_t *cache, void *image,
	const char *name, void (*release)(void *))
{
	int i, oldest = 0;
	if (!image || !PP_IsColorADSPicture(name)) return;
	for (i = 0; i < PP_COLOR_PIC_LIMIT; i++)
	{
		if (cache->images[i] == image)
		{
			cache->used[i] = ++cache->clock;
			return;
		}
		if (cache->used[i] < cache->used[oldest]) oldest = i;
	}
	if (cache->images[oldest]) release(cache->images[oldest]);
	cache->images[oldest] = image;
	cache->used[oldest] = ++cache->clock;
}

#endif
