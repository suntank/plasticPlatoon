#!/usr/bin/env python3
"""Capture Sandbreak in an isolated engine using windowless software rendering.

Run with --label NAME after compiling baseq2/maps/pp_sandbreak.bsp.
All capture_sandkeep options remain available as explicit overrides.
"""
from pathlib import Path
import sys

from capture_sandkeep import main

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    sys.argv[1:1] = [
        "--map-name", "pp_sandbreak",
        "--map", str(ROOT / "baseq2/maps/pp_sandbreak.bsp"),
        "--materials", str(ROOT / "baseq2"),
        "--views", str(ROOT / "tools/maps/sandbreak_views.json"),
        "--output-root", str(ROOT / "build/sandbreak-qa"),
        "--display-backend", "dummy", "--renderer", "soft", "--farsee",
    ]
    main()
