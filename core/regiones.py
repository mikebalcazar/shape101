"""Booleanas 2D de contornos cerrados: UNIÓN, RESTA e INTERSECCIÓN  ·  fase B2a.

Es el CurveBoolean de Rhino y el REGION/UNION de AutoCAD: dos o más contornos
cerrados se combinan y queda el contorno del resultado. Se hace **exacto** con
OpenCASCADE —el mismo kernel de los sólidos (core/solido)—: cada contorno se
vuelve una cara plana, las caras se suman, se restan o se cruzan, y el borde
del resultado vuelve a ser entidades del dibujo. Un arco sigue siendo arco y
una spline sigue siendo spline (entra al kernel como B-spline, no como
polilínea), así que el contorno que sale es el que va a la CNC.

Qué entra: polilínea cerrada (con bulges), círculo, elipse completa y spline
cerrada. Qué sale, por cada borde del resultado:

- sólo rectas y arcos → **una polilínea cerrada** con sus bulges (o un círculo,
  si es un círculo entero);
- con splines o elipses de por medio → las piezas en orden (polilíneas para
  los tramos de rectas y arcos, splines, arcos de elipse), **agrupadas**:
  shape101 no tiene «policurva», y el grupo hace que se muevan juntas.

Los huecos del resultado salen como contornos aparte. Las entidades de entrada
se reemplazan, como en AutoCAD; todo va en una transacción (un Ctrl+Z).
"""

from __future__ import annotations

import math

from . import entidades as ent_mod
from . import nurbs as mod_nurbs


class NoSeCombina(ValueError):
    """El pedido no tiene resultado posible; el mensaje es para el usuario."""


OPERACIONES = ("union", "resta", "interseccion")


# --- Del dibujo al kernel -----------------------------------------------------

def _edge_bspline(c):
    """Una NURBS nuestra como arista de OpenCASCADE (Geom_BSplineCurve). Una
    curva sin nudos repetidos en las puntas (la cerrada periódica) se pasa
    antes a sujeta: es la misma curva (`tramo` del dominio entero)."""
    from build123d import Edge
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.Geom import Geom_BSplineCurve
    from OCP.gp import gp_Pnt
    try:        # OCP 7.8+: los arreglos de OpenCASCADE como plantillas
        from OCP.collections import Array1_double as TColStd_Array1OfReal
        from OCP.collections import Array1_gp_Pnt as TColgp_Array1OfPnt
        from OCP.collections import Array1_int as TColStd_Array1OfInteger
    except ImportError:     # OCP anterior
        from OCP.TColgp import TColgp_Array1OfPnt
        from OCP.TColStd import TColStd_Array1OfInteger, TColStd_Array1OfReal

    p = c.grado
    if not (c.nudos[0] == c.nudos[p] and c.nudos[-1] == c.nudos[-1 - p]):
        c = c.tramo(*c.dominio)
    polos = TColgp_Array1OfPnt(1, len(c.control))
    for i, q in enumerate(c.control, 1):
        polos.SetValue(i, gp_Pnt(q[0], q[1], 0.0))
    distintos, mult = [], []
    for k in c.nudos:
        if distintos and abs(k - distintos[-1]) < 1e-15:
            mult[-1] += 1
        else:
            distintos.append(k)
            mult.append(1)
    nudos = TColStd_Array1OfReal(1, len(distintos))
    mults = TColStd_Array1OfInteger(1, len(mult))
    for i, (k, m) in enumerate(zip(distintos, mult), 1):
        nudos.SetValue(i, k)
        mults.SetValue(i, m)
    if c.pesos is not None:
        pesos = TColStd_Array1OfReal(1, len(c.pesos))
        for i, w in enumerate(c.pesos, 1):
            pesos.SetValue(i, w)
        curva = Geom_BSplineCurve(polos, pesos, nudos, mults, p, False)
    else:
        curva = Geom_BSplineCurve(polos, nudos, mults, p, False)
    return Edge(BRepBuilderAPI_MakeEdge(curva).Edge())


