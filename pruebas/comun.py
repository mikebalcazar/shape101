"""Lo que comparten las pruebas: el reporte y cuatro ayudas.

Deliberadamente pequeño. Una suite de pruebas con su propio framework se
convierte en otro programa que mantener, y cuando falla no se sabe si falló el
programa o la prueba. Aquí hay una clase con cinco métodos y ni una línea de
magia: cada comprobación dice **qué** se esperaba en el idioma del taller, no
`assertEqual(a, b)`.

Las pruebas no imprimen nada. Anotan en el reporte y `verificar.py` decide qué
enseñar; así una corrida de quince pruebas cabe en una pantalla y un fallo se
lee de un golpe.
"""

from __future__ import annotations

import contextlib
import math
import pathlib
import shutil
import tempfile


class Fallo(Exception):
    """Una comprobación que no se cumplió y que impide seguir esa prueba."""


class Reporte:
    """Lo que una prueba anota mientras corre."""

    def __init__(self, nombre: str, descripcion: str = ""):
        self.nombre = nombre
        self.descripcion = descripcion
        self.hechas = 0
        self.fallos: list[str] = []

    # -- comprobaciones -----------------------------------------------------

    def cierto(self, condicion, que: str, detalle: str = "") -> bool:
        """La comprobación de siempre. `que` se escribe en positivo: lo que
        **debería** pasar, para que la línea del fallo se lea sola."""
        self.hechas += 1
        if condicion:
            return True
        self.fallos.append(que + (f"  ({detalle})" if detalle else ""))
        return False

    def igual(self, obtenido, esperado, que: str) -> bool:
        return self.cierto(obtenido == esperado, que,
                           f"se obtuvo {obtenido!r}, se esperaba {esperado!r}")

    def casi(self, obtenido, esperado, que: str, tol: float = 1e-6) -> bool:
        """Para números. La tolerancia por omisión es de coma flotante, no
        «lo que se vea cerca»: este programa existe para planos que se cortan,
        y una prueba floja no protege de nada."""
        try:
            ok = abs(float(obtenido) - float(esperado)) <= tol
        except (TypeError, ValueError):
            ok = False
        return self.cierto(ok, que,
                           f"se obtuvo {obtenido!r}, se esperaba {esperado!r} ±{tol}")

    def punto(self, obtenido, esperado, que: str, tol: float = 1e-6) -> bool:
        """Dos coordenadas de un golpe: (x, y)."""
        try:
            ok = (abs(obtenido[0] - esperado[0]) <= tol
                  and abs(obtenido[1] - esperado[1]) <= tol)
        except (TypeError, IndexError):
            ok = False
        return self.cierto(ok, que,
                           f"se obtuvo {_pt(obtenido)}, se esperaba {_pt(esperado)}")

    def levanta(self, excepcion, funcion, que: str, *args, **kw) -> bool:
        """Que algo **no** se deje hacer también es una regla que hay que
        comprobar: una capa bloqueada, un nombre inválido."""
        try:
            funcion(*args, **kw)
        except excepcion:
            return self.cierto(True, que)
        except Exception as exc:   # levantó, pero la equivocada
            return self.cierto(False, que, f"levantó {type(exc).__name__}: {exc}")
        return self.cierto(False, que, "no levantó nada")

    def exige(self, condicion, que: str, detalle: str = "") -> None:
        """Como `cierto`, pero corta la prueba. Para lo que sin ello deja de
        tener sentido: si el archivo no se escribió, comprobar su contenido
        sólo produce ruido encima del fallo de verdad."""
        if not self.cierto(condicion, que, detalle):
            raise Fallo(que)


def _pt(p) -> str:
    try:
        return f"({p[0]:.4f}, {p[1]:.4f})"
    except Exception:
        return repr(p)


@contextlib.contextmanager
def carpeta():
    """Una carpeta temporal que se borra sola. Ninguna prueba escribe en la
    carpeta del usuario: el autoguardado y las preferencias viven ahí, y una
    prueba no tiene por qué pisarle los dibujos a nadie."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="shape101-prueba-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def largo(a, b) -> float:
    return math.dist(a[:2], b[:2])
