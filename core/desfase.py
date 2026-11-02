"""DESFASE de curvas libres: spline y elipse  ·  fase B3 del rumbo de modelado.

La curva a una distancia fija de una spline (o de una elipse) no es una spline
ni una elipse: no tiene forma cerrada. Por eso hasta la fase B3 DESFASE se
negaba con ellas («las aproximaciones se notan en el corte»). Rhino lo resuelve
como aquí: se aproxima con una B-spline **a una tolerancia garantizada**, de
modo que en todo su largo la curva nueva está a la distancia pedida, más o
menos la tolerancia. Se usa una décima de la tolerancia del documento (cinco
micras por omisión), muy por debajo de lo que corta una CNC de taller; t050 lo
mide en los dos sentidos.

Cómo: OpenCASCADE da la curva desfasada exacta (Geom_OffsetCurve) y la aproxima
(GeomConvert_ApproxCurve, cúbica C2). El lado sale del clic.

Lo que se niega: desfasar hacia adentro de una curva más que su radio de
curvatura más cerrado de ese lado. Ahí la curva nueva se cruzaría consigo misma
—un lazo—, y un lazo en la CNC es una pieza arruinada. Se dice el radio.
"""

from __future__ import annotations

import math

from . import tolerancia as mod_tolerancia


class NoSeDesfasa(ValueError):
    """El desfase no tiene resultado limpio; el mensaje es para el usuario."""


def _muestras(e, n=600):
    """(punto, derivada, segunda derivada) a lo largo de la curva."""
    if e.tipo == "spline":
        c = e.curva()
        a, b = c.dominio
        return [c.derivadas(a + (b - a) * i / n) for i in range(n + 1)]
    cx, cy = e.centro
    ax, ay = e.eje_mayor
    bx, by = -ay * e.razon, ax * e.razon
    t0, t1 = e.param_ini, e.param_fin
    if (t1 - t0) % (2 * math.pi) < 1e-9:
        t1 = t0 + 2 * math.pi
    salida = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        co, si = math.cos(t), math.sin(t)
        salida.append(([cx + ax * co + bx * si, cy + ay * co + by * si],
                       [-ax * si + bx * co, -ay * si + by * co],
                       [-ax * co - bx * si, -ay * co - by * si]))
    return salida


def _lado(e, punto) -> int:
    """+1 si el clic quedó a la derecha de la curva (en su sentido), -1 si a
    la izquierda. Se mira en el punto de la curva más cercano al clic."""
    if e.tipo == "spline":
        c = e.curva()
        t, q = c.cercano(punto)
        d = c.derivada(t)
    else:
        from .recortar import _param_elipse
        t = _param_elipse(e, punto)
        ax, ay = e.eje_mayor
        bx, by = -ay * e.razon, ax * e.razon
        q = [e.centro[0] + ax * math.cos(t) + bx * math.sin(t), e.centro[1] + ay * math.cos(t) + by * math.sin(t)]
        d = [-ax * math.sin(t) + bx * math.cos(t), -ay * math.sin(t) + by * math.cos(t)]
    cruz = d[0] * (punto[1] - q[1]) - d[1] * (punto[0] - q[0])
    return -1 if cruz > 0 else 1


def _radio_mas_cerrado(e, lado: int) -> float:
    """El menor radio de curvatura de la curva **hacia el lado** del desfase.
    Curvatura con signo: positiva cuando la curva dobla a la izquierda."""
    peor = math.inf
    for _, d1, d2 in _muestras(e):
        v = math.hypot(*d1)
        if v < 1e-12:
            continue
        k = (d1[0] * d2[1] - d1[1] * d2[0]) / v ** 3
        # Hacia la izquierda (lado -1) estorba lo que dobla a la izquierda (k > 0).
        if (lado < 0 and k > 0) or (lado > 0 and k < 0):
            peor = min(peor, 1 / abs(k))
    return peor


def _curva_occ(e):
    """La curva de OpenCASCADE de la entidad, recortada a su tramo."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.Geom import Geom_TrimmedCurve

    from . import regiones

    arista = regiones._aristas_de(e)[0]
    curva = BRep_Tool.Curve_s(arista.wrapped, 0.0, 0.0)
    ad = BRepAdaptor_Curve(arista.wrapped)
    u0, u1 = ad.FirstParameter(), ad.LastParameter()
    if e.tipo == "elipse" and (e.param_fin - e.param_ini) % (2 * math.pi) > 1e-9:
        curva = Geom_TrimmedCurve(curva, u0, u1)
    return curva


def desfasar(doc, e, distancia: float, punto) -> dict:
    """La entidad nueva (dict) a `distancia` de la spline o elipse `e`, del
    lado del `punto`."""
    from OCP.Geom import Geom_OffsetCurve
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.GeomConvert import GeomConvert_ApproxCurve
    from OCP.gp import gp_Dir

    from . import regiones

    if e.tipo not in ("spline", "elipse"):
        raise NoSeDesfasa(f"Aquí se desfasan splines y elipses, no {e.tipo}.")
    d = float(distancia)
    if not d > 0:
        raise NoSeDesfasa("La distancia del desfase tiene que ser mayor que cero.")
    lado = _lado(e, punto)
    radio = _radio_mas_cerrado(e, lado)
    if d >= radio:
        raise NoSeDesfasa(f"A esa distancia la curva nueva se cruzaría consigo misma: "
                          f"de ese lado su radio más cerrado es {radio:.2f}.")
    tol = mod_tolerancia.de(doc) / 10
    # Geom_OffsetCurve con el eje Z desfasa hacia la derecha con distancia positiva.
    off = Geom_OffsetCurve(_curva_occ(e), d * lado, gp_Dir(0, 0, 1))
    ap = GeomConvert_ApproxCurve(off, tol, GeomAbs_C2, 400, 3)
    if not ap.HasResult() or ap.MaxError() > tol:
        raise NoSeDesfasa("No se pudo aproximar el desfase a la tolerancia del documento.")
    c = regiones.nurbs_de_bspline(ap.Curve())
    base = e.a_dict()
    cerrada = bool(getattr(e, "cerrada", False)) or (
        e.tipo == "elipse" and (e.param_fin - e.param_ini) % (2 * math.pi) < 1e-9)
    nuevo = {k: base[k] for k in ("capa", "color", "grosor", "tipo_linea", "escala_tl", "espacio", "plano")
             if k in base}
    nuevo.update({"tipo": "spline", "puntos_control": [p[:2] for p in c.control],
                  "nudos": [k - c.nudos[0] for k in c.nudos],
                  "pesos": list(c.pesos) if c.pesos is not None else [],
                  "grado": c.grado, "puntos_ajuste": [], "cerrada": cerrada})
    return {"entidad": nuevo, "error_max": ap.MaxError(), "tolerancia": tol}
