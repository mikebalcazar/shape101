"""t053 · Superficies libres: LOFT, REVOLVER y BARRER con curvas abiertas, y RED.

Hasta la fase D1 todo lo que salía del 3D era un sólido cerrado: una curva
abierta no servía. Ahora, como en Rhino (core/solido/superficies.py):

- LOFT con secciones abiertas tiende una piel;
- REVOLVER con un perfil abierto deja una superficie de revolución;
- BARRER con un perfil abierto deja una superficie;
- RED cierra con un parche el borde de varias curvas que se tocan.

Se mide con lo que tiene fórmula —un segmento que gira es un cilindro (2πrh),
un semicírculo barrido en recta es medio cilindro (πrL), cuatro líneas en
cuadro son un cuadrado— y con que las curvas de las que sale la superficie
queden **sobre** ella. Ninguna tiene volumen, y el aviso lo sabe.
"""

from __future__ import annotations

import math

from fastapi import HTTPException

from core import entidades as E
from core import tolerancia
from core.documento import Documento
from core.solido import cuerpo as mod
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "superficies libres: loft, revolver y barrer abiertos, y red de curvas"


def _doc():
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    tolerancia.enchufar(lambda: doc)
    mod.olvidar()
    return doc


def _agregar(doc, *ents):
    with doc.transaccion("Dibujar"):
        return [doc.agregar(e).id for e in ents]


def _forma(doc, malla):
    return mod.regenerar(doc.entidades[malla["id"]]).solido


def _distancia(forma, p) -> float:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
    return BRepExtrema_DistShapeShape(v, forma.wrapped).Value()


def correr(r: comun.Reporte) -> None:
    previo = tolerancia._doc_actual
    try:
        _loft(r)
        _revolver(r)
        _barrer(r)
        _red(r)
    finally:
        tolerancia.enchufar(previo)
        mod.olvidar()


def _loft(r: comun.Reporte) -> None:
    doc = _doc()
    secciones = [E.Spline(puntos_ajuste=[[0, 0], [100, 40 * k + 10], [200, 0]]) for k in range(3)]
    ids = _agregar(doc, *secciones)
    m = rutas.loft(rutas.Seleccion(ids=ids, separacion=50))
    r.cierto(m["es_superficie"] and m["volumen_mm3"] == 0, "LOFT con secciones abiertas tiende una superficie (sin volumen)")
    forma = _forma(doc, m)
    peor = 0.0
    for k, sp in enumerate(secciones):
        c = sp.curva()
        a, b = c.dominio
        for i in range(9):
            x, y = c.punto(a + (b - a) * i / 8)
            peor = max(peor, _distancia(forma, (x, y, 50.0 * k)))
    r.cierto(peor < 1e-6, "y pasa exacta por las tres secciones, cada una a su altura", f"{peor:.2e}")
    try:
        rutas.loft(rutas.Seleccion(ids=ids))
        r.cierto(False, "secciones abiertas en la misma ventana y sin separación deberían avisar")
    except HTTPException as exc:
        r.cierto("separación" in exc.detail, "sin separación, en la misma ventana, avisa", exc.detail)


def _revolver(r: comun.Reporte) -> None:
    doc = _doc()
    ids = _agregar(doc, E.Linea(p1=[50, 0], p2=[50, 100]), E.Linea(p1=[0, -10], p2=[0, 200]))
    m = rutas.revolver(rutas.Seleccion(ids=ids))
    r.cierto(m["es_superficie"], "REVOLVER con un perfil abierto deja una superficie")
    r.casi(m["area_mm2"], 2 * math.pi * 50 * 100, "un segmento a 50 del eje, de 100 de alto, da el cilindro de 2πrh", 0.5)
    ids = _agregar(doc, E.Spline(puntos_ajuste=[[50, 0], [80, 60], [40, 120]]), E.Linea(p1=[0, 0], p2=[0, 150]))
    m = rutas.revolver(rutas.Seleccion(ids=ids))
    r.cierto(m["es_superficie"] and m["area_mm2"] > 0, "y con una spline abierta de perfil, también")


def _barrer(r: comun.Reporte) -> None:
    doc = _doc()
    perfil = E.Arco(centro=[0, 0], radio=20, ang_ini=0, ang_fin=180)
    perfil.plano = "XZ"
    ids = _agregar(doc, perfil, E.Linea(p1=[0, 0], p2=[0, 200]))
    m = rutas.barrer(rutas.Seleccion(ids=ids))
    r.cierto(m["es_superficie"], "BARRER con un perfil abierto deja una superficie")
    r.casi(m["area_mm2"], math.pi * 20 * 200, "un semicírculo de r 20 barrido 200 en recta es medio cilindro (πrL)", 0.5)


def _red(r: comun.Reporte) -> None:
    doc = _doc()
    cuadro = [E.Linea(p1=[0, 0], p2=[200, 0]), E.Linea(p1=[200, 0], p2=[200, 200]),
              E.Linea(p1=[200, 200], p2=[0, 200]), E.Linea(p1=[0, 200], p2=[0, 0])]
    m = rutas.red(rutas.Seleccion(ids=_agregar(doc, *cuadro)))
    r.cierto(m["es_superficie"], "RED cierra con un parche el borde de cuatro curvas")
    r.casi(m["area_mm2"], 40000, "cuatro líneas en cuadro de 200 dan un parche de 40 000", 0.5)

    bordes = [E.Linea(p1=[0, 0], p2=[200, 0]),
              E.Spline(puntos_ajuste=[[200, 0], [230, 100], [200, 200]]),
              E.Linea(p1=[200, 200], p2=[0, 200]),
              E.Spline(puntos_ajuste=[[0, 200], [-30, 100], [0, 0]])]
    m = rutas.red(rutas.Seleccion(ids=_agregar(doc, *bordes)))
    forma = _forma(doc, m)
    peor = 0.0
    for e in bordes:
        if e.tipo == "linea":
            pts = [[e.p1[0] + (e.p2[0] - e.p1[0]) * i / 8, e.p1[1] + (e.p2[1] - e.p1[1]) * i / 8] for i in range(9)]
        else:
            c = e.curva()
            a, b = c.dominio
            pts = [c.punto(a + (b - a) * i / 8) for i in range(9)]
        peor = max(peor, max(_distancia(forma, (x, y, 0.0)) for x, y in pts))
    r.cierto(peor < 1e-3, "con splines de borde, el parche pasa por sus cuatro curvas", f"{peor:.2e}")

    abierto = [E.Linea(p1=[0, 0], p2=[200, 0]), E.Linea(p1=[200, 0], p2=[200, 200]),
               E.Linea(p1=[200, 200], p2=[0, 200])]
    try:
        rutas.red(rutas.Seleccion(ids=_agregar(doc, *abierto)))
        r.cierto(False, "tres lados de un cuadro no cierran un borde: debería avisar")
    except HTTPException as exc:
        r.cierto("borde" in exc.detail, "tres lados que no cierran avisan", exc.detail)
