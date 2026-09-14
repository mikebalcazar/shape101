"""Deshacer y rehacer  ·  feature 10.

Va en F0 **a propósito**. Si el historial llega después, cada herramienta de
dibujo y de edición hay que reescribirla para que avise de lo que cambió.
Puesto antes, una herramienta nueva sólo tiene que llamar a los métodos del
documento y el deshacer le sale gratis.

Cómo funciona: el documento no se fotografía entero (un plano son megabytes y
habría que copiarlo en cada clic). Se anota **la operación primitiva y su
inversa**: qué entidad se agregó, qué tenía antes la que se modificó, en qué
posición estaba la que se borró. Deshacer es aplicar las inversas al revés.

Las operaciones se agrupan en transacciones con nombre («Mover», «Borrar 12
entidades») para que un Ctrl+Z deshaga *una acción del usuario*, no un
vigésimo de acción.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config


@dataclass
class Transaccion:
    nombre: str
    ops: list = field(default_factory=list)


class Historial:
    def __init__(self, limite: int = config.HISTORIAL_MAX):
        self.limite = limite
        self.hechas: list[Transaccion] = []
        self.deshechas: list[Transaccion] = []
        self._abierta: Transaccion | None = None
        self._profundidad = 0
        self.silencio = False      # al cargar un archivo no se anota nada

    # -- transacciones ------------------------------------------------------
    def abrir(self, nombre: str) -> None:
        if self.silencio:
            return
        if self._profundidad == 0:
            self._abierta = Transaccion(nombre)
        self._profundidad += 1

    def cerrar(self) -> None:
        if self.silencio:
            return
        self._profundidad -= 1
        if self._profundidad > 0:
            return
        self._profundidad = 0
        tr, self._abierta = self._abierta, None
        if tr is None or not tr.ops:
            return           # una transacción que no cambió nada no se apunta
        self.hechas.append(tr)
        self.deshechas.clear()
        if len(self.hechas) > self.limite:
            del self.hechas[0]

    def anotar(self, op: tuple) -> None:
        if self.silencio:
            return
        if self._abierta is None:
            # operación suelta: se le hace su propia transacción
            self._abierta = Transaccion(op[0])
            self._abierta.ops.append(op)
            self.hechas.append(self._abierta)
            self.deshechas.clear()
            self._abierta = None
            if len(self.hechas) > self.limite:
                del self.hechas[0]
            return
        self._abierta.ops.append(op)

    # -- estado -------------------------------------------------------------
    @property
    def puede_deshacer(self) -> bool:
        return bool(self.hechas)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self.deshechas)

    def nombre_deshacer(self) -> str | None:
        return self.hechas[-1].nombre if self.hechas else None

    def nombre_rehacer(self) -> str | None:
        return self.deshechas[-1].nombre if self.deshechas else None

    def limpiar(self) -> None:
        self.hechas.clear()
        self.deshechas.clear()
        self._abierta = None
        self._profundidad = 0


class _Contexto:
    """`with doc.transaccion("Mover"):` — agrupa y cierra aunque truene algo."""

    def __init__(self, historial: Historial, nombre: str):
        self.h = historial
        self.nombre = nombre

    def __enter__(self):
        self.h.abrir(self.nombre)
        return self.h

    def __exit__(self, *exc):
        self.h.cerrar()
        return False
