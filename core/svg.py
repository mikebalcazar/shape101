"""La hoja como SVG, en milímetros  ·  0.19.0 (vista previa e impresión).

Para imprimir con la hoja **centrada en el papel** hace falta mandarle a la
impresora una página del tamaño exacto del papel con el dibujo puesto donde
va, y eso se hace mejor con una página HTML de `@page { size: W H; margin: 0 }`
que con el visor de PDF de Chromium, que reacomoda a su gusto. El dibujo de
esa página es este SVG: los mismos trazos de `papel.trazos_papel`, en mm, y
por lo tanto lo mismo que sale en el PDF y en pantalla.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

from . import papel
from .documento import Documento


def _color(c: str | None) -> str:
    return c or "#1A1F27"


def hoja_svg(doc: Documento, layout: dict, con_logo: bool = True) -> str:
    """SVG de la hoja completa (marco, pie, ventanas y lo dibujado encima)."""
    h = papel.trazos_papel(doc, layout, propias=True)
    ancho, alto = h["ancho"], h["alto"]
    partes: list[str] = []
    partes.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                  f'width="{ancho}mm" height="{alto}mm" viewBox="0 0 {ancho} {alto}" '
                  f'font-family="Raleway, Cifras, Arial, sans-serif">')
    partes.append(f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="#fff"/>')
    # y crece hacia abajo en SVG y hacia arriba en el papel: se voltea.
    partes.append(f'<g transform="translate(0 {alto}) scale(1 -1)">')
    for t in h["trazos"]:
        if t.get("imprime") is False:
            continue
        cl = t.get("clase")
        if cl == "linea":
            pts = t.get("puntos") or []
            if len(pts) < 2:
                continue
            d = " ".join(f"{p[0]:.3f},{p[1]:.3f}" for p in pts)
            grosor = max(0.13, float(t.get("grosor") or 0.25))
            dash = ""
            pat = t.get("patron") or []
            if pat:
                esc = float(t.get("escala_tl") or 1.0)
                dash = ' stroke-dasharray="' + " ".join(f"{max(0.3, abs(v) * esc):.2f}" for v in pat) + '"'
            partes.append(f'<polyline points="{d}" fill="none" stroke="{_color(t.get("color"))}" '
                          f'stroke-width="{grosor:.3f}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
        elif cl == "relleno":
            d = " ".join("M " + " L ".join(f"{p[0]:.3f},{p[1]:.3f}" for p in pol) + " Z"
                         for pol in (t.get("poligonos") or []) if len(pol) >= 3)
            if d:
                partes.append(f'<path d="{d}" fill="{_color(t.get("color"))}" fill-rule="evenodd" stroke="none"/>')
        elif cl == "texto":
            p = t["p"]
            altura = float(t.get("altura") or 2.5)
            anc = {"CENTRO": "middle", "DER": "end"}.get(t.get("alineacion"), "start")
            rot = float(t.get("rotacion") or 0)
            # el texto se pinta sin voltear: un grupo interno lo endereza
            partes.append(f'<g transform="translate({p[0]:.3f} {p[1]:.3f}) scale(1 -1) rotate({-rot:.3f})">'
                          f'<text x="0" y="0" font-size="{altura:.3f}" text-anchor="{anc}" '
                          f'fill="{_color(t.get("color"))}">{html.escape(str(t.get("texto") or ""))}</text></g>')
        elif cl == "imagen" and con_logo:
            ruta = Path(t.get("archivo") or "")
            if not ruta.exists():
                continue
            try:
                from PIL import Image
                with Image.open(ruta) as im:
                    prop = im.height / im.width
            except Exception:
                prop = 0.5
            datos = base64.b64encode(ruta.read_bytes()).decode("ascii")
            w = float(t.get("ancho") or 20)
            hh = w * prop
            x, y = t["p"]
            partes.append(f'<g transform="translate({x:.3f} {y + hh:.3f}) scale(1 -1)">'
                          f'<image x="0" y="0" width="{w:.3f}" height="{hh:.3f}" '
                          f'xlink:href="data:image/png;base64,{datos}"/></g>')
    partes.append("</g></svg>")
    return "".join(partes)
