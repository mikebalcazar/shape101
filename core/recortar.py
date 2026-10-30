"""RECORTAR sobre curvas libres: spline y elipse  ·  fase B1 del rumbo de modelado.

La línea, el arco y la polilínea se recortan en el navegador (ui/editar.js).
Una spline o una elipse no: hay que partir la curva exacta, y eso vive aquí,
donde está la NURBS (core/nurbs.py). El navegador manda el clic y los cruces
—que ya calcula exactos sobre la curva (ui/curvas.js)— y recibe qué cambia y
qué se agrega, para aplicarlo como cualquier otra operación (un Ctrl+Z la
deshace entera).

La regla es la de RECORTAR de siempre: se quita el pedazo entre los dos cruces
que rodean el clic; si sólo hay cruce de un lado, se quita hasta la punta.

- **Abierta**, con cruce a los dos lados: quedan dos curvas (la original y una
  nueva). Con cruce de un solo lado: se acorta.
- **Cerrada**: hacen falta dos cruces; queda una curva abierta, la que da la
  vuelta por el otro lado. En una spline cerrada ese lado puede pasar por la
  costura: se pegan los dos pedazos en uno (`Nurbs.seguida_de`).
- Un cruce a menos de la tolerancia de una punta es la punta misma (A3).

Una spline recortada guarda su NURBS (puntos de control y nudos) y pierde los
puntos de ajuste: el pedazo ya no es la curva que pasaba por todos ellos.
"""

from __future__ import annotations

import math

from . import tolerancia as mod_tolerancia


class NoSeRecorta(ValueError):
    """El pedido no tiene recorte posible; el mensaje es para el usuario."""


def _como_spline(base: dict, c) -> dict:
    d = dict(base)
    d.update({
        "puntos_control": [[p[0], p[1]] for p in c.control],
        # Los nudos del pedazo arrancan donde se cortó (0.3, por ejemplo). La
        # curva es la misma con todos corridos a cero, y hay lectores de DXF
        # —ezdxf entre ellos— que dan por hecho que el primero es cero.
        "nudos": [k - c.nudos[0] for k in c.nudos],
        "pesos": list(c.pesos) if c.pesos is not None else [],
        "grado": c.grado,
        "puntos_ajuste": [],
        "cerrada": False,
    })
    d.pop("id", None)
    return d


def _elegir(ts, tp, dominio, cerrada, eps):
    """Los cruces que rodean al clic: (antes, despues), cada uno un t o None.
    En una cerrada dan la vuelta: si no hay antes, el último; si no hay
    después, el primero."""
    a, b = dominio
    if not cerrada:
        ts = [t for t in ts if a + eps < t < b - eps]
    ts = sorted(set(ts))
    antes = [t for t in ts if t < tp]
    despues = [t for t in ts if t > tp]
    prev = antes[-1] if antes else None
    nxt = despues[0] if despues else None
    if cerrada:
        if prev is None and ts:
            prev = ts[-1]
        if nxt is None and ts:
            nxt = ts[0]
    return prev, nxt


