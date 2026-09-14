"""t003 · Las capas: plantilla, nombres, grosores, herencia y bloqueo.

La regla de la casa es que **las capas se ganan al usarse**: un dibujo nuevo
nace con dos, y el resto del catálogo de Taller 101 aparece cuando una
herramienta lo pide. Trece capas vacías son trece renglones que hay que leer
para encontrar la única que se está usando.

Lo demás que se comprueba aquí son las cuatro formas conocidas de mandar a
AutoCAD un archivo que rechaza o que se ve distinto: un nombre con caracteres
prohibidos, un grosor que no está en la tabla del DXF, una entidad que dice
heredar de su capa y no hereda, y una capa bloqueada que se deja editar.
"""

from __future__ import annotations

from core import capas as mod_capas
from core import config
from core import entidades as ent
from core.capas import Capa, NombreCapaInvalido
from core.documento import CapaBloqueada, CapaEnUso, Documento
from pruebas import comun

DESCRIPCION = "plantilla, nombres, grosores, herencia y bloqueo"


def correr(r: comun.Reporte) -> None:
    _plantilla(r)
    _nombres(r)
    _grosores(r)
    _herencia(r)
    _bloqueo_y_uso(r)


def _plantilla(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    r.igual(sorted(doc.capas), ["0", "COTAS"],
            "un dibujo nuevo nace con dos capas y no con trece")

    cotas = doc.capas["COTAS"]
    r.igual(cotas.color.upper(), config.AZUL.upper(),
            "COTAS nace en el azul de Taller 101")
    r.igual(cotas.grosor, 18, "COTAS nace con grosor 0.18")

    # El catálogo sigue completo: lo que cambia es cuándo se crea.
    r.cierto(len(mod_capas.CATALOGO) > 2,
             "el catálogo de Taller 101 sigue completo aunque no se cree entero")
    nombre = mod_capas.asegurar(doc, "MUROS")
    r.igual(nombre, "MUROS", "una herramienta puede pedir su capa del catálogo")
    r.cierto("MUROS" in doc.capas, "y al pedirla se crea en ese momento")

    # Pedir una que no está en el catálogo también vale: se crea en blanco.
    mod_capas.asegurar(doc, "LO QUE SEA")
    r.cierto("LO QUE SEA" in doc.capas,
             "una capa que no está en el catálogo se crea igual")


def _nombres(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    for malo in ['CON<PICO', 'CON"COMILLA', "CON/DIAGONAL", "CON|TUBO", "   "]:
        r.levanta(NombreCapaInvalido, doc.capa_agregar,
                  f"se rechaza el nombre de capa «{malo.strip() or '(vacío)'}»",
                  Capa(malo))
    r.levanta(NombreCapaInvalido, doc.capa_agregar,
              "se rechaza un nombre de más de 255 caracteres", Capa("A" * 256))

    doc.capa_agregar(Capa("  CON ESPACIOS AFUERA  "))
    r.cierto("CON ESPACIOS AFUERA" in doc.capas,
             "los espacios de los extremos se recortan y el nombre se acepta")

    r.levanta(ValueError, doc.capa_agregar,
              "no se puede crear dos veces la misma capa", Capa("0"))
    r.levanta(ValueError, doc.capa_modificar,
              "la capa 0 no se renombra", "0", {"nombre": "CERO"})


def _grosores(r: comun.Reporte) -> None:
    """AutoCAD sólo acepta la tabla de grosores del DXF. Un 27 inventado se
    ajusta al válido más cercano en vez de viajar al archivo."""
    r.igual(mod_capas.grosor_valido(27), 25, "un grosor de 27 se ajusta al 25")
    r.igual(mod_capas.grosor_valido(1000), 211, "un grosor enorme se ajusta al mayor válido")
    r.igual(mod_capas.grosor_valido(config.GROSOR_POR_CAPA), config.GROSOR_POR_CAPA,
            "«por capa» no es un grosor que se ajuste: se respeta")

    doc = Documento.nuevo()
    capa = doc.capa_agregar(Capa("PRUEBA", grosor=27))
    r.igual(capa.grosor, 25, "una capa nueva con grosor inventado se guarda con el válido")
    doc.capa_modificar("PRUEBA", {"grosor": 999})
    r.igual(doc.capas["PRUEBA"].grosor, 211,
            "y al cambiarlo también se ajusta, no al escribir el DXF")


def _herencia(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    doc.capa_agregar(Capa("CUERPO", color="#112233", grosor=35, tipo_linea="OCULTO"))
    with doc.transaccion("Dibujar"):
        hereda = doc.agregar(ent.Linea(p1=[0, 0], p2=[10, 0], capa="CUERPO"))
        propia = doc.agregar(ent.Linea(p1=[0, 5], p2=[10, 5], capa="CUERPO",
                                       color="#FF0000", grosor=50,
                                       tipo_linea="CONTINUOUS"))

    r.igual(doc.color_efectivo(hereda).upper(), "#112233",
            "una entidad sin color propio toma el de su capa")
    r.igual(doc.grosor_efectivo(hereda), 35,
            "una entidad sin grosor propio toma el de su capa")
    r.igual(doc.tipo_linea_efectivo(hereda), "OCULTO",
            "una entidad sin tipo de línea propio toma el de su capa")

    r.igual(doc.color_efectivo(propia).upper(), "#FF0000",
            "y una con color propio manda sobre la capa")
    r.igual(doc.grosor_efectivo(propia), 50, "lo mismo con el grosor propio")

    # Cambiar la capa cambia lo que heredan sus entidades, sin tocarlas.
    doc.capa_modificar("CUERPO", {"color": "#00FF00"})
    r.igual(doc.color_efectivo(hereda).upper(), "#00FF00",
            "cambiar la capa cambia lo heredado sin tocar la entidad")
    r.igual(doc.color_efectivo(propia).upper(), "#FF0000",
            "y no toca a la que tiene color propio")


def _bloqueo_y_uso(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    doc.capa_agregar(Capa("FIJA"))
    with doc.transaccion("Dibujar"):
        linea = doc.agregar(ent.Linea(p1=[0, 0], p2=[100, 0], capa="FIJA"))

    doc.capa_modificar("FIJA", {"bloqueada": True})
    r.levanta(CapaBloqueada, doc.agregar,
              "en una capa bloqueada no se dibuja",
              ent.Linea(p1=[0, 0], p2=[1, 1], capa="FIJA"))
    r.levanta(CapaBloqueada, doc.modificar,
              "una entidad de capa bloqueada no se modifica",
              linea.id, {"p2": [200, 0]})
    r.levanta(CapaBloqueada, doc.borrar,
              "una entidad de capa bloqueada no se borra", linea.id)

    doc.capa_modificar("FIJA", {"bloqueada": False})
    r.levanta(CapaEnUso, doc.capa_borrar,
              "una capa con entidades dentro no se borra por accidente", "FIJA")
    r.levanta(ValueError, doc.capa_borrar, "la capa 0 no se borra", "0")

    with doc.transaccion("Borrar"):
        doc.borrar(linea.id)
    doc.capa_borrar("FIJA")
    r.cierto("FIJA" not in doc.capas, "vacía sí se borra")
