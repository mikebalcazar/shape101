"""El documento de shape101 como historial regenerable  ·  P3.

Un documento es una lista de operaciones en JSON. Se regenera desde cero cada
vez (P3 pide medirlo así); la caché por operación queda para la app.

Operaciones:
  {"op": "boceto",   "entidades": [...draw101...]}        o "t101d": ruta
  {"op": "extruir",  "mm": 18}
  {"op": "restar",   "entidades": [...], "mm": 18}       barreno/cajeado: se extruye y se resta
  {"op": "redondear", "aristas": ["lado[0]|lado[1]", ...], "r": 20}
  {"op": "empujar_cara", "cara": "arriba", "mm": 10}     positivo = hacia afuera

Las referencias (caras y aristas) son **nombres por derivación** (nombres.py):
así una cota del boceto puede cambiar y «arriba», «lado[2]» o
«lado[1]|lado[2]» siguen significando lo mismo.
"""
from __future__ import annotations

import json
import pathlib
import time

from build123d import Face, extrude, fillet

from core.solido import boceto, nombres, t101d


class Regenerado:
    def __init__(self, solido, nombrador: nombres.Nombrador, tiempos: list[dict], estado=None):
        self.solido = solido
        self.nombrador = nombrador
        self.tiempos = tiempos          # [{op, ms}]
        self.estado = estado

    @property
    def ms(self) -> float:
        return sum(t["ms"] for t in self.tiempos)


def _entidades(op: dict) -> list[dict]:
    if "entidades" in op:
        return op["entidades"]
    return t101d.leer(op["t101d"])["entidades"]


OPERACIONES = {"boceto", "extruir", "restar", "redondear", "empujar_cara"}


class Estado:
    def __init__(self):
        self.solido = None
        self.nom = nombres.Nombrador()
        self.boceto_pendiente = None
        self.tiempos: list[dict] = []
        self.ops: list[dict] = []


def _paso(est: Estado, i: int, op: dict) -> None:
    t0 = time.perf_counter()
    clase = op["op"]
    nom, solido = est.nom, est.solido
    if clase == "boceto":
        est.boceto_pendiente = _entidades(op)
    elif clase == "extruir":
        if est.boceto_pendiente is None:
            raise ValueError(f"op {i}: extruir sin boceto antes")
        ents = est.boceto_pendiente
        solido = extrude(boceto.cara_de(ents), amount=op["mm"])
        nom.bautizar_extrusion(solido, [a for e in ents for a in boceto.aristas_de(e)], op["mm"])
        est.boceto_pendiente = None
    elif clase == "restar":
        ents = _entidades(op)
        herramienta = extrude(boceto.cara_de(ents), amount=op["mm"])
        nom_h = nombres.Nombrador()
        nom_h.bautizar_extrusion(herramienta, [a for e in ents for a in boceto.aristas_de(e)], op["mm"], prefijo=f"restar[{i}]/")
        solido = solido - herramienta
        nom.rebautizar(solido, nuevas=nom_h.caras)
    elif clase == "redondear":
        aristas = [nom.arista(solido, a) for a in op["aristas"]]
        nuevo = fillet(aristas, radius=op["r"])
        candidatas = [f for f in nuevo.faces() if nom.nombre_de(f) is None]
        nuevas = {f"redondeo[{i}]/{na}": f for na, f in zip(op["aristas"], _ordenar_redondeos(candidatas, aristas))}
        solido = nuevo
        nom.rebautizar(solido, nuevas=nuevas)
    elif clase == "empujar_cara":
        cara = nom.cara(op["cara"])
        mm = op["mm"]
        if mm != 0:
            if mm > 0:
                pieza = extrude(cara, amount=abs(mm))
                solido = solido + pieza
                movida = Face(pieza.faces().sort_by(lambda f: f.normal_at().dot(cara.normal_at()))[-1].wrapped)
            else:
                pieza = extrude(cara, amount=-abs(mm))
                solido = solido - pieza
                movida = Face(pieza.faces().sort_by(lambda f: f.normal_at().dot(cara.normal_at()))[0].wrapped)
            nom.rebautizar(solido, nuevas={"__movida__": movida}, heredan={op["cara"]: "__movida__"})
    else:
        raise ValueError(f"op {i}: no conozco «{clase}»")
    est.solido = solido
    est.ops.append(op)
    est.tiempos.append({"op": f"{i}:{clase}", "ms": (time.perf_counter() - t0) * 1000})


def regenerar(operaciones: list[dict]) -> Regenerado:
    """Desde cero, siempre. Es lo que P3 mide."""
    est = Estado()
    for i, op in enumerate(operaciones):
        _paso(est, i, op)
    return Regenerado(est.solido, est.nom, est.tiempos, est)


def extender(reg: "Regenerado", op: dict) -> Regenerado:
    """Una operación más sobre lo ya regenerado: lo que haría la app con caché
    por operación cuando lo que cambia es la última. Devuelve el mismo
    Regenerado, actualizado."""
    est = reg.estado
    _paso(est, len(est.ops), op)
    reg.solido, reg.nombrador, reg.tiempos = est.solido, est.nom, est.tiempos
    return reg


def _ordenar_redondeos(caras_nuevas, aristas):
    """Cada cara de redondeo va con la arista que la produjo: la más cercana."""
    out = []
    restantes = list(caras_nuevas)
    for a in aristas:
        m = a.position_at(0.5)
        mejor = min(restantes, key=lambda f: (f.center() - m).length)
        restantes.remove(mejor)
        out.append(mejor)
    return out


def cargar(ruta) -> list[dict]:
    return json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))


def guardar(operaciones: list[dict], ruta) -> None:
    pathlib.Path(ruta).write_text(json.dumps(operaciones, ensure_ascii=False, indent=1), encoding="utf-8")
