"""t051 · Bocetos 3D con varios contornos, huecos e islas, y con curvas libres.

Hasta la fase C1 el boceto de un sólido tomaba el contorno más grande como
borde y **todos** los demás como huecos: un botón dentro de una ventana salía
como otro hueco, y dos piezas separadas no se podían extruir juntas. Además,
una spline o una elipse del boceto se ignoraban sin decir nada, así que un
contorno con una curva libre «no cerraba».

Ahora (core/solido/boceto.caras_de) cada contorno cerrado se clasifica por
anidamiento, como el PlanarSrf de Rhino: rodeado por un número par de
contornos es material, por uno impar es hueco. Y la spline y la elipse entran
al kernel exactas (B-spline y elipse), no como polilíneas.

Se comprueba por la misma ruta que usa EXTRUIR en el programa:

- marco con ventana, botón dentro de la ventana y una pieza aparte: tres
  sólidos con el volumen de la fórmula;
- una spline cerrada con un hueco de elipse, y un contorno hecho de una spline
  abierta y una línea con un hueco de 0.02 mm: se extruyen, y la cara de
  arriba lleva la spline exacta;
- REVOLVER con una spline cerrada de perfil;
- lo que no tiene una forma clara avisa: dos contornos que se cruzan, y
  REVOLVER con dos piezas separadas.
"""

from __future__ import annotations

import math

from core import entidades as E
from core import regiones
from core import tolerancia
from core.documento import Documento
from core.solido import boceto, rutas
from pruebas import comun

DESCRIPCION = "bocetos 3D con varios contornos, huecos, islas, splines y elipses"

ESPESOR = 18.0


def _rect(x0, y0, x1, y1):
    return E.Polilinea(puntos=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], cerrada=True)


def _doc():
    from core.solido import cuerpo as mod_cuerpo
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    tolerancia.enchufar(lambda: doc)
    mod_cuerpo.olvidar()
    return doc


def _extruir(doc, ents):
    with doc.transaccion("Dibujar"):
        ids = [doc.agregar(e).id for e in ents]
    return rutas.extruir(rutas.Extruir(ids=ids, mm=ESPESOR))


def correr(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod_cuerpo
    previo = tolerancia._doc_actual
    try:
        _islas(r)
        _curvas_libres(r)
        _revolver(r)
        _avisos(r)
    finally:
        tolerancia.enchufar(previo)
        mod_cuerpo.olvidar()


def _islas(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod_cuerpo
    doc = _doc()
    malla = _extruir(doc, [_rect(0, 0, 100, 100), _rect(20, 20, 80, 80), _rect(40, 40, 60, 60),
                           _rect(200, 0, 300, 100)])
    esperado = (100 * 100 - 60 * 60 + 20 * 20 + 100 * 100) * ESPESOR
    r.casi(malla["volumen_mm3"], esperado,
           "marco con ventana, botón en la ventana y pieza aparte: el volumen de la fórmula", 1.0)
    reg = mod_cuerpo.regenerar(doc.entidades[malla["id"]])
    r.igual(len(reg.solido.solids()), 3, "son tres sólidos: el marco, el botón y la pieza")
    caras = boceto.caras_de([e.a_dict() for e in (_rect(0, 0, 100, 100), _rect(20, 20, 80, 80),
                                                   _rect(40, 40, 60, 60))], 0.05)
    r.igual(sorted(len(f.inner_wires()) for f in caras), [0, 1],
            "el marco lleva su hueco y el botón es material (no otro hueco)")


def _curvas_libres(r: comun.Reporte) -> None:
    doc = _doc()
    sp = E.Spline(puntos_control=[[0, 0], [400, -100], [600, 200], [400, 500], [0, 400], [-200, 200]],
                  cerrada=True)
    el = E.Elipse(centro=[200, 200], eje_mayor=[80, 0], razon=0.5)
    malla = _extruir(doc, [sp, el])
    area = regiones.area_de_contorno([sp.a_dict()]) - math.pi * 80 * 40
    # OpenCASCADE integra el volumen de una cara de B-spline con un error del
    # orden de 1e-4 relativo (ver B2a): se le da ese margen.
    r.casi(malla["volumen_mm3"], area * ESPESOR,
           "una spline cerrada con un hueco de elipse se extruye con su volumen", area * ESPESOR * 5e-4)
    from core.solido import cuerpo as mod_cuerpo
    reg = mod_cuerpo.regenerar(doc.entidades[malla["id"]])
    c = sp.curva()
    a, b = c.dominio
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt
    peor = 0.0
    for i in range(12):
        x, y = c.punto(a + (b - a) * i / 12)
        v = BRepBuilderAPI_MakeVertex(gp_Pnt(x, y, ESPESOR)).Vertex()
        d = BRepExtrema_DistShapeShape(v, reg.solido.wrapped)
        peor = max(peor, d.Value())
    r.cierto(peor < 1e-6, "y la spline va exacta en el canto de arriba (no una polilínea)", f"{peor:.2e}")

    doc = _doc()
    abierta = E.Spline(puntos_ajuste=[[0, 0], [100, 60], [200, 0]])
    malla = _extruir(doc, [abierta, E.Linea(p1=[200.02, 0], p2=[0, 0.01])])
    r.cierto(malla.get("volumen_mm3", 0) > 0,
             "una spline abierta y una línea, con un hueco de 0.02 mm, cierran y se extruyen")


def _revolver(r: comun.Reporte) -> None:
    doc = _doc()
    with doc.transaccion("Dibujar"):
        perfil = doc.agregar(E.Spline(puntos_control=[[100, 0], [200, 50], [150, 200], [100, 150]],
                                      cerrada=True))
        eje = doc.agregar(E.Linea(p1=[0, -100], p2=[0, 400]))
    malla = rutas.revolver(rutas.Seleccion(ids=[perfil.id, eje.id]))
    r.cierto(malla.get("volumen_mm3", 0) > 0, "REVOLVER acepta una spline cerrada como perfil")


def _avisos(r: comun.Reporte) -> None:
    r.levanta(ValueError, boceto.caras_de, "dos contornos que se cruzan avisan (hay que unirlos antes)",
              [_rect(0, 0, 100, 100).a_dict(), _rect(50, 50, 150, 150).a_dict()], 0.05)
    from fastapi import HTTPException
    from core.solido import cuerpo as mod_cuerpo
    from core.solido import historial
    ops = historial.asegurar_ids([
        {"op": "boceto", "entidades": [_rect(100, 0, 200, 100).a_dict(), _rect(300, 0, 400, 100).a_dict()]},
        {"op": "revolver", "perfil": "0", "eje": [[0, 0], [0, 100]], "grados": 360.0}])
    doc = _doc()
    try:
        historial.regenerar(ops)
        r.cierto(False, "revolver dos piezas separadas tendría que avisar")
    except (ValueError, HTTPException) as exc:
        r.cierto("una sola pieza" in str(exc), "REVOLVER con dos piezas separadas avisa que quiere una sola",
                 str(exc))
