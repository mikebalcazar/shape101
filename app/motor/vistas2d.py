"""Del sólido a vistas 2D de draw101 con líneas ocultas  ·  P5.

Planta, alzado, lateral y un corte por un plano, con HLR (el algoritmo de
líneas ocultas de OpenCascade, el mismo que usa build123d para exportar SVG:
el patrón es el de `build123d/exporters.py`). Cada vista se escribe como
entidades de draw101 —líneas, arcos, círculos; lo que no es ninguno, como
polilínea muestreada— en un documento `.t101d`: las visibles en la capa «0» y
las ocultas en «T101-OCULTO», que draw101 trae en su catálogo con tipo de
línea HIDDEN (discontinua).
"""
from __future__ import annotations

import math

from build123d import Compound, Edge, Plane, Shape, Vector, section
from OCP.BRepLib import BRepLib
from OCP.gp import gp_Ax2
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

from app.motor import draw101_lector as d1

CAPA_VISIBLES = "0"
CAPA_OCULTAS = "T101-OCULTO"

# nombre → (desde dónde se mira, qué es «arriba» en el papel)
VISTAS = {
    "planta": ((0, 0, 1), (0, 1, 0)),
    "alzado": ((0, -1, 0), (0, 0, 1)),
    "lateral": ((1, 0, 0), (0, 0, 1)),
}


def proyectar(forma: Shape, desde, arriba, con_ocultas=True) -> tuple[list[Edge], list[Edge], Plane]:
    """Aristas visibles y ocultas de la forma vista desde `desde`, ya
    expresadas en el plano de la vista (2D: z = 0)."""
    hlr = HLRBRep_Algo()
    hlr.Add(forma.wrapped)
    origen = forma.center()
    dir_ = Vector(desde).normalized()
    eje_x = Vector(arriba).normalized().cross(dir_)
    sistema = gp_Ax2(origen.to_pnt(), dir_.to_dir(), eje_x.to_dir())
    hlr.Projector(HLRAlgo_Projector(sistema))
    hlr.Update()
    hlr.Hide()
    a = HLRBRep_HLRToShape(hlr)
    vis = [c for c in (a.VCompound(), a.Rg1LineVCompound(), a.OutLineVCompound()) if not c.IsNull()]
    ocu = [c for c in ((a.HCompound(), a.OutLineHCompound()) if con_ocultas else ()) if not c.IsNull()]
    for c in vis + ocu:
        BRepLib.BuildCurves3d_s(c, 1e-6)
    plano = Plane(origin=origen, x_dir=eje_x, z_dir=dir_)
    # las aristas salen en 3D sobre el plano de proyección: se pasan a coordenadas del plano
    # HLRBRep_HLRToShape ya devuelve las aristas en el sistema del proyector
    # (x, y del papel; z = 0): no hay que volver a transformarlas.
    visibles = [e for c in vis for e in Compound(c).edges()]
    ocultas = [e for c in ocu for e in Compound(c).edges()]
    return visibles, ocultas, plano


def cortar(forma: Shape, plano: Plane) -> list[Edge]:
    """El contorno del corte por `plano`, en coordenadas del plano."""
    cara = section(forma, plano)
    return [plano.to_local_coords(e) for e in cara.edges()]


