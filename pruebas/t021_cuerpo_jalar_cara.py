"""Bloque 2 del 3D · jalar una cara.

Es el gesto de Maya: señalas una cara y la mueves. Aquí no se deforma una
malla —se agrega una operación al historial y la pieza se rehace—, que es lo
que hace que siga siendo un sólido exacto y exportable a STEP después de
jalarla veinte veces.

Lo que fija:

- Positivo es hacia afuera, negativo hacia adentro, y el volumen cambia
  exactamente lo que dice la fórmula.
- **Las caras se llaman por lo que son, no por un número.** Después de jalar
  «arriba», la cara de arriba se sigue llamando «arriba»: si no, la segunda
  jalada movería otra cara y el usuario no entendería nada.
- Una jalada imposible no rompe el modelo: se rechaza y el historial se queda
  como estaba.
"""
from __future__ import annotations

from core import entidades as E
from core.documento import Documento
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "jalar una cara y que la pieza se rehaga"

ANCHO, FONDO, ESPESOR = 900.0, 600.0, 18.0


def correr(r: comun.Reporte):
    from core.solido import cuerpo as mod

    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    mod.olvidar()
    poli = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, FONDO, 0], [0, FONDO, 0]],
                       cerrada=True)
    doc.agregar(poli)
    cid = rutas.extruir(rutas.Extruir(ids=[poli.id], mm=ESPESOR))["id"]

    # 1 · hacia afuera
    malla = rutas.empujar_cara(cid, rutas.EmpujarCara(cara="arriba", mm=12))
    r.casi(malla["volumen_mm3"], ANCHO * FONDO * (ESPESOR + 12),
           "jalar «arriba» 12 mm hacia afuera engorda la pieza justo 12 mm", 1.0)
    r.igual(malla["caja"], [ANCHO, FONDO, ESPESOR + 12], "la caja crece sólo en alto")
    r.igual(malla["n_caras"], 6, "sigue siendo un prisma de 6 caras")

    # 2 · el nombre sobrevive: la de arriba se sigue llamando «arriba»
    refs = rutas.referencias(cid)
    r.cierto("arriba" in refs["caras"],
             "después de jalarla, la cara de arriba se sigue llamando «arriba»")
    malla = rutas.empujar_cara(cid, rutas.EmpujarCara(cara="arriba", mm=10))
    r.casi(malla["volumen_mm3"], ANCHO * FONDO * (ESPESOR + 22),
           "una segunda jalada mueve la misma cara, no otra", 1.0)

    # 3 · hacia adentro
    malla = rutas.empujar_cara(cid, rutas.EmpujarCara(cara="arriba", mm=-22))
    r.casi(malla["volumen_mm3"], ANCHO * FONDO * ESPESOR,
           "jalar hacia adentro lo mismo deja la pieza como estaba", 1.0)

    # 4 · un canto también se jala: la pieza se hace más larga
    malla = rutas.empujar_cara(cid, rutas.EmpujarCara(cara="lado[1]", mm=100))
    r.casi(malla["caja"][0], ANCHO + 100, "jalar un canto alarga la pieza 100 mm", 0.01)

    # 5 · cero no hace nada, y no ensucia el historial
    antes = len(doc.entidades[cid].operaciones)
    rutas.empujar_cara(cid, rutas.EmpujarCara(cara="arriba", mm=0))
    r.igual(len(doc.entidades[cid].operaciones), antes,
            "jalar cero milímetros no agrega una operación vacía al historial")

    # 6 · lo imposible se rechaza y el historial no se ensucia
    antes = list(doc.entidades[cid].operaciones)
    try:
        rutas.empujar_cara(cid, rutas.EmpujarCara(cara="no_existe", mm=5))
        r.cierto(False, "jalar una cara que no existe se rechaza")
    except Exception as e:
        r.cierto("no_existe" in str(e), "jalar una cara que no existe se rechaza diciendo cuál era")
    r.igual(doc.entidades[cid].operaciones, antes,
            "tras el rechazo el historial se queda exactamente como estaba")
    r.casi(mod.malla(doc.entidades[cid])["caja"][0], ANCHO + 100,
           "y la pieza sigue siendo la de antes", 0.01)

    # 7 · sobre algo que no es un cuerpo
    try:
        rutas.empujar_cara(poli.id, rutas.EmpujarCara(cara="arriba", mm=5))
        r.cierto(False, "no se puede jalar la cara de una polilínea")
    except Exception as e:
        r.cierto("polilinea" in str(e), "jalar la cara de algo plano se rechaza diciendo qué es")
