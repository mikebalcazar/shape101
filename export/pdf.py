"""Imprimir  ·  features 64, 66 y 67.

El PDF se dibuja con **los mismos trazos** que la vista previa de la pantalla
(`core/papel.py`). No hay un «motor de impresión» aparte: si lo que se ve no es
lo que se imprime, nadie se entera hasta que el plano está en la obra.

Las fuentes de Taller 101 viajan dentro de la app y se incrustan en el PDF. Si
faltaran, se cae a las fuentes base del PDF: sale sin la tipografía de la casa,
pero sale. Nunca se traba una impresión por una fuente — es la misma regla que
`core/marca.py` de Taller 101.
"""

from __future__ import annotations

import re

import io
import pathlib

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from core import papel
from core.documento import Documento

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MM = 72.0 / 25.4          # milímetros a puntos PostScript

_fuentes_listas = None


def _fuentes() -> tuple[str, str]:
    """(normal, negrita). Devuelve Helvetica si las nuestras no están."""
    global _fuentes_listas
    if _fuentes_listas is not None:
        return _fuentes_listas
    try:
        pdfmetrics.registerFont(TTFont("Raleway", str(RAIZ / "assets/fonts/Raleway-400.ttf")))
        pdfmetrics.registerFont(TTFont("Raleway-Bold", str(RAIZ / "assets/fonts/Raleway-700.ttf")))
        _fuentes_listas = ("Raleway", "Raleway-Bold")
    except Exception:
        _fuentes_listas = ("Helvetica", "Helvetica-Bold")
    return _fuentes_listas


_cifras_lista = None


def _fuente_cifras() -> str | None:
    """Fira Sans para los números (ver ui/styles.css). En el PDF no hay
    `unicode-range`: se usa entera en los textos que son **medidas** —el
    número de una cota, «⌀35», «45°»—, y Raleway en los que llevan letras."""
    global _cifras_lista
    if _cifras_lista is None:
        try:
            pdfmetrics.registerFont(TTFont("Cifras", str(RAIZ / "assets/fonts/FiraSans-400.ttf")))
            _cifras_lista = "Cifras"
        except Exception:
            _cifras_lista = ""
    return _cifras_lista or None


_ES_MEDIDA = re.compile(r"^[\s\d.,+\-±×°%⌀ø]+(mm|cm|m)?$")


def _fuente_para(texto: str, normal: str) -> str:
    if _ES_MEDIDA.match(str(texto or "")):
        return _fuente_cifras() or normal
    return normal


def _pintar_hoja(c, doc: Documento, layout: dict) -> None:
    hoja = papel.trazos_papel(doc, layout)
    normal, _ = _fuentes()

    for t in hoja["trazos"]:
        if t.get("imprime") is False:
            continue                       # el marco de la ventana no se imprime
        if t["clase"] == "imagen":
            try:
                img = ImageReader(t["archivo"])
                iw, ih = img.getSize()
                alto_mm = t["ancho"] * ih / iw
                c.drawImage(img, t["p"][0] * MM, t["p"][1] * MM,
                            t["ancho"] * MM, alto_mm * MM, mask="auto")
            except Exception:
                pass                       # sin logotipo se imprime igual
            continue
        color = HexColor(t.get("color") or "#000000")
        if t["clase"] == "relleno":
            c.setFillColor(color)
            p = c.beginPath()
            for pol in t.get("poligonos") or []:
                if len(pol) < 3:
                    continue
                p.moveTo(pol[0][0] * MM, pol[0][1] * MM)
                for q in pol[1:]:
                    p.lineTo(q[0] * MM, q[1] * MM)
                p.close()
            c.drawPath(p, stroke=0, fill=1)
            continue
        if t["clase"] == "texto":
            c.setFillColor(color)
            c.saveState()
            c.translate(t["p"][0] * MM, t["p"][1] * MM)
            if t.get("rotacion"):
                c.rotate(t["rotacion"])
            c.setFont(_fuente_para(t["texto"], normal), t["altura"] * MM)
            alineacion = t.get("alineacion", "IZQ")
            for i, linea in enumerate(str(t["texto"]).split("\n")):
                y = -i * t["altura"] * 1.25 * MM
                if alineacion == "CENTRO":
                    c.drawCentredString(0, y, linea)
                elif alineacion == "DER":
                    c.drawRightString(0, y, linea)
                else:
                    c.drawString(0, y, linea)
            c.restoreState()
            continue

        pts = t["puntos"]
        if len(pts) < 2:
            continue
        c.setStrokeColor(color)
        # El grosor viene en milímetros de papel: es el mismo número que dice la
        # capa, y por eso una capa de 0.35 sale de 0.35 en el papel.
        c.setLineWidth(max(t.get("grosor", 0.25), 0.05) * MM)
        patron = t.get("patron") or []
        c.setDash([abs(v) * MM for v in patron] or [], 0)
        p = c.beginPath()
        p.moveTo(pts[0][0] * MM, pts[0][1] * MM)
        for q in pts[1:]:
            p.lineTo(q[0] * MM, q[1] * MM)
        c.drawPath(p, stroke=1, fill=0)
    c.setDash([], 0)