def spline(doc, e, punto, cruces) -> dict:
    """El plan de recorte de una spline: {"cambios": {id: {...}}, "agregar": [...]}."""
    c = e.curva()
    tol = mod_tolerancia.de(doc)
    a, b = c.dominio
    # Cada cruce, como parámetro sobre la curva. Uno que no está sobre ella (a
    # más de la tolerancia) no es de esta curva y se ignora.
    ts = []
    for q in cruces:
        t, p = c.cercano(q)
        if math.dist(p, q[:2]) <= tol:
            ts.append(t)
    tp = c.cercano(punto)[0]
    # La tolerancia, llevada a parámetro con la velocidad de la curva en cada
    # punta: así «pegado a la punta» quiere decir lo mismo que en una línea.
    vel = max(math.hypot(*c.derivada(a)), math.hypot(*c.derivada(b)), 1e-12)
    eps = tol / vel
    cerrada = bool(e.cerrada)
    prev, nxt = _elegir(ts, tp, (a, b), cerrada, eps)
    base = e.a_dict()

    if cerrada:
        if prev is None or nxt is None or abs(prev - nxt) < 1e-12:
            raise NoSeRecorta("Una curva cerrada necesita dos cruces para quitarle un trozo.")
        if nxt < prev:
            resto = c.tramo(nxt, prev)                     # lo quitado pasa por la costura
        else:
            # Lo que queda pasa por la costura: el pedazo hasta el final y el
            # del principio, pegados en uno.
            fin = c.tramo(nxt, b) if nxt < b - 1e-15 else None
            ini = c.tramo(a, prev) if prev > a + 1e-15 else None
            resto = fin.seguida_de(ini) if fin and ini else (fin or ini)
        return {"cambios": {e.id: _como_spline(base, resto)}, "agregar": []}

    if prev is None and nxt is None:
        raise NoSeRecorta("El trozo que señalaste no está entre cruces.")
    if prev is not None and nxt is not None:
        return {"cambios": {e.id: _como_spline(base, c.tramo(a, prev))},
                "agregar": [_como_spline(base, c.tramo(nxt, b))]}
    if nxt is not None:
        return {"cambios": {e.id: _como_spline(base, c.tramo(nxt, b))}, "agregar": []}
    return {"cambios": {e.id: _como_spline(base, c.tramo(a, prev))}, "agregar": []}


def _param_elipse(e, q) -> float:
    """El parámetro t de la elipse (c + u·cos t + v·sin t) para el punto q."""
    ax, ay = e.eje_mayor[0], e.eje_mayor[1]
    bx, by = -ay * e.razon, ax * e.razon
    x, y = q[0] - e.centro[0], q[1] - e.centro[1]
    det = ax * by - bx * ay
    co = (x * by - bx * y) / det
    si = (ax * y - x * ay) / det
    return math.atan2(si, co) % (2 * math.pi)


def elipse(doc, e, punto, cruces) -> dict:
    """El plan de recorte de una elipse o arco de elipse: cambia sus
    parámetros de inicio y fin, como el arco de círculo."""
    dos_pi = 2 * math.pi
    t0 = e.param_ini % dos_pi
    barrido = (e.param_fin - e.param_ini) % dos_pi or dos_pi
    completa = barrido >= dos_pi - 1e-9
    a = math.hypot(*e.eje_mayor)
    eps = mod_tolerancia.de(doc) / max(a * e.razon, 1e-12)     # tolerancia como ángulo (cota segura)
    rel = lambda q: (_param_elipse(e, q) - t0) % dos_pi
    ts = [rel(q) for q in cruces]
    tp = rel(punto)
    prev, nxt = _elegir(ts, tp, (0.0, barrido), completa, eps)
    if completa:
        if prev is None or nxt is None or abs(prev - nxt) < 1e-12:
            raise NoSeRecorta("Una elipse completa necesita dos cruces para quitarle un trozo.")
        ini, fin = t0 + nxt, t0 + prev
        if fin <= ini:
            fin += dos_pi
        return {"cambios": {e.id: {"param_ini": ini, "param_fin": fin}}, "agregar": []}
    if prev is None and nxt is None:
        raise NoSeRecorta("No hay cruce dentro del arco de elipse.")
    if prev is not None and nxt is not None:
        base = e.a_dict()
        base.pop("id", None)
        base.update({"param_ini": t0 + nxt, "param_fin": t0 + barrido})
        return {"cambios": {e.id: {"param_ini": t0, "param_fin": t0 + prev}}, "agregar": [base]}
    if nxt is not None:
        return {"cambios": {e.id: {"param_ini": t0 + nxt, "param_fin": t0 + barrido}}, "agregar": []}
    return {"cambios": {e.id: {"param_ini": t0, "param_fin": t0 + prev}}, "agregar": []}


def recortar(doc, e, punto, cruces) -> dict:
    if e.tipo == "spline":
        return spline(doc, e, punto, cruces)
    if e.tipo == "elipse":
        return elipse(doc, e, punto, cruces)
    raise NoSeRecorta(f"Aquí se recortan splines y elipses, no {e.tipo}.")
