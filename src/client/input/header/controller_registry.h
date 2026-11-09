/* Keep player assignments stable when SDL changes its enumeration order. */
#ifndef CONTROLLER_REGISTRY_H
#define CONTROLLER_REGISTRY_H

static void
IN_MapControllerSlots(const int previous_ids[SS_MAX_LOCAL_PLAYERS],
	const int incoming_ids[SS_MAX_LOCAL_PLAYERS], int incoming_count,
	int slots[SS_MAX_LOCAL_PLAYERS])
{
	qboolean occupied[SS_MAX_LOCAL_PLAYERS] = {false};
	int i, j;

	/* Reserve every surviving device before allocating new arrivals. */
	for (i = 0; i < incoming_count; ++i)
	{
		slots[i] = -1;
		for (j = 0; j < SS_MAX_LOCAL_PLAYERS; ++j)
		{
			if (previous_ids[j] == incoming_ids[i])
			{
				slots[i] = j;
				occupied[j] = true;
				break;
			}
		}
	}

	for (i = 0; i < incoming_count; ++i)
	{
		if (slots[i] >= 0)
		{
			continue;
		}
		for (j = 0; j < SS_MAX_LOCAL_PLAYERS; ++j)
		{
			if (!occupied[j])
			{
				slots[i] = j;
				occupied[j] = true;
				break;
			}
		}
	}
}

#endif
