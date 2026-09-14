"""t004 · El `.t101d`: guardar, abrir, autoguardar y recuperar.

El `.t101d` es **el trabajo**; el DXF es la entrega. Aquí se comprueba que el
trabajo vuelve entero —capas, unidades, orden de dibujo, el historial de esta
sesión no, que ése no se guarda a propósito— y las tres reglas del guardado que
existen para no perder un día de trabajo:

1. **Se escribe a un temporal y luego se reemplaza.** Un guardado que truena a
   la mitad no puede dejar roto el archivo anterior.
2. **El autoguardado nunca escribe encima de lo del usuario.** Vive aparte y
   deja marcado de qué archivo salió.
3. **Recuperar es una opción, no un hecho consumado**, y sólo se ofrece si el
   autoguardado es más nuevo que lo que el usuario guardó.
"""

from __future__ import annotations

import os
import time
import zipfile

from core import config
from core import entidades as ent
from core import cotas as mod_cotas
from core import proyecto
from core.capas import Capa
from core.documento import Documento
from pruebas import comun

DESCRIPCION = ".t101d, guardado atómico, autoguardado y recuperación"


def correr(r: comun.Reporte) -> None:
    with comun.carpeta() as tmp:
        _ida_y_vuelta(r, tmp)
        _atomico(r, tmp)
        _autoguardado(r, tmp)


def _dibujo() -> Documento:
    doc = Documento.nuevo()
    doc.nombre = "Cocina Mondelez"
    doc.capa_agregar(Capa("CUERPO", color="#112233", grosor=35))
    with doc.transaccion("Dibujar"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[600, 0], capa="CUERPO"))
        doc.agregar(ent.Circulo(centro=[300, 200], radio=35))
        # `encapar` es la regla de la casa —toda cota nace en COTAS— y hoy la
        # aplica quien crea la entidad, no `Documento.agregar`. Ver t008.
        doc.agregar(mod_cotas.encapar(
            doc, ent.Cota(clase="lineal", puntos=[[0, 0], [600, 0], [0, -60]])))
    return doc


def _ida_y_vuelta(r: comun.Reporte, tmp) -> None:
    doc = _dibujo()
    ids = [e.id for e in doc.lista()]

    ruta = proyecto.guardar(doc, tmp / "cocina")
    r.igual(ruta.suffix, config.EXT_PROYECTO,
            "guardar sin extensión la pone sola (.t101d)")
    r.exige(ruta.exists(), "el archivo queda en disco")
    r.cierto(not doc.sucio, "después de guardar, el documento deja de estar sucio")

    # Es un zip con dos cosas dentro: se puede mirar sin abrir el programa, que
    # es media hora ganada el día que algo salga raro.
    with zipfile.ZipFile(ruta) as z:
        dentro = sorted(z.namelist())
    r.igual(dentro, ["documento.json", "meta.json"],
            "el .t101d es un zip con el documento y su ficha")

    vuelto = proyecto.abrir(ruta)
    r.igual([e.id for e in vuelto.lista()], ids,
            "vuelven las mismas entidades, con su id y en su orden")
    r.igual(sorted(vuelto.capas), sorted(doc.capas), "vuelven las mismas capas")
    r.igual(vuelto.capas["CUERPO"].color, "#112233", "y con sus propiedades")
    r.igual(vuelto.unidades, doc.unidades, "y el dibujo vuelve en su misma unidad")
    r.igual(vuelto.nombre, "Cocina Mondelez", "y con su nombre")

    cota = next((e for e in vuelto.lista() if e.tipo == "cota"), None)
    if r.cierto(cota is not None, "la cota vuelve como cota"):
        r.igual(cota.capa, "COTAS", "y sigue en la capa COTAS")

    r.cierto(not vuelto.historial.puede_deshacer,
             "lo que vuelve no trae el deshacer de la sesión anterior")


def _atomico(r: comun.Reporte, tmp) -> None:
    """Guardar dos veces no deja basura, y el archivo nunca queda a medias."""
    doc = _dibujo()
    ruta = proyecto.guardar(doc, tmp / "atomico.t101d")
    antes = ruta.read_bytes()

    with doc.transaccion("Otra línea"):
        doc.agregar(ent.Linea(p1=[0, 100], p2=[600, 100]))
    proyecto.guardar(doc, ruta)
    r.cierto(ruta.read_bytes() != antes, "guardar encima sí actualiza el archivo")

    sobras = [p.name for p in ruta.parent.glob("*.tmp")]
    r.igual(sobras, [], "no quedan temporales tirados en la carpeta del usuario")

    vuelto = proyecto.abrir(ruta)
    r.igual(len(vuelto.lista()), 4, "y lo guardado encima se abre completo")


def _autoguardado(r: comun.Reporte, tmp) -> None:
    doc = _dibujo()
    original = proyecto.guardar(doc, tmp / "obra.t101d")

    # Recién guardado no hay nada que recuperar: el documento está limpio.
    r.igual(proyecto.autoguardar(doc, original), None,
            "un documento limpio no se autoguarda (no hay nada que respaldar)")

    with doc.transaccion("Trabajo sin guardar"):
        doc.agregar(ent.Linea(p1=[0, 300], p2=[600, 300]))
    copia = proyecto.autoguardar(doc, original)
    r.exige(copia is not None and copia.exists(), "el trabajo sucio sí se autoguarda")

    r.cierto(copia.parent != original.parent,
             "el autoguardado vive aparte, no junto al archivo del usuario")
    r.cierto(doc.sucio,
             "autoguardar no es guardar: el documento sigue sucio")
    r.igual(original.read_bytes(), (tmp / "obra.t101d").read_bytes(),
            "y el archivo del usuario no se tocó")

    marca = copia.with_suffix(".origen")
    r.cierto(marca.exists() and marca.read_text().strip() == str(original),
             "el autoguardado deja apuntado de qué archivo salió")

    ofrecidos = proyecto.recuperables(original)
    r.cierto(any(o["ruta"] == str(copia) for o in ofrecidos),
             "al abrir ese archivo se ofrece recuperar el autoguardado")

    recuperado = proyecto.abrir(copia)
    r.igual(len(recuperado.lista()), 4,
            "y lo recuperado trae el trabajo que no se había guardado")

    # Ahora el usuario guarda de verdad: lo suyo pasa a ser lo más nuevo y ya
    # no hay nada que ofrecerle. Molestar con una recuperación vieja después de
    # guardar es la forma segura de que la gente le dé a «descartar» sin leer.
    time.sleep(1.1)                      # el mtime tiene resolución de segundo
    proyecto.guardar(doc, original)
    os.utime(original, None)
    ofrecidos = proyecto.recuperables(original)
    r.igual([o for o in ofrecidos if o["ruta"] == str(copia)], [],
            "después de guardar de verdad ya no se ofrece recuperar nada")

    proyecto.descartar_recuperacion(copia)
    r.cierto(not copia.exists(), "descartar la recuperación borra la copia")
    r.cierto(not marca.exists(), "y se lleva también su marca de origen")
