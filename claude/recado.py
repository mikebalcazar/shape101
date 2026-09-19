"""El mandadero · recado 29: volver a disparar el armado de 0.12.0.

El recado 28 corrió limpio a las 02:33 UTC y empujó `claude/publicar-0.12.0`,
pero tres horas después no hay cuaderno de armado, ni bueno ni malo: el flujo
de Windows no arrancó. Aquí se hace un commit de verdad —una nota en el
recado— y se lleva la rama de publicación a ese commit nuevo, que es lo único
que dispara un evento. Si este recado corre, Actions está vivo.
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
    tmp = pathlib.Path("/tmp/recado29")
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
        f"- corrido: {ahora}\n- recado: volver a disparar el armado de 0.12.0\n\n```\n"
        "El armado de 0.12.0 no arrancó tras el recado 28. Commit de verdad y rama de\n"
        "publicación movida a él, para que haya un evento nuevo.\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m", "Volver a disparar el armado de 0.12.0 con un commit de verdad"], cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    sha = correr(["git", "rev-parse", "HEAD"], cwd=shape).strip()
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    print(f"{DESTINO} movida al commit nuevo {sha}: el armado de 0.12.0 arranca de verdad")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"el recado falló: {type(e).__name__}: {e}")
        sys.exit(1)
