"""Leer DXF  ·  feature 2   (y el gancho para DWG, feature 1, que es F7).

Regla de la casa: **nada se pierde en silencio.** Lo que el modelo entiende se
convierte a entidad nativa y se puede editar; lo que no, se anota como `Cruda`
—tipo y handle— y se queda donde está: el documento guarda el texto del DXF
original y al exportar se parte de él (ver `export/dxf.py`). El lector devuelve
además un informe de qué entró como qué, y la interfaz lo enseña. Un plano que
pierde capas al abrirse y no avisa es peor que uno que no abre.

Qué entra nativo hoy: LINE, LWPOLYLINE, POLYLINE (2D), CIRCLE, ARC, ELLIPSE,
POINT, SOLID, TEXT, MTEXT, INSERT, HATCH.

Qué entra como `Cruda` a propósito: SPLINE, DIMENSION, LEADER, MULTILEADER y
todo lo demás. No es descuido — reescribir una cota o una spline con nudos
propios las mueve un pelo, y un plano de taller no se puede mover un pelo. Se
promueven a nativas en F2 (spline) y F5 (cotas), cuando haya herramientas que
de verdad las editen.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile

import ezdxf

from . import capas as mod_capas
from . import dwg as mod_dwg
from . import unidades as mod_unidades
from . import entidades as ent_mod
from .capas import Capa
from .documento import Documento
from .entidades import Bloque

NATIVAS = {
    "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE",
    "POINT", "SOLID", "TEXT", "MTEXT", "INSERT", "HATCH",
}


class Informe:
    def __init__(self):
        self.nativas: dict[str, int] = {}
        self.preservadas: dict[str, int] = {}
        self.en_bloques: dict[str, int] = {}
        self.avisos: list[str] = []

    def suma(self, donde: dict, tipo: str) -> None:
        donde[tipo] = donde.get(tipo, 0) + 1

    def a_dict(self) -> dict:
        return {
            "nativas": self.nativas,
            "preservadas": self.preservadas,
            "en_bloques": self.en_bloques,
            "avisos": self.avisos,
            "total": sum(self.nativas.values()) + sum(self.preservadas.values()),
        }


# El DWG vive en `core/dwg.py`, que sabe de los tres motores. Aquí se
# reexporta lo que el resto del programa ya importaba de este módulo, para no
# ir cambiando imports por medio proyecto.
from .dwg import DWGNoDisponible, oda_disponible  # noqa: E402,F401


def _xy(v) -> list:
    """Vec3 de ezdxf → [x, y]. No admite rebanadas, y el CAD es 2D."""
    try:
        return [float(v.x), float(v.y)]
    except AttributeError:
        return [float(v[0]), float(v[1])]


def _llano(texto) -> str:
    """El texto que una persona lee, sin los códigos de formato del DXF.

    Un MTEXT no guarda «PLANTA»: guarda
    `{\\fRomanS_|V50|b1|i0|c0|p2;PLANTA}`, y una cota guarda `\\A1;3.00`. Si eso
    se pinta tal cual —y se pintaba— el plano se llena de basura y los rótulos
    dejan de leerse. Al **exportar** no se toca nada: lo que sale es el DXF
    original, con sus códigos enteros.
    """
    s = str(texto or "")
    if "\\" not in s and "{" not in s and "%%" not in s:
        return s
    try:
        from ezdxf.tools.text import plain_mtext
        return plain_mtext(s)
    except Exception:
        return s


#: Dónde se guardan las copias de los DXF de origen mientras el programa vive.
#: Se limpia solo al salir. Antes esto era una cadena dentro del documento; con
#: un plano de verdad eran 222 MB de memoria y 8 segundos al abrir, por algo que
#: sólo se usa al exportar.
_CARPETA_ORIGEN: str | None = None


def _guardar_origen(ruta: pathlib.Path) -> str:
    """Deja una copia del DXF de origen donde el documento pueda releerla."""
    global _CARPETA_ORIGEN
    if _CARPETA_ORIGEN is None:
        import atexit
        _CARPETA_ORIGEN = tempfile.mkdtemp(prefix="dibujador-origen-")
        atexit.register(shutil.rmtree, _CARPETA_ORIGEN, True)
    import uuid
    destino = pathlib.Path(_CARPETA_ORIGEN) / f"{uuid.uuid4().hex}.dxf"
    shutil.copyfile(ruta, destino)
    return str(destino)


def _texto_dxf(doc_dxf) -> str:
    """El dibujo completo como texto DXF, para poder reabrirlo tal cual."""
    import io
    buf = io.StringIO()
    doc_dxf.write(buf, fmt="asc")
    return buf.getvalue()


# --- Capas -----------------------------------------------------------------

def _color_de_capa(capa_dxf) -> str:
    try:
        if capa_dxf.rgb:
            return mod_capas.rgb_a_hex(capa_dxf.rgb)
    except Exception:
        pass
    aci = abs(capa_dxf.dxf.get("color", 7))
    try:
        from ezdxf.colors import aci2rgb
        return mod_capas.rgb_a_hex(aci2rgb(aci))
    except Exception:
        return "#FFFFFF"


def _leer_capas(doc_dxf, doc: Documento) -> None:
    doc.capas = {}
    for capa_dxf in doc_dxf.layers:
        nombre = capa_dxf.dxf.name
        try:
            grosor = int(capa_dxf.dxf.get("lineweight", 25))
        except Exception:
            grosor = 25
        if grosor < 0:
            grosor = 25
        capa = Capa(
            nombre=nombre,
            color=_color_de_capa(capa_dxf),
            grosor=mod_capas.grosor_valido(grosor),
            tipo_linea=(capa_dxf.dxf.get("linetype", "CONTINUOUS") or "CONTINUOUS").upper(),
            visible=capa_dxf.is_on(),
            bloqueada=capa_dxf.is_locked(),
            imprime=bool(capa_dxf.dxf.get("plot", 1)),
            descripcion=getattr(capa_dxf, "description", "") or "",
        )
        doc.capas[nombre] = capa
    if "0" not in doc.capas:
        doc.capas["0"] = Capa("0")


# --- Propiedades comunes ---------------------------------------------------

def _comunes(e_dxf) -> dict:
    d = {"capa": e_dxf.dxf.get("layer", "0"),
         "handle_origen": e_dxf.dxf.get("handle", "") or ""}
    tc = e_dxf.dxf.get("true_color", None)
    if tc is not None:
        r = (tc >> 16) & 0xFF; g = (tc >> 8) & 0xFF; b = tc & 0xFF
        d["color"] = mod_capas.rgb_a_hex((r, g, b))
    lw = e_dxf.dxf.get("lineweight", -1)
    if lw is not None and lw >= 0:
        d["grosor"] = int(lw)
    lt = (e_dxf.dxf.get("linetype", "BYLAYER") or "").upper()
    if lt and lt not in ("BYLAYER", "BYBLOCK"):
        d["tipo_linea"] = lt
    ls = e_dxf.dxf.get("ltscale", 1.0)
    if ls and ls != 1.0:
        d["escala_tl"] = float(ls)
    return d


# --- Conversión de entidades ----------------------------------------------

def _convertir(e_dxf, informe: Informe):
    t = e_dxf.dxftype()
    c = _comunes(e_dxf)
    try:
        if t == "LINE":
            return ent_mod.Linea(p1=_xy(e_dxf.dxf.start), p2=_xy(e_dxf.dxf.end), **c)
        if t == "LWPOLYLINE":
            pts = [[p[0], p[1], p[4] if len(p) > 4 else 0.0] for p in e_dxf.get_points()]
            return ent_mod.Polilinea(puntos=pts, cerrada=bool(e_dxf.closed), **c)
        if t == "POLYLINE":
            if e_dxf.get_mode() not in ("AcDb2dPolyline", "AcDb3dPolyline"):
                return None                       # mallas y superficies: van crudas
            pts = [[v.dxf.location.x, v.dxf.location.y, getattr(v.dxf, "bulge", 0.0)]
                   for v in e_dxf.vertices]
            return ent_mod.Polilinea(puntos=pts, cerrada=bool(e_dxf.is_closed), **c)
        if t == "CIRCLE":
            return ent_mod.Circulo(centro=_xy(e_dxf.dxf.center), radio=float(e_dxf.dxf.radius), **c)
        if t == "ARC":
            return ent_mod.Arco(centro=_xy(e_dxf.dxf.center), radio=float(e_dxf.dxf.radius),
                                ang_ini=float(e_dxf.dxf.start_angle),
                                ang_fin=float(e_dxf.dxf.end_angle), **c)
        if t == "ELLIPSE":
            return ent_mod.Elipse(centro=_xy(e_dxf.dxf.center),
                                  eje_mayor=_xy(e_dxf.dxf.major_axis),
                                  razon=float(e_dxf.dxf.ratio),
                                  param_ini=float(e_dxf.dxf.start_param),
                                  param_fin=float(e_dxf.dxf.end_param), **c)
        if t == "POINT":
            return ent_mod.Punto(p=_xy(e_dxf.dxf.location), **c)
        if t == "SOLID":
            pts = []
            for nombre in ("vtx0", "vtx1", "vtx2", "vtx3"):
                v = e_dxf.dxf.get(nombre, None)
                if v is not None:
                    pts.append(_xy(v))
            return ent_mod.Solido(puntos=pts, **c)
        if t == "TEXT":
            return ent_mod.Texto(p=_xy(e_dxf.dxf.insert), texto=_llano(e_dxf.dxf.text),
                                 altura=float(e_dxf.dxf.height),
                                 rotacion=float(e_dxf.dxf.get("rotation", 0.0)),
                                 estilo=e_dxf.dxf.get("style", "Standard"), **c)
        if t == "MTEXT":
            return ent_mod.TextoM(p=_xy(e_dxf.dxf.insert), texto=_llano(e_dxf.text),
                                  altura=float(e_dxf.dxf.char_height),
                                  ancho=float(e_dxf.dxf.get("width", 0.0)),
                                  rotacion=float(e_dxf.dxf.get("rotation", 0.0)),
                                  estilo=e_dxf.dxf.get("style", "Standard"),
                                  adjunto=int(e_dxf.dxf.get("attachment_point", 1)), **c)
        if t == "INSERT":
            attrs = {}
            for at in e_dxf.attribs:
                attrs[at.dxf.tag] = at.dxf.text
            return ent_mod.Insercion(bloque=e_dxf.dxf.name, p=_xy(e_dxf.dxf.insert),
                                     escala=[float(e_dxf.dxf.get("xscale", 1.0)),
                                             float(e_dxf.dxf.get("yscale", 1.0))],
                                     rotacion=float(e_dxf.dxf.get("rotation", 0.0)),
                                     atributos=attrs, **c)
        if t == "HATCH":
            rutas = []
            for ruta in e_dxf.paths:
                try:
                    verts = [[v[0], v[1], v[2] if len(v) > 2 else 0.0]
                             for v in ruta.vertices]
                except AttributeError:
                    # Contorno por **aristas** (líneas, arcos, elipses, splines).
                    # Es lo normal en un plano de arquitectura de verdad: el
                    # primer DWG ajeno que entró traía 77 rayados y los 77 eran
                    # así. Se aplanan a vértices, que es lo que necesitamos para
                    # pintarlos y para saber dónde están.
                    from ezdxf.path import from_hatch_boundary_path
                    p = from_hatch_boundary_path(ruta)
                    verts = [[v.x, v.y, 0.0] for v in p.flattening(FINURA)]
                if verts:
                    rutas.append(verts)
            if not rutas:
                return None
            solido = e_dxf.dxf.get("solid_fill", 1) == 1
            return ent_mod.Rayado(rutas=rutas,
                                  patron=e_dxf.dxf.get("pattern_name", "SOLID"),
                                  escala=float(e_dxf.dxf.get("pattern_scale", 1.0)),
                                  angulo=float(e_dxf.dxf.get("pattern_angle", 0.0)),
                                  solido=solido, **c)
    except Exception as exc:
        informe.avisos.append(f"{t} no se pudo convertir ({exc}); se preservó tal cual")
        return None
    return None


#: Cuánto se afina al teselar curvas ajenas, en unidades del dibujo. Fino
#: importa poco en pantalla y mucho al imprimir; 0.1 mm no lo distingue nadie.
FINURA = 0.1


def _como_se_ve(e_dxf) -> tuple[list, list]:
    """Cómo se dibuja una entidad que no modelamos: líneas ya teseladas y textos.

    Lo saca del propio archivo con `virtual_entities()`, que es lo que ezdxf
    usa para «explotar» una cota, un multilíder o un rayado en las rayas que
    de verdad se pintan. **No es su geometría** —no se le hace osnap, no se
    edita, no se escribe al DXF— es sólo para verla.

    Sin esto, un plano ajeno abre con sus cotas y sus rayados invisibles. Están
    ahí, salen intactos al exportar, pero en pantalla parece que se perdieron, y
    parecer que se perdieron es casi tan malo como perderlos.
    """
    lineas: list = []
    textos: list = []

    def agregar(sub):
        st = sub.dxftype()
        try:
            if st == "LINE":
                lineas.append([_xy(sub.dxf.start), _xy(sub.dxf.end)])
            elif st == "LWPOLYLINE":
                pts = [[p[0], p[1]] for p in sub.get_points()]
                if sub.closed and pts:
                    pts = pts + [pts[0]]
                if len(pts) >= 2:
                    lineas.append(pts)
            elif st == "POLYLINE":
                pts = [[v.dxf.location.x, v.dxf.location.y] for v in sub.vertices]
                if len(pts) >= 2:
                    lineas.append(pts)
            elif st in ("ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
                from ezdxf.path import make_path
                p = make_path(sub)
                pts = [[v.x, v.y] for v in p.flattening(FINURA)]
                if len(pts) >= 2:
                    lineas.append(pts)
            elif st == "SOLID":
                pts = []
                for nombre in ("vtx0", "vtx1", "vtx3", "vtx2"):   # el orden del DXF
                    v = sub.dxf.get(nombre, None)
                    if v is not None:
                        pts.append(_xy(v))
                if len(pts) >= 3:
                    lineas.append(pts + [pts[0]])
            elif st in ("TEXT", "MTEXT", "ATTRIB"):
                txt = sub.text if st == "MTEXT" else sub.dxf.get("text", "")
                if txt:
                    textos.append({
                        "p": _xy(sub.dxf.insert),
                        "texto": _llano(txt),
                        "altura": float(sub.dxf.get("char_height", None)
                                        or sub.dxf.get("height", 2.5)),
                        "rotacion": float(sub.dxf.get("rotation", 0.0) or 0.0),
                    })
        except Exception:
            pass            # una raya de más o de menos no vale una excepción

    try:
        virtuales = list(e_dxf.virtual_entities())
    except Exception:
        virtuales = []
    for sub in virtuales:
        agregar(sub)

    # Una cota o un multilíder son varias cosas y `virtual_entities()` las
    # devuelve. Una **spline** no: es una sola, y ese método no le aplica. Se
    # aplana ella misma. Es el caso más común de todos — un plano de
    # arquitectura viene lleno de splines.
    if not lineas and not textos:
        agregar(e_dxf)

    # Una tabla (ACAD_TABLE) no siempre da entidades virtuales: es un objeto
    # propietario y lo que lleva dentro es texto en celdas. Se saca celda por
    # celda — una tabla de acabados sin sus letras es una cuadrícula vacía.
    if not textos and e_dxf.dxftype() == "ACAD_TABLE":
        try:
            for fila in range(int(e_dxf.dxf.n_rows)):
                for col in range(int(e_dxf.dxf.n_cols)):
                    try:
                        celda = e_dxf.get_text(fila, col)
                    except Exception:
                        celda = ""
                    if celda:
                        textos.append({"p": _xy(e_dxf.dxf.insert),
                                       "texto": _llano(celda), "altura": 2.5,
                                       "rotacion": 0.0, "celda": [fila, col]})
        except Exception:
            pass

    # Un rayado sólido no tiene entidades virtuales: lo que se ve es su
    # contorno, y ése sí se puede sacar de los caminos del contorno.
    if not lineas and e_dxf.dxftype() == "HATCH":
        try:
            from ezdxf.path import from_hatch_boundary_path
            for ruta in e_dxf.paths:
                p = from_hatch_boundary_path(ruta)
                pts = [[v.x, v.y] for v in p.flattening(FINURA)]
                if len(pts) >= 2:
                    lineas.append(pts)
        except Exception:
            pass

    return lineas, textos


#: Cómo se alinea un TEXT/ATTRIB del DXF, en nuestros términos.
_ALINEACION = {0: "IZQ", 1: "CENTRO", 2: "DER", 3: "IZQ", 4: "CENTRO", 5: "DER"}


def _texto_de_atributo(at, informe: Informe):
    """Un ATTRIB de un bloque, como texto nuestro — visible y editable.

    **Aquí faltaba la mitad de los rótulos de un plano de verdad.** Un bloque
    con atributos —una etiqueta de carpintería, el número de un local, un campo
    del pie de plano— guarda su dibujo en la definición del bloque y su
    **texto** en cada inserción, como ATTRIB. Se leían y se guardaban en la
    inserción, pero nadie los pintaba: en el DWG de Mondelez eran **1 316
    etiquetas** —las `CA-23` de cada mueble— que sencillamente no salían.

    Se traen como texto suelto, no como parte de la inserción, por lo que pidió
    Mike: *«¿hay manera de conservar esos dibujos y volverlos editables?»*. Un
    atributo suelto se pica, se mueve y se corrige como cualquier otro texto.
    El precio, dicho para que no sorprenda: al exportar salen como TEXT y no
    como ATTRIB de su bloque.
    """
    try:
        # Bit 1 de `flags`: atributo invisible. AutoCAD no lo enseña, así que
        # aquí tampoco — pero se trae, para no perderlo en silencio.
        oculto = bool(int(at.dxf.get("invisible", 0) or 0)) or \
            bool(int(at.dxf.get("flags", 0) or 0) & 1)
        p = _xy(at.dxf.insert)
        # Un texto centrado o a la derecha guarda su punto de verdad en
        # `align_point`; el `insert` se queda donde estaba antes de alinearlo.
        halign = int(at.dxf.get("halign", 0) or 0)
        if halign in (1, 2, 3, 4, 5):
            try:
                p = _xy(at.dxf.align_point)
            except Exception:
                pass
        texto = _llano(at.dxf.get("text", ""))
        if not texto:
            return None
        e = ent_mod.Texto(
            p=p, texto=texto,
            altura=float(at.dxf.get("height", 2.5) or 2.5),
            rotacion=float(at.dxf.get("rotation", 0.0) or 0.0),
            alineacion=_ALINEACION.get(halign, "IZQ"),
            estilo=at.dxf.get("style", "Standard"),
            **_comunes(at))
        e.visible = not oculto
        # De dónde salió, para poder decirlo y para no confundirlo con un texto
        # que alguien escribió a mano.
        e.origen = "atributo"
        informe.suma(informe.nativas, "ATTRIB")
        return e
    except Exception:
        return None


def _cargar_entidades(espacio, doc: Documento, informe: Informe, destino: list | None = None):
    en_bloque = destino is not None
    for e_dxf in espacio:
        t = e_dxf.dxftype()
        # Los atributos de una inserción son texto que hay que pintar, y en un
        # plano de obra son los rótulos que más importan. Ver `_texto_de_atributo`.
        if t == "INSERT":
            for at in getattr(e_dxf, "attribs", []) or []:
                texto = _texto_de_atributo(at, informe)
                if texto is None:
                    continue
                if en_bloque:
                    destino.append(texto)
                else:
                    doc.entidades[texto.id] = texto
                    doc.orden.append(texto.id)
        ent = _convertir(e_dxf, informe) if t in NATIVAS else None
        if ent is None:
            lineas, textos = _como_se_ve(e_dxf)
            ent = ent_mod.Cruda(dxftype=t, dibujo=lineas, textos=textos,
                                **_comunes(e_dxf))
            informe.suma(informe.en_bloques if en_bloque else informe.preservadas, t)
        else:
            informe.suma(informe.en_bloques if en_bloque else informe.nativas, t)
        if en_bloque:
            destino.append(ent)
        else:
            doc.entidades[ent.id] = ent
            doc.orden.append(ent.id)


# =========================================================================
# Los planos del archivo ajeno  ·  layouts de espacio papel
# =========================================================================
# Un DWG de arquitecto no trae sólo el modelo: trae las **hojas** ya armadas
# —el A1 con sus seis ventanas, cada una a su escala, y el pie de plano de esa
# oficina—. Eso es la mitad del trabajo de un plano, y hasta aquí se tiraba a
# la basura al abrir: nos quedábamos con el modelo y con nuestras hojas vacías.
#
# Lo que se importa:
#   · el tamaño del papel, ya girado (`plot_rotation`);
#   · cada VIEWPORT como una de nuestras ventanas, con su encuadre y su escala
#     sacada de `alto de la ventana / altura de vista`;
#   · las capas que esa ventana congela, que en un plano de verdad son la
#     diferencia entre ver la instalación eléctrica o no verla;
#   · **lo dibujado en la hoja**: su marco, su pie de plano, sus notas. Se
#     guarda como un bloque `*PAPEL_…` y la hoja lo pinta en vez de nuestro
#     rótulo. Sin esto la hoja importada se ve con el pie de Taller 101 encima
#     del de ellos, que es peor que no importarla.
#
# Lo que NO se importa, a propósito: la configuración de trazado (plotter,
# tabla de plumillas, márgenes de la impresora). Eso es de la máquina de esa
# oficina, no del plano.

#: Prefijo de los bloques donde se guarda lo dibujado en una hoja ajena. El
#: `*` no es adorno: `export/dxf.py` ya se salta los bloques que empiezan así,
#: porque son bloques de sistema y no se reescriben.
PREFIJO_PAPEL = "*PAPEL_"


def _formato_de(ancho: float, alto: float) -> str:
    """Qué formato de los nuestros es este papel, o CUSTOM."""
    from . import papel as mod_papel
    for nombre, (a, b) in mod_papel.FORMATOS.items():
        if abs(a - ancho) <= 1.5 and abs(b - alto) <= 1.5:
            return nombre
    return mod_papel.CUSTOM


def _medidas_hoja(lay) -> tuple[float, float]:
    """Ancho y alto del papel de un layout, en milímetros y ya girado.

    `paper_width`/`paper_height` vienen sin girar y `plot_rotation` dice cuánto
    gira la hoja al imprimirse; lo dibujado en la hoja, en cambio, ya está en
    el sistema girado. Quien tiene la verdad es LIMMAX cuando trae algo, y por
    eso manda: si se toma el papel sin girar, un A1 apaisado se importa como
    A1 vertical y el pie de plano se sale de la hoja.
    """
    d = lay.dxf_layout.dxf
    k = 25.4 if int(d.get("plot_paper_units", 1) or 1) == 0 else 1.0
    ancho = float(d.get("paper_width", 0) or 0) * k
    alto = float(d.get("paper_height", 0) or 0) * k
    if int(d.get("plot_rotation", 0) or 0) % 2 == 1:
        ancho, alto = alto, ancho
    try:
        lmax = d.get("limmax", None)
        lx, ly = float(lmax[0]) * k, float(lmax[1]) * k
        if lx > 10 and ly > 10:
            ancho, alto = lx, ly
    except (TypeError, IndexError, ValueError):
        pass
    if not (ancho > 10 and alto > 10):
        from . import papel as mod_papel
        ancho, alto = mod_papel.FORMATOS["A3"]
    return round(ancho, 3), round(alto, 3)


def _ventanas_de(lay, ancho: float, alto: float, factor: float) -> list[dict]:
    """Los VIEWPORT de la hoja, como ventanas nuestras."""
    from . import papel as mod_papel
    salida: list[dict] = []
    for vp in lay.viewports():
        try:
            va = float(vp.dxf.width)
            vh = float(vp.dxf.height)
            cx, cy = float(vp.dxf.center[0]), float(vp.dxf.center[1])
            altura_vista = float(vp.dxf.view_height)
        except (AttributeError, TypeError, ValueError):
            continue
        if va <= 0 or vh <= 0 or altura_vista <= 0:
            continue
        # El primer VIEWPORT de toda hoja no es una ventana: es el propio
        # espacio papel, y mide más que el papel. Si se importa, la hoja sale
        # con el modelo entero encima del pie de plano.
        if va > ancho * 1.02 or vh > alto * 1.02:
            continue
        if int(vp.dxf.get("status", 1) or 0) < 0:
            continue                    # ventana apagada en el original
        # Sólo se importan ventanas en planta. Una ventana en isométrica se
        # vería mal aquí —somos 2D— y es mejor no traerla que traerla torcida.
        dv = vp.dxf.get("view_direction_vector", (0, 0, 1))
        try:
            if abs(float(dv[0])) > 1e-6 or abs(float(dv[1])) > 1e-6:
                continue
        except (TypeError, IndexError, ValueError):
            pass
        # **El encuadre no es `view_center_point` a secas.** Ese punto está
        # medido desde el objetivo de la vista (`view_target_point`), y en un
        # plano de verdad el objetivo casi nunca es el origen: si se ignora, la
        # ventana encuadra un pedazo de terreno vacío y la hoja sale en blanco.
        vc = vp.dxf.get("view_center_point", (0, 0, 0))
        vt = vp.dxf.get("view_target_point", (0, 0, 0))
        centro = [(float(vc[0]) + float(vt[0])) * factor,
                  (float(vc[1]) + float(vt[1])) * factor]
        # La escala es el denominador: cuántos milímetros de dibujo caben en
        # uno de papel.
        escala = (altura_vista * factor) / vh
        v = mod_papel.ventana_nueva(cx - va / 2, cy - vh / 2, va, vh, centro,
                                    round(escala, 6))
        v["rotacion"] = -float(vp.dxf.get("view_twist_angle", 0.0) or 0.0)
        v["marco"] = False              # la hoja ajena trae su propio marco
        congeladas = [str(c) for c in (vp.frozen_layers or [])]
        if congeladas:
            v["capas_apagadas"] = congeladas
        salida.append(v)
    return salida


def _leer_layouts(doc_dxf, doc: Documento, informe: Informe) -> None:
    """Trae las hojas del archivo ajeno a `doc.layouts`."""
    from . import papel as mod_papel
    factor = float(doc.factor_unidades or 1.0)
    traidas = 0
    for lay in doc_dxf.layouts:
        if lay.name.lower() == "model":
            continue
        try:
            ancho, alto = _medidas_hoja(lay)
            L = mod_papel.layout_nuevo(lay.name, _formato_de(ancho, alto))
            if L["formato"] == mod_papel.CUSTOM:
                L["ancho"], L["alto"] = ancho, alto
            L["ventanas"] = _ventanas_de(lay, ancho, alto, factor)
            L["ajeno"] = True
            L["rotulo"]["dibujo"] = lay.name

            # Lo dibujado en la hoja: marco, pie de plano, notas. Va a un
            # bloque para que se tesele con las capas de ahora y no con las de
            # cuando se abrió — prender una capa tiene que cambiar la hoja
            # igual que cambia el modelo.
            sub: list = []
            _cargar_entidades((e for e in lay if e.dxftype() != "VIEWPORT"),
                              doc, informe, destino=sub)
            if sub:
                nombre_bloque = PREFIJO_PAPEL + lay.name
                doc.bloques[nombre_bloque] = Bloque(
                    nombre=nombre_bloque, base=[0.0, 0.0], entidades=sub)
                L["bloque_papel"] = nombre_bloque
            doc.layouts.append(L)
            traidas += 1
        except Exception as exc:            # una hoja rota no tira el archivo
            informe.avisos.append(f"No se pudo leer la hoja «{lay.name}»: {exc}")
    if traidas:
        ventanas = sum(len(L.get("ventanas") or []) for L in doc.layouts)
        informe.avisos.append(
            f"Se importaron {traidas} hoja(s) del archivo, con {ventanas} "
            "ventana(s) y su pie de plano. Están en las pestañas de abajo."
        )


# =========================================================================
# Referencias externas (XREF)
# =========================================================================
# Un XREF es un plano **que vive en otro archivo**. El DWG guarda el bloque
# vacío y la ruta a ese archivo; el dibujo está allá. En el DWG de Mondelez el
# fondo de arquitectura entero —muros, ejes, columnas— es un solo XREF, y por
# eso faltaba: no es que se ignorara, es que no venía.
#
# Ahora se va a buscar. Si el archivo referido está donde el DWG dice que está
# —o al lado—, se abre y su dibujo se mete en el bloque, y con eso aparece.
# Cuesta lo que cuesta abrir ese otro archivo, que es lo que Mike aceptó de
# antemano: *«aunque se tarde un par de segundos más en abrir»*.
#
# Lo que NO se hace: buscarlo por todo el disco. Un archivo con el nombre
# correcto en otra carpeta puede ser otra revisión del plano, y montar la
# revisión equivocada del fondo de arquitectura es peor que no montar ninguna.

#: Hasta dónde se sigue la cadena. Un XREF puede referir a otro; tres niveles
#: es más de lo que se ve en un proyecto de verdad, y corta cualquier ciclo.
XREF_PROFUNDIDAD = 3


def _candidatos_xref(carpeta: pathlib.Path, ruta_dicha: str) -> list[pathlib.Path]:
    """Dónde puede estar el archivo de un XREF, en orden de confianza."""
    ruta_dicha = (ruta_dicha or "").strip().replace("\\", "/")
    if not ruta_dicha:
        return []
    nombre = pathlib.PurePosixPath(ruta_dicha).name
    fuera = []
    # 1. La ruta que dice el archivo, resuelta desde donde está el plano.
    fuera.append((carpeta / ruta_dicha).resolve())
    # 2. El mismo nombre, al lado del plano. Es lo que pasa cuando alguien
    #    manda el conjunto por correo y se guarda todo en una carpeta.
    fuera.append(carpeta / nombre)
    # 3. Y con la extensión cambiada: hay quien manda el DXF del fondo.
    base = pathlib.PurePosixPath(nombre).stem
    for ext in (".dwg", ".DWG", ".dxf", ".DXF"):
        fuera.append(carpeta / (base + ext))
    vistos, unicos = set(), []
    for p in fuera:
        if str(p) not in vistos:
            vistos.add(str(p))
            unicos.append(p)
    return unicos


def _resolver_xrefs(doc: Documento, informe: Informe, carpeta: pathlib.Path,
                    profundidad: int = XREF_PROFUNDIDAD) -> None:
    """Rellena los bloques de XREF con el dibujo del archivo al que apuntan."""
    pendientes = [(n, r) for n, r in (doc.xrefs or {}).items()
                  if not doc.bloques.get(n) or not doc.bloques[n].entidades]
    if not pendientes:
        return
    if profundidad <= 0:
        informe.avisos.append(
            "Hay referencias externas anidadas muy hondo: no se siguieron más.")
        return

    resueltos, sin_hallar = [], []
    for nombre, ruta_dicha in pendientes:
        archivo = next((p for p in _candidatos_xref(carpeta, ruta_dicha) if p.is_file()), None)
        if archivo is None:
            sin_hallar.append((nombre, ruta_dicha))
            continue
        try:
            hijo, _ = leer(archivo, _profundidad=profundidad - 1)
        except Exception as exc:
            informe.avisos.append(
                f"La referencia externa «{nombre}» está en {archivo.name} pero no "
                f"se pudo abrir: {exc}")
            continue

        # Sus capas entran con el prefijo del XREF, como en AutoCAD: así se
        # pueden apagar todas de un golpe y no se pisan con las de aquí.
        renombre = {}
        for cn, capa in hijo.capas.items():
            nuevo = cn if cn.startswith(nombre + "|") else f"{nombre}|{cn}"
            renombre[cn] = nuevo
            if nuevo not in doc.capas:
                copia = Capa.de_dict(capa.a_dict())
                copia.nombre = nuevo
                doc.capas[nuevo] = copia
        # Y sus bloques, para que sus inserciones encuentren qué dibujar.
        for bn, bl in hijo.bloques.items():
            if bn not in doc.bloques:
                for sub in bl.entidades:
                    sub.capa = renombre.get(sub.capa, sub.capa)
                doc.bloques[bn] = bl

        dentro = []
        for e in hijo.lista():
            if getattr(e, "espacio", ""):
                continue          # lo que estaba en las hojas del hijo no entra
            e.capa = renombre.get(e.capa, e.capa)
            e.origen = "xref"
            dentro.append(e)
        doc.bloques[nombre] = Bloque(nombre=nombre, base=[0.0, 0.0], entidades=dentro)
        resueltos.append((nombre, len(dentro), archivo))

    if resueltos:
        detalle = ", ".join(f"«{n}» ({c} entidades)" for n, c, _ in resueltos)
        informe.avisos.append(
            f"Se abrieron {len(resueltos)} referencia(s) externa(s) y su dibujo "
            f"ya se ve: {detalle}. Entran como bloque, con sus capas "
            "prefijadas; se ven y se pueden apagar, pero se editan en su propio "
            "archivo.")
    if sin_hallar:
        detalle = "; ".join(f"«{n}» → {r}" for n, r in sin_hallar[:3])
        informe.avisos.append(
            f"Faltan {len(sin_hallar)} referencia(s) externa(s): {detalle}"
            + ("…" if len(sin_hallar) > 3 else "")
            + ". Lo que dibujan está en esos archivos, no en éste. Ponlos donde "
            "dice la ruta, o al lado de este plano, y vuelve a abrirlo.")


def leer_dxf(ruta: str | pathlib.Path, carpeta: pathlib.Path | None = None,
             _profundidad: int = XREF_PROFUNDIDAD) -> tuple[Documento, Informe]:
    ruta = pathlib.Path(ruta)
    from . import progreso
    progreso.poner(f"Leyendo el DXF ({ruta.stat().st_size / 1e6:.0f} MB)…")
    doc_dxf = ezdxf.readfile(str(ruta))
    doc = Documento(con_plantilla=False)
    informe = Informe()
    doc.historial.silencio = True
    try:
        doc.nombre = ruta.stem
        # El archivo tal cual. Al exportar se parte de aquí, así que las cotas,
        # splines y objetos de otros programas salen intactos. Se guarda una
        # copia en disco, no el texto en memoria: ver `Documento.origen_dxf`.
        doc.origen_dxf_ruta = _guardar_origen(ruta)
        _leer_capas(doc_dxf, doc)

        for est in doc_dxf.styles:
            doc.estilos_texto[est.dxf.name] = {
                "nombre": est.dxf.name,
                "fuente": est.dxf.get("font", ""),
                "archivo": est.dxf.get("font", ""),
                "altura": float(est.dxf.get("height", 0.0)),
                "ancho": float(est.dxf.get("width", 1.0)),
                "oblicuo": float(est.dxf.get("oblique", 0.0)),
            }

        for ds in doc_dxf.dimstyles:
            doc.estilos_cota[ds.dxf.name] = {
                "nombre": ds.dxf.name,
                "estilo_texto": ds.dxf.get("dimtxsty", "Standard"),
                "altura_texto": float(ds.dxf.get("dimtxt", 2.5)),
                "tam_flecha": float(ds.dxf.get("dimasz", 2.0)),
                "ext_linea": float(ds.dxf.get("dimexe", 1.25)),
                "hueco_origen": float(ds.dxf.get("dimexo", 0.625)),
                "decimales": int(ds.dxf.get("dimdec", 0)),
                "factor_escala": float(ds.dxf.get("dimscale", 1.0)),
            }

        xrefs: list[str] = []
        for blk in doc_dxf.blocks:
            # Se saltan el modelo y las hojas, que no son bloques de verdad —
            # pero **no** los anónimos `*U…`, `*D…`, `*X…`. Ésos sí tienen
            # geometría: son lo que AutoCAD arma solo al hacer una matriz o al
            # explotar una cota, y saltárselos dejaba huecos en el plano. En el
            # DWG de Mondelez eran 43 inserciones apuntando a la nada.
            n = blk.name.upper()
            if n.startswith("*MODEL_SPACE") or n.startswith("*PAPER_SPACE"):
                continue
            # Una referencia externa (XREF) es un archivo aparte que aquí no
            # está: el bloque existe pero viene vacío. Se dice, no se calla.
            try:
                if blk.block is not None and blk.block.dxf.get("flags", 0) & 4:
                    xrefs.append(blk.name)
                    # La ruta al archivo de verdad: es lo que después permite
                    # ir a buscarlo. Ver `_resolver_xrefs`.
                    doc.xrefs[blk.name] = str(blk.block.dxf.get("xref_path", "") or "")
            except Exception:
                pass
            sub: list = []
            _cargar_entidades(blk, doc, informe, destino=sub)
            doc.bloques[blk.name] = Bloque(
                nombre=blk.name,
                base=_xy(blk.block.dxf.base_point) if blk.block else [0.0, 0.0],
                entidades=sub,
            )

        progreso.poner("Importando el modelo…")
        _cargar_entidades(doc_dxf.modelspace(), doc, informe)
        ent_mod.sembrar_contador(doc.entidades.values())
        if doc.capa_activa not in doc.capas:
            doc.capa_activa = "0"
        # A milímetros, si el archivo viene en otra unidad  ·  ver core/unidades.py
        insunits = None
        try:
            insunits = int(doc_dxf.header.get("$INSUNITS", 0) or 0)
        except (TypeError, ValueError):
            insunits = None
        doc.insunits_origen = insunits
        conv = mod_unidades.a_milimetros(doc, insunits)
        if conv["convertido"]:
            informe.avisos.append(
                f"El plano venía en {conv['unidad']}: se convirtió a milímetros "
                f"(x{conv['factor']:g}). Al exportar se devuelve como vino."
            )
        elif conv.get("medida_absurda"):
            informe.avisos.append(
                f"El archivo dice estar en {conv['unidad']}, pero con esa unidad "
                f"el plano mediría {conv['medida_absurda'] / 1000:,.0f} m. No se "
                "convirtió: se deja como viene. Si las medidas salen raras, es esto."
            )
        elif insunits in (0, None):
            informe.avisos.append(
                "El archivo no dice en qué unidad está. Se toma como milímetros; "
                "si las cotas salen mil veces más chicas, era metros."
            )
        # Las hojas, al final: necesitan el factor de unidades ya resuelto para
        # traducir el encuadre de cada ventana, que está en unidades del modelo.
        progreso.poner("Importando las hojas…")
        _leer_layouts(doc_dxf, doc, informe)

        # Y las referencias externas, que son archivos aparte: se van a buscar
        # donde el plano dice que están.  ·  ver `_resolver_xrefs`
        if doc.xrefs:
            progreso.poner("Buscando las referencias externas…")
        _resolver_xrefs(doc, informe, pathlib.Path(carpeta or ruta.parent),
                        _profundidad)
    finally:
        doc.historial.silencio = False
    doc.sucio = False
    return doc, informe


# --- DWG  ·  feature 1 (F7) ------------------------------------------------

def leer_dwg(ruta: str | pathlib.Path,
             _profundidad: int = XREF_PROFUNDIDAD) -> tuple[Documento, Informe]:
    """DWG → DXF por el mejor motor que haya, y de ahí el camino normal.

    Ver `core/dwg.py`: ODA si está instalado, si no LibreDWG, si no acad-ts.
    No hace falta instalar nada para que esto funcione.
    """
    ruta = pathlib.Path(ruta)
    with tempfile.TemporaryDirectory() as tmp:
        convertido = pathlib.Path(tmp) / (ruta.stem + ".dxf")
        r = mod_dwg.a_dxf(ruta, convertido)
        motor, apagadas = r["motor"], r["apagadas"]
        # La carpeta que importa es la del DWG, no la del DXF de paso: es donde
        # están los archivos de sus referencias externas.
        doc, informe = leer_dxf(convertido, carpeta=ruta.parent,
                                _profundidad=_profundidad)

    # **El apagado de capas del DXF de LibreDWG no sirve.** LibreDWG escribe el
    # color de capa en negativo, y en DXF eso quiere decir «apagada»: un plano
    # ajeno abría con todas las capas apagadas, o sea en blanco, y parecía que
    # lo habíamos perdido. Quien tiene la verdad es acad-ts, y `core/dwg.py` se
    # la pregunta. Si no se pudo averiguar (`None`), se encienden todas: una
    # capa encendida de más se apaga con dos clics.
    if motor == "libredwg":
        apagadas_set = {n.upper() for n in (apagadas or [])}
        cambiadas = 0
        for nombre, capa in doc.capas.items():
            debe = nombre.upper() not in apagadas_set
            if capa.visible != debe:
                capa.visible = debe
                cambiadas += 1
        if cambiadas:
            informe.avisos.append(
                f"Se corrigió el encendido de {cambiadas} capa(s): el conversor "
                "las marca apagadas de más."
                # Ojo: `None` es «no se pudo averiguar»; una lista vacía es
                # «se averiguó, y ninguna estaba apagada». Confundirlos hace que
                # el aviso mienta.
                + (" No se pudo leer el estado real, así que quedaron todas "
                   "encendidas." if apagadas is None else "")
            )

    # El nombre y la ruta son los del DWG, no los del DXF de paso.
    doc.ruta = None                 # un DWG no se guarda encima sin decirlo
    doc.nombre = ruta.name
    doc.origen_dwg = str(ruta)
    informe.avisos.append(
        f"DWG leído con {NOMBRE_MOTOR.get(motor, motor)}."
        + ("" if motor == "oda" else
           " Si algo del plano no se ve como en AutoCAD, dilo: el DWG es "
           "formato cerrado y estos motores lo leen por ingeniería inversa.")
    )
    return doc, informe


#: Cómo se llama cada motor cuando se lo enseñamos a una persona.
NOMBRE_MOTOR = {
    "oda": "el ODA File Converter",
    "libredwg": "LibreDWG",
    "acad-ts": "acad-ts (el motor de respaldo, para DWG de 2007)",
}


def leer(ruta: str | pathlib.Path,
         _profundidad: int = XREF_PROFUNDIDAD) -> tuple[Documento, Informe]:
    ruta = pathlib.Path(ruta)
    # Si ya se leyó este mismo archivo y no cambió, se recupera lo leído: dos
    # segundos en vez de un minuto. Ver `core/cache_apertura.py`.
    from . import cache_apertura, progreso
    try:
        progreso.poner("Buscando en la caché…")
        guardado = cache_apertura.leer(ruta)
        if guardado is not None:
            return guardado
        if ruta.suffix.lower() == ".dwg":
            salida = leer_dwg(ruta, _profundidad=_profundidad)
        else:
            salida = leer_dxf(ruta, _profundidad=_profundidad)
        progreso.poner("Guardando en la caché para la próxima vez…")
        cache_apertura.guardar(ruta, *salida)
        return salida
    finally:
        progreso.limpiar()
