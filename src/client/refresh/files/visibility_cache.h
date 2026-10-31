/* Cached PVS stamp sets. Area portals and frustum tests remain per-view. */
#ifndef PP_VISIBILITY_CACHE_H
#define PP_VISIBILITY_CACHE_H
#define PP_VISIBILITY_SLOTS 4
typedef struct
{
	int cluster, cluster2;
	mnode_t **marks;
	size_t count;
	unsigned age;
} pp_visibility_entry_t;
typedef struct
{
	pp_visibility_entry_t entries[PP_VISIBILITY_SLOTS];
	unsigned clock;
} pp_visibility_cache_t;
static inline void PP_ClearVisibilityCache(pp_visibility_cache_t *cache)
{
	for (unsigned i = 0; i < PP_VISIBILITY_SLOTS; ++i) free(cache->entries[i].marks);
	memset(cache, 0, sizeof(*cache));
}
static inline int PP_RestoreVisibility(pp_visibility_cache_t *cache, int cluster, int cluster2, int stamp)
{
	for (unsigned i = 0; i < PP_VISIBILITY_SLOTS; ++i)
	{
		pp_visibility_entry_t *entry = cache->entries+i;
		if (!entry->marks || entry->cluster != cluster || entry->cluster2 != cluster2) continue;
		for (size_t j = 0; j < entry->count; ++j) entry->marks[j]->visframe = stamp;
		entry->age = ++cache->clock;
		return 1;
	}
	return 0;
}
static inline void PP_SaveVisibility(pp_visibility_cache_t *cache, int cluster, int cluster2,
	mnode_t *nodes, int numnodes, mleaf_t *leaves, int numleaves, int stamp)
{
	unsigned slot = 0;
	size_t count = 0, index = 0;
	for (unsigned i = 1; i < PP_VISIBILITY_SLOTS; ++i)
		if (cache->entries[i].age < cache->entries[slot].age) slot = i;
	for (int i = 0; i < numnodes; ++i) if (nodes[i].visframe == stamp) ++count;
	for (int i = 0; i < numleaves; ++i) if (leaves[i].visframe == stamp) ++count;
	if (!count) return;
	mnode_t **marks = malloc(count * sizeof(*marks));
	if (!marks) return;
	for (int i = 0; i < numnodes; ++i) if (nodes[i].visframe == stamp) marks[index++] = nodes+i;
	for (int i = 0; i < numleaves; ++i) if (leaves[i].visframe == stamp) marks[index++] = (mnode_t *)(leaves+i);
	pp_visibility_entry_t *entry = cache->entries+slot;
	free(entry->marks);
	entry->marks = marks; entry->count = count;
	entry->cluster = cluster; entry->cluster2 = cluster2; entry->age = ++cache->clock;
}
#endif
