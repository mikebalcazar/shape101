"""Escribir DXF  ·  feature 4.

Sale **DXF ASCII R2013 (AC1027)**. Lo abren AutoCAD 2013 en adelante, Rhino,
BricsCAD, LibreCAD, QCAD, Illustrator, Inkscape y Fusion, y soporta todo lo que
la hoja de ruta va a necesitar: MTEXT, HATCH, DIMENSION, bloques, layouts y
viewports. R2018 no agrega nada que usemos y corta versiones viejas.

## Cómo se conserva lo que no modelamos

Hay dos caminos, y el que se toma depende de si el dibujo vino de un archivo:

**Dibujo abierto de un DXF/DWG** → se parte del **archivo original**. Se borran
de él las entidades que sí modelamos (para volver a escribirlas desde nuestro
modelo, ya editadas) y **se deja intacto todo lo demás**: cotas, splines,
bloques anónimos, objetos propietarios de otros programas, tablas de estilos.
No se reconstruye nada, así que no hay nada que pueda salir mal.

**Dibujo nuevo** → se arma un DXF desde cero.

La primera versión de este módulo reconstruía las entidades ajenas desde sus
tags. Funcionaba con splines y se rompía con las cotas: una cota vive a medias
en un bloque anónimo con su propio handle, y al revivirla chocaban los handles
y el archivo quedaba sucio. Devolverle a un arquitecto su plano sin cotas es
exactamente el error que este módulo existe para no cometer.
"""

from __future__ import annotations

import io
import math
import pathlib

import ezdxf

from core import capas as mod_capas
from core import config
from core.documento import Documento


class ResultadoEscritura:
    def __init__(self):
        self.escritas = 0
        self.preservadas = 0
        self.perdidas: list[str] = []
        self.avisos: list[str] = []

    def a_dict(self) -> dict:
        return {"escritas": self.escritas, "preservadas": self.preservadas,
                "perdidas": self.perdidas, "avisos": self.avisos}

    def __repr__(self):
        return (f"<DXF {self.escritas} escritas, {self.preservadas} preservadas, "
                f"{len(self.perdidas)} perdidas>")


def _rgb(color_hex: str) -> int:
    return ezdxf.rgb2int(mod_capas.hex_a_rgb(color_hex))


# --- Tablas ----------------------------------------------------------------

def _preparar_capas(doc_dxf, doc: Documento) -> None:
    for capa in doc.capas.values():
        if capa.nombre in doc_dxf.layers:
            capa_dxf = doc_dxf.layers.get(capa.nombre)
        else:
            capa_dxf = doc_dxf.layers.add(capa.nombre)
        capa_dxf.rgb = mod_capas.hex_a_rgb(capa.color)
        capa_dxf.dxf.lineweight = mod_capas.grosor_valido(capa.grosor)
        tl = _nombre_tipo_linea(doc_dxf, capa.tipo_linea)
        if tl:
            capa_dxf.dxf.linetype = tl
        capa_dxf.dxf.plot = 1 if capa.imprime else 0
        try:
            capa_dxf.description = capa.descripcion
        except Exception:
            pass
        capa_dxf.on() if capa.visible else capa_dxf.off()
        capa_dxf.lock() if capa.bloqueada else capa_dxf.unlock()

    # Capas que el usuario borró y que venían del archivo original.
    for nombre in [c.dxf.name for c in doc_dxf.layers]:
        if nombre in doc.capas or nombre in ("0", "Defpoints"):
            continue
        if any(e.dxf.get("layer", "0") == nombre for e in doc_dxf.modelspace()):
            continue        # todavía la usa algo que preservamos: se queda
        try:
            doc_dxf.layers.remove(nombre)
        except Exception:
            pass