def cara_de(e):
    """La cara plana que encierra una entidad cerrada, o ValueError."""
    from build123d import Edge, Face, Plane, Wire

    from .solido import boceto

    t = e.tipo
    if t == "polilinea":
        if not e.cerrada or len(e.puntos) < 3:
            raise NoSeCombina("Sólo se combinan contornos cerrados: esa polilínea está abierta.")
        aristas = boceto.aristas_de(e.a_dict())
    elif t == "circulo":
        aristas = boceto.aristas_de(e.a_dict())
    elif t == "elipse":
        if ((e.param_fin - e.param_ini) % (2 * math.pi)) > 1e-9:
            raise NoSeCombina("Sólo se combinan elipses completas, no arcos de elipse.")
        a = math.hypot(*e.eje_mayor)
        plano = Plane(origin=(e.centro[0], e.centro[1], 0),
                      x_dir=(e.eje_mayor[0] / a, e.eje_mayor[1] / a, 0), z_dir=(0, 0, 1))
        aristas = [Edge.make_ellipse(a, a * e.razon, plano)]
    elif t == "spline":
        if not e.cerrada:
            raise NoSeCombina("Sólo se combinan contornos cerrados: esa spline está abierta.")
        aristas = [_edge_bspline(e.curva())]
    else:
        raise NoSeCombina(f"Se combinan polilíneas cerradas, círculos, elipses y splines cerradas; no {t}.")
    return Face(Wire(aristas))


# --- Del kernel al dibujo -----------------------------------------------------

