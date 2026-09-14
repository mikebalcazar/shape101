"""Espacio papel: formatos, pie de plano y ventanas  ·  features 60 a 63 y 68.

Aquí se arma la **hoja**: el marco, el pie de plano de Taller 101 y las ventanas
que enseñan un trozo del dibujo a una escala fija.

Todo sale como trazos en milímetros de papel, y esos mismos trazos son los que
pinta la pantalla (vista previa, feature 68), los que van al PDF (64) y los que
van a la imagen (66). Una sola geometría para las tres cosas: si el PDF y la
pantalla se dibujaran por caminos distintos, tarde o temprano se verían
distintos, y la única forma de enterarse sería imprimiendo.
"""

from __future__ import annotations

import datetime as dt
import math

from . import config, dibujo, idioma
from .documento import Documento

# --- Formatos  ·  feature 62 ----------------------------------------------
# Milímetros, apaisado. Es como se dobla un plano de taller y como entra en la
# carpeta de obra.
FORMATOS = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
    # Las dos de pulgadas, que son las que salen de una impresora de oficina en
    # México: media carta no, pero carta y tabloide sí, y sin ellas hay que
    # imprimir un A4 en papel carta y perder 8 mm de margen.
    "CARTA": (279.4, 215.9),        # 11 × 8.5 in
    "TABLOIDE": (431.8, 279.4),     # 17 × 11 in
}

#: Una hoja a la medida. Guarda su ancho y alto en el propio layout, así que
#: no vive en esta tabla: `medidas()` la resuelve.
CUSTOM = "CUSTOM"
CUSTOM_MIN = 50.0
CUSTOM_MAX = 5000.0


def medidas(layout: dict) -> tuple[float, float]:
    """Ancho y alto del papel de esta hoja, en mm.

    Un formato de la tabla manda; `CUSTOM` usa lo que traiga el layout. Se pasa
    siempre por aquí —y no por `FORMATOS[...]` a pelo— para que una hoja a la
    medida no se caiga a A3 en el sitio donde a alguien se le olvide.
    """
    f = (layout or {}).get("formato", "A3")
    if f == CUSTOM:
        ancho = float((layout or {}).get("ancho") or 420.0)
        alto = float((layout or {}).get("alto") or 297.0)
        ancho = min(max(ancho, CUSTOM_MIN), CUSTOM_MAX)
        alto = min(max(alto, CUSTOM_MIN), CUSTOM_MAX)
        return ancho, alto
    return FORMATOS.get(f, FORMATOS["A3"])

MARGEN = 10.0          # del borde del papel al marco

# El pie de plano es una **barra vertical pegada al marco derecho**, como en
# los despachos de arquitectura (lo pidió Mike el 6-sep-2026: «no lo quiero
# abajo, estamos enfocados en arquitectura»). Hasta la 0.18.2 era un cuadro
# abajo a la derecha, de 180 × 40. Las dos constantes viejas se conservan para
# quien las importe, pero la geometría sale de `barra_ancho` y `area_util`.
ROTULO_ANCHO = 180.0
ROTULO_ALTO = 40.0
BARRA_ANCHO_CHICA = 42.0    # hojas hasta A3 / tabloide
BARRA_ANCHO_GRANDE = 55.0   # A2 en adelante


def barra_ancho(ancho_papel: float) -> float:
    """Cuánto mide de ancho la barra del pie según el tamaño de la hoja."""
    return BARRA_ANCHO_GRANDE if ancho_papel >= 500 else BARRA_ANCHO_CHICA


def area_util(layout: dict) -> tuple[float, float, float, float]:
    """El rectángulo donde van las ventanas: dentro del marco y a la izquierda
    de la barra del pie, con 5 mm de aire. (x0, y0, x1, y1) en mm de papel."""
    ancho, alto = medidas(layout)
    return (MARGEN + 5, MARGEN + 5, ancho - MARGEN - barra_ancho(ancho) - 5, alto - MARGEN - 5)

# Escalas que se usan en el taller. La lista existe para que nadie invente una
# 1:37 sin querer: un plano a escala rara no se puede medir con escalímetro.
ESCALAS = [1, 2, 5, 10, 20, 25, 50, 75, 100, 200]

COLOR_MARCO = "#1A1F27"
TINTA = "#1A1F27"       # a lo que se traduce el blanco al imprimir


