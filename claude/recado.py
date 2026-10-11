"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el séptimo)

#110 · sin aceleración gráfica, y con volcado de caída
  La 0.19.5 descartó lo anterior: ningún proceso se cayó —los detectores
  estaban puestos— y el segundo intento iba con sesión limpia. Lo que queda:
  el contenido de una ventana CON MARCO se desarma a los 22 ms sin que nadie la
  cierre, y crear la siguiente tumba a Electron a nivel nativo. La de arranque,
  transparente y sin marco, sobrevive. Esa diferencia señala al driver de
  video. Se apaga la aceleración gráfica y se enciende el volcado de caída en
  disco, que dice en qué DLL se cayó si vuelve a pasar.

Medido en el chat con Electron: las dos llamadas corren antes de `ready` sin
reventar y una ventana con marco pinta por software.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
REPO = "nest101"
PARCHES = ["build/110-sin-grafica.patch"]
APLICADORES: list[str] = []
SENAS = [
    ("electron/main.js", "app.disableHardwareAcceleration()", "la gráfica apagada"),
    ("electron/main.js", "crashReporter.start(", "el volcado de caída"),
    ("electron/main.js", 'app.getGPUInfo("basic")', "el apunte de qué gráfica hay"),
    ("claude/notas-0.19.6.txt", "por software", "las notas de la 0.19.6"),
]
NO_DEBE: list[tuple[str, str, str]] = []
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """Sin aceleración gráfica, y con volcado de caída (#110)

Lo que dijo el registro de la 0.19.5 en la máquina de Mike:

    22:56:31.055  creando la ventana
    22:56:31.091  empieza a cargar
    22:56:31.113  el contenido de la ventana se destruyó   ← 22 ms
    22:56:31.129  creando la ventana (sesión limpia)       ← y aquí muere todo

Y NINGÚN proceso se cayó: ni ventana, ni gráfica, ni red, ni utilidades. Los
detectores de #108 y #109 estaban puestos y no vieron nada. Eso descarta la
librería ajena matando procesos (#109) y la sesión guardada (#108): el segundo
intento iba limpio y ni llegó a abrir.

Lo que queda: el contenido de una ventana CON MARCO se desarma sin que nadie la
cierre —no hay renglón de «se está cerrando»— y crear la siguiente tumba a
Electron a nivel nativo, por debajo de cualquier atrapador de errores. La
ventana del arranque, transparente y sin marco, sobrevive: usa otro camino de
composición. Esa diferencia señala a la gráfica —driver de video—, que es por
donde Electron pinta las ventanas con marco.

Dos cosas, las dos antes de que arranque nada:

1. Se apaga la aceleración gráfica (`app.disableHardwareAcceleration()`).
   Chromium pinta por software; el 3D (WebGL) sigue funcionando, más lento. Si
   con esto abre, era eso, y se afina después: prender la gráfica sólo donde
   no tumba.
2. Se enciende el volcado de caída (`crashReporter`), sólo en disco, sin mandar
   nada a ningún lado. Si vuelve a caerse, queda un archivo en la carpeta de
   datos que dice en qué módulo —qué DLL— se cayó. Es el dato que no se puede
   adivinar desde fuera y el que cierra esto.

Y en arranque.log queda la tarjeta de video del equipo y dónde quedan los
volcados, para leerlos desde el chat.

Medido antes de empujar con Electron de verdad: las dos llamadas corren antes
de `ready` sin reventar, y una ventana con marco pinta por software. Lo demás
igual: verificar.py TODO OK y pruebas/licencia.mjs 53 de 53.
"""

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    v = os.environ.get("TOKEN_SHAPE101")
    return t.replace(v, "***") if v else t


def correr(orden, cwd=None, entorno=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True, env=entorno)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(
            f"falló {' '.join(orden[:3])}: {(h.stdout + h.stderr).strip()[-1200:]}"))
    return h.stdout


def main() -> int:
    t = os.environ.get("TOKEN_SHAPE101")
    if not t:
        print("falta TOKEN_SHAPE101")
        return 1

    tmp = pathlib.Path("/tmp/mandado-nest101")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    repo = tmp / REPO

    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t}@github.com/{DUENO}/{REPO}", str(repo)])
    anotar(f"{REPO} clonado")
    correr(["git", "config", "user.name", "nest101 (mandado desde shape101)"], cwd=repo)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=repo)

    # 1 · las librerías primero: medir sin ellas fue lo que tiró el mandado 108.
    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS)} librerías instaladas")

    # 2 · los parches
    for p in PARCHES:
        if not (repo / p).exists():
            anotar(f"{p} no está: se da por aplicado")
            continue
        correr(["git", "apply", "--check", p], cwd=repo)
        correr(["git", "apply", p], cwd=repo)
        correr(["git", "rm", "-q", p], cwd=repo)
        anotar(f"{p} aplicado y retirado")

    for archivo, sena, que in SENAS:
        if sena not in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} no quedó con {que}")
    for archivo, sena, que in NO_DEBE:
        if sena in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} todavía trae {que}")
    anotar("el parche dejó lo que debía")

    for js in ("electron/licencia.js", "electron/licencia-nucleo.js", "electron/main.js"):
        correr(["node", "--check", js], cwd=repo)
    anotar("los tres archivos de la puerta pasan node --check")

    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)

    # 3 · medir, que es lo que autoriza a empujar
    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr(["node", "pruebas/licencia.mjs"], cwd=repo, entorno=entorno)
    if "todo bien" not in salida:
        raise RuntimeError("pruebas/licencia.mjs no acabó en «todo bien»")
    anotar("pruebas/licencia.mjs: " + salida.strip().splitlines()[-1])

    # 4 · empujar
    if not correr(["git", "status", "--porcelain"], cwd=repo).strip():
        anotar("no había nada que cambiar")
        return 0
    (repo / "claude" / "ultimo-mandado.md").write_text(
        "# Último mandado\n\n*Lo escribe el mandadero de shape101 al correr en "
        "Actions, prestado a nest101.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
        "```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=repo)
    correr(["git", "commit", "-m", COMMIT.rstrip()], cwd=repo)
    correr(["git", "push", "origin", "HEAD:main"], cwd=repo)
    anotar("empujado a main de nest101")
    return 0


def avisar_del_fracaso(error: str) -> None:
    """El aviso va a shape101, que es donde este corredor sí puede escribir."""
    t = os.environ.get("TOKEN_SHAPE101")
    tmp = pathlib.Path("/tmp/aviso-shape101")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        correr(["git", "clone", "--depth", "1",
                f"https://x-access-token:{t}@github.com/{DUENO}/shape101", str(tmp)])
        correr(["git", "checkout", "-B", "claude/recado-fallo"], cwd=tmp)
        correr(["git", "config", "user.name", "shape101 (recado)"], cwd=tmp)
        correr(["git", "config", "user.email", "mike@forespot.com"], cwd=tmp)
        (tmp / "claude").mkdir(exist_ok=True)
        (tmp / "claude" / "ultimo-recado.md").write_text(
            "# Último recado · FALLÓ (mandado de nest101)\n\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n",
            encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=tmp)
        correr(["git", "commit", "-m", "mandado de nest101 fallido: dónde se rompió"], cwd=tmp)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=tmp)
        print("aviso dejado en claude/recado-fallo de shape101")
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {_sin_secretos(str(e2))}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        d = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el mandado falló: {d}")
        avisar_del_fracaso(d)
        sys.exit(1)
