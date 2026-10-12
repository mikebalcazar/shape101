"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el noveno)

#112 · la interfaz no se queda vieja en la caché
  Mike, 11-oct, con la 0.19.7 recién instalada y abriendo: «Solo me sale esto
  en el engrane de configuración», y la foto era el menú de SEPTIEMBRE. El
  instalador sí traía el menú nuevo (se abrió y se leyó). En su
  `%APPDATA%\\nest101\\Cache` estaba el `app.js` del 16-sep: `StaticFiles`
  no manda `Cache-Control`, y sin él Chromium da por fresco un archivo viejo
  durante días sin volver a preguntar. El servidor manda ahora `no-cache`
  (pregunta antes de usar; con ETag es un 304 barato) y el programa vacía la
  caché antes de abrir la ventana, para lo ya guardado sin cabecera.

Medido en el chat: `verificar.py` TODO OK (con el bloque #112: cabecera, ETag,
304 y orden en main.js), `clearCache()` corrido en Electron 33 de verdad.
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
PARCHES = ["build/112-interfaz-sin-cache-vieja.patch"]
APLICADORES: list[str] = []
SENAS = [
    ("server.py", 'r.headers["Cache-Control"] = "no-cache"', "la cabecera que hace preguntar"),
    ("server.py", "_UISinCacheVieja(directory=UI", "el montaje de la interfaz con esa cabecera"),
    ("electron/main.js", "session.defaultSession.clearCache()", "el vaciado de la caché vieja"),
    ("claude/notas-0.19.8.txt", "no se queda vieja", "las notas de la 0.19.8"),
    ("verificar.py", "#112: LA INTERFAZ SE VUELVE A PEDIR", "la comprobación"),
]
NO_DEBE = [
    ("server.py", 'app.mount("/", StaticFiles(directory=UI', "el montaje viejo sin cabecera"),
]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """La interfaz no se queda vieja en la caché (#112)

Mike, 11-oct-2026, con la 0.19.7 recién instalada y ya abriendo: «Solo me sale
esto en el engrane de configuración». La foto era el menú de ajustes de
SEPTIEMBRE —cuatro secciones, «General settings»—, no el de #105 con licencia,
llave de Claude y unidades. El instalador publicado sí traía el nuevo: se
abrió el 7z de adentro y `resources/app_py/ui/app.js` lleva `cLicCambiar`.

Lo que pasaba. En `%APPDATA%\\nest101\\Cache\\Cache_Data` había un archivo de
143 KB del 16 de septiembre: el `app.js` de entonces. El servidor local sirve
la interfaz con `StaticFiles`, que manda `ETag` y `Last-Modified` pero NO
`Cache-Control`. Sin esa cabecera, Chromium —el de Electron— calcula la
frescura por su cuenta: un archivo que llevaba semanas sin cambiar se da por
bueno varios días SIN volver a preguntar. Tres actualizaciones seguidas, y la
ventana seguía pintando la interfaz de hace un mes.

Lo que cambia:
· `server.py`: la interfaz viaja con `Cache-Control: no-cache`. No es «no
  guardes», es «pregunta antes de usar»; como ya hay `ETag`, la pregunta es
  un 304 contra el propio equipo. Vale también para quien la abra en un
  navegador de verdad.
· `main.js`: `session.defaultSession.clearCache()` antes de abrir la ventana.
  La cabecera sólo gobierna lo que se guarde de aquí en adelante; lo ya
  guardado sin ella seguiría dándose por fresco. Vaciar cuesta nada.

Cómo se mide: verificar.py pide index.html, app.js y styles.css y comprueba la
cabecera, que viene ETag, que preguntar con él es un 304, y que el vaciado va
antes de `crearVentana()` en main.js. `clearCache()` se corrió en Electron 33
de verdad.

Medido antes de empujar: verificar.py TODO OK.
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

    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS)} librerías instaladas")

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
    anotar("el parche dejó lo que debía, y se llevó lo que debía")

    for js in ("electron/licencia.js", "electron/licencia-nucleo.js", "electron/main.js"):
        correr(["node", "--check", js], cwd=repo)
    anotar("los tres archivos de la puerta pasan node --check")

    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)

    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr(["node", "pruebas/licencia.mjs"], cwd=repo, entorno=entorno)
    if "todo bien" not in salida:
        raise RuntimeError("pruebas/licencia.mjs no acabó en «todo bien»")
    anotar("pruebas/licencia.mjs: " + salida.strip().splitlines()[-1])

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
