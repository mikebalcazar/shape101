"""El mandadero · recado 3: devolver lo que el trasplante se llevó de más.

El recado 1 excluyó toda carpeta llamada `node_modules`, y eso fue demasiado:
draw101 **guarda dentro del repositorio** `dwgjs/node_modules`, que son los dos
motores que leen DWG. Sin ellos, el flujo de armado se detiene en «Motores DWG
presentes» —y con razón: una app que dice abrir DWG y no los trae es peor que
una que no lo dice—.

En vez de adivinar qué más falta, aquí se compara la lista de archivos que git
tiene en draw101 contra lo que hay en shape101 y se restaura la diferencia. Lo
que se excluye es lo que **debe** ser distinto: la historia de git, los flujos,
el contrato de trabajo y la carpeta `claude/` de cada quien.

De paso se tira `p1-peso-windows.yml`, que era del camino desechado.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/restaurar-dwgjs"
# Lo que de verdad no se copia: cada repositorio tiene el suyo.
NO_TRAER_RAIZ = {".github", "claude"}
NO_TRAER_ARCHIVO = {"OPERAR.md", "CLAUDE.md"}

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
        raise RuntimeError(_sin_secretos(f"falló {orden[0]} {orden[1] if len(orden) > 1 else ''}: "
                                         f"{h.stderr.strip()[-800:]}"))
    return h.stdout


def renombrar(t: str) -> tuple[str, int]:
    n = 0
    for viejo, nuevo in (("draw101", "shape101"), ("DRAW101", "SHAPE101"), ("Draw101", "Shape101")):
        n += t.count(viejo)
        t = t.replace(viejo, nuevo)
    return t, n


def main() -> int:
    t_draw, t_shape = os.environ.get("TOKEN_DRAW101"), os.environ.get("TOKEN_SHAPE101")
    if not t_draw or not t_shape:
        print("faltan los secretos")
        return 1
    tmp = pathlib.Path("/tmp/recado3")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    draw, shape = tmp / "draw101", tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_draw}@github.com/{DUENO}/draw101", str(draw)])
    correr(["git", "clone",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    seguidos = [r for r in correr(["git", "ls-files"], cwd=draw).splitlines() if r.strip()]
    anotar(f"draw101 tiene {len(seguidos)} archivos en git")

    faltaban, renombrados = [], 0
    for rel in seguidos:
        partes = rel.split("/")
        if partes[0] in NO_TRAER_RAIZ or rel in NO_TRAER_ARCHIVO:
            continue
        destino = shape / rel
        if destino.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(draw / rel, destino)
        faltaban.append(rel)
        # El renombre no toca node_modules: ahí no hay identidad nuestra, hay
        # código ajeno, y cambiarle el texto a una dependencia es pedir un bug
        # que nadie va a encontrar.
        if "node_modules" not in rel:
            try:
                texto = destino.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            nuevo, n = renombrar(texto)
            if n:
                destino.write_text(nuevo, encoding="utf-8")
                renombrados += 1

    anotar(f"faltaban {len(faltaban)} archivos; restaurados ({renombrados} además renombrados)")
    porcarpeta: dict[str, int] = {}
    for rel in faltaban:
        clave = "/".join(rel.split("/")[:2])
        porcarpeta[clave] = porcarpeta.get(clave, 0) + 1
    for clave, n in sorted(porcarpeta.items(), key=lambda x: -x[1])[:15]:
        anotar(f"  · {clave}: {n}")

    basura = shape / ".github" / "workflows" / "p1-peso-windows.yml"
    if basura.is_file():
        basura.unlink()
        anotar("borrado .github/workflows/p1-peso-windows.yml (era del camino desechado)")

    # Las dos comprobaciones que el flujo de armado hace, hechas aquí antes
    for ruta in ("dwgjs/node_modules/@mlightcad/libredwg-web/wasm/libredwg-web.wasm",
                 "dwgjs/node_modules/@node-projects/acad-ts/dist"):
        if not (shape / ruta).exists():
            raise RuntimeError(f"sigue faltando {ruta}")
    anotar("los dos motores de DWG están en su sitio")

    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: devolver lo que el trasplante se llevó de más\n\n```\n" + "\n".join(lineas) + "\n```\n",
        encoding="utf-8")

    correr(["git", "add", "-A", "-f"], cwd=shape)
    correr(["git", "commit", "-m",
            "Devueltos los motores de DWG y lo demás que el trasplante se llevó\n\n"
            "El trasplante excluyó toda carpeta llamada node_modules, y draw101 guarda\n"
            "dwgjs/node_modules dentro del repositorio: son los dos motores que leen DWG.\n"
            "Sin ellos el armado se detiene, y con razón. En vez de adivinar qué más faltaba\n"
            "se comparó la lista de archivos de git de draw101 contra la de shape101 y se\n"
            "restauró la diferencia entera. A las dependencias no se les cambia el texto:\n"
            "ahí no hay identidad nuestra, hay código ajeno.\n\n"
            "También se tira p1-peso-windows.yml, que era del camino desechado."],
           cwd=shape)
    correr(["git", "push", "-f", "origin", RAMA], cwd=shape)
    correr(["git", "push", "origin", f"{RAMA}:main"], cwd=shape)
    anotar(f"empujada {RAMA} y llevada a main")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado3/shape101")
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
        correr(["git", "commit", "-m", "recado fallido: lo que se alcanzó a hacer y dónde se rompió"], cwd=shape)
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
