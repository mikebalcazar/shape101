"""El mandadero, prestado a nest101  ·  SÓLO EN LA RAMA `claude/mandado-nest101`.

**El `recado.py` de `main` no se tocó.** Actions hace `checkout` de la rama que
dispara el push, así que esta versión corre únicamente cuando el chat de
nest101 crea `claude/recado-nest101-*`. El mandadero de shape101 sigue siendo
el de `main`, con su `recado.json`, intacto.

Por qué existe: el conector de GitHub del chat da 403 en `.github/workflows/` y
manda cada archivo entero desde su contexto, así que no puede ni tocar el flujo
ni reescribir `ui/app.js` (150 KB) o `verificar.py` (50 KB). Un corredor con
token sí. Mike lo autorizó.

## Este mandado (el cuarto)

Un solo parche, y de los que el conector no puede ni tocar: es del flujo.

#107 · el escaparate se arma al publicar
  Mike, 11-oct-2026: «no se ha actualizado la descarga de la versión en el
  website showcase de suite101.app». El sitio enseñaba la 0.19.2 con la 0.19.3
  ya publicada. `armar-sitio.py` ya lee la versión y la liga de `<app>.json`,
  pero volver a armarlo era un paso a mano después de publicar — y un paso a
  mano dentro de algo automático es un paso que no existe. Ahora `apps.yml` lo
  arma y lo empuja en la misma entrega, justo después del contrato.

El parche se midió en el chat: aplica limpio sobre `main` y el YAML sigue
siendo válido. Si `verificar.py` o `pruebas/licencia.mjs` fallan, no se empuja
nada y el aviso queda en `claude/recado-fallo` de shape101.
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
PARCHES = ["build/107-sitio-al-publicar.patch"]
APLICADORES: list[str] = []
# Lo que el parche TIENE que haber dejado.
SENAS = [
    (".github/workflows/apps.yml", "armar-sitio.py", "el sitio armado al publicar"),
    (".github/workflows/apps.yml", 'git commit -m "el sitio enseña nest101 $V"',
     "el empujón del sitio"),
]
NO_DEBE: list[tuple[str, str, str]] = []
LIBRERIAS = [
    "fastapi", "uvicorn", "ezdxf", "openpyxl", "reportlab==4.4.10", "pillow",
    "numpy", "opencv-python-headless", "anthropic", "pypdfium2",
    "python-multipart", "truststore", "httpx",
]
COMMIT = """Publicar también deja el escaparate al día (#107)

Mike, 11-oct-2026: «no se ha actualizado la descarga de la versión en el website
showcase de suite101.app». Con la 0.19.3 publicada y comprobada, el sitio seguía
ofreciendo la 0.19.2 y su instalador.

No era que el sitio estuviera mal escrito. `descargas/sitio/herramientas/
armar-sitio.py` ya lee la versión y la liga de descarga de `<app>.json` —se
arregló así en octubre, justo porque la ficha llevaba tres semanas de atraso—,
pero volver a armarlo seguía siendo un paso a mano después de cada entrega. Un
paso a mano dentro de algo automático es un paso que no existe: el instalador se
publica solo, el contrato se actualiza solo, y el sitio se quedaba esperando a
que alguien se acordara.

Ahora `apps.yml` lo arma y lo empuja en la misma entrega, dentro del mismo clon
de `descargas` donde ya escribe `nest101.json` y el README. Va DESPUÉS de empujar
el contrato a propósito: si armar el sitio fallara, los programas instalados ya
se enteraron de la versión nueva y lo único que queda rojo es el sitio; al revés
sería peor. Empujar `sitio/` dispara `publicar-sitio.yml` de descargas, que lo
sube a Cloudflare Pages.

De paso rearma las diez páginas, así que también se lleva lo que otra app haya
publicado sin armar el sitio.

Medido por el corredor antes de empujar: verificar.py TODO OK y
pruebas/licencia.mjs 50 de 50. Llega por el mandadero de shape101 porque el
conector del chat da 403 en .github/workflows/.
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

    # 1 · los parches
    for p in PARCHES:
        if not (repo / p).exists():
            anotar(f"{p} no está: se da por aplicado")
            continue
        correr(["git", "apply", "--check", p], cwd=repo)
        correr(["git", "apply", p], cwd=repo)
        correr(["git", "rm", "-q", p], cwd=repo)
        anotar(f"{p} aplicado y retirado")

    # lo que el parche tenía que dejar —y lo que tenía que llevarse
    for archivo, sena, que in SENAS:
        if sena not in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} no quedó con {que}")
    for archivo, sena, que in NO_DEBE:
        if sena in (repo / archivo).read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo} todavía trae {que}")
    anotar("el parche dejó lo que debía")

    # el flujo tiene que seguir siendo YAML válido: si no, la próxima entrega
    # no arranca siquiera, y eso se ve hasta que hace falta publicar
    correr([sys.executable, "-c",
            "import yaml,sys; yaml.safe_load(open('.github/workflows/apps.yml',"
            "encoding='utf-8')); print('yaml ok')"], cwd=repo)
    anotar("apps.yml sigue siendo YAML válido")

    for a in APLICADORES:
        if (repo / a).exists():
            anotar(correr([sys.executable, a], cwd=repo).strip())
            correr(["git", "rm", "-q", a], cwd=repo)

    # 2 · medir, que es lo que autoriza a empujar
    correr([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    correr([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"] + LIBRERIAS)
    anotar(f"{len(LIBRERIAS) + 1} librerías instaladas")

    entorno = dict(os.environ, PYTHONUTF8="1")
    salida = correr([sys.executable, "verificar.py"], cwd=repo, entorno=entorno)
    if "TODO OK" not in salida:
        raise RuntimeError("verificar.py no acabó en TODO OK")
    anotar("verificar.py: TODO OK")

    salida = correr(["node", "pruebas/licencia.mjs"], cwd=repo, entorno=entorno)
    if "todo bien" not in salida:
        raise RuntimeError("pruebas/licencia.mjs no acabó en «todo bien»")
    anotar("pruebas/licencia.mjs: " + salida.strip().splitlines()[-1])

    # 3 · empujar
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