def _preparar_estilos(doc_dxf, doc: Documento) -> None:
    for nombre, est in doc.estilos_texto.items():
        if nombre not in doc_dxf.styles:
            doc_dxf.styles.add(nombre, font=est.get("archivo") or "Raleway-400.ttf")
    for nombre, est in doc.estilos_cota.items():
        ds = doc_dxf.dimstyles.get(nombre) if nombre in doc_dxf.dimstyles \
            else doc_dxf.dimstyles.add(nombre)
        ds.dxf.dimtxt = est.get("altura_texto", 2.5)
        ds.dxf.dimasz = est.get("tam_flecha", 2.0)
        ds.dxf.dimexe = est.get("ext_linea", 1.25)
        ds.dxf.dimexo = est.get("hueco_origen", 0.625)
        ds.dxf.dimdec = est.get("decimales", 0)
        ds.dxf.dimscale = est.get("factor_escala", 1.0)
        if est.get("estilo_texto") in doc_dxf.styles:
            ds.dxf.dimtxsty = est["estilo_texto"]


def _nombre_tipo_linea(doc_dxf, nombre: str) -> str | None:
    """Los DXF ajenos escriben «Continuous», «CONTINUOUS» o «continuous». Es
    el mismo tipo de línea; el archivo decide cómo se llama."""
    if not nombre:
        return None
    for lt in doc_dxf.linetypes:
        if lt.dxf.name.upper() == nombre.upper():
            return lt.dxf.name
    return None


def _atributos(e) -> dict:
    """Lo que la entidad hereda de la capa no se escribe: escribirlo rompería
    el «por capa» del archivo y el plano dejaría de responder a sus capas."""
    a = {"layer": e.capa}
    if e.color:
        a["true_color"] = _rgb(e.color)
    if e.grosor is not None:
        a["lineweight"] = mod_capas.grosor_valido(e.grosor)
    if e.tipo_linea:
        a["linetype"] = e.tipo_linea
    if e.escala_tl and e.escala_tl != 1.0:
        a["ltscale"] = e.escala_tl
    if not e.visible:
        a["invisible"] = 1
    return a


# --- Entidades -------------------------------------------------------------

