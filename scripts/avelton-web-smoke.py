#!/usr/bin/env python3
"""Render the release bundle and retain diagnostics on both success and failure."""
import argparse
import functools
import http.server
import json
import os
import threading
import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, default=Path("target/avelton-smoke"))
    parser.add_argument("--hardware-gpu", action="store_true",
                        help="Use the browser's physical GPU instead of CI software WebGL")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((Path(__file__).resolve().parents[1] / "avelton.json").read_text())
    evidence = {"name": metadata["name"], "version": metadata["version"],
                "errors": [], "console": [], "status": "failed"}
    with TemporaryDirectory(prefix="avelton-smoke-") as tmp:
        root = Path(tmp).resolve()
        with zipfile.ZipFile(args.bundle) as archive:
            for info in archive.infolist():
                if not (root / info.filename).resolve().is_relative_to(root):
                    raise ValueError("bundle contains path traversal")
            archive.extractall(root)
        sites = list(root.glob("*/index.html"))
        assert len(sites) == 1, "expected exactly one release site"
        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(sites[0].parent))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                # Full Chromium uses the current headless compositor and WebGPU stack.
                # Software WebGL is supported by every app. Chromium's experimental
                # software WebGPU adapter loses its device in Linux CI; retain the
                # blank-canvas check and test the supported fallback instead.
                graphics = [] if args.hardware_gpu else ["--use-angle=swiftshader",
                    "--enable-unsafe-swiftshader", "--disable-blink-features=WebGPU"]
                evidence["graphics"] = "hardware" if args.hardware_gpu else "software-webgl"
                browser = playwright.chromium.launch(
                    channel="chromium", headless=not bool(os.getenv("DISPLAY")),
                    args=graphics + ["--disable-dev-shm-usage"])
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000},
                                            device_scale_factor=1)
                    page.on("pageerror", lambda error: evidence["errors"].append(str(error)))
                    page.on("console", lambda message: evidence["console"].append(
                        {"type": message.type, "text": message.text[:5000]}))
                    page.goto(f"http://127.0.0.1:{server.server_port}/",
                              wait_until="networkidle", timeout=120000)
                    page.wait_for_function(
                        "[...document.querySelectorAll('canvas')].some(c=>c.width>100 && c.height>100)",
                        timeout=120000)
                    evidence["title"] = page.title()
                    assert "Avelton" in evidence["title"], evidence["title"]
                    canvas = page.locator("canvas").first
                    deadline = time.monotonic() + 60
                    while True:
                        canvas.screenshot(path=str(args.output / "canvas.png"))
                        with Image.open(args.output / "canvas.png") as snapshot:
                            evidence["canvas_stddev"] = ImageStat.Stat(snapshot.convert("RGB")).stddev
                        if max(evidence["canvas_stddev"]) > 5:
                            break
                        assert not evidence["errors"], evidence["errors"]
                        assert time.monotonic() < deadline, "UI rendered a blank canvas"
                        page.wait_for_timeout(1000)
                    assert not evidence["errors"], evidence["errors"]
                    evidence["status"] = "passed"
                finally:
                    if 'page' in locals():
                        evidence["canvas_count"] = page.locator("canvas").count()
                        evidence["loading_text"] = page.locator("body").inner_text()[:2000]
                        page.screenshot(path=str(args.output / "startup.png"))
                    (args.output / "startup.json").write_text(json.dumps(evidence, indent=2) + "\n")
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
