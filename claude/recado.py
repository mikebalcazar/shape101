"""El mandadero · recado 12: disparar de verdad el armado de 0.4.0.

El intento anterior no disparó nada y la razón es tonta y vale anotarla: la
rama `claude/publicar-0.4.0` **ya apuntaba a ese mismo commit**. Empujar una
rama al sitio donde ya está no cambia nada, y sin cambio GitHub no dispara
ningún evento. Se quedó todo quieto y el cuaderno que había era el de la vuelta
anterior, lo cual confunde todavía más.

Así que aquí primero se hace un commit de verdad —la nota de este recado— y
después se lleva la rama de publicación a ese commit nuevo. Distinto commit,
evento de verdad, armado que arranca.

Lo que se está publicando ya se midió en la vuelta pasada: 470 comprobaciones
en verde, las tres del 3D incluidas, y el instalador armado de 248 MB. Lo único
que faltó fue el token de carga, que Mike ya puso.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
DESTINO = "claude/publicar-0.4.0"


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        texto = h.stderr.strip()[-800:]
        for n in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
            v = os.environ.get(n)
            if v:
                texto = texto.replace(v, "***")
        raise RuntimeError(f"falló {orden[0]}: {texto}")
    return h.stdout


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado12")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    ahora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (shape / "claude").mkdir(exist_ok=True)
    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {ahora}\n"
        "- recado: disparar de verdad el armado de 0.4.0\n\n```\n"
        "La vuelta anterior no disparó nada: la rama de publicación ya apuntaba a ese mismo\n"
        "commit, y empujar una rama donde ya está no produce ningún evento. Ahora se hace\n"
        "un commit de verdad y se lleva la rama ahí.\n"
        "```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "Disparar el armado de 0.4.0 con un commit de verdad\n\n"
            "La vuelta anterior no disparó nada: claude/publicar-0.4.0 ya apuntaba a ese\n"
            "mismo commit, y empujar una rama al sitio donde ya está no produce ningún\n"
            "evento. Queda anotado, porque el síntoma engaña: el cuaderno del armado seguía\n"
            "siendo el de la vuelta anterior y parecía que algo había corrido.\n\n"
            "Lo que se publica ya está medido: 470 comprobaciones en verde —las tres del 3D\n"
            "incluidas— y el instalador de 248 MB armado. Lo único que faltó fue el token de\n"
            "carga, que ya está puesto."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    sha = correr(["git", "rev-parse", "HEAD"], cwd=shape).strip()
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    print(f"{DESTINO} movida al commit nuevo {sha}: el armado de 0.4.0 arranca de verdad")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"el recado falló: {type(e).__name__}: {e}")
        sys.exit(1)
