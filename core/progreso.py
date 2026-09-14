"""Qué está haciendo el motor ahora mismo, para que la interfaz lo diga.

Abrir un DWG grande son cincuenta segundos de conversión, y durante ese tiempo
la ventana no cambiaba: no se sabía si el programa estaba trabajando o se había
trabado. Mike lo pidió con esas palabras — *«agrega algún indicador de que el
programa está trabajando cuando alguna operación tarda más de medio segundo»*.

Aquí sólo hay una cadena y quién la pone. Las etapas largas (`core/dwg.py`,
`core/dxf_lector.py`) la van cambiando; `server.py` la sirve en `/api/progreso`
y la interfaz la pregunta cada medio segundo mientras espera una respuesta.
"""

from __future__ import annotations

import threading
import time

_candado = threading.Lock()
_actual: str = ""
_desde: float = 0.0


def poner(mensaje: str) -> None:
    global _actual, _desde
    with _candado:
        _actual = mensaje
        _desde = time.time()


def limpiar() -> None:
    poner("")


def actual() -> dict:
    with _candado:
        return {"mensaje": _actual,
                "segundos": round(time.time() - _desde, 1) if _actual else 0.0}
