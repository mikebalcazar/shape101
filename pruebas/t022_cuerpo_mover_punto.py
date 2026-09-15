"""Bloque 3 del 3D · mover un punto del contorno.

Es lo otro que se hace en Maya: agarrar un vértice y moverlo. La diferencia
—y es la que importa en un taller— es que aquí no se estira una malla: se
cambia el contorno con el que nació la pieza y **todo lo que se hizo después se
vuelve a aplicar solo**.

Por eso esta prueba insiste en dos números:

- Un rectángulo al que se le mueve una esquina deja de ser rectángulo y se
  vuelve trapecio, y el volumen tiene que ser el del trapecio. Si saliera el
  del rectángulo, la malla se habría estirado sin rehacer la pieza.
- Una cara jalada **antes** de mover el punto tiene que seguir jalada
  **después**. Ahí es donde se ve que el historial sirve para algo.
"""
from __future__ import annotations

from core import entidades as E
from core.documento import Documento
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "mover un punto y que la pieza se reconstruya"

ANCHO, FONDO, ESPESOR = 900.0, 600.0, 18.0


def trapecio(abajo: float, arriba: float, alto: float, espesor: float) -> float:
    return (abajo + arriba) / 2 * alto * espesor


def correr(r: comun.Reporte):
    from core.solido import cuerpo as mod

    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    mod.olvidar()
    poli = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, FONDO, 0], [0, FONDO, 0]],
                       cerrada=True)
    doc.agregar(poli)
    cid = rutas.extruir(rutas.Extruir(ids=[poli.id], mm=ESPESOR))["id"]

    # 1 · mover una esquina: el rectángulo se vuelve trapecio
    malla = rutas.mover_punto(cid, rutas.MoverPunto(entidad=0, punto=1, x=1200, y=0))
    r.casi(malla["volumen_mm3"], trapecio(1200, ANCHO, FONDO, ESPESOR),
           "movida la esquina, el volumen es el del trapecio y no el del rectángulo", 1.0)
    r.casi(malla["caja"][0], 1200.0, "la pieza llega hasta 1200 de ancho", 0.01)
    r.igual(malla["n_caras"], 6, "sigue siendo un sólido cerrado de 6 caras")

    # 2 · lo que se hizo después se vuelve a aplicar solo
    rutas.empujar_cara(cid, rutas.EmpujarCara(cara="arriba", mm=12))
    malla = rutas.mover_punto(cid, rutas.MoverPunto(entidad=0, punto=1, x=1500, y=0))
    r.casi(malla["volumen_mm3"], trapecio(1500, ANCHO, FONDO, ESPESOR + 12),
           "la cara que se jaló antes sigue jalada después de mover el punto", 1.0)
    r.casi(malla["caja"][2], ESPESOR + 12, "el espesor jalado se conserva", 0.01)
    r.cierto("arriba" in rutas.referencias(cid)["caras"],
             "y la cara de arriba se sigue llamando «arriba»")

    # 3 · volver el punto a su sitio devuelve la pieza original
    malla = rutas.mover_punto(cid, rutas.MoverPunto(entidad=0, punto=1, x=ANCHO, y=0))
    r.casi(malla["volumen_mm3"], ANCHO * FONDO * (ESPESOR + 12),
           "devuelto el punto, la pieza vuelve a ser la de antes", 1.0)

    # 4 · el historial no crece al mover: se edita el boceto, no se apila
    r.igual([op["op"] for op in doc.entidades[cid].operaciones],
            ["boceto", "extruir", "empujar_cara"],
            "mover un punto edita el boceto en vez de apilar operaciones nuevas")

    # 5 · un círculo se mueve por su centro
    doc2 = Documento.nuevo()
    rutas.enchufar(lambda: doc2)
    circ = E.Circulo(centro=[100, 100], radio=50)
    doc2.agregar(circ)
    cid2 = rutas.extruir(rutas.Extruir(ids=[circ.id], mm=10))["id"]
    malla = rutas.mover_punto(cid2, rutas.MoverPunto(entidad=0, punto=0, x=400, y=250))
    r.casi(malla["volumen_mm3"], 3.141592653589793 * 50 ** 2 * 10,
           "movido el círculo, el volumen no cambia: sólo cambió de sitio", 5.0)

    # 6 · lo que no existe, se dice claro
    rutas.enchufar(lambda: doc)
    for entidad, punto, que in ((5, 0, "una entidad que el boceto no tiene"),
                                (0, 99, "un punto que la polilínea no tiene")):
        try:
            rutas.mover_punto(cid, rutas.MoverPunto(entidad=entidad, punto=punto, x=0, y=0))
            r.cierto(False, f"mover {que} se rechaza")
        except Exception as e:
            r.cierto("no tiene" in str(e), f"mover {que} se rechaza en el idioma del taller",
                     f"el error dijo: {e}")