def entidad_de(arista: Edge, capa: str, ent):
    """Una arista 2D (z = 0) → la entidad de draw101 que le corresponde."""
    tipo = arista.geom_type.name
    a, b = arista.start_point(), arista.end_point()
    if tipo == "LINE":
        return ent.Linea(p1=[a.X, a.Y], p2=[b.X, b.Y], capa=capa)
    if tipo == "CIRCLE":
        c = arista.arc_center
        r = arista.radius
        if (a - b).length < 1e-7:
            return ent.Circulo(centro=[c.X, c.Y], radio=r, capa=capa)
        a0 = math.degrees(math.atan2(a.Y - c.Y, a.X - c.X)) % 360
        a1 = math.degrees(math.atan2(b.Y - c.Y, b.X - c.X)) % 360
        # draw101 dibuja los arcos antihorarios: si la arista va al revés, se invierte
        m = arista.position_at(0.5)
        am = math.degrees(math.atan2(m.Y - c.Y, m.X - c.X)) % 360
        if (am - a0) % 360 > (a1 - a0) % 360:
            a0, a1 = a1, a0
        return ent.Arco(centro=[c.X, c.Y], radio=r, ang_ini=a0, ang_fin=a1, capa=capa)
    # El HLR devuelve las curvas proyectadas como BSplines aunque sean arcos
    # exactos: se muestrea la arista y, si todos los puntos equidistan de un
    # centro, es un arco (o un círculo) y se escribe como tal.
    n = 32
    pts = [(p.X, p.Y) for p in (arista.position_at(k / n) for k in range(n + 1))]
    # Un círculo visto de canto se proyecta como una recta, y el HLR la
    # devuelve como BSpline: si todos los puntos están sobre la recta que une
    # los extremos, es una línea.
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    largo = math.hypot(x2 - x1, y2 - y1)
    if largo > 1e-9 and all(abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) / largo < 1e-4 for x, y in pts):
        return ent.Linea(p1=[x1, y1], p2=[x2, y2], capa=capa)
    arco = _ajustar_arco(pts)
    if arco is not None:
        cx, cy, rad = arco
        if math.dist(pts[0], pts[-1]) < 1e-6:
            return ent.Circulo(centro=[cx, cy], radio=rad, capa=capa)
        a0 = math.degrees(math.atan2(pts[0][1] - cy, pts[0][0] - cx)) % 360
        a1 = math.degrees(math.atan2(pts[-1][1] - cy, pts[-1][0] - cx)) % 360
        am = math.degrees(math.atan2(pts[n // 2][1] - cy, pts[n // 2][0] - cx)) % 360
        if (am - a0) % 360 > (a1 - a0) % 360:
            a0, a1 = a1, a0
        return ent.Arco(centro=[cx, cy], radio=rad, ang_ini=a0, ang_fin=a1, capa=capa)
    return ent.Polilinea(puntos=[[x, y, 0.0] for x, y in pts], cerrada=False, capa=capa)


def _ajustar_arco(pts, tol=1e-4):
    """Centro y radio del círculo por el primer, el medio y el último punto,
    si TODOS los puntos caen sobre él (a menos de `tol`); si no, None."""
    (x1, y1), (x2, y2), (x3, y3) = pts[0], pts[len(pts) // 2], pts[-1]
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    if r < 1e-6 or any(abs(math.hypot(x - ux, y - uy) - r) > tol for x, y in pts):
        return None
    return ux, uy, r


def documento_de_vistas(forma: Shape, corte: Plane | None = None, separacion: float = 200.0):
    """Un .t101d con planta, alzado, lateral (y el corte), una junto a otra."""
    ent = d1.entidades()
    capas = _capas()
    doc = d1.nuevo_documento()
    capas.asegurar(doc, CAPA_OCULTAS)
    x = 0.0
    resumen = {}
    for nombre, (desde, arriba) in VISTAS.items():
        vis, ocu, _ = proyectar(forma, desde, arriba)
        caja = _caja(vis + ocu)
        dx, dy = x - caja[0], -caja[1]
        for e in vis:
            doc.agregar(_mover(entidad_de(e, CAPA_VISIBLES, ent), dx, dy))
        for e in ocu:
            doc.agregar(_mover(entidad_de(e, CAPA_OCULTAS, ent), dx, dy))
        resumen[nombre] = {"visibles": len(vis), "ocultas": len(ocu), "origen": [dx, dy], "caja": caja}
        x += (caja[2] - caja[0]) + separacion
    if corte is not None:
        aristas = cortar(forma, corte)
        caja = _caja(aristas)
        dx, dy = x - caja[0], -caja[1]
        for e in aristas:
            doc.agregar(_mover(entidad_de(e, CAPA_VISIBLES, ent), dx, dy))
        resumen["corte"] = {"visibles": len(aristas), "ocultas": 0, "origen": [dx, dy], "caja": caja}
    return doc, resumen


def _capas():
    import importlib
    d1._cargar()
    return importlib.import_module("core.capas")


def _caja(aristas):
    xs, ys = [], []
    for e in aristas:
        bb = e.bounding_box()
        xs += [bb.min.X, bb.max.X]
        ys += [bb.min.Y, bb.max.Y]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def _mover(e, dx, dy):
    t = e.tipo
    if t == "linea":
        e.p1 = [e.p1[0] + dx, e.p1[1] + dy]
        e.p2 = [e.p2[0] + dx, e.p2[1] + dy]
    elif t in ("circulo", "arco"):
        e.centro = [e.centro[0] + dx, e.centro[1] + dy]
    elif t == "polilinea":
        e.puntos = [[p[0] + dx, p[1] + dy, p[2] if len(p) > 2 else 0.0] for p in e.puntos]
    return e
