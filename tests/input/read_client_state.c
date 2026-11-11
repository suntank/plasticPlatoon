/* Read-only target-device QA helper. Compile against the same engine headers;
 * reads only camera, current command, and public player state from the game. */
#define _GNU_SOURCE
#include "../../src/client/header/client.h"
#include <stddef.h>
#include <stdint.h>
#include <sys/uio.h>
#include <unistd.h>

static int read_state(pid_t pid, uintptr_t address, void *out, size_t size)
{
	struct iovec local = {out, size}, remote = {(void *)address, size};
	return process_vm_readv(pid, &local, 1, &remote, 1, 0) == (ssize_t)size;
}

int main(int argc, char **argv)
{
	player_state_t ps;
	vec3_t angles;
	usercmd_t cmd;
	uintptr_t base;
	pid_t pid;
	if (argc != 3) return 2;
	pid = (pid_t)strtol(argv[1], NULL, 10);
	base = (uintptr_t)strtoull(argv[2], NULL, 16);
	if (!read_state(pid, base + offsetof(client_state_t, frame) + offsetof(frame_t, playerstate), &ps, sizeof(ps)) ||
		!read_state(pid, base + offsetof(client_state_t, viewangles), &angles, sizeof(angles)) ||
		!read_state(pid, base + offsetof(client_state_t, cmd), &cmd, sizeof(cmd)))
	{
		perror("read game state");
		return 1;
	}
	printf("{\"pitch\":%.6f,\"yaw\":%.6f,\"server_pitch\":%.6f,\"server_yaw\":%.6f,"
		"\"buttons\":%u,\"ammo\":%d,\"assist\":%d,\"target_pitch\":%d,\"target_yaw\":%d,"
		"\"hip_pitch\":%d,\"hip_yaw\":%d}\n", angles[PITCH], angles[YAW],
		ps.viewangles[PITCH], ps.viewangles[YAW], cmd.buttons, ps.stats[STAT_AMMO],
		ps.stats[STAT_AIMASSIST_FLAGS], ps.stats[STAT_AIMASSIST_PITCH], ps.stats[STAT_AIMASSIST_YAW],
		ps.stats[STAT_AIMASSIST_HIP_PITCH], ps.stats[STAT_AIMASSIST_HIP_YAW]);
	return 0;
}
