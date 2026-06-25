#!/usr/bin/env python3
"""Rasterize the figure SVGs to PNG using headless Chrome (no extra deps).

Reads each SVG's intrinsic width/height and screenshots at 2x for crisp output
(suitable for Substack / web). White background is preserved (the SVGs draw their
own white rect). Run from anywhere:

    .venv/bin/python docs/papers/figures/export_png.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCALE = 2  # 2x device pixels

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    sys.exit("No Chrome/Chromium found for rasterization.")


def dims(svg: str) -> tuple[int, int]:
    head = svg[:400]
    w = re.search(r"width='(\d+)'", head)
    h = re.search(r"height='(\d+)'", head)
    if not (w and h):
        raise ValueError("could not read width/height from SVG root")
    return int(w.group(1)), int(h.group(1))


def main() -> None:
    chrome = find_chrome()
    svgs = sorted(HERE.glob("figure*.svg"))
    if not svgs:
        sys.exit("no figure*.svg found")
    for svg in svgs:
        w, h = dims(svg.read_text())
        png = svg.with_suffix(".png")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--force-device-scale-factor={SCALE}",
            f"--window-size={w},{h}",
            f"--screenshot={png}",
            svg.as_uri(),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = png.exists() and png.stat().st_size > 0
        status = "OK" if ok else f"FAIL (rc={r.returncode})"
        size = f"{png.stat().st_size//1024}KB @ {w*SCALE}x{h*SCALE}" if ok else ""
        print(f"{status:10} {png.name:38} {size}")
        if not ok:
            sys.stderr.write(r.stderr[-400:] + "\n")


if __name__ == "__main__":
    main()
