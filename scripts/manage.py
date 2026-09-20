"""Integración local de make; no implementa lógica de descarga."""

import fcntl
import http.cookiejar
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = Path(os.environ["CFG"]).expanduser()
PREFIX = Path(os.environ["PREFIX"]).expanduser()
LIBRARY = Path(os.environ["IVX_DIR"]).expanduser()
UNITS = Path.home() / ".config/systemd/user"


def confirm(paths):
    print("Se eliminarán exclusivamente:")
    for path in paths:
        print(f"  {path}")
    if input("¿Continuar? Escribe BORRAR: ") != "BORRAR":
        raise ValueError("Cancelado; no se ha borrado nada")


def quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def cookies():
    path = CFG / "cookies.txt"
    if not path.is_file():
        raise ValueError(f"Falta {path}; exporta cookies en formato Netscape desde tu navegador")
    path.chmod(0o600)
    lines = path.read_text().splitlines()
    if not lines or "Netscape HTTP Cookie File" not in lines[0]:
        raise ValueError("cookies.txt no tiene cabecera Netscape HTTP Cookie File")
    jar = http.cookiejar.MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    items = [c for c in jar if c.domain.lstrip(".") == "ivoox.com"
             or c.domain.endswith(".ivoox.com")]
    if not items:
        raise ValueError("No contiene cookies de ivoox.com")
    expired = sum(c.expires is not None and c.expires > 0 and c.expires < time.time() for c in items)
    print(f"Formato correcto, permisos 600, {len(items)} cookies de iVoox")
    if expired:
        print(f"AVISO: {expired} cookies han caducado (campo expires); vuelve a exportarlas")


def timer_install():
    interval = os.environ["INTERVAL"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:s|min|h|d|w)", interval) or float(re.match(r"[\d.]+", interval)[0]) <= 0:
        raise ValueError("INTERVAL debe ser positivo; ejemplos: 30min, 6h, 1d")
    for value in [str(PREFIX), str(CFG), str(LIBRARY)]:
        if any(char in value for char in "\n\r\x00"):
            raise ValueError("Las rutas no pueden contener saltos de línea")
    UNITS.mkdir(parents=True, exist_ok=True)
    service = "\n".join([
        "# Managed by ivx make timer-install", "[Unit]", "Description=Sincronizar podcasts iVoox",
        "", "[Service]", "Type=oneshot", "UMask=0077",
        "Environment=" + quote(f"PATH={PREFIX}/bin:/usr/local/bin:/usr/bin"),
        "Environment=" + quote(f"IVX_DIR={LIBRARY}"),
        "Environment=" + quote(f"IVX_CFG={CFG}"),
        "Environment=" + quote(f"UV_CACHE_DIR={CFG}/uv-cache"),
        "Environment=UV_PYTHON=/usr/bin/python UV_PYTHON_DOWNLOADS=never UV_NO_MANAGED_PYTHON=1",
        "ExecStart=" + quote(PREFIX / "bin/ivx") + " sync",
        "TimeoutStartSec=infinity", "", "[Install]", "WantedBy=default.target", "",
    ])
    timer = "\n".join([
        "# Managed by ivx make timer-install", "[Unit]", "Description=Sincronización periódica de iVoox",
        "", "[Timer]", "OnBootSec=5min", f"OnUnitActiveSec={interval}", "Persistent=true",
        "Unit=ivx-sync.service", "", "[Install]", "WantedBy=timers.target", "",
    ])
    for name, content in [("ivx-sync.service", service), ("ivx-sync.timer", timer)]:
        target = UNITS / name
        if target.exists() and not target.read_text().startswith("# Managed by ivx"):
            raise ValueError(f"Unidad ajena existente: {target}; revísala antes de sustituirla")
        target.write_text(content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print(f"Unidades instaladas; intervalo {interval}")


def uninstall():
    targets = [PREFIX / "bin/ivx", UNITS / "ivx-sync.service", UNITS / "ivx-sync.timer"]
    confirm([path for path in targets if path.exists()])
    if targets[2].exists():
        subprocess.run(["systemctl", "--user", "disable", "--now", "ivx-sync.timer"], check=True)
    if targets[1].exists():
        subprocess.run(["systemctl", "--user", "stop", "ivx-sync.service"], check=True)
    for path in targets:
        path.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print("Binario y unidades retirados; biblioteca y configuración conservadas")


def clean():
    # Mismo bloqueo que ivx: nunca tocar una descarga activa.
    locks = []
    try:
        for base in [LIBRARY, ROOT / ".test-runs"]:
            if base.exists():
                handle = (base / ".ivx.lock").open("a")
                locks.append(handle)
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        parts = [p for p in LIBRARY.rglob("*.part") if p.is_file() and not p.is_symlink()]
        runs = [p for p in (ROOT / ".test-runs").glob("run-*")
                if p.is_dir() and not p.is_symlink() and (p / ".ivx-test").is_file()]
        targets = parts + [p.with_suffix(p.suffix + ".json") for p in parts
                           if p.with_suffix(p.suffix + ".json").is_file()] + runs
        if not targets:
            print("Nada que limpiar")
            return
        confirm(targets)
        for path in targets:
            if path in runs:
                shutil.rmtree(path)
            else:
                path.unlink()
        print(f"Eliminados {len(targets)} elementos; no se pueden recuperar con ivx")
    finally:
        for handle in locks:
            handle.close()


if __name__ == "__main__":
    try:
        {"cookies": cookies, "timer-install": timer_install,
         "uninstall": uninstall, "clean": clean}[sys.argv[1]]()
    except (ValueError, OSError, EOFError, subprocess.CalledProcessError) as exc:
        sys.exit(f"ERROR: {exc}")
