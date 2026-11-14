"""Test-only config isolation; retain connected real/virtual controllers and shim.

Disable bindings and physical analog/mouse/gyro gains, while direct harness
commands (+attack/+left and secondary held fields) retain their normal behavior.
"""
import math
import re

SETTINGS = {name: 0 for name in (
    'joy_sensitivity', 'joy_forwardsensitivity', 'joy_sidesensitivity',
    'joy_yawspeed', 'joy_pitchspeed', 'joy_extra_yawspeed', 'joy_extra_pitchspeed',
    'gyro_mode', 'sensitivity', 'm_yaw', 'm_pitch', 'm_forward', 'm_side', 'm_up')}
RELEASES = ('gb_up', 'gb_down', 'gb_left', 'gb_right', 'gb_modifier',
            'forward', 'back', 'moveleft', 'moveright', 'left', 'right',
            'lookup', 'lookdown', 'moveup', 'movedown', 'attack', 'ads',
            'use', 'speed', 'strafe', 'klook', 'mlook', 'joyaltselector')


def config():
    return 'unbindall\n' + ''.join('set %s "%s"\n' % item for item in SETTINGS.items()) + \
           ''.join('-%s\n' % name for name in RELEASES)


def neutralize(command, wait):
    command('unbindall')
    for name in RELEASES:
        command('-' + name)
    for name, value in SETTINGS.items():
        command('set %s %s' % (name, value))
    for slot in range(4):
        for name in ('attack', 'forward', 'back', 'moveleft', 'moveright', 'left', 'right', 'jump'):
            command('pp_test_input %d %s 0' % (slot, name))
    wait(.5)
    return verify(command)


def verify(command):
    queries = {}; retries = {}
    for name, value in SETTINGS.items():
        attempts = []
        for attempt in range(3):
            reply = command(name); attempts.append(reply)
            found = re.search(r'"' + re.escape(name) + r'" is "([^"\r\n]*)"', reply)
            try:
                actual = float(found[1]) if found else None
            except ValueError:
                actual = None
            if actual is None:
                continue
            if actual != value:
                raise RuntimeError('Input isolation setting mismatch: ' + name + ': ' + reply)
            break
        else:
            raise RuntimeError('Input isolation cvar query unreadable after 3 attempts: ' + name + ': ' + repr(attempts))
        if len(attempts) > 1:
            retries[name] = attempts
        queries[name] = reply
    bindings = command('bindlist')
    if re.search(r'^\S+\s+"[^"\r\n]+"\s*$', bindings, re.M):
        raise RuntimeError('Input isolation bindings are not empty: ' + bindings)
    return dict(passed=True, method='config_only_unbound_physical_inputs',
                compiled_driver_unchanged=True, actual_cvar_queries=queries,
                cvar_query_retries=retries, bindlist=bindings, physical_axes_mouse_gyro_gains_zero=True)


def angle_difference(a, b):
    return (a - b + 180) % 360 - 180


def phase_audit(phase, before, after, rows, targets):
    checks = {}; slots = {}
    turning = any(re.search(r'pp_test_input\s+\d+\s+(left|right)\s+1$', c)
                  for c in phase.get('commands', []))
    functional = phase['label'].startswith('functional-')
    for state_name, state in [('before', before), ('after', after)]:
        checks[state_name + '_zero_usercmd_movement'] = len(state.get('slots', [])) == 4 and all(
            all(s.get(k) == 0 for k in ('cmd_forward', 'cmd_sidemove', 'cmd_upmove'))
            for s in state['slots'])
    for i in range(4):
        own = [r for r in rows if int(r['slot']) == i]
        if not own:
            checks['slot%d_rows_present' % i] = False
            continue
        xs = [float(r['x']) for r in own]; ys = [float(r['y']) for r in own]
        yaw = [float(r['yaw']) for r in own]
        finite = all(math.isfinite(v) for v in xs + ys + yaw)
        spread = max(angle_difference(y, yaw[0]) for y in yaw) - min(angle_difference(y, yaw[0]) for y in yaw)
        slots[str(i)] = dict(x_range=max(xs)-min(xs), y_range=max(ys)-min(ys),
            yaw_span_degrees=spread, intended_turning=turning,
            functional_transition=functional, reference_render_yaw=yaw[0])
        checks['slot%d_finite_camera' % i] = finite
        if not functional:
            # Moving train has already stopped before its measured bridge phase.
            # Normal weapon kick moves render origin by <=.5 per axis.
            checks['slot%d_fixed_xy_with_recoil' % i] = max(xs)-min(xs) <= 1.001 and max(ys)-min(ys) <= 1.001
            if not turning:
                checks['slot%d_fixed_render_yaw_with_recoil' % i] = spread <= 1.001
                a = before['slots'][i]['viewangles'][1]; b = after['slots'][i]['viewangles'][1]
                checks['slot%d_fixed_base_yaw' % i] = abs(angle_difference(a, b)) <= .001
                if i in targets:
                    checks['slot%d_commanded_render_yaw' % i] = all(abs(angle_difference(y, targets[i][4])) <= .501 for y in yaw)
            checks['slot%d_fixed_base_pitch' % i] = abs(angle_difference(
                before['slots'][i]['viewangles'][0], after['slots'][i]['viewangles'][0])) <= .001
    return dict(passed=all(checks.values()), checks=checks, slots=slots,
                scope='Zero movement at both endpoints; raw camera bounds for all rows. Combat recoil allowed; only scripted DM turning exempts yaw. Short death/respawn camera transitions exempt camera bounds.')


def update_targets(commands, targets):
    for command in commands:
        parts = command.split()
        if len(parts) == 7 and parts[0] == 'cl_bench_pose':
            targets[int(parts[1])] = [float(v) for v in parts[2:]]
