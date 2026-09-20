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


def tiradores(cuerpo) -> dict:
    """De qué se puede jalar esta pieza: **sus vértices y sus aristas de
    verdad**, no los puntos del boceto.

    Mike, el 19-sep: «todas las aristas son independientes y todos los puntos
    también». Hasta la 0.13.0 los tiradores salían del contorno, así que una
    esquina de abajo y la de arriba eran el mismo punto y moverla movía las
    dos. Ahora cada uno es suyo.

    Cada tirador viaja con su **nombre**, no con un índice: `abajo|lado[0]|
    lado[3]` es la esquina donde se juntan esas tres caras, y lo sigue siendo
    aunque cambie una cota del boceto. Es lo mismo que ya hacía posible jalar
    una cara y que siguiera jalada.

    Todo en coordenadas del kernel; `rutas.py` lo gira al plano de la pieza.
    """
    reg = regenerar(cuerpo)
    salida = {"id": cuerpo.id, "plano": getattr(cuerpo, "plano", "XY"),
              "vertices": [], "aristas": []}
    if reg.solido is None:
        return salida
    for nombre, v in reg.nombrador.vertices(reg.solido).items():
        salida["vertices"].append({"nombre": nombre, "p": [v.X, v.Y, v.Z]})
    for nombre, e in reg.nombrador.aristas(reg.solido).items():
        m = e.position_at(0.5)
        a, b = e.start_point(), e.end_point()
        salida["aristas"].append({"nombre": nombre, "p": [m.X, m.Y, m.Z],
                                  "a": [a.X, a.Y, a.Z], "b": [b.X, b.Y, b.Z],
                                  "recta": e.geom_type.name == "LINE"})
    return salida


def mover_vertice(operaciones: list, nombre: str, d) -> list:
    """Una operación más al final: esa esquina, corrida. No se toca nada de lo
    anterior, así que deshacer es quitar la última y ya."""
    return json.loads(json.dumps(operaciones)) + [
        {"op": "mover_vertice", "vertice": nombre, "d": [float(k) for k in d]}]


def mover_arista(operaciones: list, nombre: str, d) -> list:
    return json.loads(json.dumps(operaciones)) + [
        {"op": "mover_arista", "arista": nombre, "d": [float(k) for k in d]}]


# --- el historial, para verlo y editarlo -----------------------------------
#
# Mike, 19-sep: «el mantener algo de historial de cómo se generó un barreno
# (ej. se hace un trazo de un cilindro y se resta al volumen), pero después se
# quiere agrandar o achicar: sólo se podría incrementar o disminuir el diámetro
# del cilindro original sin necesidad de trazarlo todo de nuevo».
#
# Eso ya lo hacía el motor desde el primer día: un cuerpo es una lista de
# operaciones y regenerar es volver a correrlas. Lo que faltaba era **enseñarlo
# y dejarlo tocar**. De eso se trata lo de aquí abajo: describir cada operación
# en palabras del taller, con sus números editables, y aplicar el cambio.
#
# Cada campo dice su `clave` —dónde vive el número dentro de la operación— para
# que la pantalla no tenga que saber de qué está hecha cada una. Si mañana hay
# una operación nueva, se describe aquí y la pantalla ya sabe pintarla.

def _campo(clave, etiqueta, valor, unidad="mm", minimo=None):
    return {"clave": clave, "etiqueta": etiqueta, "valor": round(float(valor), 4),
            "unidad": unidad, "minimo": minimo}


def _del_boceto(op) -> tuple:
    """Título y campos de un boceto, según lo que traiga dentro."""
    ents = op.get("entidades") or []
    if len(ents) == 1 and ents[0].get("tipo") == "circulo":
        e = ents[0]
        return (f"Círculo ⌀{round(float(e.get('radio', 0)) * 2, 2)}",
                [_campo("entidades/0/radio", "Radio", e.get("radio", 0)),
                 _campo("entidades/0/centro/0", "Centro X", (e.get("centro") or [0, 0])[0]),
                 _campo("entidades/0/centro/1", "Centro Y", (e.get("centro") or [0, 0])[1])])
    n = sum(len(e.get("puntos") or []) if e.get("tipo") == "polilinea" else 1 for e in ents)
    return (f"Contorno · {len(ents)} entidad(es), {n} punto(s)", [])