def _piezas_de_wire(wire) -> list[dict]:
    """Las aristas del borde, en orden de recorrido, como piezas sencillas:
    {"t": "recta"|"arco", "p0", "p1", "bulge"} o {"t": "spline", "curva"} o
    {"t": "elipse", ...} o {"t": "circulo", ...}."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.GeomAbs import GeomAbs_BSplineCurve, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_Line
    from OCP.TopAbs import TopAbs_REVERSED

    piezas = []
    ex = BRepTools_WireExplorer(wire.wrapped)
    while ex.More():
        arista = ex.Current()
        ad = BRepAdaptor_Curve(arista)
        u0, u1 = ad.FirstParameter(), ad.LastParameter()
        rev = arista.Orientation() == TopAbs_REVERSED
        a, b = ad.Value(u0), ad.Value(u1)
        p0, p1 = ([a.X(), a.Y()], [b.X(), b.Y()]) if not rev else ([b.X(), b.Y()], [a.X(), a.Y()])
        tipo = ad.GetType()
        if tipo == GeomAbs_Line:
            piezas.append({"t": "recta", "p0": p0, "p1": p1, "bulge": 0.0})
        elif tipo == GeomAbs_Circle:
            circ = ad.Circle()
            barrido = u1 - u0
            if barrido >= 2 * math.pi - 1e-9:
                c = circ.Location()
                piezas.append({"t": "circulo", "centro": [c.X(), c.Y()], "radio": circ.Radius()})
            else:
                antihorario = (circ.Axis().Direction().Z() > 0) != rev
                b = math.tan(barrido / 4) * (1 if antihorario else -1)
                piezas.append({"t": "arco", "p0": p0, "p1": p1, "bulge": b})
        elif tipo == GeomAbs_Ellipse:
            el = ad.Ellipse()
            c, xd = el.Location(), el.XAxis().Direction()
            sentido = 1 if el.Axis().Direction().Z() > 0 else -1
            mayor = [xd.X() * el.MajorRadius(), xd.Y() * el.MajorRadius()]
            # Nuestra elipse: c + U cos t + V sin t, con V = U girado 90° × razón.
            # Si el eje de OpenCASCADE apunta abajo, su t corre al revés.
            # (El sentido de recorrido no cambia los puntos de un arco de elipse.)
            t0, t1 = (u0, u1) if sentido > 0 else (-u1, -u0)
            piezas.append({"t": "elipse", "centro": [c.X(), c.Y()], "eje_mayor": mayor,
                           "razon": el.MinorRadius() / el.MajorRadius(),
                           "param_ini": t0, "param_fin": t1,
                           "completa": (u1 - u0) >= 2 * math.pi - 1e-9})
        elif tipo == GeomAbs_BSplineCurve:
            bs = ad.BSpline()
            n = bs.NbPoles()
            control = [[bs.Pole(i).X(), bs.Pole(i).Y()] for i in range(1, n + 1)]
            nudos = []
            for i in range(1, bs.NbKnots() + 1):
                nudos += [bs.Knot(i)] * bs.Multiplicity(i)
            pesos = [bs.Weight(i) for i in range(1, n + 1)] if bs.IsRational() else None
            if bs.IsPeriodic():
                raise NoSeCombina("El resultado trae una curva periódica que todavía no sé convertir.")
            c = mod_nurbs.Nurbs(bs.Degree(), control, nudos, pesos)
            da, db = c.dominio
            if u0 > da + 1e-12 or u1 < db - 1e-12:
                c = c.tramo(u0, u1)
            if rev:
                c = c.invertida()
            piezas.append({"t": "spline", "curva": c})
        else:
            raise NoSeCombina("El resultado trae una curva de un tipo que todavía no sé convertir.")
        ex.Next()
    return piezas


def _a_entidades(piezas: list[dict], base: dict) -> list[dict]:
    """Las piezas de un borde cerrado como entidades del dibujo (dicts)."""
    if len(piezas) == 1 and piezas[0]["t"] == "circulo":
        p = piezas[0]
        return [dict(base, tipo="circulo", centro=p["centro"], radio=p["radio"])]
    if len(piezas) == 1 and piezas[0]["t"] == "elipse" and piezas[0]["completa"]:
        p = piezas[0]
        return [dict(base, tipo="elipse", centro=p["centro"], eje_mayor=p["eje_mayor"], razon=p["razon"],
                     param_ini=0.0, param_fin=2 * math.pi)]
    if len(piezas) == 1 and piezas[0]["t"] == "spline":
        c = piezas[0]["curva"]
        return [dict(base, tipo="spline", puntos_control=[q[:2] for q in c.control],
                     nudos=[k - c.nudos[0] for k in c.nudos],
                     pesos=list(c.pesos) if c.pesos is not None else [], grado=c.grado,
                     puntos_ajuste=[], cerrada=False)]
    if all(p["t"] in ("recta", "arco") for p in piezas):
        puntos = [[p["p0"][0], p["p0"][1], p["bulge"]] if abs(p["bulge"]) > 1e-12 else [p["p0"][0], p["p0"][1]]
                  for p in piezas]
        return [dict(base, tipo="polilinea", puntos=puntos, cerrada=True)]
    # Mezcla: tramos de rectas y arcos como polilíneas abiertas, y cada curva
    # libre como su propia entidad, en el orden del borde. El borde se recorre
    # empezando por una curva libre: si no, el tramo de rectas donde
    # OpenCASCADE empezó a recorrerlo saldría partido en dos polilíneas.
    k = next(i for i, p in enumerate(piezas) if p["t"] not in ("recta", "arco"))
    piezas = piezas[k:] + piezas[:k]
    salida = []
    tramo = []

    def cerrar_tramo():
        if tramo:
            pts = [[p["p0"][0], p["p0"][1], p["bulge"]] if abs(p["bulge"]) > 1e-12 else [p["p0"][0], p["p0"][1]]
                   for p in tramo]
            pts.append([tramo[-1]["p1"][0], tramo[-1]["p1"][1]])
            salida.append(dict(base, tipo="polilinea", puntos=pts, cerrada=False))
            tramo.clear()

    for p in piezas:
        if p["t"] in ("recta", "arco"):
            tramo.append(p)
            continue
        cerrar_tramo()
        if p["t"] == "spline":
            c = p["curva"]
            salida.append(dict(base, tipo="spline", puntos_control=[q[:2] for q in c.control],
                               nudos=[k - c.nudos[0] for k in c.nudos],
                               pesos=list(c.pesos) if c.pesos is not None else [], grado=c.grado,
                               puntos_ajuste=[], cerrada=False))
        elif p["t"] == "elipse":
            salida.append(dict(base, tipo="elipse", centro=p["centro"], eje_mayor=p["eje_mayor"],
                               razon=p["razon"], param_ini=p["param_ini"], param_fin=p["param_fin"]))
        else:
            raise NoSeCombina("El resultado trae una pieza que todavía no sé convertir.")
    cerrar_tramo()
    return salida


def cara_de_contorno(entidades: list[dict]):
    """La cara que encierra un contorno de **varias** piezas que se siguen
    (polilíneas abiertas, splines, arcos de elipse), como las que deja una
    booleana con curvas libres. Las puntas se sueldan a la tolerancia."""
    from build123d import Edge, Face, Plane, Wire

    from .solido import boceto

    aristas = []
    for d in boceto.soldadas(entidades):
        t = d.get("tipo")
        if t in ("linea", "arco", "arco3", "polilinea", "circulo"):
            aristas += boceto.aristas_de(d)
        elif t == "spline":
            aristas.append(_edge_bspline(ent_mod.de_dict(d).curva()))
        elif t == "elipse":
            a = math.hypot(*d["eje_mayor"])
            plano = Plane(origin=(d["centro"][0], d["centro"][1], 0),
                          x_dir=(d["eje_mayor"][0] / a, d["eje_mayor"][1] / a, 0), z_dir=(0, 0, 1))
            if (d["param_fin"] - d["param_ini"]) % (2 * math.pi) < 1e-9:
                aristas.append(Edge.make_ellipse(a, a * d["razon"], plano))
            else:
                aristas.append(Edge.make_ellipse(a, a * d["razon"], plano,
                                                 math.degrees(d["param_ini"]), math.degrees(d["param_fin"])))
        else:
            raise NoSeCombina(f"Un contorno no puede llevar un {t}.")
    return Face(Wire(aristas))


# Gauss-Legendre de 16 nodos en [-1, 1]: exacta para polinomios de grado 31,
# y en un arco de hasta 22.5° deja el error por debajo de 1e-15 relativo.
_GL = None


def _gauss():
    global _GL
    if _GL is None:
        import numpy as np
        _GL = np.polynomial.legendre.leggauss(16)
    return _GL


def _integral(f, a: float, b: float, partes: int) -> float:
    """½∫(x y' - y x') dt de una curva f(t) → (punto, derivada), en [a, b]
    partido en `partes` tramos iguales."""
    nodos, pesos = _gauss()
    total = 0.0
    h = (b - a) / partes
    for k in range(partes):
        t0 = a + k * h
        for x, w in zip(nodos, pesos):
            (px, py), (dx, dy) = f(t0 + (x + 1) * h / 2)
            total += w * (px * dy - py * dx) * h / 2
    return total / 2


def _pieza(d: dict):
    """(inicio, fin, ½∮ x dy − y dx) de una pieza de contorno, en su sentido."""
    t = d.get("tipo")
    if t == "polilinea":
        pts = d["puntos"]
        n = len(pts)
        tramos = n if d.get("cerrada") else n - 1
        total = 0.0
        for i in range(tramos):
            p1, p2 = pts[i], pts[(i + 1) % n]
            b = p1[2] if len(p1) > 2 else 0.0
            total += (p1[0] * p2[1] - p2[0] * p1[1]) / 2
            if abs(b) > 1e-12:
                # Lo que el arco agrega o quita a la cuerda (Green sobre el
                # arco menos la cuerda): r²/2 · (θ - sin θ), θ con signo.
                ang = 4 * math.atan(b)
                cuerda = math.dist(p1[:2], p2[:2])
                r = cuerda / (2 * math.sin(abs(ang) / 2))
                total += r * r / 2 * (ang - math.sin(ang))
        fin = pts[0] if d.get("cerrada") else pts[-1]
        return pts[0][:2], fin[:2], total
    if t == "circulo":
        c, r = d["centro"], d["radio"]
        p = [c[0] + r, c[1]]
        return p, p, math.pi * r * r
    if t == "elipse":
        c, (ax, ay), k = d["centro"], d["eje_mayor"], d["razon"]
        bx, by = -ay * k, ax * k
        t0, t1 = d["param_ini"], d["param_fin"]
        if (t1 - t0) % (2 * math.pi) < 1e-9:
            t1 = t0 + 2 * math.pi
        while t1 <= t0:
            t1 += 2 * math.pi
        f = lambda t: ([c[0] + ax * math.cos(t) + bx * math.sin(t), c[1] + ay * math.cos(t) + by * math.sin(t)],
                       [-ax * math.sin(t) + bx * math.cos(t), -ay * math.sin(t) + by * math.cos(t)])
        I = _integral(f, t0, t1, max(1, math.ceil((t1 - t0) / (math.pi / 8))))
        return f(t0)[0], f(t1)[0], I
    if t == "spline":
        cur = ent_mod.de_dict(d).curva()
        f = lambda t: cur.derivadas(t)[:2]
        I = 0.0
        nd = cur.nudos_distintos()
        for a, b in zip(nd, nd[1:]):
            I += _integral(f, a, b, 1 if cur.pesos is None else 4)
        a, b = cur.dominio
        return cur.punto(a), cur.punto(b), I
    raise NoSeCombina(f"Un contorno no puede llevar un {t}.")


def area_de_contorno(entidades: list[dict]) -> float:
    """El área que encierra un contorno de una o varias piezas, exacta: Green
    (½∮ x dy − y dx) integrado sobre la curva misma. No se le pide al kernel:
    con una cara de B-spline, OpenCASCADE da el área con errores de unidades
    (la misma curva, 28 803.8 o 28 807.8 según cómo se le pase). Las piezas se
    encadenan por sus puntas: la que va al revés cuenta con el signo cambiado."""
    total = 0.0
    fin_anterior = None
    for d in entidades:
        p0, p1, I = _pieza(d)
        if fin_anterior is not None and math.dist(fin_anterior, p1) < math.dist(fin_anterior, p0):
            p0, p1, I = p1, p0, -I
        total += I
        fin_anterior = p1
    return abs(total)


# --- La operación -------------------------------------------------------------

def combinar(doc, ids: list[str], operacion: str) -> dict:
    """El plan: {"borrar": ids, "contornos": [[entidades de un borde], …]}.

    `resta`: la primera entidad menos las demás. `union` e `interseccion`: de
    todas. No toca el documento: quien llama aplica el plan en una
    transacción y agrupa los bordes de varias piezas.
    """
    if operacion not in OPERACIONES:
        raise ValueError(f"operación desconocida: {operacion}")
    ents = [doc.entidades[i] for i in ids if i in doc.entidades]
    if len(ents) < 2:
        raise NoSeCombina("Hacen falta al menos dos contornos cerrados.")
    caras = [cara_de(e) for e in ents]
    resultado = caras[0]
    for otra in caras[1:]:
        if operacion == "union":
            resultado = resultado.fuse(otra)
        elif operacion == "resta":
            resultado = resultado.cut(otra)
        else:
            resultado = resultado.intersect(otra)
    caras_res = [f for f in resultado.faces() if f.area > 1e-12] if resultado is not None else []
    if not caras_res:
        raise NoSeCombina("El resultado queda vacío: los contornos no se tocan." if operacion == "interseccion"
                          else "El resultado queda vacío.")
    e0 = ents[0]
    base = {"capa": e0.capa, "color": e0.color, "grosor": e0.grosor, "tipo_linea": e0.tipo_linea,
            "espacio": e0.espacio, "plano": getattr(e0, "plano", "XY")}
    contornos = []
    area = 0.0
    for f in caras_res:
        bordes = [_a_entidades(_piezas_de_wire(w), base) for w in [f.outer_wire()] + list(f.inner_wires())]
        area += area_de_contorno(bordes[0]) - sum(area_de_contorno(h) for h in bordes[1:])
        contornos += bordes
    return {"borrar": [e.id for e in ents], "contornos": contornos, "area": area,
            "piezas": len(caras_res)}