def color_impresion(hex_color: str) -> str:
    """El papel es blanco: lo que venga en blanco se imprime en negro.

    En un CAD el fondo del modelo suele ser oscuro y media capa está en blanco.
    Mandarlo tal cual al papel imprime una hoja en blanco y nadie se entera
    hasta que sale del plóter. Los plotters de verdad hacen exactamente esta
    traducción, y por eso aquí también.
    """
    c = (hex_color or "").lstrip("#")
    if len(c) != 6:
        return hex_color or TINTA
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return TINTA
    if min(r, g, b) > 225:
        return TINTA
    return "#" + c.upper()


def layout_nuevo(nombre: str = "Plano 1", formato: str = "A3") -> dict:
    """Una hoja vacía con su marco y su pie de plano."""
    return {
        "nombre": nombre,
        "formato": formato if (formato in FORMATOS or formato == CUSTOM) else "A3",
        "rotulo": {
            "proyecto": "", "cliente": "", "dibujo": "",
            "folio": "1/1", "revision": "A", "fecha": "", "escala": "",
            "dibujo_por": "",
        },
        "ventanas": [],
    }


def ventana_nueva(x, y, ancho, alto, centro, escala=20.0) -> dict:
    """Una ventana: un rectángulo del papel que enseña el dibujo a una escala.

    `escala` es el denominador: 20 significa 1:20, o sea que 20 mm de mueble
    ocupan 1 mm de papel.
    """
    return {"x": float(x), "y": float(y), "ancho": float(ancho), "alto": float(alto),
            "centro": [float(centro[0]), float(centro[1])], "escala": float(escala),
            "rotacion": 0.0, "marco": True}


# =========================================================================
# Recorte
# =========================================================================
def _recortar(p1, p2, caja):
    """Liang–Barsky: deja del segmento sólo el trozo que cae dentro de la caja.

    Sin esto, el dibujo se saldría de su ventana y se metería encima del pie de
    plano. Es exactamente lo que hace un viewport de AutoCAD.
    """
    x0, y0, x1, y1 = caja
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]),
                 (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None            # paralelo y fuera
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            if r > t0:
                t0 = r
        else:
            if r < t0:
                return None
            if r < t1:
                t1 = r
    return ([p1[0] + t0 * dx, p1[1] + t0 * dy],
            [p1[0] + t1 * dx, p1[1] + t1 * dy])


def _recortar_poligono(pol, caja):
    """Sutherland–Hodgman: el polígono recortado al rectángulo (convexo)."""
    x0, y0, x1, y1 = caja
    lados = (
        (lambda p: p[0] >= x0, lambda a, b: [x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0])]),
        (lambda p: p[0] <= x1, lambda a, b: [x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0])]),
        (lambda p: p[1] >= y0, lambda a, b: [a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0]),
        (lambda p: p[1] <= y1, lambda a, b: [a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1]),
    )
    salida = [list(p) for p in pol]
    for dentro, cruce in lados:
        if not salida:
            break
        entrada, salida = salida, []
        prev = entrada[-1]
        for p in entrada:
            if dentro(p):
                if not dentro(prev):
                    salida.append(cruce(prev, p))
                salida.append(p)
            elif dentro(prev):
                salida.append(cruce(prev, p))
            prev = p
    return salida


# =========================================================================
# El pie de plano  ·  features 62 y 63
# =========================================================================
def _partir(texto: str, ancho_mm: float, altura: float, max_lineas: int = 3) -> list[str]:
    """Parte un texto en renglones que quepan en `ancho_mm` (letra de `altura`).

    Aproximación de 0.55·altura por carácter, que es lo que mide Raleway de
    promedio. Si no cabe ni en `max_lineas`, el último renglón se corta con «…»:
    un nombre de proyecto de tres líneas que se sale de la barra se ve peor
    que uno recortado.
    """
    t = " ".join(str(texto or "").split())
    if not t:
        return []
    por_linea = max(4, int(ancho_mm / (0.55 * altura)))
    lineas: list[str] = []
    actual = ""
    for palabra in t.split(" "):
        prueba = (actual + " " + palabra).strip()
        if len(prueba) <= por_linea:
            actual = prueba
            continue
        if actual:
            lineas.append(actual)
        actual = palabra if len(palabra) <= por_linea else palabra[:por_linea - 1] + "…"
    if actual:
        lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1][:por_linea - 1].rstrip() + "…"
    return lineas


