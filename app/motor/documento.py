"""El documento de shape101: UNA pieza más su historial de operaciones.

Decisiones de Mike del 13-sep, por botones:
  - un documento = una pieza (el ensamble vendrá aparte, como documento que
    referencia piezas);
  - mm con centésimas: lo que se teclea y se muestra va a 0,01; el kernel por
    dentro trabaja exacto;
  - la pieza guarda material y espesor como dato, aparte de la geometría.

El archivo `.s101` es JSON UTF-8 con los bocetos EMBEBIDOS (entidades de
draw101, nunca la ruta de un .t101d: un archivo suelto es un archivo que se
pierde). Un boceto se puede AGREGAR como `{"op": "boceto", "t101d": ruta}`: se
lee ahí mismo y lo que se guarda son sus entidades, ya en milímetros, más de
qué archivo y en qué unidades vinieron.

La caché por operación es parte del contrato, no una mejora: P3 midió 10 s
para regenerar 60 operaciones desde cero. Cada operación guarda el sólido y
los nombres de caras que dejó; al regenerar se busca la primera operación que
cambió y sólo se ejecutan ésa y las que siguen. `tiempos` del Regenerado trae
únicamente lo que de verdad se volvió a ejecutar.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

from app.motor import historial, t101d

FORMATO = "shape101"
VERSION_FORMATO = 1
PLANOS_BLOQUE_1 = {"XY"}


def _ahora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _redondear(v, decimales: int):
    """Toda medida que entra se redondea a `decimales` (centésimas): 10,006 → 10,01."""
    if isinstance(v, float):
        return round(v, decimales)
    if isinstance(v, list):
        return [_redondear(x, decimales) for x in v]
    if isinstance(v, dict):
        return {k: _redondear(x, decimales) for k, x in v.items()}
    return v


class Documento:
    def __init__(self, pieza: dict, unidades: str = "mm", decimales: int = 2,
                 operaciones: list | None = None, creado: str | None = None, modificado: str | None = None):
        self.pieza = dict(pieza)
        self.unidades = unidades
        self.decimales = decimales
        self.operaciones: list[dict] = list(operaciones or [])
        self.creado = creado or _ahora()
        self.modificado = modificado or self.creado
        self._cache: list[dict] = []        # una entrada por operación ya ejecutada

    # -- crear / abrir / guardar ---------------------------------------------
    @classmethod
    def nuevo(cls, nombre: str, material: str, espesor_mm: float) -> "Documento":
        return cls(pieza={"nombre": str(nombre), "material": str(material),
                          "espesor_mm": round(float(espesor_mm), 2)})

    def a_dict(self) -> dict:
        return {"formato": FORMATO, "version": VERSION_FORMATO, "unidades": self.unidades,
                "decimales": self.decimales, "pieza": dict(self.pieza),
                "operaciones": [dict(op) for op in self.operaciones],
                "creado": self.creado, "modificado": self.modificado}

    def guardar(self, ruta) -> pathlib.Path:
        ruta = pathlib.Path(ruta)
        if ruta.suffix.lower() != ".s101":
            ruta = ruta.with_suffix(".s101")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.modificado = _ahora()
        tmp = ruta.with_suffix(".s101.tmp")
        tmp.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(ruta)          # primero el temporal, luego el reemplazo: nunca un archivo a medias
        return ruta

    @classmethod
    def abrir(cls, ruta) -> "Documento":
        datos = json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))
        if datos.get("formato") != FORMATO:
            raise ValueError(f"{ruta}: no es un archivo de shape101 (formato «{datos.get('formato')}»)")
        if int(datos.get("version", 1)) > VERSION_FORMATO:
            raise ValueError(f"{ruta}: lo hizo una versión más nueva de shape101 (formato {datos['version']})")
        doc = cls(pieza=datos["pieza"], unidades=datos.get("unidades", "mm"), decimales=int(datos.get("decimales", 2)),
                  operaciones=datos.get("operaciones", []), creado=datos.get("creado"), modificado=datos.get("modificado"))
        for op in doc.operaciones:
            doc._validar(op)
        return doc

    # -- el historial ----------------------------------------------------------
    def _validar(self, op) -> dict:
        if not isinstance(op, dict) or "op" not in op:
            raise ValueError("una operación es un objeto con la clave «op»")
        if op["op"] not in historial.OPERACIONES:
            raise ValueError(f"no conozco la operación «{op['op']}»; las que hay: {', '.join(sorted(historial.OPERACIONES))}")
        if op["op"] == "boceto":
            plano = op.get("plano", "XY")
            if plano not in PLANOS_BLOQUE_1:
                raise ValueError(f"el plano «{plano}» todavía no: por ahora sólo XY")
            if "t101d" in op:
                if "entidades" in op:
                    raise ValueError("un boceto trae o sus «entidades» o un «t101d», no los dos")
                op = dict(op)
                lectura = t101d.leer(op.pop("t101d"))
                if not lectura["entidades"]:
                    raise ValueError(f"{pathlib.Path(lectura['archivo']).name}: el modelo no trae "
                                     f"líneas, arcos, círculos ni polilíneas que hagan un boceto")
                op["entidades"] = lectura["entidades"]
                op["origen"] = {"archivo": lectura["archivo"], "dibujo": lectura["dibujo"],
                                "unidades": lectura["unidades"], "importado": _ahora()}
            if "entidades" not in op:
                raise ValueError("un boceto lleva sus entidades embebidas («entidades»), no una ruta")
        return _redondear(op, self.decimales)

    def agregar(self, op: dict) -> dict:
        op = self._validar(op)
        self.operaciones.append(op)
        self.modificado = _ahora()
        return op

    def editar(self, i: int, op: dict) -> dict:
        op = self._validar(op)
        self.operaciones[i] = op          # IndexError si no existe: se deja ver
        self.modificado = _ahora()
        return op

    def borrar(self, i: int) -> dict:
        op = self.operaciones.pop(i)
        self.modificado = _ahora()
        return op

    # -- regenerar con caché por operación -------------------------------------
    @staticmethod
    def _clave(op: dict) -> str:
        return json.dumps(op, sort_keys=True, ensure_ascii=False)

    def regenerar(self) -> historial.Regenerado:
        claves = [self._clave(op) for op in self.operaciones]
        k = 0
        while k < len(claves) and k < len(self._cache) and self._cache[k]["clave"] == claves[k]:
            k += 1
        est = historial.Estado()
        if k > 0:
            base = self._cache[k - 1]
            est.solido = base["solido"]
            est.nom.caras = dict(base["caras"])
            est.boceto_pendiente = base["boceto_pendiente"]
            est.ops = list(self.operaciones[:k])
        cache = self._cache[:k]
        for i in range(k, len(self.operaciones)):
            historial._paso(est, i, self.operaciones[i])
            cache.append({"clave": claves[i], "solido": est.solido, "caras": dict(est.nom.caras),
                          "boceto_pendiente": est.boceto_pendiente})
        self._cache = cache
        return historial.Regenerado(est.solido, est.nom, est.tiempos, est)
