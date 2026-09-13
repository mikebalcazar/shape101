"""Corre las pruebas de aceptación de la app shape101.

    python app/verificar.py            todas
    python app/verificar.py t01        sólo ésa

Mismo arnés que `poc/verificar.py`, pero aquí las pruebas no miden una
viabilidad: **dicen si un bloque del plan está hecho**. Las escribe el chat de
shape101 antes de que se programe el bloque; Jr. programa hasta que pasan.

Igual que en draw101, antes de importar nada se apunta HOME a una carpeta
temporal: ninguna corrida toca las preferencias ni los dibujos de nadie.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import sys
import tempfile
import time
import traceback

RAIZ = pathlib.Path(__file__).resolve().parent          # app/
_CASA = tempfile.mkdtemp(prefix="shape101-casa-")
os.environ["HOME"] = _CASA
os.environ["USERPROFILE"] = _CASA
sys.path.insert(0, str(RAIZ.parent))

from poc import comun  # noqa: E402   (el arnés vive en poc/, no se duplica)


def pruebas_disponibles() -> list[str]:
    return sorted(p.stem for p in (RAIZ / "pruebas").glob("t[0-9][0-9]_*.py"))


def correr(nombres: list[str]) -> int:
    total_fallos = 0
    hechas = 0
    ms_total = 0.0
    for nombre in nombres:
        r = comun.Reporte(nombre)
        t0 = time.perf_counter()
        try:
            mod = importlib.import_module(f"app.pruebas.{nombre}")
            r.descripcion = getattr(mod, "DESCRIPCION", "")
            mod.correr(r)
        except comun.Fallo:
            pass
        except Exception:
            r.fallos.append("la prueba reventó:\n" + traceback.format_exc().rstrip())
        ms = (time.perf_counter() - t0) * 1000
        total_fallos += len(r.fallos)
        hechas += r.hechas
        ms_total += ms
        marca = "ok " if not r.fallos else "MAL"
        print(f"  {marca}  {r.nombre:<22} {r.descripcion:<48} "
              f"{r.hechas:>3} comprobaciones  {ms:>7.0f} ms", flush=True)
        for f in r.fallos:
            print(f"        · {f}", flush=True)
    print()
    if total_fallos:
        print(f"  {total_fallos} fallo(s) de {hechas} comprobaciones  ·  {ms_total:.0f} ms")
    else:
        print(f"  Todo bien: {hechas} comprobaciones en {len(nombres)} pruebas  ·  {ms_total:.0f} ms")
    return 1 if total_fallos else 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    todas = pruebas_disponibles()
    elegidas = todas if not args else [n for n in todas if any(n.startswith(a) for a in args)]
    if not elegidas:
        print("  No hay nada que correr. Las que hay:", ", ".join(todas) or "(ninguna)")
        return 1
    print(f"\n  shape101 · pruebas de aceptación  ·  {len(elegidas)} pruebas\n")
    return correr(elegidas)


if __name__ == "__main__":
    sys.exit(main())
