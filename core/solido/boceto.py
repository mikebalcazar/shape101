"""De un boceto del dibujo (entidades 2D) a un sólido de build123d.

Qué se acepta: líneas, arcos, círculos y polilíneas (cerradas o no, con
bulges). Las cotas, textos y demás se ignoran: no son geometría.

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


def cara_de(entidades: list[dict]) -> Face:
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