def _escribir_entidad(espacio, e, res: ResultadoEscritura) -> None:
    a = _atributos(e)
    t = e.tipo
    try:
        if t == "linea":
            espacio.add_line(tuple(e.p1[:2]), tuple(e.p2[:2]), dxfattribs=a)
        elif t == "polilinea":
            pts = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in e.puntos]
            espacio.add_lwpolyline(pts, format="xyb", close=e.cerrada, dxfattribs=a)
        elif t == "circulo":
            espacio.add_circle(tuple(e.centro[:2]), e.radio, dxfattribs=a)
        elif t == "arco":
            espacio.add_arc(tuple(e.centro[:2]), e.radio, e.ang_ini, e.ang_fin, dxfattribs=a)
        elif t == "elipse":
            espacio.add_ellipse(tuple(e.centro[:2]), tuple(e.eje_mayor[:2]), e.razon,
                                e.param_ini, e.param_fin, dxfattribs=a)
        elif t == "spline":
            if e.puntos_ajuste:
                espacio.add_spline([tuple(p[:2]) for p in e.puntos_ajuste],
                                   degree=e.grado, dxfattribs=a)
            else:
                espacio.add_open_spline([tuple(p[:2]) for p in e.puntos_control],
                                        degree=e.grado, dxfattribs=a)
        elif t == "punto":
            espacio.add_point(tuple(e.p[:2]), dxfattribs=a)
        elif t == "solido":
            espacio.add_solid([tuple(p[:2]) for p in e.puntos], dxfattribs=a)
        elif t == "texto":
            alin = (getattr(e, "alineacion", "IZQ") or "IZQ").upper()
            if "\n" in (e.texto or ""):
                # Un texto de varios renglones (el texto de párrafo de 0.20.0)
                # sale como MTEXT: TEXT no sabe de renglones. El punto de
                # inserción es la base del primer renglón, y la justificación
                # se traduce al punto de anclaje de MTEXT (abajo-izq/centro/der).
                from ezdxf.enums import MTextEntityAlignment
                anclaje = {"CENTRO": MTextEntityAlignment.BOTTOM_CENTER,
                           "DER": MTextEntityAlignment.BOTTOM_RIGHT}.get(
                    alin, MTextEntityAlignment.BOTTOM_LEFT)
                m = espacio.add_mtext(e.texto.replace("\n", "\\P"), dxfattribs=dict(
                    a, char_height=e.altura, rotation=e.rotacion, style=e.estilo))
                # La base del primer renglón queda en `p`: MTEXT ancla abajo
                # por el último renglón, así que se baja lo que miden los demás.
                n = e.texto.count("\n")
                ang = math.radians(e.rotacion or 0.0)
                dy = -e.altura * 1.25 * n
                p = (e.p[0] - dy * math.sin(ang), e.p[1] + dy * math.cos(ang))
                m.set_location(p, attachment_point=anclaje)
            else:
                from ezdxf.enums import TextEntityAlignment
                txt = espacio.add_text(e.texto, dxfattribs=dict(
                    a, height=e.altura, rotation=e.rotacion, style=e.estilo))
                al = {"CENTRO": TextEntityAlignment.CENTER,
                      "DER": TextEntityAlignment.RIGHT}.get(alin, TextEntityAlignment.LEFT)
                txt.set_placement(tuple(e.p[:2]), align=al)
        elif t == "textom":
            a2 = dict(a, char_height=e.altura, rotation=e.rotacion,
                      style=e.estilo, attachment_point=e.adjunto)
            if e.ancho:
                a2["width"] = e.ancho
            espacio.add_mtext(e.texto, dxfattribs=a2).set_location(tuple(e.p[:2]))
        elif t == "insercion":
            espacio.add_blockref(e.bloque, tuple(e.p[:2]), dxfattribs=dict(
                a, xscale=e.escala[0], yscale=e.escala[1], rotation=e.rotacion))
        elif t == "rayado":
            h = espacio.add_hatch(dxfattribs=a)
            if not e.solido:
                h.set_pattern_fill(e.patron, scale=e.escala, angle=e.angulo)
            for ruta in e.rutas:
                h.paths.add_polyline_path(
                    [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in ruta],
                    is_closed=True, flags=1)
        elif t == "cota":
            _escribir_cota(espacio, e, a)
        elif t == "imagen":
            # A propósito: ver el comentario de core/entidades.Imagen.
            res.perdidas.append(f"imagen de referencia {e.id} (no viaja al DXF)")
            return
        elif t == "cruda":
            return   # ya está en el documento original; no se toca
        else:
            res.perdidas.append(f"{t} {e.id}")
            return
        res.escritas += 1
    except Exception as exc:   # una entidad mala no debe tumbar el guardado
        res.perdidas.append(f"{t} {e.id}: {exc}")


# --- Cotas  ·  features 50 a 59 --------------------------------------------

