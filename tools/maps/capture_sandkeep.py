#!/usr/bin/env python3
"""Capture named Sandkeep views in the real engine using an isolated runtime.

Run after compiling the level. The installed game, settings, and saves are never
changed. Xvfb + Mesa make this usable without a desktop or a GPU. These captures
are visual evidence, not performance measurements or an automated visual oracle.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import zipfile

from verify_sandkeep import BSP, SOLID

ROOT = Path(__file__).resolve().parents[2]
# x/y/z are the teleport command's player origins, not eye coordinates.
VIEWS = [
    dict(name="insertion", pose=[0, -2656, 30, 0, 90]),
    dict(name="entry_crack", pose=[0, -2288, 28, -8, 90], after_pose=[
        dict(command="noclip", wait=.3), dict(command="noclip", wait=.3)]),
    dict(name="entry_inside", pose=[0, -1840, 28, 0, 270]),
    dict(name="alphabet_blocks", pose=[-320, -1792, 28, 0, 136]),
    dict(name="outer_castle", pose=[0, -1500, 74, -6, 90]),
    dict(name="outer_tower", pose=[-448, -1250, 96, -12, 132]),
    dict(name="first_secret_approach", pose=[-896, -1328, 28, 0, 90]),
    dict(name="bailey", pose=[-112, -295, 60, -5, 90]),
    dict(name="armory_entry", pose=[-736, -130, 28, -5, 90]),
    dict(name="armory_control", pose=[-736, 635, 28, 0, 90]),
    dict(name="radio_approach", pose=[160, 400, 28, -10, 0]),
    dict(name="radio_control", pose=[800, 650, 156, 0, 90]),
    dict(name="second_secret_approach", pose=[-72, 480, 28, 0, 90]),
    dict(name="keep_gate", pose=[-112, 1390, 28, -3, 90]),
    dict(name="arena", pose=[0, 1900, 160, 0, 90]),
    dict(name="east_bucket", pose=[432, 2040, 28, 0, 0]),
    dict(name="west_bucket", pose=[-448, 2648, 28, 0, 180]),
    # PM_SPECTATOR does not expire the teleport timer, which forces pitch zero.
    # Brief normal movement expires it before freezing the downward camera.
    dict(name="arena_cover", pose=[320, 2750, 220, 24, 205], after_pose=[
        dict(command="noclip", wait=.3), dict(command="noclip", wait=.3)]),
    dict(name="extraction_gate", pose=[0, 2710, 28, -4, 90]),
    dict(name="extraction", pose=[0, 3264, 28, 0, 90]),
    dict(name="helipad", pose=[560, 3344, 256, 24, 148], after_pose=[
        dict(command="noclip", wait=.3), dict(command="noclip", wait=.3)]),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_for(predicate, process, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"engine exited {process.returncode}: {message}")
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "release")
    parser.add_argument("--map-name", default="pp_sandkeep", help="Runtime BSP basename (default: pp_sandkeep)")
    parser.add_argument("--map", type=Path, help="BSP override; defaults to source/baseq2/maps/MAP-NAME.bsp")
    parser.add_argument("--materials", type=Path, help="Additional baseq2 directory whose textures/env override the runtime copies")
    parser.add_argument("--assets", type=Path, help="Optional baseq2 art directory; models/sound/pics/sprites/players override source packages inside the private runtime")
    parser.add_argument("--label", required=True, help="Fresh output folder name")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build/sandkeep-qa")
    parser.add_argument("--renderer", choices=("gl1", "gl3", "soft"), default="gl3")
    parser.add_argument("--display-backend", choices=("xvfb", "offscreen", "dummy", "current"), default="xvfb",
                        help="Use Xvfb, SDL offscreen, windowless SDL dummy (soft renderer), or current display")
    parser.add_argument("--egl-device", type=int,
                        help="Optional SDL offscreen EGL device index (software device may differ by host)")
    parser.add_argument("--farsee", action="store_true", help="Use the 8192-unit draw distance for oversized rooms")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--views", type=Path, help="JSON list of {name, pose:[x,y,z,pitch,yaw], commands?:[], after_pose?:[{command,wait}]} for stateful interaction captures")
    parser.add_argument("--only", nargs="+", help="Capture only these view names")
    parser.add_argument("--keep-runtime", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.label):
        parser.error("label must be a simple directory basename")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", args.map_name):
        parser.error("map-name must be a plain BSP basename without its extension")
    if not re.fullmatch(r"[0-9]+x[0-9]+", args.size):
        parser.error("size must be WIDTHxHEIGHT")
    width, height = map(int, args.size.split("x"))
    if not (320 <= width <= 3840 and 240 <= height <= 2160):
        parser.error("size must be between 320x240 and 3840x2160")
    source = args.source.resolve()
    map_file = (args.map or source / "baseq2/maps" / (args.map_name + ".bsp")).resolve()
    required = [source / "quake2", source / f"ref_{args.renderer}.so",
                source / "baseq2/game.so", map_file]
    # Standalone releases carry the complete project media in this PK3.
    # Retain support for older runtimes that used a PAK without requiring one.
    if not any((source / "baseq2" / name).is_file()
               for name in ("plastic-platoon.pk3", "pak0.pak")):
        parser.error("runtime needs baseq2/plastic-platoon.pk3 or baseq2/pak0.pak")
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        parser.error("missing runtime files: " + ", ".join(missing))
    if args.assets and not args.assets.is_dir():
        parser.error("assets must be an existing baseq2 art directory")
    if args.display_backend == "dummy" and args.renderer != "soft":
        parser.error("SDL dummy display requires --renderer soft")
    if args.egl_device is not None and (args.egl_device < 0 or args.display_backend != "offscreen"):
        parser.error("--egl-device requires a nonnegative index and --display-backend offscreen")
    collision_bsp = BSP(map_file)
    if args.display_backend == "xvfb" and not shutil.which("xvfb-run"):
        parser.error("xvfb-run is required")
    views = json.loads(args.views.read_text()) if args.views else VIEWS
    if args.only:
        unknown = set(args.only) - {v["name"] for v in views}
        if unknown:
            parser.error("unknown views: " + ", ".join(sorted(unknown)))
        views = [v for v in views if v["name"] in args.only]
    for view in views:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", view["name"]) or len(view["pose"]) != 5:
            parser.error("invalid view definition")
    output = args.output_root.resolve() / args.label
    output.mkdir(parents=True, exist_ok=False)
    (output / "screenshots").mkdir()
    runtime = Path(tempfile.mkdtemp(prefix="pp-sandkeep-qa-"))
    base = runtime / "baseq2"
    (base / "maps").mkdir(parents=True)
    (runtime / "cache").mkdir()
    for name in ("quake2", f"ref_{args.renderer}.so"):
        shutil.copy2(source / name, runtime / name)
    shutil.copy2(source / "baseq2/game.so", base / "game.so")
    shutil.copy2(map_file, base / "maps" / (args.map_name + ".bsp"))
    # Deliberately omit operation-sandkeep.pk3: named archives override loose
    # files, which would silently test the old packaged map instead of this BSP.
    packages = sorted((source / "baseq2").glob("pak[0-9]*.pak"))
    if (source / "baseq2/plastic-platoon.pk3").is_file():
        packages.append(source / "baseq2/plastic-platoon.pk3")
    for path in packages:
        (base / path.name).symlink_to(path)
    for directory in ("textures", "env", "players"):
        if (source / "baseq2" / directory).is_dir():
            shutil.copytree(source / "baseq2" / directory, base / directory)
    if args.materials:
        for directory in ("textures", "env"):
            if (args.materials / directory).is_dir():
                shutil.copytree(args.materials / directory, base / directory, dirs_exist_ok=True)
    asset_overlay = None
    if args.assets:
        # Named packages take priority over loose files. This private art-only
        # archive overrides stock models without importing old maps or settings.
        allowed_suffixes = {".md2", ".md3", ".sp2", ".skin", ".pcx", ".png",
                            ".tga", ".jpg", ".jpeg", ".wal", ".wav", ".ogg"}
        asset_paths = []
        for directory in ("models", "sound", "pics", "sprites", "players"):
            asset_paths.extend(p for p in (args.assets / directory).rglob("*")
                               if p.is_file() and p.suffix.lower() in allowed_suffixes)
        archive = base / "zz-sandkeep-qa-assets.pk3"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as package:
            for path in sorted(asset_paths):
                package.write(path, path.relative_to(args.assets).as_posix())
        asset_overlay = dict(source=str(args.assets.resolve()), files=len(asset_paths),
                             bytes=sum(p.stat().st_size for p in asset_paths),
                             package_sha256=digest(archive))
    token = secrets.token_hex(16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    settings = dict(name='Player', vid_renderer=args.renderer, r_farsee=int(args.farsee), vid_fullscreen=0, r_mode=-1,
        r_customwidth=width, r_customheight=height, r_vsync=0, vid_maxfps=60,
        cl_maxfps=60, cl_async=1, s_initsound=0, cheats=1, skill=1,
        maxclients=2, coop=1, singleplayer=0, deathmatch=0,
        r_hudscale=0, crosshair=0, crosshair_3d=0, crosshair_3d_glow=0,
        cl_gun=0, cl_blend=0, scr_showpause=0, con_notifytime=0, r_fullbright=0, r_novis=0, r_cull=1,
        r_retexturing=1, r_msaa_samples=0, r_anisotropic=0, gl1_picmip=0,
        gl3_intensity=1.5, gl3_intensity_2D=1.5, vid_gamma=1, logfile=2,
        rcon_password=token)
    cfg = "\n".join(f'set {k} "{v}"' for k, v in settings.items())
    # A two-slot co-op server with one connected client keeps localhost UDP
    # available for rcon while rendering the normal single full-screen view.
    cfg += "\nmap " + args.map_name + "\n"
    (base / "sandkeep-qa.cfg").write_text(cfg)
    # Keep a reproducible config without its ephemeral localhost control token.
    (output / "settings.cfg").write_text(cfg.replace(token, "LOCAL_RCON_TOKEN"))
    command = [str(runtime / "quake2"), "-portable", "-datadir", str(runtime),
        "+set", "ip", "127.0.0.1", "+set", "port", str(port),
        "+set", "r_farsee", str(int(args.farsee)),
        "+set", "vid_renderer", args.renderer, "+set", "vid_fullscreen", "0",
        "+set", "r_mode", "-1", "+set", "r_customwidth", str(width),
        "+set", "r_customheight", str(height), "+set", "s_initsound", "0",
        "+exec", "sandkeep-qa.cfg"]
    if args.display_backend == "xvfb":
        command = ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + command
    environment = {**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1", "LP_NUM_THREADS": "2",
                   "XDG_CACHE_HOME": str(runtime / "cache")}
    if args.display_backend in ("offscreen", "dummy"):
        environment["SDL_VIDEODRIVER"] = args.display_backend
    if args.renderer == "soft":
        environment["SDL_RENDER_DRIVER"] = "software"
    if args.egl_device is not None:
        environment["SDL_HINT_EGL_DEVICE"] = str(args.egl_device)
    manifest = dict(map=str(map_file), map_name=args.map_name, map_sha256=digest(map_file),
        binary_sha256=digest(source / "quake2"), game_sha256=digest(source / "baseq2/game.so"), renderer=args.renderer,
        renderer_sha256=digest(source / f"ref_{args.renderer}.so"),
        size=[width, height], software_renderer=True, display_backend=args.display_backend,
        egl_device=args.egl_device,
        views=[], runtime=str(runtime),
        note="Real engine screenshots; architecture review, not a playthrough or GPU benchmark.")
    manifest["materials"] = {str(path.relative_to(base)): digest(path)
                             for path in sorted(base.rglob("sandkeep/*")) if path.is_file()}
    if asset_overlay:
        manifest["asset_overlay"] = asset_overlay
    process = None
    validation_errors = []
    started = time.monotonic()
    try:
        with (output / "console.log").open("w") as log:
            process = subprocess.Popen(command, cwd=runtime, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True,
                env=environment)
            def console():
                path = base / "qconsole.log"
                return path.read_text(errors="replace") if path.exists() else ""
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
                control.settimeout(.4)
                def rcon(text):
                    control.sendto(b"\xff\xff\xff\xffrcon " + token.encode() + b" " + text.encode() + b"\n",
                                   ("127.0.0.1", port))
                    try:
                        return control.recvfrom(65535)[0].decode(errors="replace")
                    except socket.timeout:
                        return "No UDP acknowledgement"
                # Singleplayer does not print the multiplayer join message.
                # Status distinguishes the spawned loopback client from CNCT.
                def ready():
                    status = rcon("status")
                    return any("Player" in line and "CNCT" not in line and "ZMBI" not in line
                               for line in status.splitlines())
                wait_for(ready, process, 50, "local player did not spawn within 50 seconds")
                control.settimeout(3)
                for text in ("god", "notarget", "noclip"):
                    rcon(text)
                time.sleep(.5)
                for view in views:
                    action_results = []
                    for text in view.get("commands", []):
                        action_results.append(dict(command=text, reply=rcon(text)))
                    pose = " ".join(str(v) for v in view["pose"])
                    rcon("cl_bench_pose 0 " + pose)
                    time.sleep(.45)
                    for action in view.get("after_pose", []):
                        if action.get("command"):
                            action_results.append(dict(command=action["command"], reply=rcon(action["command"])))
                        time.sleep(float(action.get("wait", .1)))
                    rcon("cl_perf_start qa_" + view["name"])
                    time.sleep(.12)
                    before = set((base / "scrnshot").glob("*.png"))
                    reply = rcon("viewpos")
                    rcon("screenshot png")
                    shot = wait_for(lambda: next(iter(set((base / "scrnshot").glob("*.png")) - before), None),
                                    process, 8, f"no screenshot for {view['name']}")
                    # PNG is synchronously written, but wait for a complete IEND.
                    wait_for(lambda: shot.read_bytes().endswith(b"IEND\xaeB`\x82"),
                             process, 8, f"incomplete screenshot for {view['name']}")
                    destination = output / "screenshots" / (view["name"] + ".png")
                    shutil.copy2(shot, destination)
                    rcon("cl_perf_stop")
                    poses = base / "perf" / ("qa_" + view["name"] + "-views.csv")
                    actual = None
                    if poses.exists():
                        with poses.open(newline="") as stream:
                            rows = list(csv.DictReader(stream))
                        if rows:
                            actual = {k: float(rows[-1][k]) for k in ("x", "y", "z", "pitch", "yaw", "roll")}
                    manifest["views"].append({**view, "screenshot": str(destination),
                                              "actual_eye_pose": actual,
                                              "action_results": action_results,
                                              "reply": reply, "sha256": digest(destination)})
                    print(f"captured {view['name']}", flush=True)
                rcon("quit")
            process.wait(timeout=10)
            if process.returncode:
                raise RuntimeError(f"engine exited {process.returncode}")
        manifest["complete"] = True
    except Exception as error:
        manifest["error"] = str(error)
        raise
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        if (base / "qconsole.log").exists():
            (output / "qconsole.log").write_text(
                (base / "qconsole.log").read_text(errors="replace").replace(token, "LOCAL_RCON_TOKEN"))
        if (base / "perf").exists():
            shutil.copytree(base / "perf", output / "poses", dirs_exist_ok=True)
            # Rcon dispatch may return before the client executes cl_perf_stop;
            # parse again after shutdown so all buffered rows have been flushed.
            for view in manifest["views"]:
                poses = base / "perf" / ("qa_" + view["name"] + "-views.csv")
                if poses.exists():
                    with poses.open(newline="") as stream:
                        rows = list(csv.DictReader(stream))
                    if rows:
                        view["actual_eye_pose"] = {k: float(rows[-1][k]) for k in ("x", "y", "z", "pitch", "yaw", "roll")}
                        view["captured_pose_frames"] = len(rows)
                actual = view.get("actual_eye_pose")
                if actual:
                    eye = [actual[k] for k in ("x", "y", "z")]
                    contents = collision_bsp.point_contents(eye)
                    view["actual_eye_world_contents"] = contents
                    collision = collision_bsp.collision(eye, (0., 0., 0.), (0., 0., 0.), SOLID,
                                                        opened=view.get("opened_doors", ()))
                    view["actual_eye_collision"] = collision
                    if contents & SOLID:
                        validation_errors.append(f"{view['name']}: measured camera eye is inside world solid (contents={contents})")
                    elif collision:
                        validation_errors.append(f"{view['name']}: measured camera eye intersects {collision}")
                    for axis, (minimum, maximum) in view.get("expect_eye_bounds", {}).items():
                        if not minimum <= actual[axis] <= maximum:
                            validation_errors.append(
                                f"{view['name']}: measured camera {axis}={actual[axis]} is outside expected [{minimum}, {maximum}]")
                else:
                    validation_errors.append(f"{view['name']}: no renderer camera coordinates captured")
        expected_markers = sorted({marker for view in views for marker in view.get("expect_log", [])})
        if expected_markers:
            log_path = output / "qconsole.log"
            log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
            manifest["log_markers"] = {marker: marker in log_text for marker in expected_markers}
            validation_errors.extend("missing gameplay log marker: " + marker
                                     for marker, present in manifest["log_markers"].items() if not present)
        if validation_errors:
            manifest["complete"] = False
            manifest["validation_errors"] = validation_errors
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (output / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if not args.keep_runtime:
            shutil.rmtree(runtime)
    try:
        from PIL import Image, ImageDraw
        tile_width, tile_height = 426, 266
        sheet = Image.new("RGB", (tile_width * 3, tile_height * ((len(views) + 2) // 3)), (28, 30, 34))
        draw = ImageDraw.Draw(sheet)
        for index, view in enumerate(views):
            shot = Image.open(output / "screenshots" / (view["name"] + ".png")).convert("RGB")
            shot.thumbnail((tile_width, tile_height - 26), Image.Resampling.LANCZOS)
            x, y = (index % 3) * tile_width, (index // 3) * tile_height
            sheet.paste(shot, (x, y + 26))
            draw.text((x + 8, y + 7), view["name"], fill="white")
        sheet.save(output / "contact-sheet.jpg", quality=92)
    except ImportError:
        pass  # Pillow is optional; original screenshots are the evidence.
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors))
    print(output)


if __name__ == "__main__":
    main()