#: Los campos del pie, en el orden en que se apilan. Cada uno lleva su etiqueta
#: en mayúsculas chicas y su valor debajo. Los de arriba se anclan al logotipo;
#: los de abajo (escala, fecha, folio, revisión) al borde inferior del marco.
CAMPOS_ARRIBA = [("proyecto", "PROYECTO", 3.2, 4), ("cliente", "CLIENTE", 2.8, 2),
                 ("dibujo", "DIBUJO", 3.2, 3), ("dibujo_por", "DIBUJÓ", 2.6, 1)]
CAMPOS_ABAJO = [("escala", "ESCALA"), ("fecha", "FECHA"), ("folio", "FOLIO"), ("revision", "REVISIÓN")]


def _rotulo(doc: Documento, layout: dict, ancho: float, alto: float,
            campos: list[dict] | None = None) -> list[dict]:
    """El marco y la barra del pie, en trazos de papel.

    Los datos se rellenan solos con lo que ya sabe el documento (feature 63):
    el nombre del dibujo, el cliente, la fecha de hoy y la escala de la ventana
    principal. Lo que el usuario escriba a mano gana sobre lo automático.

    Si se pasa `campos`, se le agregan las cajas de cada dato (en mm de papel)
    para que la pantalla sepa dónde está cada uno y lo deje editar con doble
    clic encima. Ver `Papel.campoEn` en ui/papel.js.
    """
    r = dict(layout.get("rotulo") or {})
    trazos: list[dict] = []
    lang = idioma.actual()

    def linea(a, b, grosor=0.25):
        trazos.append({"clase": "linea", "puntos": [a, b], "color": COLOR_MARCO,
                       "grosor": grosor, "patron": [], "capa": "T101-ROTULO",
                       "id": "rotulo"})

    def texto(p, t, altura=3.0, alineacion="IZQ", color=COLOR_MARCO):
        if not t:
            return
        trazos.append({"clase": "texto", "p": p, "texto": str(t), "altura": altura,
                       "rotacion": 0, "alineacion": alineacion, "color": color,
                       "grosor": 0.18, "patron": [], "capa": "T101-ROTULO",
                       "id": "rotulo"})

    # marco
    m = MARGEN
    linea([m, m], [ancho - m, m], 0.5)
    linea([ancho - m, m], [ancho - m, alto - m], 0.5)
    linea([ancho - m, alto - m], [m, alto - m], 0.5)
    linea([m, alto - m], [m, m], 0.5)

    # la barra: del marco de arriba al de abajo, pegada al de la derecha
    barra = barra_ancho(ancho)
    bx0, bx1 = ancho - m - barra, ancho - m
    linea([bx0, m], [bx0, alto - m], 0.35)
    aire = 3.0                       # del borde de la barra al texto
    tx = bx0 + aire
    util = barra - 2 * aire

    def caja(clave, etiqueta, y0, y1, valor):
        if campos is not None:
            campos.append({"clave": clave, "etiqueta": etiqueta, "valor": valor,
                           "caja": [bx0, y0, bx1, y1]})

    # 1. el logotipo, arriba
    y = alto - m
    banda = 26.0 if barra < 50 else 32.0
    from pathlib import Path as _P
    logo = _P(__file__).resolve().parent.parent / "assets" / "marca" / "logo.png"
    if logo.exists():
        ancho_logo = util
        trazos.append({"clase": "imagen", "archivo": str(logo),
                       "p": [tx, y - banda / 2 - ancho_logo / 4],
                       "ancho": ancho_logo, "capa": "T101-ROTULO", "id": "rotulo",
                       "color": config.AZUL, "grosor": 0, "patron": []})
    else:
        texto([bx0 + barra / 2, y - banda / 2 - 3], "101", 9.0, "CENTRO", config.AZUL)
        texto([bx0 + barra / 2, y - banda + 4], "TALLER", 2.4, "CENTRO", config.AZUL)
    y -= banda
    linea([bx0, y], [bx1, y], 0.25)

    # 2. los datos de arriba, apilados bajo el logotipo
    automaticos = {"proyecto": doc.nombre, "cliente": doc.cliente,
                   "dibujo": layout.get("nombre", ""), "dibujo_por": ""}
    for clave, etiqueta, altura, max_lineas in CAMPOS_ARRIBA:
        etiqueta = idioma.t(etiqueta, lang)
        valor = r.get(clave) or automaticos.get(clave) or ""
        renglones = _partir(valor, util, altura, max_lineas) or [""]
        y_ini = y
        texto([tx, y - 2.0 - 2.8], etiqueta, 2.0, "IZQ", "#6B7280")
        yy = y - 2.0 - 2.8 - 1.6
        for ren in renglones:
            yy -= altura
            texto([tx, yy], ren, altura)
        y = yy - 2.2
        linea([bx0, y], [bx1, y], 0.18)
        caja(clave, etiqueta, y, y_ini, r.get(clave) or "")

    # 3. los datos de abajo, anclados al marco inferior
    fecha = r.get("fecha") or dt.date.today().strftime(idioma.formato_fecha(lang))
    escala = r.get("escala") or idioma.t(_escala_principal(layout), lang)
    valores = {"escala": escala, "fecha": fecha, "folio": r.get("folio") or "1/1",
               "revision": r.get("revision") or "A"}
    fila = 11.0
    yb = m
    for clave, etiqueta in reversed(CAMPOS_ABAJO):
        etiqueta = idioma.t(etiqueta, lang)
        texto([tx, yb + fila - 2.0 - 2.4], etiqueta, 2.0, "IZQ", "#6B7280")
        texto([tx, yb + 2.2], valores[clave], 3.0)
        caja(clave, etiqueta, yb, yb + fila, r.get(clave) or "")
        yb += fila
        linea([bx0, yb], [bx1, yb], 0.18)
    return trazos