def _escribir_cota(espacio, e, a) -> None:
    """Escribe una DIMENSION de verdad, no un montón de rayas sueltas.

    Sale como cota **de AutoCAD**: se puede seleccionar allá, se recalcula si
    alguien mueve la pieza, y respeta el estilo. Exportarla explotada —líneas y
    texto por separado— habría sido más fácil y habría convertido cada plano en
    un dibujo muerto en cuanto saliera de aquí.

    `text="<>"` es el marcador del DXF para «aquí va la medida»; si el usuario
    escribió un texto propio, ese va tal cual.
    """
    texto = e.texto or "<>"
    estilo = e.estilo if e.estilo else "T101"
    p = e.puntos

    if e.clase in ("lineal", "alineada"):
        if e.clase == "alineada":
            # la distancia es la separación perpendicular entre la línea de
            # cota y el segmento medido
            dx, dy = p[1][0] - p[0][0], p[1][1] - p[0][1]
            largo = math.hypot(dx, dy) or 1.0
            dist = ((p[2][0] - p[0][0]) * -dy + (p[2][1] - p[0][1]) * dx) / largo
            dim = espacio.add_aligned_dim(
                p1=tuple(p[0][:2]), p2=tuple(p[1][:2]), distance=dist,
                text=texto, dimstyle=estilo, dxfattribs=a)
        else:
            dim = espacio.add_linear_dim(
                base=tuple(p[2][:2]), p1=tuple(p[0][:2]), p2=tuple(p[1][:2]),
                angle=e.rotacion, text=texto, dimstyle=estilo, dxfattribs=a)
    elif e.clase == "angular":
        v, p1, p2 = p[0], p[1], p[2]
        pa = p[3] if len(p) > 3 else p1
        r = math.hypot(pa[0] - v[0], pa[1] - v[1])
        a1 = math.degrees(math.atan2(p1[1] - v[1], p1[0] - v[0]))
        a2 = math.degrees(math.atan2(p2[1] - v[1], p2[0] - v[0]))
        dim = espacio.add_angular_dim_cra(
            center=tuple(v[:2]), radius=r * 0.6, start_angle=a1, end_angle=a2,
            distance=r * 0.4, text=texto, dimstyle=estilo, dxfattribs=a)
    elif e.clase in ("radio", "diametro"):
        c, borde = p[0], p[1]
        r = math.hypot(borde[0] - c[0], borde[1] - c[1])
        ang = math.degrees(math.atan2(borde[1] - c[1], borde[0] - c[0]))
        if e.clase == "radio":
            dim = espacio.add_radius_dim_cra(
                center=tuple(c[:2]), radius=r, angle=ang, text=texto, dxfattribs=a)
        else:
            opuesto = [2 * c[0] - borde[0], 2 * c[1] - borde[1]]
            dim = espacio.add_diameter_dim_2p(
                p1=tuple(opuesto), p2=tuple(borde[:2]), text=texto, dxfattribs=a)
    elif e.clase == "directriz":
        espacio.add_leader([tuple(q[:2]) for q in p], dimstyle=estilo, dxfattribs=a)
        if e.texto:
            fin = p[-1]
            t = espacio.add_text(e.texto, dxfattribs=dict(a, height=2.5, style="T101"))
            t.set_placement((fin[0] + 2, fin[1]))
        return
    else:
        raise ValueError(f"clase de cota desconocida: {e.clase}")

    dim.render()


# --- Documento -------------------------------------------------------------

def _base_desde_origen(doc: Documento, res: ResultadoEscritura):
    """Carga el DXF original y le quita todo lo que vamos a reescribir."""
    # Si el original sigue en disco se lee de ahí: pasarlo por una cadena en
    # memoria son cientos de megas de más en un plano de verdad.
    if doc.origen_dxf_ruta and pathlib.Path(doc.origen_dxf_ruta).exists():
        doc_dxf = ezdxf.readfile(doc.origen_dxf_ruta)
    else:
        doc_dxf = ezdxf.read(io.StringIO(doc.origen_dxf))
    msp = doc_dxf.modelspace()

    vivas = {e.handle_origen for e in doc.lista()
             if e.tipo == "cruda" and e.handle_origen}
    por_handle = {e.handle_origen: e for e in doc.lista() if e.handle_origen}

    for entidad in list(msp):
        h = entidad.dxf.get("handle", None)
        if h in vivas:
            # sobrevive tal cual, pero puede haber cambiado de capa o color
            nuestra = por_handle.get(h)
            if nuestra is not None:
                try:
                    entidad.dxf.layer = nuestra.capa
                    if nuestra.color:
                        entidad.dxf.true_color = _rgb(nuestra.color)
                    if nuestra.grosor is not None:
                        entidad.dxf.lineweight = mod_capas.grosor_valido(nuestra.grosor)
                    if nuestra.tipo_linea:
                        entidad.dxf.linetype = nuestra.tipo_linea
                except Exception:
                    pass
            res.preservadas += 1
        else:
            msp.delete_entity(entidad)
    return doc_dxf


