"""EXTENDER sobre curvas libres: spline y arco de elipse  ·  fase B1b.

Mike, 3-nov-2026: la spline se prolonga **suave**, como Rhino por omisión: se
sigue el polinomio de su último tramo (`Nurbs.prolongada`), así que la
extensión es la misma curva continuada, sin quiebre de tangente ni de
curvatura. Un arco de elipse sigue su elipse, que es lo suave en ella.

Como EXTENDER de siempre: se alarga por la punta más cercana al clic hasta lo
primero que se cruce. Lo que puede cruzarse son las curvas a la vista
(`ventana`), igual que al rayar picando dentro.
"""

from __future__ import annotations

import math

from . import tolerancia as mod_tolerancia


class NoSeExtiende(ValueError):
    """El pedido no tiene extensión posible; el mensaje es para el usuario."""


def _bordes_a_la_vista(doc, e, ventana, espacio: str):
    from . import regiones
    x0, y0, x1, y1 = ventana
    aristas = []
    for o in doc.lista():
        if o.id == e.id or o.tipo not in regiones.BORDES:
            continue
        if getattr(o, "espacio", "") != espacio or getattr(o, "plano", "XY") != "XY":
            continue
        c = o.caja()
        if not c or c[2] < x0 or c[0] > x1 or c[3] < y0 or c[1] > y1:
            continue
        try:
            aristas += regiones._aristas_de(o)
        except Exception:     # noqa: BLE001 — una curva degenerada no estorba
            continue
    return aristas


def _cruces(arista, bordes, tol) -> list:
    """Los puntos donde `arista` toca a alguno de `bordes`."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    puntos = []
    for b in bordes:
        d = BRepExtrema_DistShapeShape(arista.wrapped, b.wrapped)
        if not d.IsDone() or d.Value() > tol:
            continue
        for k in range(1, d.NbSolution() + 1):
            p = d.PointOnShape1(k)
            puntos.append([p.X(), p.Y()])
    return puntos


def spline(doc, e, punto, ventana, espacio: str = "") -> dict:
    from . import regiones

    c = e.curva()
    a, b = c.dominio
    al_principio = math.dist(punto[:2], c.punto(a)) < math.dist(punto[:2], c.punto(b))
    base = c.invertida() if al_principio else c
    a, b = base.dominio
    tol = mod_tolerancia.de(doc)
    bordes = _bordes_a_la_vista(doc, e, ventana, espacio)
    if not bordes:
        raise NoSeExtiende("No hay nada a la vista hacia donde extender.")
    # Cuánto prolongar: hasta cubrir la ventana, duplicando. Una racional muy
    # prolongada da pesos negativos (Nurbs.prolongada lo dice): ahí se para.
    diag = math.hypot(ventana[2] - ventana[0], ventana[3] - ventana[1])
    larga, cuanto = None, 0.5
    while cuanto <= 256:
        try:
            prueba = base.prolongada(cuanto)
        except ValueError:
            break
        larga = prueba
        extra = prueba.tramo(b, prueba.dominio[1])
        if extra.longitud(1e-2) >= diag:
            break
        cuanto *= 2
    if larga is None:
        raise NoSeExtiende("Esa curva no se puede prolongar desde esa punta.")
    extra = larga.tramo(b, larga.dominio[1])
    puntos = _cruces(regiones._edge_bspline(extra), bordes, tol)
    ts = []
    for q in puntos:
        t, p = larga.cercano(q)
        if math.dist(p, q) <= tol and t > b + 1e-9 and math.dist(p, larga.punto(b)) > tol:
            ts.append(t)
    if not ts:
        raise NoSeExtiende("No hay nada hacia donde extender por ese lado.")
    nueva = larga.tramo(a, min(ts))
    if al_principio:
        nueva = nueva.invertida()
    cambios = {"puntos_control": [q[:2] for q in nueva.control],
               "nudos": [k - nueva.nudos[0] for k in nueva.nudos],
               "pesos": list(nueva.pesos) if nueva.pesos is not None else [],
               "grado": nueva.grado, "puntos_ajuste": []}
    return {"cambios": {e.id: cambios}}


def elipse(doc, e, punto, ventana, espacio: str = "") -> dict:
    from build123d import Edge, Plane

    from . import recortar, regiones

    dos_pi = 2 * math.pi
    t0 = e.param_ini
    barrido = (e.param_fin - e.param_ini) % dos_pi
    if barrido < 1e-9:
        raise NoSeExtiende("Una elipse completa no tiene punta que extender.")
    ax, ay = e.eje_mayor
    bx, by = -ay * e.razon, ax * e.razon
    P = lambda t: [e.centro[0] + ax * math.cos(t) + bx * math.sin(t), e.centro[1] + ay * math.cos(t) + by * math.sin(t)]
    al_principio = math.dist(punto[:2], P(t0)) < math.dist(punto[:2], P(t0 + barrido))
    tol = mod_tolerancia.de(doc)
    bordes = _bordes_a_la_vista(doc, e, ventana, espacio)
    a = math.hypot(ax, ay)
    plano = Plane(origin=(e.centro[0], e.centro[1], 0), x_dir=(ax / a, ay / a, 0), z_dir=(0, 0, 1))
    entera = Edge.make_ellipse(a, a * e.razon, plano)
    hueco = dos_pi - barrido                       # lo que falta para cerrar la vuelta
    mejor = None
    for q in _cruces(entera, bordes, tol):
        t = recortar._param_elipse(e, q)
        # Cuánto hay que avanzar desde la punta hasta ese cruce, por fuera del arco.
        avance = ((t0 - t) if al_principio else (t - (t0 + barrido))) % dos_pi
        if 1e-9 < avance < hueco - 1e-9 and (mejor is None or avance < mejor):
            mejor = avance
    if mejor is None:
        raise NoSeExtiende("No hay nada hacia donde extender ese arco de elipse.")
    if al_principio:
        return {"cambios": {e.id: {"param_ini": t0 - mejor, "param_fin": t0 + barrido}}}
    return {"cambios": {e.id: {"param_ini": t0, "param_fin": t0 + barrido + mejor}}}


def extender(doc, e, punto, ventana, espacio: str = "") -> dict:
    if e.tipo == "spline":
        return spline(doc, e, punto, ventana, espacio)
    if e.tipo == "elipse":
        return elipse(doc, e, punto, ventana, espacio)
    raise NoSeExtiende(f"Aquí se extienden splines y arcos de elipse, no {e.tipo}.")
