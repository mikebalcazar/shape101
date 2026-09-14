"""Idioma de lo que el motor escribe en el papel  ·  0.19.0.

La interfaz se traduce en el navegador (ui/idioma.js) con un diccionario
español → inglés: el código sigue en español, que es como se escribió y como
lo lee Mike. Pero hay textos que **nacen en el motor y van al papel** —las
etiquetas del pie de plano, el nombre de una hoja nueva— y ésos se traducen
aquí, con la preferencia `idioma`.

Inglés es el idioma de fábrica desde la 0.19.0; español se elige en
Ayuda → Configuración.
"""

from __future__ import annotations

from . import preferencias

IDIOMAS = ("en", "es")

_EN = {
    "PROYECTO": "PROJECT", "CLIENTE": "CLIENT", "DIBUJO": "DRAWING", "DIBUJÓ": "DRAWN BY",
    "ESCALA": "SCALE", "FECHA": "DATE", "FOLIO": "SHEET", "REVISIÓN": "REVISION",
    "VARIAS": "VARIOUS", "Plano": "Sheet", "Sin título": "Untitled", "TALLER": "TALLER",
}


def actual() -> str:
    """El idioma elegido, siempre uno de IDIOMAS."""
    try:
        v = str(preferencias.leer().get("idioma") or "en").lower()[:2]
    except Exception:
        v = "en"
    return v if v in IDIOMAS else "en"


def t(texto: str, idioma: str | None = None) -> str:
    """Traduce un texto del motor al idioma elegido; si no hay traducción, tal cual."""
    if (idioma or actual()) == "es":
        return texto
    return _EN.get(texto, texto)


def formato_fecha(idioma: str | None = None) -> str:
    """dd/mm/aaaa en español; ISO (aaaa-mm-dd) en inglés, que no se presta a
    confusión entre el orden americano y el europeo."""
    return "%d/%m/%Y" if (idioma or actual()) == "es" else "%Y-%m-%d"