def a_ezdxf(doc: Documento):
    res = ResultadoEscritura()
    if doc.tiene_origen:
        doc_dxf = _base_desde_origen(doc, res)
    else:
        doc_dxf = ezdxf.new(config.DXF_VERSION, setup=True)

    from core import unidades as mod_unidades
    doc_dxf.header["$INSUNITS"] = mod_unidades.INSUNITS_POR_NOMBRE.get(getattr(doc, "unidades", "mm"), config.INSUNITS_MM)
    doc_dxf.header["$LTSCALE"] = 1.0
    doc_dxf.header["$LWDISPLAY"] = 1        # que los grosores se vean al abrir

    _preparar_capas(doc_dxf, doc)
    _preparar_estilos(doc_dxf, doc)

    # los bloques van antes que las inserciones que los usan
    for bl in doc.bloques.values():
        if bl.nombre.startswith("*") or bl.nombre in doc_dxf.blocks:
            continue
        blk = doc_dxf.blocks.new(name=bl.nombre, base_point=tuple(bl.base[:2]))
        for sub in bl.entidades:
            _escribir_entidad(blk, sub, res)

    # El modelo al modelo, y lo de cada hoja a **su** hoja. Mandarlo todo al
    # modelo pondría la nota de un plano —que está en milímetros de papel— a
    # 200 mm del origen del mueble, encima del dibujo y con el tamaño de una
    # uña. Son dos espacios distintos en el DXF igual que aquí dentro.
    msp = doc_dxf.modelspace()
    porhoja: dict[str, list] = {}
    for e in doc.lista():
        esp = getattr(e, "espacio", "")
        if esp:
            porhoja.setdefault(esp, []).append(e)
        else:
            _escribir_entidad(msp, e, res)

    for nombre, lista in porhoja.items():
        try:
            hoja = doc_dxf.layouts.get(nombre)
        except Exception:
            hoja = None
        if hoja is None:
            try:
                hoja = doc_dxf.layouts.new(nombre)
            except Exception:
                # Si ni siquiera se pudo crear la hoja, se pierde menos
                # mandándolo al modelo que tirándolo en silencio.
                hoja = msp
                res.avisos.append(
                    f"No se pudo crear la hoja «{nombre}» en el DXF: lo que se "
                    "dibujó en ella salió al modelo.")
        for e in lista:
            _escribir_entidad(hoja, e, res)
    return doc_dxf, res


def escribir(doc: Documento, ruta: str | pathlib.Path) -> ResultadoEscritura:
    ruta = pathlib.Path(ruta)
    if ruta.suffix.lower() == ".dwg":
        return escribir_dwg(doc, ruta)
    doc_dxf, res = a_ezdxf(doc)
    doc_dxf.saveas(str(ruta), encoding="utf-8", fmt="asc")
    return res


def escribir_dwg(doc: Documento, ruta: str | pathlib.Path) -> ResultadoEscritura:
    """Guardar DWG  ·  feature 3.

    Se escribe el DXF —que es donde vive toda la fidelidad del programa— y se
    convierte. El conversor lo elige `core/dwg.py`: el **ODA File Converter** si
    está instalado, y si no **acad-ts**, que va dentro del programa.

    Sobre la fidelidad, dicho claro: el DXF que produce shape101 es el archivo
    que hemos auditado con ezdxf entidad por entidad. El DWG sale de traducirlo,
    y esa traducción no la hizo Autodesk. **Para entregar, el DXF es lo seguro.**
    El DWG está para cuando del otro lado lo piden así.
    """
    import tempfile

    from core import dwg as mod_dwg

    ruta = pathlib.Path(ruta)
    with tempfile.TemporaryDirectory() as tmp:
        intermedio = pathlib.Path(tmp) / (ruta.stem + ".dxf")
        doc_dxf, res = a_ezdxf(doc)
        doc_dxf.saveas(str(intermedio), encoding="utf-8", fmt="asc")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        motor = mod_dwg.desde_dxf(intermedio, ruta, version=config.DXF_VERSION)
    if motor != "oda":
        res.avisos.append(
            "El DWG lo escribió acad-ts, no AutoCAD. Ábrelo allá antes de "
            "mandarlo; el DXF es la entrega segura."
        )
    return res
