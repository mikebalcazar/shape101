"""t008 · Las cotas: qué miden, a qué se pegan y dónde nacen.

Una cota guarda **lo que mide, no las rayas**. De ahí salen las tres cosas que
se comprueban aquí, y las tres son de taller antes que de programa:

- **La medida se calcula**, no se teclea. Un número escrito a mano en un plano
  que después se edita es una pieza mal cortada esperando su turno.
- **La cota está pegada a la pieza** (`liga`): se mueve el mueble y la cota se
  mueve y se recalcula sola.
- **Toda cota nace en `COTAS`**, dé igual en qué capa se esté trabajando: esa
  capa se apaga entera para ver el dibujo limpio.

Y al final, que salga al DXF como `DIMENSION` de verdad y no como cuatro rayas
y un texto: un plano cuyas cotas no son cotas se ve igual y no sirve para nada
del otro lado.
"""

from __future__ import annotations

import math

import ezdxf

from core import capas as mod_capas
from core import cotas as mod_cotas
from core import entidades as ent
from core.capas import Capa
from core.documento import Documento
from export import dxf as export_dxf
from pruebas import comun

DESCRIPCION = "medida, asociatividad, capa y DIMENSION"


def correr(r: comun.Reporte) -> None:
    _medida(r)
    _asociativa(r)
    _capa(r)
    with comun.carpeta() as tmp:
        _al_dxf(r, tmp)


def _medida(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Acotar"):
        lineal = doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="lineal", puntos=[[0, 0], [600, 0], [0, -60]])))
        alineada = doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="alineada", puntos=[[0, 0], [300, 400], [0, -60]])))

    r.casi(mod_cotas.medida(doc, lineal), 600,
           "una cota lineal mide la distancia entre sus dos puntos")
    r.casi(mod_cotas.medida(doc, alineada), 500,
           "una alineada mide a lo largo, no la proyección (3-4-5)")

    # El texto sobrescribe, pero la medida sigue siendo la medida: es lo que
    # permite avisar el día que alguien escribió «600» sobre algo que mide 610.
    with doc.transaccion("Texto a mano"):
        doc.modificar(lineal.id, {"texto": "600 REF"})
    r.casi(mod_cotas.medida(doc, lineal), 600,
           "poner texto a mano no cambia lo que la cota mide de verdad")

    geo = mod_cotas.geometria(doc, lineal)
    r.cierto(bool(geo.get("lineas")), "una cota se dibuja con rayas de verdad")
    r.igual((geo.get("texto") or {}).get("texto"), "600 REF",
            "y enseña el texto que se le puso")


