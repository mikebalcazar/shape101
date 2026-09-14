"""Corre las pruebas de shape101.

    python verificar.py              todas
    python verificar.py t001 t008    sólo ésas
    python verificar.py -v           además, cada comprobación que pasó

Dos decisiones que valen la pena saber:

**La carpeta del usuario se muda.** `core/config.carpeta_usuario()` cuelga de
`Path.home()`: preferencias, autoguardado, bloques y caché. Antes de importar
nada se apunta `HOME` a una carpeta temporal, así que una corrida de pruebas no
puede tocar los dibujos de nadie ni heredar preferencias de la máquina — que es
también la razón de que las pruebas den el mismo resultado en la portátil de
Mike y en el armador.

**Una prueba que revienta no tumba la corrida.** La excepción se anota como un
fallo más de esa prueba y se sigue con la siguiente. Enterarse de las quince de
una vez vale mucho más que enterarse de la primera.
"""

from __future__ import annotations

import importlib
import os
import pathlib
import sys
import tempfile
import time
import traceback

RAIZ = pathlib.Path(__file__).resolve().parent

# --- Antes de importar el programa: mudar la casa ---------------------------
_CASA = tempfile.mkdtemp(prefix="shape101-casa-")
os.environ["HOME"] = _CASA
os.environ["USERPROFILE"] = _CASA
sys.path.insert(0, str(RAIZ))

from pruebas import comun  # noqa: E402


def pruebas_disponibles() -> list[str]:
    return sorted(p.stem for p in (RAIZ / "pruebas").glob("t[0-9][0-9][0-9]_*.py"))


def correr(nombres: list[str], verboso: bool = False) -> int:
    filas = []
    total_fallos = 0
    for nombre in nombres:
        mod = importlib.import_module(f"pruebas.{nombre}")
        r = comun.Reporte(nombre, getattr(mod, "DESCRIPCION", ""))
        t0 = time.perf_counter()
        try:
            mod.correr(r)
        except comun.Fallo:
            pass                      # ya quedó anotado por `exige`
        except Exception:
            r.fallos.append("la prueba reventó:\n" + traceback.format_exc().rstrip())
        ms = (time.perf_counter() - t0) * 1000
        filas.append((r, ms))
        total_fallos += len(r.fallos)

        marca = "ok " if not r.fallos else "MAL"
        print(f"  {marca}  {r.nombre:<16} {r.descripcion:<44} "
              f"{r.hechas:>3} comprobaciones  {ms:>7.0f} ms", flush=True)
        for f in r.fallos:
            print(f"        · {f}", flush=True)

    print()
    hechas = sum(r.hechas for r, _ in filas)
    ms = sum(m for _, m in filas)
    if total_fallos:
        print(f"  {total_fallos} fallo(s) de {hechas} comprobaciones "
              f"en {len(filas)} pruebas  ·  {ms:.0f} ms")
    else:
        print(f"  Todo bien: {hechas} comprobaciones en {len(filas)} pruebas "
              f"·  {ms:.0f} ms")
    return 1 if total_fallos else 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verboso = "-v" in sys.argv
    todas = pruebas_disponibles()
    if not args:
        elegidas = todas
    else:
        elegidas = [n for n in todas if any(n.startswith(a) for a in args)]
        faltan = [a for a in args if not any(n.startswith(a) for n in todas)]
        for f in faltan:
            print(f"  (no hay prueba «{f}»)")
    if not elegidas:
        print("  No hay nada que correr. Las que hay:", ", ".join(todas))
        return 1

    from core.version import VERSION, FECHA
    print(f"\n  shape101 {VERSION} ({FECHA})  ·  {len(elegidas)} pruebas\n")
    return correr(elegidas, verboso)


if __name__ == "__main__":
    sys.exit(main())
