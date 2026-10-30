"""La tolerancia del documento: **una** distancia que decide si dos cosas se tocan.

Rhino tiene una sola «tolerancia absoluta» por documento y todo la usa: unir,
recortar, intersecar, coser un contorno, las booleanas. shape101 tenía una por
módulo —0.05 en UNIR, 1e-6 al recortar, la de OpenCASCADE (unas micras) al
coser el boceto de un sólido— y cada operación decidía distinto si dos puntos
eran el mismo. El caso que lo destapó: un contorno de un DXF ajeno con huecos
de dos centésimas **se unía** con UNIR pero **no cerraba** al extruirlo.

Lo que hay aquí:

- `POR_OMISION_MM`: 0.05 mm, la que el taller ya usaba en UNIR (t015, Mike):
  un plano de AutoCAD o de Revit trae huecos de centésimas, y medio milímetro
  ya es un error de dibujo que hay que ver, no tapar.
- `de(doc)`: la del documento, en unidades del dibujo.
- `kernel_mm()`: la del documento abierto, en milímetros, para el kernel de
  sólidos, que trabaja en milímetros y no recibe el documento (ver
  `enchufar`, el mismo patrón que `core/solido/rutas.py`).
- `soldar(puntos, tol)`: junta los puntos que caen a menos de `tol` en uno
  solo. Es lo que cose un contorno con huecos de centésimas.

**No es una guarda numérica.** Los `1e-9` y `1e-12` repartidos por el código
evitan dividir entre cero y se quedan como están: no deciden nada del dibujo.
"""

from __future__ import annotations

import math

#: La tolerancia de un dibujo nuevo, en milímetros.
POR_OMISION_MM = 0.05

#: Límites razonables. Por debajo de una micra el doble de precisión de los
#: números ya no alcanza en un plano de cien metros; por encima de un
#: milímetro, «se tocan» empieza a tapar errores de dibujo.
MINIMA_MM = 0.001
MAXIMA_MM = 1.0

_doc_actual = None


def enchufar(buscador) -> None:
    """`buscador()` devuelve el documento abierto. Lo llama `server.py`."""
    global _doc_actual
    _doc_actual = buscador


def valida_mm(valor: float) -> float:
    v = float(valor)
    if not math.isfinite(v) or v < MINIMA_MM or v > MAXIMA_MM:
        raise ValueError(f"la tolerancia va de {MINIMA_MM} a {MAXIMA_MM} mm; llegó {valor}")
    return v


def de(doc) -> float:
    """La tolerancia de `doc`, en unidades del dibujo."""
    mm = getattr(doc, "tolerancia_mm", None) or POR_OMISION_MM
    return mm / (doc.mm_por_unidad() or 1.0)


def kernel_mm() -> float:
    """La del documento abierto, en milímetros (la unidad del kernel)."""
    if _doc_actual is not None:
        try:
            doc = _doc_actual()
            if doc is not None:
                return getattr(doc, "tolerancia_mm", None) or POR_OMISION_MM
        except Exception:
            pass
    return POR_OMISION_MM


def soldar(puntos: list, tol: float) -> list:
    """Para cada punto, el representante de su grupo: el primero que apareció
    a menos de `tol`. Devuelve una lista paralela a `puntos`.

    Por rejilla de celdas de lado `tol`, no comparando todos con todos: un
    boceto de un plano ajeno puede traer miles de extremos.
    """
    celdas: dict[tuple[int, int], list] = {}
    salida = []
    for p in puntos:
        cx, cy = math.floor(p[0] / tol), math.floor(p[1] / tol)
        rep = None
        mejor = tol
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in celdas.get((cx + dx, cy + dy), ()):
                    d = math.hypot(p[0] - q[0], p[1] - q[1])
                    if d <= mejor:
                        rep, mejor = q, d
        if rep is None:
            rep = [p[0], p[1]]
            celdas.setdefault((cx, cy), []).append(rep)
        salida.append(rep)
    return salida
