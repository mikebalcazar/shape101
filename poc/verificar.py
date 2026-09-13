"""Corre las pruebas de la prueba de concepto de shape101.

    python poc/verificar.py              todas
    python poc/verificar.py p2 p3        sólo ésas
    python poc/verificar.py --resultados  además, reescribe poc/RESULTADOS.md
                                          con los números de esta corrida

Cada prueba es un paso del documento «shape101 · prueba de concepto»
(Drive, 12-sep-2026): deja un número o un sí/no, nunca una opinión. Lo que
no se pudo medir aquí se dice como tal en RESULTADOS.md.

Igual que en draw101: antes de importar nada se apunta HOME a una carpeta
temporal, así ninguna corrida toca las preferencias ni los dibujos de nadie
(el motor de draw101, que aquí se usa para leer y escribir .t101d, guarda
cosas bajo HOME).
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
import tempfile
import time
import traceback

RAIZ = pathlib.Path(__file__).resolve().parent          # poc/
_CASA = tempfile.mkdtemp(prefix="shape101-casa-")
os.environ["HOME"] = _CASA
os.environ["USERPROFILE"] = _CASA
sys.path.insert(0, str(RAIZ.parent))

from poc import comun  # noqa: E402


def pruebas_disponibles() -> list[str]:
    return sorted(p.stem for p in RAIZ.glob("p[1-9]_*.py"))


def correr(nombres: list[str]) -> tuple[int, list]:
    filas = []
    total_fallos = 0
    for nombre in nombres:
        mod = importlib.import_module(f"poc.{nombre}")
        r = comun.Reporte(nombre, getattr(mod, "DESCRIPCION", ""))
        t0 = time.perf_counter()
        try:
            mod.correr(r)
        except comun.Fallo:
            pass
        except Exception:
            r.fallos.append("la prueba reventó:\n" + traceback.format_exc().rstrip())
        ms = (time.perf_counter() - t0) * 1000
        filas.append((r, ms))
        total_fallos += len(r.fallos)
        marca = "ok " if not r.fallos else "MAL"
        print(f"  {marca}  {r.nombre:<22} {r.descripcion:<48} "
              f"{r.hechas:>3} comprobaciones  {ms:>7.0f} ms", flush=True)
        for f in r.fallos:
            print(f"        · {f}", flush=True)
        for u in r.umbrales_no_cumplidos:
            print(f"        ~ umbral NO cumplido · {u}", flush=True)
    print()
    hechas = sum(r.hechas for r, _ in filas)
    ms = sum(m for _, m in filas)
    if total_fallos:
        print(f"  {total_fallos} fallo(s) de {hechas} comprobaciones en {len(filas)} pruebas  ·  {ms:.0f} ms")
    else:
        print(f"  Todo bien: {hechas} comprobaciones en {len(filas)} pruebas  ·  {ms:.0f} ms")
    return (1 if total_fallos else 0), filas


def guardar_medidas(filas) -> pathlib.Path:
    salida = RAIZ / "salida"
    salida.mkdir(exist_ok=True)
    medidas = [n for r, _ in filas for n in r.numeros]
    (salida / "medidas.json").write_text(json.dumps(medidas, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida / "medidas.json"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    todas = pruebas_disponibles()
    elegidas = todas if not args else [n for n in todas if any(n.startswith(a) for a in args)]
    if not elegidas:
        print("  No hay nada que correr. Las que hay:", ", ".join(todas))
        return 1
    print(f"\n  shape101 · prueba de concepto  ·  {len(elegidas)} pruebas\n")
    codigo, filas = correr(elegidas)
    ruta = guardar_medidas(filas)
    print(f"  medidas en {ruta.relative_to(RAIZ.parent)}")
    if "--resultados" in sys.argv:
        from poc import resultados
        resultados.escribir(filas)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
