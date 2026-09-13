"""Lo que comparten las pruebas de la prueba de concepto: el reporte y tres
ayudas. Copiado del patrón de draw101 (pruebas/comun.py) a propósito: mismas
palabras, misma disciplina —cada comprobación dice qué se esperaba en el
idioma del taller— y, además, **cada prueba deja números**: `r.numero(...)`
anota una medición que después sale en RESULTADOS.md tal cual se midió.
"""
from __future__ import annotations

import contextlib
import math
import pathlib
import shutil
import tempfile
import time


class Fallo(Exception):
    """Una comprobación que no se cumplió y que impide seguir esa prueba."""


class Reporte:
    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre
        self.descripcion = descripcion
        self.hechas = 0
        self.fallos: list[str] = []
        self.numeros: list[dict] = []      # lo medido, para RESULTADOS.md
        self.umbrales_no_cumplidos: list[str] = []

    # -- comprobaciones -----------------------------------------------------
    def cierto(self, condicion, que: str, detalle: str = "") -> bool:
        self.hechas += 1
        if condicion:
            return True
        self.fallos.append(que + (f"  ({detalle})" if detalle else ""))
        return False

    def igual(self, obtenido, esperado, que: str) -> bool:
        return self.cierto(obtenido == esperado, que,
                           f"se obtuvo {obtenido!r}, se esperaba {esperado!r}")

    def casi(self, obtenido, esperado, que: str, tol: float = 1e-6) -> bool:
        try:
            ok = abs(float(obtenido) - float(esperado)) <= tol
        except (TypeError, ValueError):
            ok = False
        return self.cierto(ok, que,
                           f"se obtuvo {obtenido!r}, se esperaba {esperado!r} ±{tol}")

    def exige(self, condicion, que: str, detalle: str = "") -> None:
        if not self.cierto(condicion, que, detalle):
            raise Fallo(que)

    # -- lo medido ------------------------------------------------------------
    def numero(self, que: str, valor, unidad: str = "", umbral: str = "",
               cumple: bool | None = None) -> None:
        """Una medición con nombre. `umbral` es el que fija el documento de la
        prueba de concepto; `cumple` es sí/no contra ese umbral, o None si no
        hay umbral."""
        self.numeros.append({"prueba": self.nombre, "que": que, "valor": valor,
                             "unidad": unidad, "umbral": umbral, "cumple": cumple})
        # Un umbral no cumplido NO es una prueba rota: es el resultado que se
        # fue a medir. Se anota y RESULTADOS.md lo enseña; la prueba sólo
        # falla cuando algo está mal (una medida que no cuadra, un error).
        if cumple is False:
            self.umbrales_no_cumplidos.append(f"{que}: {valor} {unidad} (umbral {umbral})")


@contextlib.contextmanager
def carpeta():
    d = pathlib.Path(tempfile.mkdtemp(prefix="shape101-prueba-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def cronometro(destino: dict, clave: str):
    """`with cronometro(t, "modelado"): ...` deja t["modelado"] en ms."""
    t0 = time.perf_counter()
    yield
    destino[clave] = (time.perf_counter() - t0) * 1000


def largo(a, b) -> float:
    return math.dist(a[:2], b[:2])