def _escala_principal(layout: dict) -> str:
    vs = layout.get("ventanas") or []
    if not vs:
        return "—"
    escalas = {v.get("escala", 20) for v in vs}
    if len(escalas) == 1:
        e = escalas.pop()
        return f"1:{e:g}"
    return "VARIAS"


def _es_cota(doc: Documento, t: dict) -> bool:
    e = doc.entidades.get(t.get("id"))
    return e is not None and e.tipo == "cota"


def _caja_de(t: dict) -> tuple[float, float, float, float] | None:
    """La caja que ocupa un trazo en el modelo, o `None` si no se puede saber.

    `None` quiere decir «míralo de todos modos»: nunca se descarta a ciegas.
    """
    pts = t.get("puntos")
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    p = t.get("p")
    if p:
        # Un texto ocupa a la derecha de su punto; se deja holgura por el alto.
        h = float(t.get("altura", 2.5) or 2.5)
        largo = h * max(len(str(t.get("texto", ""))), 1)
        return (p[0] - largo, p[1] - h, p[0] + largo, p[1] + h)
    return None


# =========================================================================
# La hoja completa
# =========================================================================
def trazos_papel(doc: Documento, layout: dict, propias: bool = True) -> dict:
    """Todo lo que se imprime, en milímetros de papel.

    `propias` incluye lo que el usuario dibujó **sobre esta hoja** (notas,
    símbolos, cotas de papel). Se puede dejar fuera para la pantalla, donde eso
    lo pinta el lienzo normal y así se repinta por parche al dibujar en vez de
    rehacer la hoja entera en cada clic.
    """
    ancho, alto = medidas(layout)
    salida: list[dict] = []

    # Las cotas del modelo se pintan aparte, **por ventana**, con el tamaño de
    # cota de esta hoja (Mike, 9-sep-2026: «cada página de plano tiene su
    # propio tamaño de cota»). Lo medido no cambia —la cota vive en el modelo—;
    # lo que se impone es que su texto mida `tam_cotas` mm **en el papel**,
    # sea cual sea la escala de la ventana. Ver `cotas.escala_efectiva`.
    del_modelo = [t for t in dibujo.trazos(doc) if not _es_cota(doc, t)]
    cotas_modelo = [e for e in doc.visibles("") if e.tipo == "cota"]
    est = dict(doc.estilos_cota.get("T101", {}))
    altura_base = float(est.get("altura_texto", 2.5) or 2.5)
    tam_cotas = float(layout.get("tam_cotas") or altura_base)
    # Caja de cada trazo en el modelo, una vez para toda la hoja. Sin esto, una
    # hoja con siete ventanas transforma y recorta el plano entero siete veces:
    # en el DWG de Mondelez son 350 000 transformaciones para pintar un A1, y
    # se nota. Con la caja, cada ventana descarta de un vistazo lo que no le
    # toca.
    cajas = [_caja_de(t) for t in del_modelo]

    for j, v in enumerate(layout.get("ventanas") or []):
        # Capas congeladas en esta ventana  ·  hojas importadas. En un plano de
        # verdad es lo que hace que la hoja de instalaciones no enseñe el
        # mobiliario: la misma geometría, distinta ventana.
        apagadas = {str(c).upper() for c in (v.get("capas_apagadas") or [])}
        # unidades del dibujo → mm de papel. La escala 1:20 es mm de papel
        # contra mm de mundo; si el dibujo va en metros, una unidad son 1000 mm.
        f = doc.mm_por_unidad() / float(v.get("escala", 20) or 20)
        cx, cy = v["centro"]
        vx, vy, va, vh = v["x"], v["y"], v["ancho"], v["alto"]
        caja = (vx, vy, vx + va, vy + vh)
        rot = math.radians(v.get("rotacion", 0) or 0)
        cos, sen = math.cos(rot), math.sin(rot)

        def aPapel(p):
            x, y = (p[0] - cx) * f, (p[1] - cy) * f
            x, y = x * cos - y * sen, x * sen + y * cos
            return [vx + va / 2 + x, vy + vh / 2 + y]

        if v.get("marco", True):
            esquinas = [[vx, vy], [vx + va, vy], [vx + va, vy + vh], [vx, vy + vh]]
            for i in range(4):
                salida.append({"clase": "linea", "puntos": [esquinas[i], esquinas[(i + 1) % 4]],
                               "color": "#B9C1CC", "grosor": 0.13, "patron": [],
                               "capa": "T101-AUXILIAR", "id": "ventana", "imprime": False,
                               "ventana": j})

        # Qué trozo del modelo cabe en esta ventana, en unidades del modelo. Si
        # la ventana va girada se ensancha por la diagonal: más vale mirar de
        # más que recortar un trazo que sí entraba.
        mitad_x, mitad_y = va / 2 / f, vh / 2 / f
        if rot:
            d = math.hypot(mitad_x, mitad_y)
            mitad_x = mitad_y = d
        mundo = (cx - mitad_x, cy - mitad_y, cx + mitad_x, cy + mitad_y)

        # Las cotas de esta ventana: texto de `tam_cotas` mm de papel. En
        # unidades del modelo eso es tam × escala / k, y sobre el estilo (que
        # mide `altura_base` a 1:1) el factor es tam / altura_base × escala / k.
        escala_cota = (tam_cotas / altura_base) / f
        trazos_v = list(del_modelo)
        cajas_v = list(cajas)
        for e in cotas_modelo:
            for t in dibujo.trazos_cota(doc, e, escala_cota):
                trazos_v.append(t)
                cajas_v.append(_caja_de(t))

        for t, bb in zip(trazos_v, cajas_v):
            if bb is not None and (bb[0] > mundo[2] or bb[2] < mundo[0]
                                   or bb[1] > mundo[3] or bb[3] < mundo[1]):
                continue
            if apagadas and str(t["capa"]).upper() in apagadas:
                continue
            capa = doc.capas.get(t["capa"])
            if capa is not None and not capa.imprime:
                continue                     # las capas que no imprimen, no imprimen
            tinta = color_impresion(t.get("color"))
            if t["clase"] == "texto":
                p = aPapel(t["p"])
                if not (caja[0] <= p[0] <= caja[2] and caja[1] <= p[1] <= caja[3]):
                    continue
                salida.append({**t, "p": p, "altura": t["altura"] * f,
                               "color": tinta, "ventana": j,
                               "rotacion": t["rotacion"] + math.degrees(rot)})
                continue
            if t["clase"] == "relleno":
                # Un sólido: cada polígono se recorta a la ventana.
                pols = [_recortar_poligono([aPapel(q) for q in pol], caja) for pol in t.get("poligonos") or []]
                pols = [p for p in pols if len(p) >= 3]
                if pols:
                    salida.append({**t, "color": tinta, "poligonos": pols, "ventana": j})
                continue
            if not t.get("puntos"):
                continue
            pts = [aPapel(q) for q in t["puntos"]]
            for i in range(len(pts) - 1):
                trozo = _recortar(pts[i], pts[i + 1], caja)
                if trozo:
                    salida.append({**t, "color": tinta, "puntos": [trozo[0], trozo[1]], "ventana": j})

    # Una hoja que sale en blanco teniendo dibujo es el error que más caro se
    # paga: se descubre en el plóter, con el papel puesto. Si el modelo tiene
    # entidades y a la hoja no llegó ninguna, se dice por qué — casi siempre es
    # una capa que no imprime (el fondo de PDF nace así, a propósito) o una
    # ventana encuadrada donde no hay nada.
    avisos: list[str] = []
    if doc.entidades and layout.get("ventanas") and not any(
            t.get("imprime", True) for t in salida):
        mudas = sorted({t["capa"] for t in del_modelo
                        if (c := doc.capas.get(t["capa"])) is not None and not c.imprime})
        avisos.append(
            "Esta hoja sale en blanco: no llegó ningún trazo a la ventana."
            + (f" Todo lo que hay está en capas que no imprimen ({', '.join(mudas)})."
               if mudas else " Revisa el encuadre de la ventana.")
        )

    # El marco y el pie de plano. Si la hoja vino de otro archivo, el suyo:
    # ponerle el pie de Taller 101 encima del de la oficina que lo dibujó deja
    # dos pies de plano en la misma hoja y ninguno de los dos se puede leer.
    propio = _trazos_de_hoja_ajena(doc, layout)
    campos: list[dict] = []
    if propio is None:
        salida.extend(_rotulo(doc, layout, ancho, alto, campos))
    else:
        salida.extend(propio)

    # Y lo que se dibujó **sobre esta hoja**: las notas, los símbolos y las
    # cotas de papel. Están en milímetros de papel y se pintan tal cual — no
    # pasan por ninguna ventana, porque no son del modelo: son de la hoja.
    if propias:
        for t in dibujo.trazos(doc, espacio=layout.get("nombre", "")):
            salida.append({**t, "color": color_impresion(t.get("color"))})

    return {"ancho": ancho, "alto": alto, "trazos": salida, "avisos": avisos, "campos": campos}


