#!/usr/bin/env python3
"""Render the actual release bundle, checking startup and capturing evidence."""
import argparse
import functools
import http.server
import json
import threading
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

p=argparse.ArgumentParser()
p.add_argument("bundle",type=Path)
p.add_argument("--output",type=Path,default=Path("target/avelton-smoke"))
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
metadata=json.loads(Path("avelton.json").read_text())
with TemporaryDirectory(prefix="avelton-smoke-") as tmp:
    root=Path(tmp).resolve()
    with zipfile.ZipFile(a.bundle) as z:
        for info in z.infolist():
            if not (root/info.filename).resolve().is_relative_to(root):
                raise ValueError("bundle contains path traversal")
        z.extractall(root)
    sites=list(root.glob("*/index.html"))
    assert len(sites)==1,"expected exactly one release site"
    site=sites[0].parent
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(site))
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=["--use-angle=swiftshader","--enable-unsafe-webgpu","--disable-dev-shm-usage"])
            page=browser.new_page(viewport={"width":1440,"height":1000},device_scale_factor=1)
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/",wait_until="networkidle",timeout=120000)
            page.wait_for_function("[...document.querySelectorAll('canvas')].some(c=>c.width>100 && c.height>100)",timeout=120000)
            page.wait_for_timeout(5000)
            assert "Avelton" in page.title(),page.title()
            assert not errors,errors
            screenshot=a.output/"startup.png"
            page.screenshot(path=str(screenshot))
            image=Image.open(screenshot).convert("RGB")
            assert max(ImageStat.Stat(image).stddev)>5,"UI rendered a blank canvas"
            evidence={"name":metadata["name"],"version":metadata["version"],"title":page.title(),"errors":errors,"canvas_count":page.locator("canvas").count()}
            (a.output/"startup.json").write_text(json.dumps(evidence,indent=2)+"\n")
            browser.close()
    finally:
        server.shutdown();server.server_close()
