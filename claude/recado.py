"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el octavo)

#111 · la guardia antes de cerrar el splash — la causa de raíz
  El volcado de caída de la 0.19.6, leído con los símbolos de Electron 33:
  `CHECK(!BrowserMainRunner::ExitedMainMessageLoop())` en
  render_process_host_impl.cc:1494, en el proceso principal, al crear la
  ventana de activación. El programa ya se estaba cerrando. Por qué: cerrar el
  splash —la única ventana— emite `window-all-closed` DENTRO de `destroy()`, de
  forma síncrona (medido), y el escucha llamaba a `app.quit()` porque la
  guardia `enLaPuerta` se ponía un renglón DESPUÉS. Desde la 0.19.1 (#100).
  Se pone antes, se protege el arranque entero con `listo`, y se retiran las
  dos conjeturas de #109 y #110.

Medido en el chat: `verificar.py` TODO OK (con el bloque #111), `pruebas/
licencia.mjs` 53 de 53 y `pruebas/arranque.mjs` 19 de 19 con Electron de verdad.
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
PARCHES = ["build/111-la-guardia-antes.patch"]
APLICADORES: list[str] = []
SENAS = [
    ("electron/main.js", "enLaPuerta || !listo", "la guardia del arranque entero"),
    ("electron/main.js", "listo = true;", "el momento en que ya se puede cerrar"),
    ("claude/notas-0.19.7.txt", "arreglado de raíz", "las notas de la 0.19.7"),
    ("verificar.py", "#111: LA GUARDIA VA ANTES", "la comprobación del orden"),
]
NO_DEBE = [
    ("electron/main.js", "\napp.disableHardwareAcceleration();", "la gráfica apagada a ciegas"),
    ("electron/main.js", 'appendSwitch("disable-features", "RendererCodeIntegrity")',
     "el interruptor que no hacía falta"),
]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """La guardia va antes de cerrar el splash: la causa de raíz (#111)

El volcado de caída de la 0.19.6 en la máquina de Mike, leído con los símbolos
de Electron 33.4.11, dice dónde y por qué. Proceso principal, `nest101.exe` sin
`--type`, EXCEPTION_BREAKPOINT en:

    content::RenderProcessHostImpl::RenderProcessHostImpl(...)
    render_process_host_impl.cc:1494
    CHECK(!BrowserMainRunner::ExitedMainMessageLoop());

Es decir: al crear la ventana de activación, el bucle principal YA HABÍA
TERMINADO. El programa se estaba cerrando. Ningún driver, ninguna librería
ajena, ninguna red: Electron había recibido la orden de cerrarse.

De dónde salía la orden. `window-all-closed` se emite DENTRO de `destroy()`,
de forma síncrona —medido: el escucha corre antes de que `destroy()` devuelva—.
La puerta de licencia (#100, 0.19.1) cerraba el splash ANTES de abrir la
ventana de activación, y el splash era la única ventana: cerrarlo emitía
`window-all-closed` y el escucha llamaba a `app.quit()`. Todo lo que seguía
corría sobre un programa muriéndose: la ventana de activación nacía, su
contenido se desarmaba a los 20 ms sin que nadie la tocara (eso era el
«flash»), y la siguiente ventana reventaba en el CHECK.

#106 ya había visto el hueco y puso la guardia `enLaPuerta`… un renglón DESPUÉS
de `cerrarSplash()`. Como el evento es síncrono, cuando la guardia se ponía ya
era tarde. Un renglón.

Lo que cambia:
· `enLaPuerta = true` va ANTES de `cerrarSplash()`.
· `listo` cubre todo el arranque: hasta que la ventana principal exista,
  quedarse sin ventanas no es una orden de cerrar. Antes de la puerta no hacía
  falta porque el splash se cerraba con la ventana principal ya creada.
· Se retiran #109 (`RendererCodeIntegrity`) y #110 (gráfica apagada): eran
  conjeturas, y el volcado dijo otra cosa. El `crashReporter` de #110 se queda:
  es lo que resolvió esto.

Cómo se mide: verificar.py comprueba el ORDEN en el texto de main.js (corre en
cada armado); pruebas/arranque.mjs comprueba el HECHO en el que se apoya —que
el evento es síncrono— con Electron de verdad (a mano, 19 de 19).

Medido antes de empujar: verificar.py TODO OK, pruebas/licencia.mjs 53 de 53,
pruebas/arranque.mjs 19 de 19.
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