def _trazos_de_hoja_ajena(doc: Documento, layout: dict) -> list[dict] | None:
    """Lo que el archivo original tenía dibujado en esta hoja.

    Se guardó como bloque al abrir (`core/dxf_lector.py`) y se tesela aquí, no
    allá: así prender o apagar una capa cambia la hoja igual que cambia el
    modelo, en vez de dejarla congelada como estaba el día que se abrió.
    """
    nombre = (layout or {}).get("bloque_papel")
    if not nombre:
        return None
    bl = doc.bloques.get(nombre)
    if bl is None:
        return None
    salida: list[dict] = []
    for e in bl.entidades:
        capa = doc.capas.get(e.capa)
        if not getattr(e, "visible", True):
            continue
        if capa is not None and (not capa.visible or not capa.imprime):
            continue
        for t in dibujo.trazos_de(doc, e):
            salida.append({**t, "color": color_impresion(t.get("color")),
                           "capa": t.get("capa", e.capa), "hoja_ajena": True})
    return salida


# =========================================================================
# Acotar sobre la hoja  ·  la ventana como lupa
# =========================================================================
# Dibujar sobre una hoja sirve de poco si no te puedes enganchar a lo que se ve
# por la ventana: una cota que no toca la esquina del mueble no mide el mueble,
# mide donde atinó el ratón. Así que la geometría del modelo se proyecta a
# milímetros de papel —la ventana es una lupa: escala, giro y traslado— y el
# osnap del navegador se engancha a **eso**.
#
# Se proyecta la geometría exacta, no lo teselado: un arco sigue siendo un arco
# con su centro y su radio, así que el centro y los cuadrantes salen exactos.
# Por la ventana **no se selecciona**: eso es el modelo mirado desde aquí, y se
# edita en el modelo, igual que en AutoCAD.

