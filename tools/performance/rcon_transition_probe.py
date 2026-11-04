#!/usr/bin/env python3
"""Bounded old/new direct-rcon map-transition investigation; no timing claim."""
import argparse
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
import subprocess
import tempfile
import time
from run_lifecycle import ROOT, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=ROOT / "release")
    parser.add_argument("--data-source", type=Path, default=ROOT / "release",
                        help="Assembled runtime with baseq2 data (default: release)")
    parser.add_argument("--label", required=True)
    parser.add_argument("--renderer", choices=("gl1", "gl3"), default="gl1")
    parser.add_argument("--target-map", default="demo1", help="Different installed BSP basename (default: demo1)")
    parser.add_argument("--queued", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build/lifecycle")
    parser.add_argument("--unprivileged", help="Root validation environments only: existing account to run the game")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.label):
        parser.error("label must be a simple artifact directory basename")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_/-]{0,62}", args.target_map) or ".." in args.target_map:
        parser.error("target-map must be a plain relative BSP basename without its extension")
    args.engine, args.data_source = args.engine.resolve(), args.data_source.resolve()
    renderer_binary = "ref_" + args.renderer + ".so"
    required = [args.engine / name for name in ("quake2", renderer_binary)] + [
        args.data_source / "baseq2" / name for name in
        ("game.so", "pak0.pak", "plastic-platoon.pk3", "maps/pp_perf_fixture.bsp")]
    missing = [str(path) for path in required if not path.is_file()]
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
    for program in (["runuser"] if account else []) + ["xvfb-run"] + (["gdb"] if args.debug else []):
        if not shutil.which(program):
            parser.error(f"required program not found: {program}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    artifacts = args.output_root.resolve() / args.label
    artifacts.mkdir(exist_ok=False)
    runtime = Path(tempfile.mkdtemp(prefix="pp-rcon-map-probe-"))
    runtime.chmod(0o755)
    base = runtime / "baseq2"
    (base / "maps").mkdir(parents=True)
    (base / "perf").mkdir()
    (runtime / "cache").mkdir()
    for name in ("quake2", renderer_binary):
        shutil.copy2(args.engine / name, runtime / name)
    shutil.copy2(args.data_source / "baseq2/game.so", base / "game.so")
    shutil.copyfile(args.data_source / "baseq2/maps/pp_perf_fixture.bsp", base / "maps/pp_perf_fixture.bsp")
    target_source = args.data_source / "baseq2/maps" / (args.target_map + ".bsp")
    if target_source.is_file():
        target_copy = base / "maps" / (args.target_map + ".bsp")
        target_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_source, target_copy)
    for name in ("pak0.pak", "plastic-platoon.pk3"):
        shutil.copy2(args.data_source / "baseq2" / name, base / name)
    rcon_password = secrets.token_hex(16)
    start, _, _ = config(args.renderer, rcon_password)
    (base / "lifecycle-start.cfg").write_text(start)
    (artifacts / "lifecycle-start.cfg").write_text(start)
    (base / "transition.cfg").write_text(f"gamemap {args.target_map}\n")
    (artifacts / "transition.cfg").write_text(f"gamemap {args.target_map}\n")
    if account:
        for directory, _, files in os.walk(runtime):
            os.chown(directory, account.pw_uid, account.pw_gid)
            for name in files:
                path = Path(directory) / name
                if not path.is_symlink():
                    os.chown(path, account.pw_uid, account.pw_gid)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = ["xvfb-run", "-a", "-s", "-screen 0 640x480x24"]
    if args.debug:
        command += ["gdb", "-q", "-batch", "-ex", "set pagination off", "-ex", "set confirm off",
                    "-ex", "run", "-ex", "thread apply all bt 32", "--args"]
    command += [str(runtime / "quake2"), "-portable", "-datadir", str(runtime),
               "+set", "ip", "127.0.0.1", "+set", "port", str(port),
               "+set", "vid_renderer", args.renderer, "+set", "vid_fullscreen", "0",
               "+set", "r_mode", "-1", "+set", "r_customwidth", "240", "+set", "r_customheight", "240",
               "+set", "r_vsync", "0", "+set", "s_initsound", "0", "+exec", "lifecycle-start.cfg"]
    if account:
        command = ["runuser", "-u", args.unprivileged, "--"] + command
    manifest = dict(runtime=str(runtime), command=command, source=str(args.engine), data_source=str(args.data_source), target_map=args.target_map)
    for name in ("quake2", renderer_binary, "baseq2/game.so", "baseq2/plastic-platoon.pk3"):
        manifest[name + "_sha256"] = hashlib.sha256((runtime / name).read_bytes()).hexdigest()
    process = None
    try:
        with (artifacts / "console.log").open("w") as log:
            process = subprocess.Popen(command, cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1", "LP_NUM_THREADS": "2",
                                           "XDG_CACHE_HOME": str(runtime / "cache")})
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
                control.settimeout(1)

                def rcon(text):
                    # A command may respond after the receive timeout (notably
                    # screenshots/map loads). A new source port ensures its
                    # delayed packets cannot masquerade as the next status.
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as request:
                        request.settimeout(1)
                        request.sendto(b"\xff\xff\xff\xffrcon " + rcon_password.encode() + b" " + text.encode() + b"\n",
                                       ("127.0.0.1", port))
                        try:
                            return request.recvfrom(65535)[0].decode(errors="replace")
                        except socket.timeout:
                            return "TIMEOUT\n"

                deadline = time.monotonic() + 40
                while True:
                    status = rcon("status")
                    players = [line for line in status.splitlines() if "[loopback-client" in line]
                    if len(players) == 2 and all("CNCT" not in line and "ZMBI" not in line for line in players):
                        break
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("split clients did not become ready")
                    time.sleep(.2)
                (artifacts / "status-before.txt").write_text(status)
                rcon("cl_perf_start transition-probe")
                time.sleep(3)
                rcon("screenshot png")
                framefile = base / "perf/transition-probe-frames.csv"
                before_size = framefile.stat().st_size
                before_text = framefile.read_text()
                (artifacts / "frames-before.csv").write_text(before_text)
                reply = rcon("exec transition.cfg" if args.queued else f"map {args.target_map}")
                (artifacts / "direct-map-reply.txt").write_text(reply)
                time.sleep(8)
                response = rcon("status")
                (artifacts / "status-after.txt").write_text(response)
                after_first_size = framefile.stat().st_size
                time.sleep(3)
                after_size = framefile.stat().st_size
                players_after = [line for line in response.splitlines() if "[loopback-client" in line]
                manifest.update(frames_bytes_before=before_size, frames_bytes_after=after_size,
                    frames_bytes_first_posttransition=after_first_size,
                    status_responded=response != "TIMEOUT\n", suspected_stall=response == "TIMEOUT\n" and after_first_size == after_size,
                    two_spawned_after=len(players_after)==2 and all("CNCT" not in line and "ZMBI" not in line for line in players_after),
                    rendered_after_transition=after_size>after_first_size,
                    transitioned_to_target=bool(re.search(r"^map\s*:\s*"+re.escape(args.target_map)+r"\s*$",response,re.MULTILINE)))
                if manifest["suspected_stall"] and args.debug:
                    processes = subprocess.check_output(["ps", "-e", "-o", "pid=,comm=,args="], text=True)
                    for line in processes.splitlines():
                        fields = line.strip().split(None, 2)
                        if len(fields) == 3 and fields[1] == "quake2" and str(runtime / "quake2") in fields[2]:
                            manifest["engine_pid"] = int(fields[0])
                            os.kill(int(fields[0]), signal.SIGINT)
                            process.wait(timeout=15)
                            break
                else:
                    rcon("screenshot png")
                    rcon("quit")
        print(json.dumps(manifest, indent=2))
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for name in ("perf", "scrnshot"):
            if (base / name).exists():
                shutil.copytree(base / name, artifacts / name)
        if (base / "qconsole.log").exists():
            shutil.copy2(base / "qconsole.log", artifacts / "qconsole.log")
        (artifacts / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
