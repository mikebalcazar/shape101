"""El mandadero · recado 31: abrir las dos capas del instalador.

El armado de 0.12.0 llegó más lejos y el cuaderno lo dijo:

    mv: cannot stat 'anterior/resources/python': No such file or directory

Medido desde el chat, bajando el instalador y mirando dentro: el NSIS de
electron-builder guarda **toda la app dentro de `$PLUGINSDIR/app-64.7z`**, y
sólo deja `resources/icon.ico` suelto. En el instalador viejo de draw101 el
árbol quedaba a la vista; en el de shape101 no. Hay que abrir dos capas.

De paso, dentro de esa segunda capa el Python ya trae `build123d`: shape101
alimentándose de sí mismo sale más barato que de draw101.

El paso queda escrito para servir con las dos formas —árbol suelto o `.7z`
interno— y para decir qué encontró si no halla ninguna, en vez de un `mv` a
secas sin explicación.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
DESTINO = "claude/publicar-0.12.0"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    for n in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        v = os.environ.get(n)
        if v:
            t = t.replace(v, "***")
    return t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo)


VIEJO = """          7z x -y -oanterior anterior.exe "resources/python/*" > /dev/null
          mkdir -p runtime && mv anterior/resources/python runtime/python
"""

NUEVO = """          # El NSIS de electron-builder guarda toda la app dentro de
          # $PLUGINSDIR/app-64.7z y deja sólo el icono suelto: hay que abrir dos
          # capas. El instalador viejo de draw101 dejaba el árbol a la vista, así
          # que esto sirve con las dos formas.
          7z x -y -oanterior anterior.exe "resources/python/*" '$PLUGINSDIR/app-64.7z' > /dev/null
          if [ -d anterior/resources/python ]; then
            mkdir -p runtime && mv anterior/resources/python runtime/python
          else
            interno=$(find anterior -name 'app-64.7z' | head -1)
            if [ -z "$interno" ]; then
              echo "el instalador no trae ni resources/python ni app-64.7z; esto es lo que hay dentro:"
              7z l anterior.exe | tail -25
              exit 1
            fi
            7z x -y -oadentro "$interno" "resources/python/*" > /dev/null
            test -d adentro/resources/python || { echo "app-64.7z no trae resources/python"; exit 1; }
            mkdir -p runtime && mv adentro/resources/python runtime/python
            rm -rf adentro
          fi
"""


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado31")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if "app-64.7z" in t:
        anotar("el flujo ya abría las dos capas: no se toca")
    else:
        flujo.write_text(cambiar(t, VIEJO, NUEVO, "flujo (dos capas)"), encoding="utf-8")
        anotar("armar-y-publicar.yml: abre las dos capas del instalador (NSIS → app-64.7z)")

    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    datos = yaml.safe_load(flujo.read_text(encoding="utf-8"))
    pasos = datos["jobs"]["armar"]["steps"]
    anotar(f"el flujo sigue siendo YAML válido: {len(pasos)} pasos")
    paso = next(p for p in pasos if "empotrado" in str(p.get("name", "")))
    if "app-64.7z" not in paso["run"]:
        raise RuntimeError("el paso del Python empotrado no quedó con las dos capas")
    anotar("el paso del Python empotrado busca en las dos capas")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: abrir las dos capas del instalador\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "El Python empotrado se saca de las dos capas del instalador\n\n"
            "El armado murió con «cannot stat anterior/resources/python». Medido bajando el\n"
            "instalador y mirando dentro: el NSIS de electron-builder guarda toda la app en\n"
            "$PLUGINSDIR/app-64.7z y deja sólo el icono suelto. El instalador viejo de\n"
            "draw101 dejaba el árbol a la vista; el de shape101 no.\n\n"
            "Ahora se abren las dos capas, sirve con las dos formas, y si no encuentra el\n"
            "Python lista lo que sí hay dentro en vez de fallar en un mv sin explicación.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} movida: el armado de 0.12.0 arranca de nuevo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado31/shape101")
    if not (shape / ".git").is_dir():
        return
    try:
        correr(["git", "checkout", "--", "."], cwd=shape)
        correr(["git", "clean", "-fd"], cwd=shape)
        correr(["git", "checkout", "-B", "claude/recado-fallo"], cwd=shape)
        (shape / "claude").mkdir(exist_ok=True)
        (shape / "claude" / "ultimo-recado.md").write_text(
            "# Último recado · FALLÓ\n\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n", encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=shape)
        correr(["git", "commit", "-m", "recado fallido: dónde se rompió"], cwd=shape)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=shape)
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {e2}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        d = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el recado falló: {d}")
        avisar_del_fracaso(d)
        sys.exit(1)
