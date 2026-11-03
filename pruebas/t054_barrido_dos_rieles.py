"""t054 · BARRER2: el perfil recorre dos rieles tocando los dos (el Sweep2 de Rhino).

En cada fracción del largo de los rieles el perfil se copia por semejanza
—girado, escalado y movido— para que sus puntas caigan en los dos rieles, y se
tiende una piel por las copias (core/solido/superficies.barrido_dos_rieles).
Las copias se duplican hasta que la piel no se separa de la copia de en medio
de cada tramo más que una décima de la tolerancia del documento.

- rieles paralelos y un semicírculo: el medio cilindro exacto, πrL;
- rieles que se abren y rieles curvos: la piel no se separa de sus secciones
  más que la tolerancia, y los dos rieles quedan sobre ella (exactos en cada
  sección, a la tolerancia entre secciones);
- no importa el orden en que se señalen ni hacia dónde vaya cada riel;
- un perfil que no toca el arranque de los rieles avisa.
"""

from __future__ import annotations

import math

from build123d import Edge, Vector, Wire
from fastapi import HTTPException

from core import entidades as E
from core import tolerancia
from core.documento import Documento
from core.solido import cuerpo as mod
from core.solido import rutas, superficies
from pruebas import comun

DESCRIPCION = "BARRER2: barrido por dos rieles, con la piel a la tolerancia de sus secciones"


def _doc():
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    tolerancia.enchufar(lambda: doc)
    mod.olvidar()
    return doc


def _agregar(doc, *ents):
    with doc.transaccion("Dibujar"):
        return [doc.agregar(e).id for e in ents]


def _semicirculo():
    p = E.Arco(centro=[50, 0], radio=50, ang_ini=0, ang_fin=180)
    p.plano = "YZ"            # de (0, 0, 0) a (0, 100, 0), panza hacia arriba
    return p


def _sobre(forma, alambre, n=12) -> float:
    from build123d import Vertex
    return max(superficies._distancia(Vertex(*tuple(alambre.position_at(k / n))), forma) for k in range(n + 1))


def correr(r: comun.Reporte) -> None:
    previo = tolerancia._doc_actual
    try:
        _paralelos(r)
        _que_se_abren_y_curvos(r)
        _avisos(r)
    finally:
        tolerancia.enchufar(previo)
        mod.olvidar()


def _paralelos(r: comun.Reporte) -> None:
    doc = _doc()
    # En desorden y con un riel al revés: el historial decide los papeles.
    ids = _agregar(doc, E.Linea(p1=[300, 100], p2=[0, 100]), _semicirculo(), E.Linea(p1=[0, 0], p2=[300, 0]))
    m = rutas.barrer2(rutas.Seleccion(ids=ids))
    r.cierto(m["es_superficie"], "BARRER2 deja una superficie")
    r.casi(m["area_mm2"], math.pi * 50 * 300,
           "rieles paralelos y un semicírculo de r 50: el medio cilindro πrL, sin importar orden ni sentido", 0.5)
    r.igual(m["caja"], [300.0, 100.0, 50.0], "y ocupa 300 × 100 × 50")


def _que_se_abren_y_curvos(r: comun.Reporte) -> None:
    tol = 0.005
    perfil = Wire([Edge.make_three_point_arc(Vector(0, 0, 0), Vector(0, 50, 50), Vector(0, 100, 0))])
    casos = {
        "que se abren": (Wire([Edge.make_line(Vector(0, 0, 0), Vector(300, 0, 0))]),
                         Wire([Edge.make_line(Vector(0, 100, 0), Vector(300, 200, 0))])),
        "curvos": (Wire([Edge.make_spline([Vector(0, 0, 0), Vector(150, -40, 0), Vector(300, 0, 0)])]),
                   Wire([Edge.make_spline([Vector(0, 100, 0), Vector(150, 160, 0), Vector(300, 100, 0)])])),
    }
    for nombre, (r1, r2) in casos.items():
        piel, sep = superficies.barrido_dos_rieles(perfil, r1, r2, tol)
        r.cierto(sep <= tol, f"rieles {nombre}: la piel no se separa de sus secciones más de {tol}", f"{sep:.5f}")
        # Exactos en cada sección; entre secciones la piel los aproxima, a la
        # misma tolerancia que a las secciones.
        peor = max(_sobre(piel, r1), _sobre(piel, r2))
        r.cierto(peor <= tol, f"rieles {nombre}: los dos rieles quedan sobre la superficie (±{tol})", f"{peor:.2e}")
        r.cierto(piel.area > 0, f"rieles {nombre}: la superficie tiene área")


def _avisos(r: comun.Reporte) -> None:
    doc = _doc()
    ids = _agregar(doc, E.Linea(p1=[0, 500], p2=[300, 500]), _semicirculo(), E.Linea(p1=[0, 0], p2=[300, 0]))
    try:
        rutas.barrer2(rutas.Seleccion(ids=ids))
        r.cierto(False, "un perfil que no toca uno de los rieles debería avisar")
    except HTTPException as exc:
        r.cierto("tocar" in exc.detail, "un perfil que no toca el arranque de los rieles avisa", exc.detail)
    ids = _agregar(doc, E.Linea(p1=[0, 0], p2=[300, 0]), _semicirculo())
    try:
        rutas.barrer2(rutas.Seleccion(ids=ids))
        r.cierto(False, "con dos curvas debería avisar")
    except HTTPException as exc:
        r.cierto("tres curvas" in exc.detail, "con dos curvas pide tres", exc.detail)
