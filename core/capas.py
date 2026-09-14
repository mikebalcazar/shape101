"""Capas, tipos de línea y grosores  ·  features 45 a 49.

Una capa guarda color, grosor y tipo de línea; una entidad puede heredarlos
(`None` = «por capa») o llevar los suyos. Es el mismo contrato de AutoCAD, y es
lo que permite que un plano se imprima distinto sin tocar la geometría.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import config

# --- Tipos de línea --------------------------------------------------------
# patrón en mm: positivo = raya, negativo = espacio, 0 = punto.
TIPOS_LINEA: dict[str, dict] = {
    "CONTINUOUS": {"desc": "Continua", "patron": []},
    "CENTER":     {"desc": "Ejes ____ _ ____ _ ____", "patron": [31.75, -6.35, 6.35, -6.35]},
    "HIDDEN":     {"desc": "Oculta __ __ __ __ __",   "patron": [6.35, -3.175]},
    "DASHED":     {"desc": "Trazos __ __ __ __",      "patron": [12.7, -6.35]},
    "PHANTOM":    {"desc": "Ficticia ___ _ _ ___",    "patron": [31.75, -6.35, 6.35, -6.35, 6.35, -6.35]},
    "DOT":        {"desc": "Puntos . . . . . . .",    "patron": [0.0, -6.35]},
}

POR_CAPA = None  # azúcar para leer mejor abajo


@dataclass
class Capa:
    """Una capa del dibujo."""

    nombre: str
    color: str = "#FFFFFF"          # hex; se traduce a true color del DXF
    grosor: int = 25                # centésimas de mm
    tipo_linea: str = "CONTINUOUS"
    visible: bool = True
    bloqueada: bool = False
    imprime: bool = True
    descripcion: str = ""

    def a_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def de_dict(d: dict) -> "Capa":
        return Capa(**{k: v for k, v in d.items() if k in Capa.__dataclass_fields__})


# --- Plantilla Taller 101  ·  feature 46 -----------------------------------
# El orden importa: es el orden en que se muestran en el panel.
#: Cómo se llama la capa de las cotas. Está en una constante y no suelta por
#: ahí porque **todas las cotas nacen en ella**, sin importar en qué capa se
#: esté trabajando: ver `core/cotas.py`.
CAPA_COTAS = "COTAS"

#: El catálogo de capas de Taller 101. **No es lo que trae un dibujo nuevo** —
#: eso es `plantilla()`, dos capas y ya. Éste es el vestuario: cuando una
#: herramienta necesita su capa (importar de Taller 101, un rayado, el pie de
#: plano) se saca de aquí y se crea en ese momento.
#:
#: La razón es de Mike, y es buena: un dibujo recién abierto con trece capas
#: vacías es trece renglones que hay que leer para encontrar la única que se
#: está usando. Las capas se ganan al usarse.
CATALOGO: list[Capa] = [
    Capa("0", "#FFFFFF", 25, "CONTINUOUS",
         descripcion="Capa cero — no se borra, no se renombra"),
    Capa(CAPA_COTAS, config.AZUL, 18, "CONTINUOUS",
         descripcion="Cotas y directrices — aquí nacen todas"),
    Capa("T101-MUROS", "#8C8C8C", 50, "CONTINUOUS",
         descripcion="Obra: muros, columnas, huecos"),
    Capa("T101-CUERPO", config.AZUL, 35, "CONTINUOUS",
         descripcion="Cuerpo del mueble"),
    Capa("T101-FRENTES", config.AZUL_CLARO, 35, "CONTINUOUS",
         descripcion="Puertas, cajones y frentes"),
    Capa("T101-CUBIERTA", "#6B4F2A", 35, "CONTINUOUS",
         descripcion="Cubiertas y narices"),
    Capa("T101-HERRAJES", config.CANTO, 20, "CONTINUOUS",
         descripcion="Bisagras, correderas, jaladeras"),
    Capa("T101-TEXTO", "#1F1F1F", 18, "CONTINUOUS",
         descripcion="Anotaciones y notas de taller"),
    Capa("T101-EJES", "#B03030", 13, "CENTER",
         descripcion="Ejes de referencia"),
    Capa("T101-OCULTO", "#6E6E6E", 18, "HIDDEN",
         descripcion="Aristas no vistas"),
    Capa("T101-RAYADO", "#9A9A9A", 13, "CONTINUOUS",
         descripcion="Rayados y tramas"),
    Capa("T101-ROTULO", config.AZUL, 25, "CONTINUOUS",
         descripcion="Marco y pie de plano"),
    Capa("T101-AUXILIAR", "#C9694A", 13, "DASHED", imprime=False,
         descripcion="Construcción — no imprime"),
]


#: Nombre viejo del catálogo. Se conserva porque hay código que lo importa.
PLANTILLA_T101 = CATALOGO

#: Lo que trae un dibujo nuevo: la capa cero y la de cotas. Nada más.
PLANTILLA_NUEVA = ["0", CAPA_COTAS]


def del_catalogo(nombre: str) -> Capa | None:
    """Una copia de la capa del catálogo, para crearla cuando haga falta."""
    for c in CATALOGO:
        if c.nombre == nombre:
            return Capa.de_dict(c.a_dict())
    return None


def plantilla() -> dict[str, Capa]:
    """Con qué capas nace un dibujo: la cero y la de cotas.

    Y nada más. El resto del catálogo se crea cuando una herramienta lo pide
    (`asegurar`), no antes: un dibujo recién abierto con trece capas vacías es
    trece renglones que estorban para encontrar la que se está usando.
    """
    return {n: c for n in PLANTILLA_NUEVA if (c := del_catalogo(n)) is not None}


def asegurar(doc, nombre: str) -> str:
    """Se asegura de que exista esa capa, sacándola del catálogo si hace falta.

    Devuelve el nombre de la capa que se debe usar. Si existe con ese nombre,
    ésa; si no, se crea. Si el documento la trae bloqueada, se devuelve igual y
    quien llame se topará con el error de siempre: desbloquearla a espaldas del
    usuario sería peor que no poder dibujar.
    """
    if nombre in doc.capas:
        return nombre
    capa = del_catalogo(nombre) or Capa(nombre)
    doc.capa_agregar(capa)
    return nombre


# --- Utilidades ------------------------------------------------------------

def hex_a_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgb_a_hex(rgb) -> str:
    r, g, b = rgb
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))


def grosor_valido(v: int) -> int:
    """Ajusta al grosor DXF válido más cercano. AutoCAD rechaza los demás."""
    if v in (config.GROSOR_POR_CAPA, config.GROSOR_POR_BLOQUE, config.GROSOR_OMISION):
        return v
    return min(config.GROSORES, key=lambda g: abs(g - v))


class NombreCapaInvalido(ValueError):
    pass


PROHIBIDOS = set('<>/\\":;?*|=`')


def validar_nombre(nombre: str) -> str:
    """AutoCAD rechaza estos caracteres en un nombre de capa; mejor aquí que allá."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise NombreCapaInvalido("El nombre de la capa no puede ir vacío")
    if len(nombre) > 255:
        raise NombreCapaInvalido("El nombre de la capa no puede pasar de 255 caracteres")
    malos = sorted(PROHIBIDOS & set(nombre))
    if malos:
        raise NombreCapaInvalido("El nombre de la capa no puede llevar " + " ".join(malos))
    return nombre
