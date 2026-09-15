"""El cuerpo visto desde la aplicación: regenerar con caché y dar la malla.

`historial.py` sabe convertir una lista de operaciones en un sólido. Aquí se
resuelve lo otro: que eso no se vuelva a hacer cada vez que la pantalla pide
algo. Regenerar un cuerpo de 60 operaciones desde cero cuesta 10 segundos
—medido en la prueba de concepto, P3— y la pantalla pide la malla cada vez que
giras la vista. Sin caché, girar sería insoportable.

La caché es por **huella de las operaciones**: si la lista no cambió, el sólido
tampoco. Nada de invalidar a mano, que es de donde salen los errores que nadie
logra reproducir.

Las tres cosas que se pueden hacer con un cuerpo, y lo que significan:

- **extruir**: un contorno cerrado del dibujo se levanta y se vuelve sólido.
- **empujar una cara**: la cara se mueve y el sólido se rehace. Positivo es
  hacia afuera. La cara se nombra por lo que es, no por un número: sigue siendo
  «arriba» aunque el boceto cambie.
- **mover un punto**: se cambia un vértice del boceto y el cuerpo entero se
  vuelve a construir sobre el contorno nuevo. No se deforma la malla: se rehace
  la pieza. Por eso un barreno hecho después sigue siendo redondo.
"""
from __future__ import annotations

import json

from core.solido import historial, malla as malla_mod

# Cuántos cuerpos regenerados se guardan en memoria. Un documento con más de
# esto es raro; lo que se cae del borde se vuelve a calcular y ya.
TOPE = 24

_cache: dict[str, tuple[str, historial.Regenerado]] = {}


def _huella(operaciones: list[dict]) -> str:
    return json.dumps(operaciones, sort_keys=True, ensure_ascii=False)


def regenerar(cuerpo) -> historial.Regenerado:
    """El sólido de este cuerpo, calculado sólo si sus operaciones cambiaron."""
    huella = _huella(cuerpo.operaciones)
    guardado = _cache.get(cuerpo.id)
    if guardado is not None and guardado[0] == huella:
        return guardado[1]
    reg = historial.regenerar(cuerpo.operaciones)
    if len(_cache) >= TOPE:
        _cache.pop(next(iter(_cache)))
    _cache[cuerpo.id] = (huella, reg)
    return reg


def olvidar(id_: str | None = None) -> None:
    """Se llama al cerrar o al abrir otro dibujo. Sin esto, dos documentos con
    cuerpos del mismo id se pisarían la caché."""
    if id_ is None:
        _cache.clear()
    else:
        _cache.pop(id_, None)


def malla(cuerpo) -> dict:
    """Lo que la pantalla necesita para pintarlo: **una malla por cara**, con su
    nombre, más las aristas.

    Una sola malla para todo el sólido sería más rápida de pintar y serviría de
    poco: sin caras separadas no se puede señalar una con el ratón ni saber
    cuál es para jalarla. El nombre que viaja aquí es el mismo del historial.
    """
    reg = regenerar(cuerpo)
    if reg.solido is None:
        return {"id": cuerpo.id, "caras": [], "aristas": [], "n_caras": 0,
                "n_triangulos": 0, "caja": [0, 0, 0], "volumen_mm3": 0.0,
                "operaciones": len(cuerpo.operaciones)}
    m, _ = malla_mod.malla_de(reg, {}, ms_regenerar=reg.ms)
    caja = reg.solido.bounding_box()
    m["id"] = cuerpo.id
    m["caja"] = [round(caja.size.X, 2), round(caja.size.Y, 2), round(caja.size.Z, 2)]
    m["volumen_mm3"] = round(reg.solido.volume, 1)
    m["operaciones"] = len(cuerpo.operaciones)
    return m


def aristas(cuerpo) -> list[str]:
    reg = regenerar(cuerpo)
    if reg.solido is None:
        return []
    return sorted(reg.nombrador.aristas(reg.solido))


def caras(cuerpo) -> list[str]:
    return sorted(regenerar(cuerpo).nombrador.caras)


# --- armar las operaciones -------------------------------------------------

def ops_de_contorno(entidades: list[dict], mm: float) -> list[dict]:
    """Las dos operaciones que convierten un contorno del dibujo en un sólido.

    Las entidades se copian tal cual llegan del dibujo: el cuerpo se queda con
    su propia copia y deja de depender de que esas líneas sigan ahí. Si el
    usuario borra el contorno después, la pieza no desaparece.
    """
    if not entidades:
        raise ValueError("no hay contorno que extruir")
    if mm == 0:
        raise ValueError("un espesor de cero no hace un sólido")
    return [{"op": "boceto", "entidades": json.loads(json.dumps(entidades))},
            {"op": "extruir", "mm": float(mm)}]


def mover_punto(operaciones: list[dict], entidad: int, punto: int, x: float, y: float) -> list[dict]:
    """Cambia un vértice del boceto y devuelve las operaciones nuevas.

    Sólo toca el **primer** boceto: es el contorno con el que nació la pieza.
    Las operaciones de después —barrenos, redondeos, caras jaladas— no se tocan
    y se vuelven a aplicar solas al regenerar. Eso es justo lo que hace que
    valga la pena guardar cómo se hizo en vez de guardar la geometría.
    """
    ops = json.loads(json.dumps(operaciones))
    for op in ops:
        if op.get("op") != "boceto":
            continue
        ents = op.get("entidades") or []
        if not (0 <= entidad < len(ents)):
            raise ValueError(f"el boceto no tiene la entidad {entidad}")
        e = ents[entidad]
        if e.get("tipo") == "polilinea":
            pts = e.get("puntos") or []
            if not (0 <= punto < len(pts)):
                raise ValueError(f"esa polilínea no tiene el punto {punto}")
            bulge = pts[punto][2] if len(pts[punto]) > 2 else 0
            pts[punto] = [float(x), float(y), bulge]      # el bulge es curvatura: no se toca
        elif e.get("tipo") in ("circulo", "arco"):
            e["centro"] = [float(x), float(y)]
        elif e.get("tipo") == "linea":
            e["p1" if punto == 0 else "p2"] = [float(x), float(y)]
        else:
            raise ValueError(f"todavía no sé mover puntos de un «{e.get('tipo')}»")
        return ops
    raise ValueError("este cuerpo no tiene boceto que mover")