#: Tope de primitivas proyectadas por hoja. Pasado eso, más que ayudar estorba:
#: son megas de JSON para engancharse a un punto.
MAX_PRIMITIVAS_VENTANA = 60000


def _proyectar(pr: dict, f: float, cx: float, cy: float,
               px: float, py: float, cos: float, sen: float) -> dict | None:
    """Una primitiva del modelo, en milímetros de papel."""
    def q(p):
        x, y = (p[0] - cx) * f, (p[1] - cy) * f
        return [px + x * cos - y * sen, py + x * sen + y * cos]

    t = pr.get("tipo")
    if t == "seg":
        return {"tipo": "seg", "a": q(pr["a"]), "b": q(pr["b"])}
    if t == "punto":
        return {"tipo": "punto", "p": q(pr["p"])}
    if t == "arco":
        giro = math.degrees(math.atan2(sen, cos))
        return {"tipo": "arco", "c": q(pr["c"]), "r": pr["r"] * f,
                "a0": (pr["a0"] + giro) % 360, "a1": (pr["a1"] + giro) % 360}
    return None


def _caja_primitiva(pr: dict) -> tuple[float, float, float, float]:
    t = pr.get("tipo")
    if t == "seg":
        a, b = pr["a"], pr["b"]
        return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])
    if t == "punto":
        p = pr["p"]
        return p[0], p[1], p[0], p[1]
    c, r = pr["c"], pr["r"]
    return c[0] - r, c[1] - r, c[0] + r, c[1] + r


