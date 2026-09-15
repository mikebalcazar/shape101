"""Bloque 1 del 3D · extruir un contorno del dibujo.

Lo que fija: que un contorno cerrado dibujado como siempre se levante y se
vuelva un sólido exacto, que la pieza se guarde dentro del `.101s` como **cómo
se hizo** y no como una malla, y que salga en STEP para que lo abra otro CAD.

El número que se comprueba no es «parece un tablero»: es el volumen que dice la
fórmula. Un modelador que se equivoca por medio milímetro corta mal la madera.
"""
from __future__ import annotations

import json
import pathlib
import tempfile

from core import entidades as E
from core.documento import Documento
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "extruir un contorno y volverlo sólido"

ANCHO, FONDO, ESPESOR = 900.0, 600.0, 18.0


def tablero(doc):
    poli = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, FONDO, 0], [0, FONDO, 0]],
                       cerrada=True)
    doc.agregar(poli)
    return poli


def correr(r: comun.Reporte):
    from core.solido import cuerpo as mod

    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    mod.olvidar()
    poli = tablero(doc)

    # 1 · el contorno se levanta
    malla = rutas.extruir(rutas.Extruir(ids=[poli.id], mm=ESPESOR))
    r.exige(malla.get("n_caras") == 6, "un tablero extruido tiene 6 caras",
            f"llegaron {malla.get('n_caras')}")
    r.casi(malla["volumen_mm3"], ANCHO * FONDO * ESPESOR,
           "el volumen es el de la fórmula, no un aproximado", 1.0)
    r.igual(malla["caja"], [ANCHO, FONDO, ESPESOR], "la caja mide 900 × 600 × 18")
    r.cierto(all(c.get("nombre") for c in malla["caras"]),
             "cada cara llega con su nombre: sin eso no se puede señalar ni jalar")
    r.cierto(len(malla["aristas"]) >= 12, "llegan las aristas para dibujar el filo")

    cid = malla["id"]
    cuerpo = doc.entidades[cid]
    r.igual(cuerpo.tipo, "cuerpo", "la entidad nueva es un cuerpo")
    r.igual([op["op"] for op in cuerpo.operaciones], ["boceto", "extruir"],
            "el cuerpo guarda cómo se hizo, no la malla")
    r.igual(cuerpo.caja(), (0.0, 0.0, ANCHO, FONDO),
            "la sombra en planta se saca del contorno, sin molestar al kernel")

    # 2 · el cuerpo es suyo: borrar el contorno no lo desaparece
    with doc.transaccion("borrar el contorno"):
        doc.borrar(poli.id)
    mod.olvidar(cid)
    r.casi(mod.malla(doc.entidades[cid])["volumen_mm3"], ANCHO * FONDO * ESPESOR,
           "borrado el contorno, la pieza sigue en pie", 1.0)

    # 3 · referencias: con esos nombres se le habla al historial
    refs = rutas.referencias(cid)
    r.cierto("arriba" in refs["caras"] and "abajo" in refs["caras"],
             "las caras horizontales se llaman «arriba» y «abajo»")
    r.igual(len([c for c in refs["caras"] if c.startswith("lado[")]), 4,
            "los cuatro cantos se llaman «lado[n]»")

    # 4 · se guarda y se reabre igual
    with tempfile.TemporaryDirectory() as d:
        ruta = pathlib.Path(d) / "pieza.json"
        ruta.write_text(json.dumps(doc.entidades[cid].a_dict(), ensure_ascii=False), encoding="utf-8")
        otro = E.de_dict(json.loads(ruta.read_text(encoding="utf-8")))
        r.igual(otro.tipo, "cuerpo", "reabierto, sigue siendo un cuerpo")
        r.igual(len(otro.operaciones), 2, "reabierto, conserva sus operaciones")
        mod.olvidar(otro.id)
        r.casi(mod.malla(otro)["volumen_mm3"], ANCHO * FONDO * ESPESOR,
               "reabierto, da el mismo sólido", 1.0)

        # 5 · exportar
        paso = pathlib.Path(d) / "pieza.step"
        salida = rutas.exportar(cid, rutas.Exportar(formato="step", ruta=str(paso)))
        r.cierto(paso.exists() and salida["bytes"] > 0, "exportar STEP deja un archivo con contenido")
        try:
            rutas.exportar(cid, rutas.Exportar(formato="dwg", ruta=str(paso)))
            r.cierto(False, "un formato que no existe se rechaza")
        except Exception as e:
            r.cierto("dwg" in str(e), "un formato que no existe se rechaza diciendo cuál era")

    # 6 · lo que no se puede extruir, se dice claro
    doc2 = Documento.nuevo()
    rutas.enchufar(lambda: doc2)
    try:
        rutas.extruir(rutas.Extruir(ids=[], mm=ESPESOR))
        r.cierto(False, "extruir sin contorno se rechaza")
    except Exception as e:
        r.cierto("contorno" in str(e), "extruir sin contorno se rechaza en el idioma del taller")
    suelta = E.Linea(p1=[0, 0], p2=[100, 0])
    doc2.agregar(suelta)
    try:
        rutas.extruir(rutas.Extruir(ids=[suelta.id], mm=0))
        r.cierto(False, "un espesor de cero se rechaza")
    except Exception as e:
        r.cierto("cero" in str(e), "un espesor de cero se rechaza diciendo por qué")
