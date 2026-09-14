"""t002 · El deshacer: transacciones, orden y tope.

El deshacer está en los cimientos por una razón: cada operación anota su
inversa **dentro** de una transacción con nombre, para que un Ctrl+Z deshaga
una acción del usuario —un rectángulo entero, un arreglo de cuarenta copias— y
no un cuarto de ella. Lo que se comprueba aquí es justo eso, más las tres cosas
que se rompen sin hacer ruido: que la entidad vuelva con **su mismo id** (de él
cuelgan las cotas asociativas), que vuelva **en su lugar** en el orden de
dibujo, y que rehacer se cancele en cuanto se dibuja algo nuevo.
"""

from __future__ import annotations

from core import config
from core import entidades as ent
from core.documento import Documento
from pruebas import comun

DESCRIPCION = "deshacer, rehacer, transacciones, orden y tope"


def correr(r: comun.Reporte) -> None:
    _una_accion(r)
    _orden_y_ligas(r)
    _rehacer_se_cancela(r)
    _tope(r)


def _una_accion(r: comun.Reporte) -> None:
    """Cuarenta copias son **una** acción."""
    doc = Documento.nuevo()
    with doc.transaccion("Arreglo"):
        for i in range(40):
            doc.agregar(ent.Circulo(centro=[i * 50, 0], radio=10))
    r.igual(len(doc.lista()), 40, "el arreglo deja sus cuarenta copias")
    r.igual(doc.historial.nombre_deshacer(), "Arreglo",
            "el deshacer sabe cómo se llama lo que va a deshacer")

    doc.deshacer()
    r.igual(len(doc.lista()), 0,
            "un solo Ctrl+Z deshace el arreglo entero, no una copia")
    doc.rehacer()
    r.igual(len(doc.lista()), 40, "y un Ctrl+Y lo devuelve entero")

    r.cierto(not doc.historial.puede_rehacer,
             "después de rehacer no queda nada más que rehacer")


def _orden_y_ligas(r: comun.Reporte) -> None:
    """Vuelve con su id y en su sitio."""
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        a = doc.agregar(ent.Linea(p1=[0, 0], p2=[100, 0]))
        b = doc.agregar(ent.Linea(p1=[0, 10], p2=[100, 10]))
        c = doc.agregar(ent.Linea(p1=[0, 20], p2=[100, 20]))
    ids = [a.id, b.id, c.id]

    with doc.transaccion("Borrar"):
        doc.borrar(b.id)
    r.igual([e.id for e in doc.lista()], [a.id, c.id], "se borró la de en medio")

    doc.deshacer()
    r.igual([e.id for e in doc.lista()], ids,
            "al deshacer vuelve con su mismo id y **en medio**, no al final")

    # El id importa porque de él cuelga la cota asociativa: si al deshacer la
    # entidad volviera con un id nuevo, la cota quedaría midiendo un fantasma.
    vuelta = doc.entidades[b.id]
    r.punto(vuelta.p1, [0, 10], "y vuelve con su geometría intacta")

    with doc.transaccion("Mover"):
        doc.modificar(a.id, {"p2": [500, 0]})
    r.punto(doc.entidades[a.id].p2, [500, 0], "el cambio se aplicó")
    doc.deshacer()
    r.punto(doc.entidades[a.id].p2, [100, 0], "y el deshacer lo devuelve como estaba")


def _rehacer_se_cancela(r: comun.Reporte) -> None:
    """Dibujar después de deshacer cierra el camino de rehacer: es lo que hace
    todo CAD, y lo contrario —rehacer sobre una rama que ya no existe— produce
    dibujos imposibles de explicar."""
    doc = Documento.nuevo()
    with doc.transaccion("Uno"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[10, 0]))
    doc.deshacer()
    r.cierto(doc.historial.puede_rehacer, "después de deshacer se puede rehacer")
    with doc.transaccion("Otro"):
        doc.agregar(ent.Circulo(centro=[0, 0], radio=5))
    r.cierto(not doc.historial.puede_rehacer,
             "dibujar algo nuevo cancela el rehacer pendiente")


def _tope(r: comun.Reporte) -> None:
    """El historial tiene tope y tira lo más viejo. Sin tope, una sesión larga
    sobre un plano grande se come la memoria de la máquina."""
    doc = Documento(con_plantilla=True)
    limite = doc.historial.limite
    r.igual(limite, config.HISTORIAL_MAX, "el tope es el que dice la configuración")

    for i in range(limite + 25):
        with doc.transaccion(f"Línea {i}"):
            doc.agregar(ent.Linea(p1=[0, i], p2=[10, i]))

    r.cierto(len(doc.historial.hechas) <= limite,
             "el historial no pasa de su tope",
             f"lleva {len(doc.historial.hechas)}")
    r.igual(len(doc.lista()), limite + 25,
            "aunque el historial se pode, el dibujo conserva todo lo dibujado")