def geometria_ventanas(doc: Documento, layout: dict) -> list[dict]:
    """La geometría del modelo vista por las ventanas, en mm de papel.

    Cada primitiva lleva de qué ventana salió y a qué escala, que es lo que
    después deja que una cota de papel anuncie la medida de verdad.
    """
    from . import geometria as mod_geo

    ventanas = layout.get("ventanas") or []
    if not ventanas:
        return []
    prims = mod_geo.indice(doc, "")
    # La caja de cada primitiva **en el modelo**, una vez para toda la hoja. Sin
    # esto se proyectan las 181 000 primitivas del plano de Mondelez una vez por
    # ventana —siete— para tirar el 99 % después. Con la caja se descarta antes
    # de tocarlas: la misma cuenta que ya se hacía con los trazos.
    cajas = [_caja_primitiva(pr) for pr in prims]
    salida: list[dict] = []
    for j, v in enumerate(ventanas):
        esc = float(v.get("escala", 20) or 20)
        f = doc.mm_por_unidad() / esc
        cx, cy = v["centro"]
        vx, vy, va, vh = v["x"], v["y"], v["ancho"], v["alto"]
        px, py = vx + va / 2, vy + vh / 2
        rot = math.radians(v.get("rotacion", 0) or 0)
        cos, sen = math.cos(rot), math.sin(rot)
        apagadas = {str(c).upper() for c in (v.get("capas_apagadas") or [])}
        # Qué trozo del modelo alcanza a ver esta ventana. Girada, se ensancha
        # por la diagonal: más vale mirar de más que dejar sin enganchar algo
        # que sí se ve.
        mx, my = va / 2 * esc, vh / 2 * esc
        if rot:
            mx = my = math.hypot(mx, my)
        mundo = (cx - mx, cy - my, cx + mx, cy + my)

        for pr, bb in zip(prims, cajas):
            if bb[0] > mundo[2] or bb[2] < mundo[0] or bb[1] > mundo[3] or bb[3] < mundo[1]:
                continue          # ni se asoma por esta ventana
            if pr.get("aprox") or pr.get("cota"):
                continue          # teselado de algo ajeno (o una raya de cota): no se engancha
            if apagadas:
                e = doc.entidades.get(pr.get("id"))
                if e is not None and str(e.capa).upper() in apagadas:
                    continue
            q = _proyectar(pr, f, cx, cy, px, py, cos, sen)
            if q is None:
                continue
            x0, y0, x1, y1 = _caja_primitiva(q)
            if x1 < vx or x0 > vx + va or y1 < vy or y0 > vy + vh:
                continue          # cae fuera de la ventana
            q["id"] = pr.get("id")
            q["ventana"] = j
            q["escala"] = esc
            salida.append(q)
            if len(salida) >= MAX_PRIMITIVAS_VENTANA:
                return salida
    return salida


def previa_ventana(doc: Documento, layout: dict, j: int, holgura: float | None = None) -> list[dict]:
    """Lo que una ventana **podría** enseñar si el dibujo se corre dentro de ella.

    Mike (9-sep-2026): *«cuando muevo el modelo en el viewport, dame una vista
    en vivo de cómo se dibuja; si lo quiero mover ahorita, lo muevo a ciegas»*.
    Al empezar a arrastrar, el lienzo pide esto una vez: la misma ventana pero
    ensanchada `holgura` mm por cada lado (por omisión, el lado mayor de la
    hoja), sin marco. Como se ensancha simétricamente el centro no se mueve y
    los trazos salen en el mismo sistema de la hoja; el lienzo los corre con
    el ratón y los recorta al marco de verdad. Ver `VentanasHoja.alMover`.
    """
    ventanas = layout.get("ventanas") or []
    if not (0 <= j < len(ventanas)):
        return []
    v = dict(ventanas[j])
    if holgura is None:
        holgura = max(medidas(layout))
    v["x"] -= holgura
    v["y"] -= holgura
    v["ancho"] += 2 * holgura
    v["alto"] += 2 * holgura
    v["marco"] = False
    L = {**layout, "ventanas": [v]}
    salida = [t for t in trazos_papel(doc, L, propias=False)["trazos"] if t.get("ventana") == 0]
    for t in salida:
        t["ventana"] = j
    return salida