def escribir(doc: Documento, ruta, layouts=None) -> dict:
    """Un PDF con las hojas indicadas. Sin `layouts`, todas  ·  feature 67."""
    ruta = pathlib.Path(ruta)
    hojas = layouts if layouts is not None else doc.layouts
    if not hojas:
        raise ValueError("El dibujo no tiene ninguna hoja de impresión.")

    c = rl_canvas.Canvas(str(ruta))
    c.setTitle(doc.nombre or "Plano")
    c.setAuthor("Taller 101")
    c.setCreator("shape101 — Taller 101")

    avisos: list[str] = []
    for layout in hojas:
        ancho, alto = papel.medidas(layout)
        c.setPageSize((ancho * MM, alto * MM))
        avisos += [f"«{layout.get('nombre', 'hoja')}»: {a}"
                   for a in papel.trazos_papel(doc, layout).get("avisos", [])]
        _pintar_hoja(c, doc, layout)
        c.showPage()
    c.save()
    return {"ruta": str(ruta), "hojas": len(hojas), "avisos": avisos}


# --- Imagen  ·  feature 66 -------------------------------------------------

def imagen(doc: Documento, ruta, layout: dict, dpi: int = 150) -> dict:
    """PNG o JPG de una hoja, dibujado con los mismos trazos.

    Sirve para meter el plano en un correo o en una ficha; para imprimir se usa
    el PDF, que conserva el vector.
    """
    from PIL import Image, ImageDraw, ImageFont

    ruta = pathlib.Path(ruta)
    hoja = papel.trazos_papel(doc, layout)
    escala = dpi / 25.4            # milímetros a píxeles
    ancho = int(hoja["ancho"] * escala)
    alto = int(hoja["alto"] * escala)
    im = Image.new("RGB", (ancho, alto), "white")
    dib = ImageDraw.Draw(im)

    def px(p):
        return (p[0] * escala, alto - p[1] * escala)      # la Y del papel va al revés

    fuente_ttf = RAIZ / "assets" / "fonts" / "Raleway-400.ttf"
    for t in hoja["trazos"]:
        if t.get("imprime") is False:
            continue
        color = t.get("color") or "#000000"
        if t["clase"] == "imagen":
            try:
                logo = Image.open(t["archivo"]).convert("RGBA")
                ancho_px = max(1, int(t["ancho"] * escala))
                alto_px = max(1, int(ancho_px * logo.height / logo.width))
                logo = logo.resize((ancho_px, alto_px), Image.LANCZOS)
                x, y = px(t["p"])
                im.paste(logo, (int(x), int(y) - alto_px), logo)
            except Exception:
                pass
            continue
        if t["clase"] == "texto":
            try:
                f = ImageFont.truetype(str(fuente_ttf), max(6, int(t["altura"] * escala)))
            except Exception:
                f = ImageFont.load_default()
            x, y = px(t["p"])
            ancla = {"CENTRO": "ms", "DER": "rs"}.get(t.get("alineacion"), "ls")
            dib.text((x, y), str(t["texto"]), fill=color, font=f, anchor=ancla)
            continue
        if t["clase"] == "relleno":
            for pol in t.get("poligonos") or []:
                if len(pol) >= 3:
                    dib.polygon([px(q) for q in pol], fill=color)
            continue
        pts = [px(q) for q in t.get("puntos") or []]
        if len(pts) >= 2:
            dib.line(pts, fill=color, width=max(1, int(t.get("grosor", 0.25) * escala)))

    im.save(str(ruta))
    return {"ruta": str(ruta), "ancho": ancho, "alto": alto, "dpi": dpi,
            "avisos": hoja.get("avisos", [])}
