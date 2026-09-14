"""Los avisos de licencia de lo ajeno que viaja dentro de shape101  ·  0.19.2.

Mike, 7-sep-2026: *«desde punto de vista legal, ¿no estamos infringiendo
ninguna propiedad intelectual?»*. La mayor parte de lo que va dentro del
programa es MIT/BSD/Apache/OFL, y todas esas piden lo mismo: que el aviso
de copyright viaje con el programa. Aquí se sirve lo que junta
`build/juntar_licencias.py` en `assets/licencias/`.
"""

from __future__ import annotations

import json
import pathlib

CARPETA = pathlib.Path(__file__).resolve().parent.parent / "assets" / "licencias"


def indice() -> list[dict]:
    try:
        return json.loads((CARPETA / "indice.json").read_text("utf-8"))
    except (OSError, ValueError):
        return []


def texto(archivo: str) -> tuple[str, str] | None:
    """(contenido, tipo MIME) del archivo del índice, o None si no es de ahí."""
    nombre = pathlib.Path(archivo).name
    if nombre not in {e.get("archivo") for e in indice()}:
        return None
    ruta = CARPETA / nombre
    if not ruta.exists():
        return None
    mime = "text/html; charset=utf-8" if nombre.endswith(".html") else "text/plain; charset=utf-8"
    return ruta.read_text("utf-8", "replace"), mime