def ventana_en(layout: dict, puntos) -> dict | None:
    """La ventana de la hoja que contiene todos esos puntos de papel, si hay una."""
    for v in layout.get("ventanas") or []:
        vx, vy, va, vh = v["x"], v["y"], v["ancho"], v["alto"]
        if all(vx <= float(p[0]) <= vx + va and vy <= float(p[1]) <= vy + vh
               for p in puntos):
            return v
    return None


def factor_de_medida(layout: dict, puntos, mm_por_unidad: float = 1.0) -> float:
    """Por cuánto multiplicar lo que mide una cota puesta sobre la hoja.

    Si cae dentro de una ventana, por la escala de esa ventana: así el plano
    dice los 3 450 mm del mueble y no los 172 mm que mide en el papel. Si cae
    fuera de toda ventana —una cota del propio formato de la hoja— se queda en
    1: ahí los milímetros de papel son la medida buena.
    """
    v = ventana_en(layout, puntos)
    return float(v.get("escala", 1.0) or 1.0) / (mm_por_unidad or 1.0) if v else 1.0


def escala_de_cotas(doc: Documento, layout: dict) -> float | None:
    """Ajusta el estilo de cota a la escala de la hoja  ·  feature 59.

    Una cota con texto de 2.5 mm dibujada a 1:20 se imprime de 0.125 mm: no se
    lee ni con lupa. El texto tiene que medir 2.5 mm **en el papel**, así que en
    el dibujo tiene que medir 2.5 × la escala. Eso es exactamente lo que hace el
    DIMSCALE de AutoCAD, y es de las cosas que más se olvidan a mano.

    Si la hoja tiene ventanas a escalas distintas no se toca nada: no hay un
    número que sirva para las dos, y elegir uno estropearía la mitad del plano.
    """
    escalas = {v.get("escala", 20) for v in (layout.get("ventanas") or [])}
    if len(escalas) != 1:
        return None
    escala = float(escalas.pop()) / doc.mm_por_unidad()
    est = doc.estilos_cota.setdefault("T101", {})
    if est.get("factor_escala") != escala:
        est["factor_escala"] = escala
        doc.sucio = True
    return escala


def encuadrar_ventana(doc: Documento, v: dict, caja=None) -> dict:
    """Centra la ventana en todo el dibujo y elige la escala normalizada más
    grande que lo deje caber entero. Que la escala sea de la lista importa: un
    plano a 1:37 no se puede medir con escalímetro.

    Con `caja` [x0, y0, x1, y1] (en unidades del modelo) se encuadra **ese
    recuadro** en vez de la extensión: es la herramienta VENTANAHOJA (Mike,
    9-sep-2026: «se traza un rectángulo en el modelo sobre lo que se quiere
    englobar → Enter → abre el cuadro de Hoja nueva → la ventana enseña
    exactamente ese recuadro»).
    """
    ext = None
    if caja and len(caja) == 4:
        x0, y0, x1, y1 = (float(c) for c in caja)
        if abs(x1 - x0) > 1e-9 and abs(y1 - y0) > 1e-9:
            ext = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    if ext is None:
        ext = doc.extension()
    if not ext:
        return v
    x0, y0, x1, y1 = ext
    v["centro"] = [(x0 + x1) / 2, (y0 + y1) / 2]
    k = doc.mm_por_unidad()
    ancho = max((x1 - x0) * k, 1e-6)
    alto = max((y1 - y0) * k, 1e-6)
    necesaria = max(ancho / (v["ancho"] * 0.95), alto / (v["alto"] * 0.95))
    for e in ESCALAS:
        if e >= necesaria:
            v["escala"] = float(e)
            return v
    v["escala"] = float(ESCALAS[-1])
    return v
