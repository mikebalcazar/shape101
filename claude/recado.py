"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el sexto)

#109 · que una librería ajena no tumbe la ventana
  El instrumental de la 0.19.4 ya enseñó el patrón en la máquina de Mike, y es
  el mismo tres veces seguidas: la ventana de activación empieza a cargar y a
  los 50 ms alguien le destruye el contenido —sin que el programa la cierre— y
  al abrir la segunda se muere el programa entero. La ventana del arranque, que
  es local, sí se ve.

  Eso apunta a `RendererCodeIntegrity`: cuando una protección de empresa inyecta
  su librería en una ventana tipo Chrome, Chromium mata la ventana. Microsoft
  documenta el interruptor para los programas Electron que conviven con eso. Y
  si no fuera eso, esta misma versión lo dice: ahora cualquier proceso que se
  caiga deja su nombre y su motivo en `arranque.log`.

Medido en el chat: `verificar.py` TODO OK, `pruebas/licencia.mjs` 53 de 53 y
`pruebas/arranque.mjs` 18 de 18 con Electron de verdad.
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
PARCHES = ["build/109-que-no-la-tumben.patch"]
APLICADORES: list[str] = []
SENAS = [
    ("electron/main.js", 'appendSwitch("disable-features", "RendererCodeIntegrity")',
     "el interruptor que impide que tumben la ventana"),
    ("electron/main.js", 'app.on("child-process-gone"',
     "el apunte de cualquier proceso que se caiga"),
    ("electron/licencia.js", "creando la ventana",
     "el renglón antes de crear cada ventana"),
    ("claude/notas-0.19.5.txt", "librería ajena", "las notas de la 0.19.5"),
]
NO_DEBE: list[tuple[str, str, str]] = []
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """Que una librería ajena no pueda tumbar la ventana de activación (#109)

El instrumental de la 0.19.4 hizo su trabajo. En la máquina de Mike, tres
arranques seguidos, exactamente el mismo patrón:

    22:22:54.842  empieza a cargar
    22:22:54.895  el contenido de la ventana se destruyó   ← 53 ms
    22:22:54.896  la pantalla no cargó: ERR_FAILED (-2)
    22:22:54.902  segundo intento, con una sesión limpia
                  ← y ahí se acaba el registro: el programa se murió

Lo que eso descarta, que es la mitad del valor: no es la red —la misma
dirección abre en su Chrome, medido—, no es la sesión guardada —el segundo
intento va limpio— y no es el programa cerrando la ventana: el código que la
cierra todavía no había corrido cuando el contenido ya estaba destruido.

Y lo que señala: la ventana del arranque, que carga un archivo local, sí se ve;
la que carga una dirección de internet se muere a los 50 ms. Esa diferencia
tiene nombre conocido en máquinas de empresa: cuando un antivirus inyecta su
librería dentro de una ventana tipo Chrome, Chromium mata la ventana entera si
esa librería no está firmada como él exige —RendererCodeIntegrity—. Microsoft
documenta justo este interruptor para los programas Electron que conviven con
esas protecciones, y es lo que se apaga aquí.

Apagarlo no abre un agujero nuevo en esta app: lo que carga son su propia
interfaz local y la pantalla de la suite, las dos sin integración con Node. En
una máquina donde el problema no existe, no cambia nada.

Y por si no fuera eso, la misma versión lo dirá sin otra vuelta:

· `child-process-gone` y `render-process-gone` a nivel de TODO el programa
  —ventanas, GPU, red, utilidades—, con `reason` y `exitCode`. El escucha de
  #108 estaba pegado sólo a la ventana de la licencia y no cazó nada.
· un renglón ANTES de crear cada ventana, para que un registro que se corta de
  golpe señale el punto exacto. El de la 0.19.4 se cortaba sin decir dónde.

Medido antes de empujar: verificar.py TODO OK, pruebas/licencia.mjs 53 de 53 y
pruebas/arranque.mjs 18 de 18 con Electron de verdad.
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
