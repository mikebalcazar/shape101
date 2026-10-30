"""De un boceto del dibujo (entidades 2D) a un sólido de build123d.

Qué se acepta: líneas, arcos, círculos y polilíneas (cerradas o no, con
bulges). Las cotas, textos y demás se ignoran: no son geometría. Las puntas
sueltas se sueldan a la tolerancia del documento antes de coser (`soldadas`).

Cómo se arma: cada entidad da uno o varios `Edge`; `Wire.combine` los cose por
extremos en contornos cerrados; el contorno de mayor área es el exterior y los
demás son huecos; con eso se hace **una cara** y se extruye. Un boceto con dos
contornos exteriores separados todavía no se contempla (quedaría para la app,
no para la medición).

Bulge: convención DXF. `b = tan(θ/4)`; positivo = antihorario del vértice al
siguiente. El punto medio del arco queda a `s = b·d/2` del punto medio de la
cuerda, hacia la derecha de la dirección de la cuerda cuando b > 0.
"""
from __future__ import annotations

import math

from build123d import (Edge, Face, Plane, Vector, Wire, extrude)


def _arco_tres_puntos(p1, p2, bulge: float) -> Edge:
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    d = math.hypot(dx, dy)
    if d < 1e-12:
        raise ValueError("un tramo de polilínea con bulge y largo cero")
    s = bulge * d / 2.0
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    # perpendicular a la derecha de la dirección de la cuerda
    px, py = dy / d, -dx / d
    medio = (mx + px * s, my + py * s)
    return Edge.make_three_point_arc(Vector(p1[0], p1[1], 0), Vector(*medio, 0), Vector(p2[0], p2[1], 0))


def aristas_de(entidad: dict) -> list[Edge]:
    t = entidad.get("tipo")
    if t == "arco3":
        # Un arco ya soldado (ver `soldadas`): por sus dos extremos y un punto
        # de en medio, que es como OpenCASCADE lo arma sin redondear nada.
        a, m, b = entidad["p1"], entidad["pm"], entidad["p2"]
        return [Edge.make_three_point_arc(Vector(a[0], a[1], 0), Vector(m[0], m[1], 0),
                                          Vector(b[0], b[1], 0))]
    if t == "linea":
        a, b = entidad["p1"], entidad["p2"]
        return [Edge.make_line(Vector(a[0], a[1], 0), Vector(b[0], b[1], 0))]
    if t == "circulo":
        c, r = entidad["centro"], entidad["radio"]
        return [Edge.make_circle(r, Plane(origin=(c[0], c[1], 0)))]
    if t == "arco":
        c, r = entidad["centro"], entidad["radio"]
        a0, a1 = entidad["ang_ini"], entidad["ang_fin"]
        if a1 <= a0:
            a1 += 360.0
        return [Edge.make_circle(r, Plane(origin=(c[0], c[1], 0)), start_angle=a0, end_angle=a1)]
    if t == "polilinea":
        pts = entidad["puntos"]
        n = len(pts)
        tramos = n - 1 + (1 if entidad.get("cerrada") else 0)
        out = []
        for i in range(tramos):
            p1, p2 = pts[i], pts[(i + 1) % n]
            b = p1[2] if len(p1) > 2 else 0.0
            if abs(b) > 1e-12:
                out.append(_arco_tres_puntos(p1, p2, b))
            else:
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > 1e-12:
                    out.append(Edge.make_line(Vector(p1[0], p1[1], 0), Vector(p2[0], p2[1], 0)))
        return out
    return []        # cotas, textos, bloques…: no son geometría del boceto


def _extremos_de_arco(e: dict):
    c, r = e["centro"], e["radio"]
    a0, a1 = math.radians(e["ang_ini"]), math.radians(e["ang_fin"])
    if a1 <= a0:
        a1 += 2 * math.pi
    p = lambda a: [c[0] + r * math.cos(a), c[1] + r * math.sin(a)]
    return p(a0), p((a0 + a1) / 2), p(a1)


def soldadas(entidades: list[dict], tol: float | None = None) -> list[dict]:
    """Las mismas entidades con sus extremos sueltos soldados a la tolerancia.

    OpenCASCADE cose un contorno sólo si los extremos coinciden a unas micras.
    Un plano de AutoCAD o de Revit trae huecos de centésimas: UNIR los pasaba
    por alto (0.05 mm) y aquí el mismo contorno «no cerraba». Ahora los dos
    usan la tolerancia del documento (core/tolerancia.py), como en Rhino.

    Sólo se tocan las puntas sueltas —de líneas, arcos y polilíneas abiertas—;
    un círculo o una polilínea cerrada ya cierran solos. Una punta se mueve
    como mucho `tol`.
    """
    from core import tolerancia

    if tol is None:
        tol = tolerancia.kernel_mm()
    puntas = []          # (índice de entidad, cuál, punto)
    for i, e in enumerate(entidades):
        t = e.get("tipo")
        if t == "linea":
            puntas += [(i, "p1", e["p1"]), (i, "p2", e["p2"])]
        elif t == "arco":
            a, _, b = _extremos_de_arco(e)
            puntas += [(i, "a", a), (i, "b", b)]
        elif t == "polilinea" and not e.get("cerrada") and len(e.get("puntos") or []) >= 2:
            puntas += [(i, "ini", e["puntos"][0]), (i, "fin", e["puntos"][-1])]
    if not puntas:
        return entidades
    reps = tolerancia.soldar([p for _, _, p in puntas], tol)
    salida = [dict(e) for e in entidades]
    for (i, cual, _), rep in zip(puntas, reps):
        e = salida[i]
        if cual in ("p1", "p2"):
            e[cual] = [rep[0], rep[1]]
        elif cual in ("a", "b"):
            if e.get("tipo") == "arco":
                a, m, b = _extremos_de_arco(entidades[i])
                salida[i] = e = {"tipo": "arco3", "p1": a, "pm": m, "p2": b}
            e["p1" if cual == "a" else "p2"] = [rep[0], rep[1]]
        else:
            pts = [list(v) for v in e["puntos"]]
            k = 0 if cual == "ini" else len(pts) - 1
            pts[k] = [rep[0], rep[1]] + pts[k][2:]
            e["puntos"] = pts
    return salida


def cara_de(entidades: list[dict], tol: float | None = None) -> Face:
    entidades = soldadas(entidades, tol)
    aristas = [a for e in entidades for a in aristas_de(e)]
    if not aristas:
        raise ValueError("el boceto no trae geometría")
    contornos = Wire.combine(aristas)
    cerrados = [w for w in contornos if w.is_closed]
    if not cerrados:
        raise ValueError("el boceto no forma ningún contorno cerrado")
    caras = sorted((Face(w) for w in cerrados), key=lambda f: f.area, reverse=True)
    exterior, huecos = caras[0], caras[1:]
    return Face(exterior.outer_wire(), [h.outer_wire() for h in huecos])


def solido_de(entidades: list[dict], espesor: float):
    return extrude(cara_de(entidades), amount=espesor)