def describir(operaciones: list) -> list:
    """El historial en palabras, con los números que se pueden tocar.

    El primer boceto y su extrusión son **de nacimiento**: sin ellos no hay
    pieza. Van marcados para que la pantalla no ofrezca borrarlos.
    """
    salida = []
    for i, op in enumerate(operaciones):
        clase = op.get("op")
        campos, titulo = [], clase
        if clase == "boceto":
            titulo, campos = _del_boceto(op)
        elif clase == "extruir":
            titulo = f"Extruir {op.get('mm')}"
            campos = [_campo("mm", "Espesor", op.get("mm", 0))]
        elif clase == "restar":
            ents = op.get("entidades") or []
            forma = ents[0].get("tipo") if ents else "?"
            if forma == "circulo":
                r = float(ents[0].get("radio", 0))
                titulo = f"Barreno ⌀{round(r * 2, 2)}"
                campos = [_campo("entidades/0/radio", "Radio", r, minimo=0.01),
                          _campo("entidades/0/centro/0", "Centro X",
                                 (ents[0].get("centro") or [0, 0])[0]),
                          _campo("entidades/0/centro/1", "Centro Y",
                                 (ents[0].get("centro") or [0, 0])[1]),
                          _campo("mm", "Profundidad", op.get("mm", 0))]
            else:
                titulo = f"Corte ({forma})"
                campos = [_campo("mm", "Profundidad", op.get("mm", 0))]
        elif clase == "redondear":
            aristas = op.get("aristas") or []
            titulo = f"Redondeo r{op.get('r')} · {len(aristas)} arista(s)"
            campos = [_campo("r", "Radio", op.get("r", 0), minimo=0.01)]
        elif clase == "empujar_cara":
            titulo = f"Cara «{op.get('cara')}» jalada {op.get('mm')}"
            campos = [_campo("mm", "Cuánto", op.get("mm", 0))]
        elif clase in ("mover_vertice", "mover_arista"):
            que = "Punto" if clase == "mover_vertice" else "Arista"
            nombre = op.get("vertice") or op.get("arista") or ""
            d = op.get("d") or [0, 0, 0]
            titulo = f"{que} «{nombre}» movido"
            campos = [_campo("d/0", "En X", d[0]), _campo("d/1", "En Y", d[1]),
                      _campo("d/2", "En Z", d[2])]
        salida.append({"i": i, "op": clase, "titulo": titulo, "campos": campos,
                       "de_nacimiento": clase in ("boceto", "extruir") and i < 2})
    return salida


def _poner(op: dict, clave: str, valor: float) -> None:
    """Mete un número donde dice la clave. `entidades/0/centro/1` es
    `op["entidades"][0]["centro"][1]`: una ruta y ya, sin casos especiales.

    **El campo tiene que existir ya.** Si no se exige, una clave equivocada
    —una versión vieja de la pantalla, un dedo torcido— no falla: le cuelga a
    la operación un campo inventado que nadie lee, la pieza sale igual y el
    error se descubre tres cambios después. Mejor que se niegue aquí.
    """
    partes = clave.split("/")
    d = op
    for p in partes[:-1]:
        d = d[int(p)] if p.isdigit() else d[p]
    ultima = partes[-1]
    if ultima.isdigit():
        d[int(ultima)] = float(valor)
    else:
        if ultima not in d:
            raise KeyError(ultima)
        d[ultima] = float(valor)


def cambiar_operacion(operaciones: list, i: int, campos: dict) -> list:
    """Los números nuevos de una operación. El resto del historial no se toca:
    por eso un barreno se agranda sin volver a trazar nada."""
    ops = json.loads(json.dumps(operaciones))
    if not (0 <= i < len(ops)):
        raise ValueError(f"no hay una operación {i}")
    for clave, valor in (campos or {}).items():
        try:
            _poner(ops[i], clave, valor)
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"la operación {i} no tiene «{clave}»") from e
    return ops


def quitar_operacion(operaciones: list, i: int) -> list:
    """Quita un paso. Las de nacimiento no se quitan: sin ellas no hay pieza."""
    ops = json.loads(json.dumps(operaciones))
    if not (0 <= i < len(ops)):
        raise ValueError(f"no hay una operación {i}")
    if ops[i].get("op") in ("boceto", "extruir") and i < 2:
        raise ValueError("el contorno y la extrusión son de nacimiento: sin ellos no hay pieza")
    del ops[i]
    return ops


def ops_de_barreno(centro, radio: float, mm: float, plano_ref=None) -> dict:
    """Un barreno es un círculo extruido y restado. Se guarda así —el círculo,
    no el hueco— y por eso se le puede cambiar el diámetro después."""
    if radio <= 0:
        raise ValueError("un barreno necesita un radio mayor que cero")
    return {"op": "restar",
            "entidades": [{"tipo": "circulo", "centro": [float(centro[0]), float(centro[1])],
                           "radio": float(radio)}],
            "mm": float(mm)}
