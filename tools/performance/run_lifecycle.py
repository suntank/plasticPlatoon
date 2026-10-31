#!/usr/bin/env python3
"""Isolated functional GL lifecycle smoke, not a performance measurement."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import signal
import socket
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(renderer, rcon_password="LOCAL_RCON_TOKEN"):
    settings = dict(vid_renderer=renderer, vid_fullscreen=0, r_mode=-1,
        r_customwidth=240, r_customheight=240, r_vsync=0, vid_maxfps=60,
        cl_maxfps=60, cl_async=1, s_initsound=0, r_perf=1, r_perf_gpu=1,
        r_shadows=1, r_fullbright=0, r_novis=0, r_cull=1, r_drawentities=1,
        r_drawworld=1, r_lerpmodels=1, cl_entities=1, cl_lights=1, cl_particles=1,
        gl1_picmip=0, gl_finish=0, gl1_dynamic=1, r_retexturing=1,
        gl1_static_world=1, gl3_static_world=1, r_viscache=1,
        r_msaa_samples=0, r_anisotropic=0, cl_perf_frames=0, cl_perf_quit=0,
        cl_perf_screenshot=0, logfile=2, rcon_password=rcon_password)
    start = [f'set {name} "{value}"' for name, value in settings.items()]
    start.append("cl_bench_local 2 pp_perf_fixture")
    commands = ['alias pp_wait10 "' + ";".join(["wait"] * 10) + '"',
                'alias pp_wait60 "' + ";".join(["pp_wait10"] * 6) + '"',
                'alias pp_wait120 "pp_wait60;pp_wait60"', "pp_wait120"]
    phases = ["initial", "map-reload", "restart", "fallback", "restored"]
    for phase in phases:
        if phase == "map-reload":
            commands += ["gamemap pp_lifecycle_reload", "pp_wait120"]
        elif phase in ("restart", "restored"):
            if phase == "restored":
                commands.append(f"set {renderer}_static_world 1")
            commands += ["vid_restart", "pp_wait120"]
        elif phase == "fallback":
            commands.append(f"set {renderer}_static_world 0")
        label = f"{renderer}-{phase}"
        commands += [f"echo LIFECYCLE_START_{phase}", "status", f"cl_perf_start {label}"]
        if phase == "initial":
            commands += ["pp_wait60", f"cl_perf_start {label}", "pp_wait60"]
        else:
            commands.append("pp_wait120")
        commands += ["cl_perf_stop", "screenshot png", f"echo LIFECYCLE_DONE_{phase}"]
    commands += ["echo LIFECYCLE_COMPLETE", "quit"]
    return "\n".join(start) + "\n", "\n".join(commands) + "\n", phases


def analyze(output, renderer, phases):
    def read_csv(path):
        if path.exists():
            with path.open(newline="") as stream:
                return list(csv.DictReader(stream))
        with gzip.open(path.with_name(path.name + ".gz"), "rt", newline="") as stream:
            return list(csv.DictReader(stream))

    result = {}
    previous_serial = 0
    for phase in phases:
        label = f"{renderer}-{phase}"
        frames = read_csv(output / "perf" / (label + "-frames.csv"))
        views = read_csv(output / "perf" / (label + "-views.csv"))
        if len(frames) < 5:
            raise RuntimeError(f"{label}: only {len(frames)} complete frames")
        if any((int(f["views"]), int(f["width"]), int(f["height"])) != (2, 240, 240) for f in frames):
            raise RuntimeError(f"{label}: unexpected complete-frame dimensions/view count")
        if len(views) != len(frames) * 2 or any((int(v["width"]), int(v["height"])) != (240, 120) for v in views):
            raise RuntimeError(f"{label}: unexpected per-view dimensions/count")
        if set(int(v["slot"]) for v in views) != {0, 1} or any(v["renderer_counters"] != "1" for v in views):
            raise RuntimeError(f"{label}: missing view or renderer diagnostics")
        for view in views:
            serial = int(view["renderer_serial"])
            if serial <= previous_serial or int(view["gpu_origin_serial"]) > serial:
                raise RuntimeError(f"{label}: reused renderer serial or future GPU origin")
            previous_serial = serial
        result[phase] = dict(frames=len(frames), views=len(views), framebuffer=[240, 240],
            viewport=[240, 120], elapsed_ms=sum(float(f["frame_ms"]) for f in frames),
            median_world_triangles=statistics.median(float(f["world_triangles"]) for f in frames),
            median_model_triangles=statistics.median(float(f["model_triangles"]) for f in frames),
            median_client_vertex_bytes=statistics.median(float(f["client_vertex_bytes"]) for f in frames),
            median_dynamic_vertex_bytes=statistics.median(float(f["dynamic_vertex_bytes"]) for f in frames),
            serial_range=[int(views[0]["renderer_serial"]),int(views[-1]["renderer_serial"])],
            rss_kib_first_last=[frames[0]["rss_kib"], frames[-1]["rss_kib"]])
    log = (output / "console.log").read_text(errors="replace")
    if "LIFECYCLE_COMPLETE" not in log:
        raise RuntimeError("script did not reach completion marker")
    if log.count(f"Successfully loaded ref_{renderer}.so as rendering backend.") != 3:
        raise RuntimeError("expected initial renderer load and two vid_restart loads")
    if "Could not create capture files; use a new label" not in log:
        raise RuntimeError("duplicate capture name was not refused")
    if result["initial"]["elapsed_ms"] < 1800:
        raise RuntimeError("duplicate capture did not retain the complete initial interval")
    for error in ("Segmentation fault", "GL_INVALID_", "GL_OUT_OF_MEMORY", "Retrying with", "No usable renderer"):
        if error in log:
            raise RuntimeError(f"unexpected renderer/process error: {error}")
    for phase in phases:
        section = log.split(f"LIFECYCLE_START_{phase}", 1)[1].split(f"LIFECYCLE_DONE_{phase}", 1)[0]
        players = [line for line in section.splitlines() if "[loopback-client" in line]
        if len(players) != 2 or any("CNCT" in line or "ZMBI" in line for line in players):
            raise RuntimeError(f"{phase}: both local clients were not spawned after transition")
        result[phase]["both_clients_spawned"] = True
    shots = sorted((output / "screenshots").glob("*.png"))
    if len(shots) != len(phases):
        raise RuntimeError(f"expected {len(phases)} screenshots, got {len(shots)}")
    result["screenshots"] = dict(zip(phases, [p.name for p in shots]))
    result["renderer_loads"] = 3
    result["duplicate_capture_preserved"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "release",
                        help="Assembled runtime with quake2, renderer, and baseq2 data (default: release)")
    parser.add_argument("--renderer", choices=("gl1", "gl3"), required=True)
    parser.add_argument("--label", help="Fresh artifact directory basename (default: renderer)")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build/lifecycle")
    parser.add_argument("--unprivileged", help="Root validation environments only: existing account to run the game")
    parser.add_argument("--analyze-only", type=Path,
                        help="Validate retained plain/gzipped CSVs and logs without launching the game")
    args = parser.parse_args()
    if args.analyze_only:
        print(json.dumps(analyze(args.analyze_only, args.renderer, config(args.renderer)[2]), indent=2))
        return
    label = args.label or args.renderer
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", label):
        parser.error("label must be a simple artifact directory basename")
    args.source = args.source.resolve()
    required = ("quake2", f"ref_{args.renderer}.so", "baseq2/game.so", "baseq2/pak0.pak",
                "baseq2/plastic-platoon.pk3", "baseq2/maps/pp_perf_fixture.bsp")
    missing = [name for name in required if not (args.source / name).is_file()]
    if missing:
        parser.error("runtime inputs missing: " + ", ".join(missing))
    account = None
    if args.unprivileged:
        if os.geteuid() != 0:
            parser.error("--unprivileged is only for a root validation environment")
        try:
            account = pwd.getpwnam(args.unprivileged)
        except KeyError:
            parser.error("--unprivileged must name an existing account")
    elif os.geteuid() == 0:
        parser.error("quake2 refuses root execution; choose an existing --unprivileged account")
    for program in (["runuser"] if account else []) + ["xvfb-run"]:
        if not shutil.which(program):
            parser.error(f"required program not found: {program}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    artifacts = args.output_root.resolve() / label
    artifacts.mkdir(exist_ok=False)
    runtime = Path(tempfile.mkdtemp(prefix=f"pp-lifecycle-{args.renderer}-"))
    runtime.chmod(0o755)
    base = runtime / "baseq2"
    base.mkdir()
    for name in ("quake2", f"ref_{args.renderer}.so"):
        shutil.copy2(args.source / name, runtime / name)
    shutil.copy2(args.source / "baseq2/game.so", base / "game.so")
    for name in ("pak0.pak", "plastic-platoon.pk3"):
        # Copy into the isolated directory so an unprivileged child does not
        # need traversal rights on the source checkout or a root-owned home.
        shutil.copy2(args.source / "baseq2" / name, base / name)
    (base / "maps").mkdir()
    for name in ("pp_perf_fixture", "pp_lifecycle_reload"):
        shutil.copyfile(args.source / "baseq2/maps/pp_perf_fixture.bsp", base / f"maps/{name}.bsp")
    (base / "perf").mkdir()
    (runtime / "cache").mkdir()
    rcon_password = secrets.token_hex(16)
    start, sequence, phases = config(args.renderer, rcon_password)
    for name, contents in (("lifecycle-start.cfg", start), ("lifecycle-sequence.cfg", sequence)):
        (base / name).write_text(contents)
        (artifacts / name).write_text(contents)
    if account:
        for directory, subdirectories, files in os.walk(runtime):
            os.chown(directory, account.pw_uid, account.pw_gid)
            for name in files:
                path = Path(directory) / name
                if not path.is_symlink():
                    os.chown(path, account.pw_uid, account.pw_gid)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = ["xvfb-run", "-a", "-s", "-screen 0 640x480x24",
               str(runtime / "quake2"), "-portable", "-datadir", str(runtime),
               "+set", "ip", "127.0.0.1", "+set", "port", str(port),
               "+set", "vid_renderer", args.renderer, "+set", "vid_fullscreen", "0",
               "+set", "r_mode", "-1", "+set", "r_customwidth", "240", "+set", "r_customheight", "240",
               "+set", "r_vsync", "0", "+set", "s_initsound", "0", "+exec", "lifecycle-start.cfg"]
    if account:
        command = ["runuser", "-u", args.unprivileged, "--"] + command
    manifest = dict(runtime=str(runtime), command=command, software_renderer=True,
                    binary_sha256=digest(runtime / "quake2"),
                    renderer_sha256=digest(runtime / f"ref_{args.renderer}.so"),
                    game_sha256=digest(base / "game.so"), overlay_sha256=digest(base / "plastic-platoon.pk3"),
                    map_sha256=digest(base / "maps/pp_perf_fixture.bsp"))
    process = None
    started = time.monotonic()
    try:
        with (artifacts / "console.log").open("w") as log:
            process = subprocess.Popen(command, cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1", "LP_NUM_THREADS": "2",
                                           "XDG_CACHE_HOME": str(runtime / "cache")})
            deadline = time.monotonic() + 45
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"engine exited before session ready: {process.returncode}")
                console = (base / "qconsole.log").read_text(errors="replace") if (base / "qconsole.log").exists() else ""
                if "Player entered the game" in console:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("primary player did not enter within45 seconds")
                time.sleep(.1)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
                control.settimeout(1)
                # Player two can enter before the primary receives broadcasts;
                # the primary's log is not an authoritative second-client check.
                status_deadline = time.monotonic() + 15
                while True:
                    control.sendto(b"\xff\xff\xff\xffrcon " + rcon_password.encode() + b" status\n", ("127.0.0.1", port))
                    try:
                        reply, _ = control.recvfrom(8192)
                        status = reply.decode(errors="replace")
                        (artifacts / "initial-status.txt").write_text(status)
                        if any("Player P2" in line and "CNCT" not in line and "ZMBI" not in line for line in status.splitlines()):
                            break
                    except socket.timeout:
                        pass
                    if time.monotonic() >= status_deadline:
                        raise RuntimeError("secondary client did not reach spawned state")
                    time.sleep(.2)
                control.settimeout(3)
                control.sendto(b"\xff\xff\xff\xffrcon " + rcon_password.encode() + b" exec lifecycle-sequence.cfg\n",
                               ("127.0.0.1", port))
                try:
                    reply, _ = control.recvfrom(8192)
                    (artifacts / "control-reply.txt").write_text(reply.decode(errors="replace"))
                except socket.timeout:
                    (artifacts / "control-reply.txt").write_text("No UDP acknowledgement; observe completion marker.\n")
            manifest["returncode"] = process.wait(timeout=90)
            if process.returncode:
                raise RuntimeError(f"engine exited {process.returncode}")
        shutil.copytree(base / "perf", artifacts / "perf")
        shutil.copytree(base / "scrnshot", artifacts / "screenshots")
        shutil.copy2(base / "qconsole.log", artifacts / "qconsole.log")
        manifest["validation"] = analyze(artifacts, args.renderer, phases)
        print(json.dumps(manifest["validation"], indent=2))
    except Exception as error:
        manifest["error"] = str(error)
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        raise
    finally:
        # Also stop our isolated process group on KeyboardInterrupt/SystemExit;
        # those do not pass through the Exception handler above.
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        # Keep partial evidence when readiness, process execution, or analysis
        # fails. Output labels are exclusive, so these are this run's files.
        for name, destination in (("perf", "perf"), ("scrnshot", "screenshots")):
            if (base / name).exists():
                shutil.copytree(base / name, artifacts / destination, dirs_exist_ok=True)
        if (base / "qconsole.log").exists():
            shutil.copy2(base / "qconsole.log", artifacts / "qconsole.log")
        manifest["elapsed_seconds"] = time.monotonic() - started
        (artifacts / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
