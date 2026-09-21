"""Crea una biblioteca mínima y local para grabar docs/demo.tape."""

import json
import os
import wave
from pathlib import Path

library = Path(os.environ.get("IVX_DIR", ".demo/library")) / "program-1234"
library.mkdir(parents=True, exist_ok=True)
config = Path(os.environ.get("IVX_CFG", ".demo/config"))
config.mkdir(parents=True, exist_ok=True)
(config / "sources.txt").write_text(
    "https://www.ivoox.com/podcast-ciencia_sq_f11234_1.html\n"
)
for identifier, title, published in (
    ("101", "Ciencia: el universo observable", "2026-09-20"),
    ("102", "Historia de la computación", "2026-09-18"),
):
    audio = library / f"{identifier}.mp3"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 8000 * 12)
    audio.with_suffix(".json").write_text(json.dumps({
        "title": title,
        "published": published,
        "url": f"https://www.ivoox.com/demo_rf_{identifier}_1.html",
    }))
