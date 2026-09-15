"""Modelo de entidades del dibujo.

Se define **completo desde F0** aunque las herramientas para crearlas lleguen en
F2, F3 y F5. La razón es práctica: si el modelo crece después, cada archivo
`.t101d` guardado antes queda cojo y hay que migrarlo. El modelo es barato; la
migración no.

Convenciones:

- Coordenadas en **milímetros**, plano XY, Z se ignora (esto es un CAD 2D).
- `color`, `grosor` y `tipo_linea` en `None` significan **por capa**.
- Toda entidad tiene `id` estable: el historial y las cotas asociativas apuntan
  ahí, no a la posición en la lista.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import fields, dataclass, field, asdict
from typing import Any

_contador = itertools.count(1)


def nuevo_id() -> str:
    return f"e{next(_contador)}"


def sembrar_contador(entidades) -> None:
    """Tras abrir un archivo, el contador arranca después del id más alto."""
    global _contador
    mayor = 0
    for e in entidades:
        if isinstance(e.id, str) and e.id.startswith("e") and e.id[1:].isdigit():
            mayor = max(mayor, int(e.id[1:]))
    _contador = itertools.count(mayor + 1)


@dataclass
class Entidad:
    """Lo que toda entidad tiene."""

    id: str = field(default_factory=nuevo_id)
    capa: str = "0"
    color: str | None = None          # None = por capa
    grosor: int | None = None         # None = por capa
    tipo_linea: str | None = None     # None = por capa
    escala_tl: float = 1.0
    visible: bool = True
    # Handle de la entidad en el DXF del que se leyó, si vino de uno. Es la
    # liga que permite escribir de vuelta sobre el archivo original en vez de
    # reconstruirlo (ver export/dxf.py).
    handle_origen: str = ""
    # De dónde salió la entidad, cuando no la dibujó el usuario: "t101x" para
    # lo que genera la importación desde Taller 101. Es lo que permite
    # regenerar el mueble sin llevarse por delante las anotaciones que alguien
    # puso encima (feature 72).
    origen: str = ""
    # En qué espacio vive: `""` es el **modelo**, y cualquier otro valor es el
    # nombre de la **hoja** a la que pertenece.
    #
    # Un CAD tiene dos espacios y no son lo mismo. En el modelo se dibuja el
    # mueble a tamaño real, en milímetros de verdad. En una hoja se dibuja
    # sobre el papel, en milímetros de papel, y lo que se pone ahí es de esa
    # hoja y de ninguna otra: la nota, el símbolo, la viñeta de detalle.
    #
    # Hasta 0.13.1 esto no existía y todo caía en el modelo. Estando en una
    # hoja, el clic daba coordenadas de papel —(200, 150)— pero la entidad se
    # creaba en el modelo con esos números: en el DWG de Mondelez, a 115 metros
    # del dibujo. Se trazaba, pero no aparecía en ninguna parte, que es justo
    # como lo describió Mike.
    espacio: str = ""
    # A qué grupo pertenece, si a alguno. Picar un miembro selecciona el
    # grupo entero. Ver `core/agrupar.py`.
    grupo: str = ""

    tipo: str = field(init=False, default="entidad")

    # -- serialización ------------------------------------------------------
    def a_dict(self) -> dict:
        # No `dataclasses.asdict`: hace deepcopy recursivo y en una operación
        # sobre 2 000 entidades costaba medio segundo él solo. Aquí sólo hay
        # números, cadenas y listas de listas de números: se copian a mano.
        d = {}
        for f in fields(self):
            d[f.name] = _clon(getattr(self, f.name))
        d["tipo"] = self.tipo
        return d

    # -- geometría ----------------------------------------------------------
    def caja(self) -> tuple[float, float, float, float] | None:
        """(x0, y0, x1, y1) o None si la entidad no ocupa lugar."""
        return None


def _clon(v):
    """Copia profunda barata de lo que hay en una entidad (listas anidadas,
    dicts, escalares). Un vértice `[x, y, bulge]` se copia con `list()`."""
    if isinstance(v, list):
        return [_clon(x) if isinstance(x, (list, dict)) else x for x in v]
    if isinstance(v, dict):
        return {k: _clon(x) if isinstance(x, (list, dict)) else x for k, x in v.items()}
    return v


def _caja_de_puntos(puntos) -> tuple[float, float, float, float] | None:
    pts = [p for p in puntos if p is not None]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# --- Entidades lineales ----------------------------------------------------

@dataclass
class Linea(Entidad):
    p1: list = field(default_factory=lambda: [0.0, 0.0])
    p2: list = field(default_factory=lambda: [0.0, 0.0])
    tipo: str = field(init=False, default="linea")

    def caja(self):
        return _caja_de_puntos([self.p1, self.p2])


@dataclass
class Polilinea(Entidad):
    # cada vértice es [x, y, bulge]; bulge 0 = tramo recto
    puntos: list = field(default_factory=list)
    cerrada: bool = False
    tipo: str = field(init=False, default="polilinea")

    def caja(self):
        # Caja de los vértices. Un arco con bulge puede salirse un poco; para
        # encuadre es suficiente y no cuesta trigonometría en cada repintado.
        return _caja_de_puntos([[p[0], p[1]] for p in self.puntos])


@dataclass
class Circulo(Entidad):
    centro: list = field(default_factory=lambda: [0.0, 0.0])
    radio: float = 1.0
    tipo: str = field(init=False, default="circulo")

    def caja(self):
        cx, cy = self.centro[0], self.centro[1]
        r = self.radio
        return cx - r, cy - r, cx + r, cy + r


@dataclass
class Arco(Entidad):
    centro: list = field(default_factory=lambda: [0.0, 0.0])
    radio: float = 1.0
    ang_ini: float = 0.0     # grados, sentido antihorario
    ang_fin: float = 90.0
    tipo: str = field(init=False, default="arco")

    def caja(self):
        cx, cy = self.centro[0], self.centro[1]
        r = self.radio
        a0, a1 = self.ang_ini % 360, self.ang_fin % 360
        pts = [
            [cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))],
            [cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))],
        ]
        # los cuadrantes que el arco cruza también tocan la caja
        barrido = (a1 - a0) % 360
        for q in (0, 90, 180, 270):
            if (q - a0) % 360 <= barrido:
                pts.append([cx + r * math.cos(math.radians(q)), cy + r * math.sin(math.radians(q))])
        return _caja_de_puntos(pts)


@dataclass
class Elipse(Entidad):
    centro: list = field(default_factory=lambda: [0.0, 0.0])
    eje_mayor: list = field(default_factory=lambda: [1.0, 0.0])  # vector desde el centro
    razon: float = 1.0            # eje menor / eje mayor
    param_ini: float = 0.0        # radianes
    param_fin: float = 2 * math.pi
    tipo: str = field(init=False, default="elipse")

    def caja(self):
        cx, cy = self.centro[0], self.centro[1]
        ax, ay = self.eje_mayor[0], self.eje_mayor[1]
        a = math.hypot(ax, ay)
        b = a * self.razon
        # caja del elipsoide completo rotado
        t = math.atan2(ay, ax)
        dx = math.hypot(a * math.cos(t), b * math.sin(t))
        dy = math.hypot(a * math.sin(t), b * math.cos(t))
        return cx - dx, cy - dy, cx + dx, cy + dy


@dataclass
class Spline(Entidad):
    puntos_ajuste: list = field(default_factory=list)     # por dónde pasa
    puntos_control: list = field(default_factory=list)    # o los de control
    grado: int = 3
    cerrada: bool = False
    tipo: str = field(init=False, default="spline")

    def caja(self):
        return _caja_de_puntos(self.puntos_ajuste or self.puntos_control)


@dataclass
class Punto(Entidad):
    p: list = field(default_factory=lambda: [0.0, 0.0])
    tipo: str = field(init=False, default="punto")

    def caja(self):
        return _caja_de_puntos([self.p])


@dataclass
class Solido(Entidad):
    """SOLID: triángulo o cuadrilátero relleno."""
    puntos: list = field(default_factory=list)
    tipo: str = field(init=False, default="solido")

    def caja(self):
        return _caja_de_puntos(self.puntos)


@dataclass
class Cuerpo(Entidad):
    """Un sólido 3D. **No guarda geometría: guarda cómo se hizo.**

    Adentro va la lista de operaciones —boceto, extruir, barreno, redondeo,
    cara jalada— y el sólido se reconstruye a partir de ella. Guardar la malla
    sería más simple y serviría de poco: en cuanto se mueve un punto del
    contorno habría que deformarla, y un barreno hecho después dejaría de ser
    redondo. Rehaciendo la pieza, sigue siéndolo.

    Ojo con el nombre: `Solido` ya existe en este archivo y es otra cosa —el
    SOLID del DXF, un relleno plano—. Éste es el cuerpo de tres dimensiones.
    """
    operaciones: list = field(default_factory=list)
    tipo: str = field(init=False, default="cuerpo")

    def caja(self):
        """La sombra en planta, para encuadrar la vista. Se saca del contorno
        del boceto y no del sólido: pedirle la caja al kernel obligaría a
        regenerar la pieza cada vez que alguien encuadra."""
        for op in self.operaciones:
            if op.get("op") != "boceto":
                continue
            pts = []
            for e in op.get("entidades") or []:
                t = e.get("tipo")
                if t == "polilinea":
                    pts += [[p[0], p[1]] for p in (e.get("puntos") or [])]
                elif t in ("circulo", "arco"):
                    c, rad = e.get("centro") or [0, 0], e.get("radio") or 0
                    pts += [[c[0] - rad, c[1] - rad], [c[0] + rad, c[1] + rad]]
                elif t == "linea":
                    pts += [e.get("p1", [0, 0])[:2], e.get("p2", [0, 0])[:2]]
            return _caja_de_puntos(pts)
        return None


# --- Texto -----------------------------------------------------------------

@dataclass
class Texto(Entidad):
    p: list = field(default_factory=lambda: [0.0, 0.0])
    texto: str = ""
    altura: float = 2.5
    rotacion: float = 0.0
    estilo: str = "T101"
    alineacion: str = "IZQ"     # IZQ | CENTRO | DER
    tipo: str = field(init=False, default="texto")

    def caja(self):
        x, y = self.p[0], self.p[1]
        ancho = 0.6 * self.altura * max(1, len(self.texto))
        return x, y, x + ancho, y + self.altura


@dataclass
class TextoM(Entidad):
    """MTEXT: texto de párrafo con ancho de columna."""
    p: list = field(default_factory=lambda: [0.0, 0.0])
    texto: str = ""
    altura: float = 2.5
    ancho: float = 0.0          # 0 = sin límite
    rotacion: float = 0.0
    estilo: str = "T101"
    adjunto: int = 1            # 1 = arriba-izquierda, como en DXF
    tipo: str = field(init=False, default="textom")

    def caja(self):
        x, y = self.p[0], self.p[1]
        ancho = self.ancho or 0.6 * self.altura * max(1, len(self.texto))
        lineas = max(1, self.texto.count("\n") + 1)
        return x, y - self.altura * lineas, x + ancho, y


# --- Bloques ---------------------------------------------------------------

@dataclass
class Bloque:
    """Definición de bloque. Las inserciones la referencian por nombre."""
    nombre: str
    base: list = field(default_factory=lambda: [0.0, 0.0])
    entidades: list = field(default_factory=list)
    descripcion: str = ""

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "base": self.base,
            "descripcion": self.descripcion,
            "entidades": [e.a_dict() for e in self.entidades],
        }

    @staticmethod
    def de_dict(d: dict) -> "Bloque":
        return Bloque(
            nombre=d["nombre"],
            base=d.get("base", [0.0, 0.0]),
            descripcion=d.get("descripcion", ""),
            entidades=[de_dict(x) for x in d.get("entidades", [])],
        )


@dataclass
class Insercion(Entidad):
    bloque: str = ""
    p: list = field(default_factory=lambda: [0.0, 0.0])
    escala: list = field(default_factory=lambda: [1.0, 1.0])
    rotacion: float = 0.0
    atributos: dict = field(default_factory=dict)
    tipo: str = field(init=False, default="insercion")

    def caja(self):
        # sin resolver el bloque sólo se conoce el punto de inserción; el
        # documento la afina cuando hace falta (ver Documento.caja_de).
        return _caja_de_puntos([self.p])


# --- Rayado ----------------------------------------------------------------

@dataclass
class Rayado(Entidad):
    """HATCH. Cada ruta es una lista de vértices [x, y, bulge] cerrada."""
    rutas: list = field(default_factory=list)
    patron: str = "SOLID"
    escala: float = 1.0
    angulo: float = 0.0
    solido: bool = True
    asociado: list = field(default_factory=list)   # ids de los contornos
    tipo: str = field(init=False, default="rayado")

    def caja(self):
        pts = [[p[0], p[1]] for ruta in self.rutas for p in ruta]
        return _caja_de_puntos(pts)


# --- Cotas (el modelo; las herramientas llegan en F5) ----------------------

@dataclass
class Cota(Entidad):
    """DIMENSION.

    `clase` es lineal | alineada | angular | radio | diametro | directriz.
    `puntos` son los puntos de definición según la clase.
    `medida` la calcula el motor; `texto` la sobrescribe si no va vacío.
    `liga` guarda los ids de las entidades a las que la cota está pegada — es
    lo que hace posible la asociatividad (feature 58) sin que el DXF la cargue.
    """
    clase: str = "lineal"
    puntos: list = field(default_factory=list)
    medida: float = 0.0
    texto: str = ""
    estilo: str = "T101"
    rotacion: float = 0.0
    liga: list = field(default_factory=list)
    # Por cuánto se multiplica lo medido para anunciar la medida de verdad.
    #
    # Sólo se usa acotando **sobre una hoja**: ahí la cota mide milímetros de
    # papel, y 172 mm de papel sobre una ventana a 1:20 son 3 450 mm de mueble.
    # Sin esto, una cota puesta en el plano diría 172 y el que corta la pieza
    # la cortaría de 172. Es el DIMLFAC de AutoCAD, y aquí se pone solo con la
    # escala de la ventana donde cayó la cota.
    factor_medida: float = 1.0
    # Tamaño propio de **esta** cota (texto, flechas, huecos), como proporción.
    #
    # Mike (9-sep-2026): un panel con el tamaño base de las cotas de todo el
    # documento, y por cota la opción de «encadenar» a ese base: queda como
    # proporción (1.5× el base) y si el base cambia, la cota cambia con todo el
    # documento. Sin encadenar, `factor_tamano` es un tamaño absoluto propio:
    # multiplica el estilo a 1:1 y no sigue al DIMSCALE del documento.
    factor_tamano: float = 1.0
    encadenada: bool = True
    tipo: str = field(init=False, default="cota")

    def caja(self):
        return _caja_de_puntos(self.puntos)


# --- Imagen de referencia  ·  feature 8 -----------------------------------

@dataclass
class Imagen(Entidad):
    """Una foto o un plano escaneado puesto debajo del dibujo, para calcar.

    Se guarda la **ruta**, no la imagen: un `.t101d` con tres fotos de obra
    dentro pesaría veinte megas y se mandaría por correo con todo y ellas. Si
    el archivo se mueve, la app lo dice y sigue funcionando.

    No viaja al DXF. Meter una imagen en un DXF exige un OLE o un IMAGEDEF con
    su ruta absoluta, que en la máquina de otro no existe; una referencia rota
    dentro de un plano ajeno es peor que no mandarla.
    """
    archivo: str = ""
    p: list = field(default_factory=lambda: [0.0, 0.0])   # esquina inferior izquierda
    ancho: float = 100.0
    alto: float = 100.0
    opacidad: float = 1.0
    tipo: str = field(init=False, default="imagen")

    def caja(self):
        return self.p[0], self.p[1], self.p[0] + self.ancho, self.p[1] + self.alto


# --- Entidad no modelada ---------------------------------------------------

@dataclass
class Cruda(Entidad):
    """Una entidad DXF que este programa todavía no modela.

    No se tira ni se reconstruye: se **deja donde está**. El documento guarda
    el DXF original completo y al exportar se parte de él, así que una cota,
    una spline o un objeto propietario de otro programa salen bit por bit como
    entraron, con sus bloques anónimos, sus estilos y sus handles.

    Aquí sólo se guarda de qué tipo es (para poder enseñarlo y seleccionarlo) y
    su handle en el archivo original. Se puede cambiar de capa, de color y de
    grosor; su geometría no se toca hasta que exista la herramienta que la
    edite de verdad.
    """
    dxftype: str = ""
    #: Cómo **se ve**, para poder pintarla. No es su geometría: es la que el
    #: propio archivo dice que hay que dibujar, sacada de ezdxf al abrir
    #: (`virtual_entities()`), tesela ya hecha. Existe porque un plano ajeno
    #: sin sus cotas ni sus rayados se ve medio vacío y parece que se perdieron,
    #: cuando en realidad están enteros y salen intactos al exportar.
    #:
    #: **Nadie edita esto y nadie lo escribe al DXF.** Si alguien mueve la
    #: entidad, este dibujo se mueve con ella y ya; el archivo sigue mandando.
    dibujo: list = field(default_factory=list)      # [[[x, y], ...], ...]
    textos: list = field(default_factory=list)      # [{p, texto, altura, rotacion}]
    tipo: str = field(init=False, default="cruda")

    def caja(self):
        pts = [p for linea in self.dibujo for p in linea]
        pts += [t["p"] for t in self.textos if t.get("p")]
        return _caja_de_puntos(pts)


# --- Registro y fábrica ----------------------------------------------------

CLASES: dict[str, type] = {
    "linea": Linea,
    "polilinea": Polilinea,
    "circulo": Circulo,
    "arco": Arco,
    "elipse": Elipse,
    "spline": Spline,
    "punto": Punto,
    "solido": Solido,
    "cuerpo": Cuerpo,
    "texto": Texto,
    "textom": TextoM,
    "insercion": Insercion,
    "rayado": Rayado,
    "cota": Cota,
    "imagen": Imagen,
    "cruda": Cruda,
}


def de_dict(d: dict) -> Entidad:
    """Reconstruye una entidad desde su diccionario."""
    tipo = d.get("tipo", "linea")
    cls = CLASES.get(tipo)
    if cls is None:
        raise ValueError(f"Entidad desconocida en el archivo: {tipo!r}")
    campos = {k: v for k, v in d.items()
              if k in cls.__dataclass_fields__ and k != "tipo"}
    ent = cls(**campos)
    return ent
