"""Render alternativo de la demo mediante capturas reales de Textual."""

import argparse
import asyncio
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ivoox_cli.cli import MpvPlayer, create_tui  # noqa: E402


async def capture():
    demo = ROOT / ".demo"
    os.environ.update({"IVX_DIR": str(demo / "library"), "IVX_CFG": str(demo / "config")})
    runpy.run_path(str(ROOT / "docs/demo_setup.py"))
    args = argparse.Namespace(
        directory=demo / "library", config=demo / "config", local_only=True
    )
    player = MpvPlayer(audio_output="null")
    app = create_tui(args, player=player)
    frames = demo / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        (frames / "01.svg").write_text(app.export_screenshot(title="ivx"))
        await pilot.press("f", *"ciencia")
        await pilot.pause()
        (frames / "02.svg").write_text(app.export_screenshot(title="ivx · buscar"))
        await pilot.press("enter", "tab", "enter")
        await asyncio.sleep(1)
        (frames / "03.svg").write_text(app.export_screenshot(title="ivx · reproduciendo"))
        await asyncio.sleep(1)
        (frames / "04.svg").write_text(app.export_screenshot(title="ivx · reproduciendo"))

    magick = shutil.which("magick")
    if not magick:
        raise RuntimeError("Se necesita ImageMagick para el render alternativo")
    subprocess.run([
        magick, "-background", "#1e1e2e", "-delay", "120",
        *map(str, sorted(frames.glob("*.svg"))), "-loop", "0", str(ROOT / "docs/demo.gif")
    ], check=True)


if __name__ == "__main__":
    asyncio.run(capture())
