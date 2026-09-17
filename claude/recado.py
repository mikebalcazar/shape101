"""El mandadero · recado 18: diagnóstico. ¿Por qué el recado 17 se quedó mudo?

Dos disparos del recado 17 y ninguno escribió ni éxito ni fallo. Eso sólo pasa
si se rompe **antes de clonar**, que es cuando aún no hay dónde escribir: por
ejemplo, si `TOKEN_SHAPE101` expiró o se borró.

Este recado no usa los tokens de Mike para reportar. Escribe en el propio
checkout del corredor, que trae su credencial puesta por `actions/checkout`,
y empuja con ella a la rama `claude/recado-diagnostico`. Si ni eso aparece,
Actions no está corriendo nada.

Lo que mide: si los dos secretos llegan con algo dentro, y si con
`TOKEN_SHAPE101` se puede clonar. Nunca escribe el valor de un token.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def correr(orden, cwd=None, ok=True) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0 and ok:
        raise RuntimeError(f"falló {orden[0]}: {h.stderr.strip()[-600:]}")
    return (h.stdout + h.stderr).strip()


def main() -> int:
    aqui = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
    t_shape = os.environ.get("TOKEN_SHAPE101") or ""
    t_draw = os.environ.get("TOKEN_DRAW101") or ""
    anotar(f"TOKEN_SHAPE101: {'llega con ' + str(len(t_shape)) + ' caracteres' if t_shape else 'VACÍO o ausente'}")
    anotar(f"TOKEN_DRAW101: {'llega con ' + str(len(t_draw)) + ' caracteres' if t_draw else 'VACÍO o ausente'}")

    if t_shape:
        tmp = pathlib.Path("/tmp/diag")
        shutil.rmtree(tmp, ignore_errors=True)
        h = subprocess.run(["git", "clone", "--depth", "1",
                            f"https://x-access-token:{t_shape}@github.com/mikebalcazar/shape101", str(tmp)],
                           capture_output=True, text=True)
        if h.returncode == 0:
            anotar("clonar shape101 con TOKEN_SHAPE101: FUNCIONA")
        else:
            err = h.stderr.strip()[-300:].replace(t_shape, "***")
            anotar(f"clonar shape101 con TOKEN_SHAPE101: FALLA → {err}")

    (aqui / "claude").mkdir(exist_ok=True)
    (aqui / "claude" / "ultimo-recado.md").write_text(
        "# Último recado · DIAGNÓSTICO\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=aqui)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=aqui)
    correr(["git", "add", "claude/ultimo-recado.md"], cwd=aqui)
    correr(["git", "commit", "-m", "diagnóstico: qué llega al recado y qué no"], cwd=aqui)
    # Con la credencial del propio corredor, no con los tokens de Mike.
    correr(["git", "push", "-f", "origin", "HEAD:claude/recado-diagnostico"], cwd=aqui)
    anotar("diagnóstico empujado con la credencial del corredor")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"el diagnóstico falló: {type(e).__name__}: {e}")
        sys.exit(1)
