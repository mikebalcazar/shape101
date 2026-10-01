"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

## Por qué existe esto

nest101 no puede publicar solo y draw101 sí. La diferencia es una línea: el
`armar-y-publicar.yml` de draw101 se dispara con `push` de
`claude/publicar-*`, y el `apps.yml` de nest101 sólo tiene
`workflow_dispatch`, que necesita la API de Actions. Medido hoy desde el chat
de nest101: `git push` 403 del proxy, `api.github.com` 403, `gh` no está, y el
conector da 403 en `.github/workflows/` tanto con `create_or_update_file` como
con `push_files` — lo mismo que midió draw101 el 12-sep (muro
`2026-09-14-1000`) y que el muro `2026-09-14-1010` dejó claro que Mike no
puede arreglar dando permisos.

Mike autorizó usar este mandadero para romper el círculo: un corredor con un
token sí puede escribir en `.github/workflows/`. Es la misma idea del muro
`2026-09-14-1000` §3 vía A, aplicada al revés.

## Qué hace, en orden, y qué lo detiene

1. Clona `nest101` con `TOKEN_SHAPE101`. Si ese token no alcanza a nest101,
   aquí se para y lo dice: es lo primero que hay que saber.
2. Aplica `build/apps-disparo-por-rama.patch` (el disparo por rama) y retira el
   parche del repositorio.
3. Corre los dos aplicadores de `claude/` —los cambios de #102 que no caben por
   el conector (`core/modelos.py` de 50 KB, `ui/app.js` de 140 KB) y las
   comprobaciones de #101/#102 para `verificar.py`— y retira los andamios.
4. **Mide**: `python verificar.py` y `python claude/comprobar_103.py`. Si
   cualquiera de los dos no acaba en verde, no se empuja nada.
5. Empuja a `main` de nest101.

Si algo falla, el aviso con el detalle queda en la rama `claude/recado-fallo`
de shape101, igual que siempre (y esa rama no vuelve a disparar el flujo).

Este archivo se borra de la rama cuando el mandado esté hecho; la rama entera
es desechable.
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
PARCHE = "build/apps-disparo-por-rama.patch"
APLICADORES = ["claude/aplicar_101_102.py", "claude/aplicar_101_102_pruebas.py"]
ANDAMIOS = APLICADORES + ["claude/101-102-pendiente.md"]
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore",
]
COMMIT = """Se publica desde el chat: apps.yml se dispara con la rama (#104), y los tres pendientes

Lo que desatasca: `apps.yml` ahora arranca también con `push` de
`claude/publicar-<version>`, como el `armar-y-publicar.yml` de draw101. El
conector del chat sabe crear ramas, así que con esto nest101 se publica desde el
chat sin que nadie apriete un botón. La versión sale del nombre de la rama; a
mano sigue saliendo del formulario, y disparado por rama `publicar` es true.

Por qué llega por el mandadero de shape101: el conector de GitHub da 403 en
`.github/workflows/` (medido hoy con `create_or_update_file` y con `push_files`,
y ya lo había medido draw101 el 12-sep), el proxy del chat no deja `git push` ni
`api.github.com`, y el permiso que lo arreglaría no lo puede dar Mike (muro
2026-09-14-1010). Un corredor con token sí puede. Mike lo autorizó.

De paso entran los tres cambios de #102 y #101 que no caben por el conector
porque el archivo viaja entero desde el contexto del chat:

  · core/modelos.py — con el total derivado y sin zoclo, `alto_cuerpo` ya es el
    cuerpo: quitarle la plancha otra vez encogía el mueble un espesor en cada
    recálculo (900 → 880 → 860 con piedra de 20). Es #059 otra vez, que se
    arregló en la rama con zoclo y se quedó vivo en ésta.
  · ui/app.js — la captura: la plancha entra en las cuatro ramas. Es donde nace
    #102. El saneo de core/proyecto.py ya corregía el resultado; esto evita que
    la pantalla siga generando el dato malo.
  · verificar.py — las comprobaciones de #101 y #102, incluido el barrido de 636
    configuraciones de tipo, zoclo, cubierta, candado y overrides.

Medido por el corredor antes de empujar: `python verificar.py` en verde y
`python claude/comprobar_103.py` en verde. Si alguno no lo estuviera, este
commit no existiría.
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

    # 1 · ¿alcanza el token?
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t}@github.com/{DUENO}/{REPO}", str(repo)])
    anotar(f"{REPO} clonado: el token alcanza para leer")
    correr(["git", "config", "user.name", "nest101 (mandado desde shape101)"], cwd=repo)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=repo)

    # 2 · el disparo por rama
    if (repo / PARCHE).exists():
        correr(["git", "apply", "--check", PARCHE], cwd=repo)
        correr(["git", "apply", PARCHE], cwd=repo)
        correr(["git", "rm", "-q", PARCHE], cwd=repo)
        anotar(f"{PARCHE} aplicado y retirado")
    else:
        anotar(f"{PARCHE} no está: se da por aplicado")

    texto_flujo = (repo / ".github/workflows/apps.yml").read_text(encoding="utf-8")
    if "claude/publicar-*" not in texto_flujo:
        raise RuntimeError("apps.yml no quedó con el disparo por rama")
    anotar("apps.yml dice claude/publicar-*")

    # 3 · los tres pendientes
    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
        else:
            anotar(f"{a} no está: se da por aplicado")
    for a in ANDAMIOS:
        if (repo / a).exists():
            correr(["git", "rm", "-q", a], cwd=repo)
    anotar("andamios retirados")

    # 4 · medir, que es lo que autoriza a empujar
    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS)} librerías instaladas")

    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr([sys.executable, "claude/comprobar_103.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("comprobar_103.py no acabó en TODO OK")
    anotar("comprobar_103.py: TODO OK")

    # 5 · empujar
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
