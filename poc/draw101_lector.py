"""Leer y escribir el documento de draw101 (`.t101d`) con el propio motor de
draw101, sin tocarlo.

El documento de la prueba de concepto dice «.t101x» y «core/t101x.py», pero
en draw101 eso es **otra cosa**: el proyecto de Taller 101 (cocina, gabinetes)
que draw101 importa. El dibujo de draw101 —lo que se guarda con rectángulos,
círculos y cotas— es el `.t101d`: un zip con `meta.json` y `documento.json`,
escrito por `core/proyecto.py`. Es ese el que se lee aquí. Se anota en
RESULTADOS.md para que nadie vuelva a buscar en el archivo equivocado.

draw101 se localiza por la variable DRAW101 o, si no está, como carpeta
hermana `../draw101`. No se copia ni un archivo suyo: se importa su `core`.
"""
from __future__ import annotations

import os
import pathlib
import sys

_RAIZ_DRAW101 = pathlib.Path(os.environ.get("DRAW101", pathlib.Path(__file__).resolve().parents[2] / "draw101"))


def _cargar():
    if not (_RAIZ_DRAW101 / "core" / "proyecto.py").exists():
        raise RuntimeError(f"no encuentro draw101 en {_RAIZ_DRAW101}; apunta DRAW101 a su carpeta")
    if str(_RAIZ_DRAW101) not in sys.path:
        sys.path.insert(0, str(_RAIZ_DRAW101))
    from core import proyecto, documento, entidades, cotas  # noqa: E402
    return proyecto, documento, entidades, cotas


def leer(ruta) -> list[dict]:
    """Las entidades del modelo como dicts planos (los de `a_dict`)."""
    proyecto, *_ = _cargar()
    doc = proyecto.abrir(ruta)
    return [e.a_dict() for e in doc.entidades.values() if getattr(e, "espacio", "") == ""]


def nuevo_documento():
    _, documento, *_ = _cargar()
    return documento.Documento()


def entidades():
    return _cargar()[2]


def cotas():
    return _cargar()[3]


def guardar(doc, ruta) -> pathlib.Path:
    proyecto, *_ = _cargar()
    return proyecto.guardar(doc, ruta)


def abrir(ruta):
    proyecto, *_ = _cargar()
    return proyecto.abrir(ruta)
