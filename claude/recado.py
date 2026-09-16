"""El mandadero · recado 11: volver a disparar el armado de 0.4.0.

La rama `claude/publicar-0.4.0` ya existe, apuntando al commit donde las
pruebas del 3D no encontraban el kernel. El conector del chat sabe **crear**
una rama, no moverla, así que la mueve esto: `main` —ya con el arreglo y con el
cuaderno del armado— encima de esa rama, y el armado arranca de nuevo.

Se reusa el número 0.4.0 a propósito: nunca llegó a publicarse, así que no hay
nada allá afuera que se llame así.
"""
from __future__ import annotations

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
    tmp = pathlib.Path("/tmp/recado11")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    sha = correr(["git", "rev-parse", "HEAD"], cwd=shape).strip()
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    print(f"{DESTINO} movida a {sha}: el armado de 0.4.0 arranca de nuevo")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"el recado falló: {type(e).__name__}: {e}")
        sys.exit(1)
