"""Pruebas de integración REALES. Conserva artefactos hasta make clean."""

import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_urls():
    path = ROOT / "test.env"
    require(path.is_file(), "Falta test.env; copia test.env.example y ajusta las URLs")
    config = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip("\"'")
    for key in ("TEST_EPISODE", "TEST_LIST", "TEST_PROGRAM"):
        config[key] = os.environ.get(key, config.get(key, ""))
        require(config[key].startswith("https://"), f"Falta una URL HTTPS para {key}")
    return config


def main():
    urls = load_urls()
    parent = ROOT / ".test-runs"
    parent.mkdir(exist_ok=True)
    with (parent / ".ivx.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_tests(urls, parent)


def run_tests(urls, parent):
    run = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    (run / ".ivx-test").touch()
    env = os.environ.copy()
    env.update({"IVX_CFG": str(run / "config"), "UV_CACHE_DIR": str(ROOT / ".cache/uv"),
                "UV_PYTHON": "/usr/bin/python", "UV_PYTHON_DOWNLOADS": "never",
                "UV_NO_MANAGED_PYTHON": "1"})
    command = ["uv", "run", "--script", str(ROOT / "ivx")]
    print(f"Pruebas reales; artefactos: {run}", flush=True)
    report = {"urls": urls, "checks": []}

    def cli(library, *args, timeout=300):
        invocation = [*command, "--dir", str(library), *args]
        result = subprocess.run(invocation, env=env, capture_output=True, text=True, timeout=timeout, check=False)
        with (run / "commands.log").open("a") as output:
            output.write(f"{invocation!r}\n{result.stdout}\n{result.stderr}\n")
        print(result.stderr, end="", flush=True)
        require(result.returncode == 0, f"ivx falló ({result.returncode}); consulta {run}/commands.log")
        return json.loads(result.stdout.splitlines()[-1]), result.stderr

    def check_audio(library, expected):
        files = sorted(library.glob("*/*.mp3"))
        require(len(files) == expected, f"Se esperaban {expected} audios en {library}, hay {len(files)}")
        for path in files:
            mime = subprocess.check_output(["file", "--brief", "--mime-type", str(path)], text=True).strip()
            if shutil.which("ffprobe"):
                probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                        "stream=codec_type,codec_name", "-of", "json", str(path)],
                                       capture_output=True, text=True, check=True)
                require(any(s.get("codec_type") == "audio" for s in json.loads(probe.stdout)["streams"]),
                        f"ffprobe no reconoce audio: {path}")
            else:
                description = subprocess.check_output(["file", "--brief", str(path)], text=True)
                require(mime.startswith("audio/") or "Audio file" in description or "MPEG ADTS" in description,
                        f"No es audio: {path}: {mime}")
        for folder in {path.parent for path in files}:
            playlist = folder / "playlist.m3u"
            require(playlist.is_file(), f"Falta {playlist}")
            entries = [line for line in playlist.read_text().splitlines() if line and not line.startswith("#")]
            require(set(entries) == {p.name for p in folder.glob("*.mp3")}, "Playlist incompleta")
        return files

    for kind, key, count in [("episode", "TEST_EPISODE", 1), ("list", "TEST_LIST", 2),
                             ("program", "TEST_PROGRAM", 2)]:
        library = run / kind
        first, _ = cli(library, "get", urls[key], "-n", "2")
        require(first["downloaded"] == count and first["failed"] == 0, f"Descarga incorrecta: {first}")
        if kind == "program":
            require(first["method"] == "rss", "TEST_PROGRAM debe publicar un RSS utilizable")
        files = check_audio(library, count)
        snapshots = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}
        time.sleep(1.5)
        second, _ = cli(library, "get", urls[key], "-n", "2")
        require(second["downloaded"] == 0 and second["skipped"] == count, "La segunda ejecución repite descargas")
        require(snapshots == {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}, "Se modificaron audios existentes")
        report["checks"].append({"kind": kind, "first": first, "second": second, "audio_valid": True})
        print(f"OK {kind}: {count} audios, playlist y segunda descarga = 0", flush=True)
        time.sleep(1.5)

    # Atravesar realmente el límite entre páginas sin descargar todos los audios.
    page1, _ = cli(run / "unused", "inspect", urls["TEST_LIST"], "--pages", "1")
    page2, _ = cli(run / "unused", "inspect", urls["TEST_LIST"], "--pages", "2")
    ids1 = [e["id"] for e in page1["episodes"]]
    ids2 = [e["id"] for e in page2["episodes"]]
    require(page2["pages"] == 2 and len(ids2) > len(ids1), "TEST_LIST no permite verificar dos páginas distintas")
    require(len(ids2) == len(set(ids2)) and ids2[:len(ids1)] == ids1, "Paginación inconsistente o duplicados")
    boundary_url = page2["episodes"][len(ids1)]["url"]
    boundary, _ = cli(run / "page2", "get", boundary_url, "-n", "2")
    check_audio(run / "page2", 1)
    report["checks"].append({"kind": "pagination", "page1_count": len(ids1),
                              "two_pages_count": len(ids2), "boundary_download": boundary})
    print(f"OK paginación: {len(ids1)} → {len(ids2)} episodios; audio de segunda página válido", flush=True)

    # Fuerza el mismo fallback que usa discover cuando falta RSS, sin modificar ivx.
    scraped, _ = cli(run / "html", "get", urls["TEST_PROGRAM"], "-n", "2", "--no-rss")
    require(scraped["method"] == "html" and scraped["downloaded"] == 2, "Fallback HTML incorrecto")
    check_audio(run / "html", 2)
    require({p.name for p in (run / "html").glob("*/*.mp3")} ==
            {p.name for p in (run / "program").glob("*/*.mp3")}, "HTML y RSS discrepan en los episodios")
    report["checks"].append({"kind": "html_fallback", "result": scraped})
    print("OK programa sin RSS: descarga real por HTML", flush=True)

    # Interrupción real del proceso mientras recibe audio, y continuación con Range.
    library = run / "resume"
    invocation = [*command, "--dir", str(library), "get", urls["TEST_EPISODE"], "-n", "2", "--rate", "65536"]
    with (run / "interrupted.log").open("w") as output:
        process = subprocess.Popen(invocation, env=env, stdout=output, stderr=output, start_new_session=True)
        try:
            deadline = time.monotonic() + 90
            partial = None
            while time.monotonic() < deadline and process.poll() is None:
                candidates = list(library.glob("*/*.part"))
                if candidates and candidates[0].stat().st_size >= 65536:
                    partial = candidates[0]
                    break
                time.sleep(0.1)
            require(partial is not None, "No se pudo interrumpir una descarga activa")
            os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=20)
            require(process.returncode != 0 and partial.exists(), "No quedó un parcial tras la interrupción")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=20)
    prefix = partial.read_bytes()
    resumed, stderr = cli(library, "get", urls["TEST_EPISODE"], "-n", "2")
    require("RESUME " in stderr and "HTTP 206" in stderr, "El servidor no reanudó con HTTP 206")
    files = check_audio(library, 1)
    with files[0].open("rb") as audio:
        require(audio.read(len(prefix)) == prefix, "La reanudación modificó los bytes iniciales")
    report["checks"].append({"kind": "resume", "partial_bytes": len(prefix),
                              "prefix_sha256": hashlib.sha256(prefix).hexdigest(), "result": resumed})
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"OK reanudación HTTP 206 desde {len(prefix)} bytes", flush=True)
    print(f"PASS: episodio, lista, RSS, idempotencia, paginación, HTML y reanudación. Informe: {run}/report.json", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"FAIL: {exc}")