def _asociativa(r: comun.Reporte) -> None:
    """Se mueve la pieza y la cota va detrás. Es feature 58 y es la diferencia
    entre un plano que se mantiene solo y uno que hay que revisar cota por cota
    después de cada cambio."""
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        pieza = doc.agregar(ent.Linea(p1=[0, 0], p2=[600, 0]))
        cota = doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="lineal",
            puntos=[[0, 0], [600, 0], [0, -60]],
            liga=[{"id": pieza.id, "campo": "p1", "indice": None},
                  {"id": pieza.id, "campo": "p2", "indice": None},
                  None])))
    r.casi(mod_cotas.medida(doc, cota), 600, "la cota nace midiendo la pieza")

    with doc.transaccion("Estirar"):
        doc.modificar(pieza.id, {"p2": [900, 0]})
        tocadas = mod_cotas.actualizar_ligadas(doc, [pieza.id])

    r.cierto(cota.id in tocadas, "al mover la pieza, la cota se entera")
    r.punto(doc.entidades[cota.id].puntos[1], [900, 0],
            "el punto de la cota que colgaba de la pieza se movió con ella")
    r.casi(mod_cotas.medida(doc, cota), 900,
           "y la medida se recalculó sola: 900, no 600")

    # El punto que puso el usuario a mano —dónde va la línea de cota— no se
    # mueve: **la pieza se estiró, no se trasladó**. Aquí se coló un error que
    # no truena: como sólo se apuntaba el desplazamiento de los puntos que
    # cambiaron, un estirado se leía como traslado y la línea de cota se iba
    # 300 de lado. Se ve plausible y sale a la luz midiendo en el papel.
    r.punto(doc.entidades[cota.id].puntos[2], [0, -60],
            "al estirar la pieza, la línea de cota se queda donde el usuario la puso")

    # Y el traslado sí arrastra todo, que es lo que pidió Mike el 7-sep: se
    # mueve el mueble entero y la cota queda igual respecto de él.
    with doc.transaccion("Trasladar"):
        doc.modificar(pieza.id, {"p1": [0, 200], "p2": [900, 200]})
        mod_cotas.actualizar_ligadas(doc, [pieza.id])
    r.punto(doc.entidades[cota.id].puntos[2], [0, 140],
            "trasladar la pieza sí se lleva la línea de cota con ella")
    r.casi(mod_cotas.medida(doc, cota), 900,
           "y al trasladar, la medida no cambia")

    # Y si la pieza se borra, la liga se limpia en vez de quedar apuntando a un
    # fantasma. Una cota que mide algo que ya no existe es peor que ninguna.
    with doc.transaccion("Borrar"):
        doc.borrar(pieza.id)
        mod_cotas.limpiar_ligas(doc, [pieza.id])
    ligas = [l for l in doc.entidades[cota.id].liga if l]
    r.igual([l for l in ligas if l.get("id") == pieza.id], [],
            "al borrar la pieza, la cota deja de apuntar a ella")


def _capa(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    doc.capa_agregar(Capa("MUROS"))
    doc.capa_activa = "MUROS"

    with doc.transaccion("Acotar trabajando en MUROS"):
        cota = doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="lineal", puntos=[[0, 0], [100, 0], [0, -20]], capa="MUROS")))
    r.igual(cota.capa, mod_capas.CAPA_COTAS,
            "una cota trazada trabajando en MUROS nace igual en COTAS")

    # Y si la capa no existe —un plano ajeno, por ejemplo— se crea del catálogo.
    ajeno = Documento(con_plantilla=False)
    ajeno.capa_agregar(Capa("A-DIMS"))
    ajeno.capa_activa = "A-DIMS"
    suelta = mod_cotas.encapar(ajeno, ent.Cota(clase="lineal",
                                               puntos=[[0, 0], [10, 0], [0, -2]]))
    r.igual(suelta.capa, mod_capas.CAPA_COTAS,
            "en un plano sin capa de cotas, la cota la crea")
    r.cierto(mod_capas.CAPA_COTAS in ajeno.capas,
             "y la capa queda creada del catálogo")

    # Lo que **no** es cota no se toca: `encapar` sólo manda cotas.
    linea = mod_cotas.encapar(doc, ent.Linea(p1=[0, 0], p2=[1, 1], capa="MUROS"))
    r.igual(linea.capa, "MUROS", "lo que no es cota se queda en su capa")


def _al_dxf(r: comun.Reporte, tmp) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Acotar"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[600, 0]))
        doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="lineal", puntos=[[0, 0], [600, 0], [0, -60]])))
        doc.agregar(mod_cotas.encapar(doc, ent.Cota(
            clase="radio", puntos=[[300, 300], [335, 300]])))

    ruta = tmp / "cotas.dxf"
    export_dxf.escribir(doc, ruta)
    doc_dxf = ezdxf.readfile(str(ruta))
    tipos = [e.dxftype() for e in doc_dxf.modelspace()]
    r.igual(tipos.count("DIMENSION"), 2,
            "las cotas salen como DIMENSION, no como rayas y un texto suelto")

    from ezdxf import audit
    aud = audit.Auditor(doc_dxf)
    aud.run()
    r.igual(len(aud.errors), 0, "y el archivo con cotas pasa el auditor")

    capas_usadas = {e.dxf.layer for e in doc_dxf.modelspace()
                    if e.dxftype() == "DIMENSION"}
    r.igual(capas_usadas, {mod_capas.CAPA_COTAS},
            "y llegan al archivo en la capa COTAS")
