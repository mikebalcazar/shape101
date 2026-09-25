"""El cuerpo visto desde la aplicación: regenerar con caché y dar la malla.

`historial.py` sabe convertir una lista de operaciones en un sólido. Aquí se
resuelve lo otro: que eso no se vuelva a hacer cada vez que la pantalla pide
algo. Regenerar un cuerpo de 60 operaciones desde cero cuesta 10 segundos
—medido en la prueba de concepto, P3— y la pantalla pide la malla cada vez que
giras la vista. Sin caché, girar sería insoportable.

La caché es por **huella de las operaciones**: si la lista no cambió, el sólido
tampoco. Nada de invalidar a mano, que es de donde salen los errores que nadie
logra reproducir.

Lo que se puede hacer con un cuerpo, y lo que significa:

- **extruir**: un contorno cerrado del dibujo se levanta y se vuelve sólido.
- **revolver, barrer, loft**: las otras tres maneras de que nazca un cuerpo.
  Torneado alrededor de un eje, perfil recorriendo un camino, y piel que pasa
  por varias secciones. No son para madera: son para cualquier pieza.
- **extruir_cara**: material nuevo con el perfil de una cara. No estira la
  cara: agrega un sólido encima.
- **empujar una cara**: la cara se mueve y el sólido se rehace. Positivo es
  hacia afuera. La cara se nombra por lo que es, no por un número: sigue siendo
  «arriba» aunque el boceto cambie.
- **mover un punto**: se cambia un vértice del boceto y el cuerpo entero se
  vuelve a construir sobre el contorno nuevo. No se deforma la malla: se rehace
  la pieza. Por eso un barreno hecho después sigue siendo redondo.
"""
from __future__ import annotations

import json

from core.solido import historial, malla as malla_mod, planos

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
    # La extrusión dice **de qué boceto** sale, por id. Antes se sobreentendía
    # («el de arriba») y eso se rompía en cuanto hubiera dos bocetos, que es
    # justo lo que hace falta para un loft o un barrido.
    return historial.asegurar_ids(
        [{"op": "boceto", "entidades": json.loads(json.dumps(entidades))},
         {"op": "extruir", "mm": float(mm), "perfil": "0"}])


# --- el grupo model, desde el dibujo  ·  0.19.0 -----------------------------
#
# Las tres funciones de abajo son hermanas de `ops_de_contorno`: reciben lo que
# el usuario señaló en el dibujo y devuelven el historial con el que nace la
# pieza. Todas ponen el boceto **en el plano de la ventana donde se dibujó**,
# no en el suelo: un barrido quiere el perfil en la Frontal y el camino en la
# Superior, y esos dos ya no se pueden rotar juntos al final.


def _boceto_de(entidades: list[dict], z: float = 0.0) -> dict:
    """Un paso «boceto» con su copia de las entidades y su plano."""
    if not entidades:
        raise ValueError("falta el contorno")
    plano = planos.del_dibujo(entidades[0].get("plano", "XY"), z)
    op = {"op": "boceto", "entidades": json.loads(json.dumps(entidades))}
    if plano is not None:
        op["plano"] = plano
    return op


def _dos_puntos(entidad: dict) -> dict:
    """Los dos extremos de la línea que el usuario señaló como eje."""
    t = entidad.get("tipo")
    if t == "linea":
        a, b = entidad.get("p1"), entidad.get("p2")
    elif t == "polilinea":
        pts = entidad.get("puntos") or []
        if len(pts) < 2:
            raise ValueError("el eje necesita una línea de dos puntos")
        a, b = pts[0], pts[-1]
    else:
        raise ValueError(f"un eje se señala con una línea, no con un «{t}»")
    return {"a": [float(a[0]), float(a[1])], "b": [float(b[0]), float(b[1])]}


def es_cerrada(entidad: dict) -> bool:
    """¿Esta entidad, ella sola, encierra un área?

    Por lo que la entidad **dice** y no por geometría a ojo: un círculo y una
    polilínea marcada como cerrada, sí; todo lo demás, no. Un contorno hecho de
    líneas sueltas cuenta como abierto aunque a la vista se cierre, y los
    comandos lo dicen con todas sus letras: se juntan antes con UNIR. Adivinar
    aquí es adivinar en silencio, y un contorno mal adivinado sale como una
    pieza mal hecha que nadie sabe por qué salió así.
    """
    t = entidad.get("tipo")
    if t == "circulo":
        return True
    if t == "polilinea":
        return bool(entidad.get("cerrada")) and len(entidad.get("puntos") or []) >= 3
    return False


def repartir(entidades: list[dict]) -> tuple[list[dict], list[dict]]:
    """La selección partida en (cerradas, abiertas), en el orden en que venía."""
    cerradas, abiertas = [], []
    for e in entidades:
        (cerradas if es_cerrada(e) else abiertas).append(e)
    return cerradas, abiertas


def ops_de_revolver(perfil: list[dict], eje: dict, grados: float = 360.0) -> list[dict]:
    """Torneado: el contorno gira alrededor de una línea del mismo dibujo."""
    if not (0 < float(grados) <= 360):
        raise ValueError("un revolucionado gira entre 0 y 360 grados")
    return historial.asegurar_ids([
        _boceto_de(perfil),
        {"op": "revolver", "perfil": "0", "eje": _dos_puntos(eje), "grados": float(grados)},
    ])


def ops_de_barrer(perfil: list[dict], camino: list[dict]) -> list[dict]:
    """El contorno recorre un camino. Los dos pueden venir de ventanas
    distintas —perfil en la Frontal, camino en la Superior— y cada uno se
    coloca en la suya."""
    if not camino:
        raise ValueError("falta el camino por donde barrer")
    return historial.asegurar_ids([
        _boceto_de(perfil),
        _boceto_de(camino),
        {"op": "barrer", "perfil": "0", "camino": "1"},
    ])


def ops_de_loft(secciones: list[list[dict]], alturas: list[float] | None = None,
                reglado: bool = False) -> list[dict]:
    """Una piel que pasa por varias secciones.

    `alturas` separa las secciones a lo largo de la normal de su ventana. Hace
    falta cuando se dibujaron todas en la misma: dos contornos de la Superior
    están los dos en el suelo, y una piel entre dos cosas que viven en el mismo
    plano no tiene volumen. Si ya vienen de ventanas distintas, se deja vacío.
    """
    if len(secciones) < 2:
        alturas_txt = "una sección" if len(secciones) == 1 else "ninguna"
        raise ValueError(f"un loft necesita al menos dos secciones, y llegó {alturas_txt}")
    alturas = list(alturas or [0.0] * len(secciones))
    while len(alturas) < len(secciones):
        alturas.append(0.0)
    ops = [_boceto_de(s, float(h)) for s, h in zip(secciones, alturas)]
    ops = historial.asegurar_ids(ops)
    ops.append({"op": "loft", "perfiles": [o["id"] for o in ops], "reglado": bool(reglado)})
    return historial.asegurar_ids(ops)


def agregar(operaciones: list, op: dict) -> list:
    """Una operación más al final, con su id recién puesto.

    Todo lo que agregue pasos pasa por aquí: así no hay dos maneras de darle
    identidad a una operación, y nunca nace una sin ella.
    """
    ops = historial.asegurar_ids(operaciones)
    nueva = json.loads(json.dumps(op))
    if nueva.get("id") in (None, ""):
        nueva["id"] = historial.id_libre(ops)
    return ops + [nueva]


def mover_punto(operaciones: list[dict], entidad: int, punto: int, x: float, y: float) -> list[dict]:
    """Cambia un vértice del boceto y devuelve las operaciones nuevas.

    Sólo toca el **primer** boceto: es el contorno con el que nació la pieza.
    Las operaciones de después —barrenos, redondeos, caras jaladas— no se tocan
    y se vuelven a aplicar solas al regenerar. Eso es justo lo que hace que
    valga la pena guardar cómo se hizo en vez de guardar la geometría.
    """
    ops = historial.asegurar_ids(operaciones)
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
    return agregar(operaciones, {"op": "mover_vertice", "vertice": nombre,
                                 "d": [float(k) for k in d]})


def mover_arista(operaciones: list, nombre: str, d) -> list:
    return agregar(operaciones, {"op": "mover_arista", "arista": nombre,
                                 "d": [float(k) for k in d]})


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


# --- las cotas del boceto  ·  0.16.0 -----------------------------------------
#
# Mike: *«hoy sólo se mueven los puntos con el ratón; que cambiar el ancho a 900
# sea teclear 900»*.
#
# Un contorno no trae cotas escritas: trae puntos. Así que las cotas se **sacan
# del contorno** —su caja— y al teclear una se estira el contorno hasta que la
# caja mida eso. No hay un resolvedor de restricciones detrás, y por eso esto
# es honesto para un rectángulo y para cualquier contorno de taller: lo que se
# promete es la medida de fuera, que es la que se corta.
#
# Lo que **no** hace, y conviene saberlo: no sostiene un lado paralelo a otro
# ni un ángulo recto por sí mismo. Si el contorno ya es un rectángulo, estirarlo
# lo deja rectángulo; si es una L, la L se estira entera, no un solo tramo.


def _puntos_del(op) -> list:
    """Todos los puntos del boceto que se pueden estirar, como referencias
    vivas (entidad, clave, índice) para poder escribirlos de vuelta."""
    fuera = []
    for e in op.get("entidades") or []:
        t = e.get("tipo")
        if t == "polilinea":
            for i, _ in enumerate(e.get("puntos") or []):
                fuera.append((e, "puntos", i))
        elif t in ("circulo", "arco"):
            fuera.append((e, "centro", None))
        elif t == "linea":
            fuera.append((e, "p1", None))
            fuera.append((e, "p2", None))
    return fuera


def _leer(ref) -> tuple:
    e, clave, i = ref
    p = e[clave][i] if i is not None else e[clave]
    return (float(p[0]), float(p[1]))


def _escribir(ref, x: float, y: float) -> None:
    e, clave, i = ref
    if i is not None:
        viejo = e[clave][i]
        bulge = viejo[2] if len(viejo) > 2 else 0
        e[clave][i] = [float(x), float(y), bulge]     # el bulge es curvatura: no se toca
    else:
        e[clave] = [float(x), float(y)]


def _caja_del(op) -> tuple:
    """La caja del boceto: (x0, y0, x1, y1). Un círculo cuenta con su radio,
    porque lo que mide la pieza es por dónde pasa el filo, no dónde está el
    centro."""
    xs, ys = [], []
    for ref in _puntos_del(op):
        e = ref[0]
        x, y = _leer(ref)
        r = float(e.get("radio", 0)) if e.get("tipo") in ("circulo", "arco") else 0.0
        xs += [x - r, x + r]
        ys += [y - r, y + r]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _es_rectangulo(op, tol: float = 1e-6) -> bool:
    ents = op.get("entidades") or []
    if len(ents) != 1 or ents[0].get("tipo") != "polilinea":
        return False
    e = ents[0]
    pts = e.get("puntos") or []
    if len(pts) != 4 or not e.get("cerrada"):
        return False
    if any(len(p) > 2 and abs(p[2]) > tol for p in pts):
        return False                                  # con bulge no es un rectángulo
    xs = {round(float(p[0]), 6) for p in pts}
    ys = {round(float(p[1]), 6) for p in pts}
    return len(xs) == 2 and len(ys) == 2


def _estirar(op: dict, eje: int, medida: float) -> None:
    """Estira el boceto en un eje hasta que su caja mida `medida`.

    Se estira **desde el lado chico**: la esquina de origen se queda donde
    está y el contorno crece hacia el otro lado. Es lo que uno espera al
    teclear una medida: el dibujo no se va del lugar.

    Un círculo dentro del boceto —un hueco— **mueve su centro pero conserva su
    radio**. Estirar un tablero de 600 a 900 no debe dejar el barreno ovalado:
    en madera no hay barrenos ovalados.
    """
    caja = _caja_del(op)
    a0, a1 = caja[eje], caja[eje + 2]
    largo = a1 - a0
    if largo <= 1e-9:
        raise ValueError("este contorno no tiene medida en ese sentido")
    if medida <= 0:
        raise ValueError("una medida tiene que ser mayor que cero")
    k = float(medida) / largo
    for ref in _puntos_del(op):
        p = list(_leer(ref))
        p[eje] = a0 + (p[eje] - a0) * k
        _escribir(ref, p[0], p[1])


def _correr(op: dict, eje: int, destino: float) -> None:
    """Lleva la esquina de origen del boceto a esa coordenada, sin deformarlo."""
    caja = _caja_del(op)
    d = float(destino) - caja[eje]
    if abs(d) < 1e-12:
        return
    for ref in _puntos_del(op):
        p = list(_leer(ref))
        p[eje] += d
        _escribir(ref, p[0], p[1])


def _del_boceto(op) -> tuple:
    """Título y campos de un boceto, según lo que traiga dentro."""
    ents = op.get("entidades") or []
    if len(ents) == 1 and ents[0].get("tipo") == "circulo":
        e = ents[0]
        return (f"Círculo ⌀{round(float(e.get('radio', 0)) * 2, 2)}",
                [_campo("entidades/0/radio", "Radio", e.get("radio", 0)),
                 _campo("entidades/0/centro/0", "Centro X", (e.get("centro") or [0, 0])[0]),
                 _campo("entidades/0/centro/1", "Centro Y", (e.get("centro") or [0, 0])[1])])
    x0, y0, x1, y1 = _caja_del(op)
    ancho, fondo = round(x1 - x0, 2), round(y1 - y0, 2)
    n = sum(len(e.get("puntos") or []) if e.get("tipo") == "polilinea" else 1 for e in ents)
    if _es_rectangulo(op):
        titulo = f"Rectángulo {ancho} × {fondo}"
    else:
        titulo = f"Contorno {ancho} × {fondo} · {n} punto(s)"
    campos = [_campo("ancho", "Ancho", ancho, minimo=0.01),
              _campo("fondo", "Fondo", fondo, minimo=0.01),
              _campo("x", "Esquina X", x0), _campo("y", "Esquina Y", y0)]
    return (titulo, campos)


def describir(operaciones: list) -> list:
    """El historial en palabras, con los números que se pueden tocar.

    El primer boceto y su extrusión son **de nacimiento**: sin ellos no hay
    pieza. Van marcados para que la pantalla no ofrezca borrarlos.
    """
    salida = []
    ops = historial.asegurar_ids(operaciones)
    mapa, nace = historial.enlaces(ops), historial.nace_el_solido(ops)
    for i, op in enumerate(ops):
        clase = op.get("op")
        campos, titulo = [], clase
        if clase == "boceto":
            titulo, campos = _del_boceto(op)
        elif clase == "extruir":
            titulo = f"Extruir {op.get('mm')}"
            campos = [_campo("mm", "Espesor", op.get("mm", 0))]
        elif clase == "revolver":
            g = op.get("grados", 360)
            titulo = f"Torneado {g}°" if g != 360 else "Torneado"
            campos = [_campo("grados", "Grados", g, unidad="°", minimo=0.01)]
        elif clase == "barrer":
            titulo = "Barrido por un camino"
        elif clase == "loft":
            titulo = f"Loft entre {len(op.get('perfiles') or [])} perfiles"
        elif clase == "primitiva":
            forma = op.get("forma", "?")
            nombre = {"caja": "Prisma", "cilindro": "Cilindro", "cono": "Cono",
                      "esfera": "Esfera", "piramide": "Pirámide"}.get(forma, forma)
            if forma in ("caja", "piramide"):
                titulo = f"{nombre} {op.get('ancho')} × {op.get('fondo')} × {op.get('alto')}"
                campos = [_campo("ancho", "Ancho", op.get("ancho", 0), minimo=0.01),
                          _campo("fondo", "Fondo", op.get("fondo", 0), minimo=0.01),
                          _campo("alto", "Alto", op.get("alto", 0), minimo=0.01)]
            elif forma == "esfera":
                titulo = f"{nombre} r{op.get('radio')}"
                campos = [_campo("radio", "Radio", op.get("radio", 0), minimo=0.01)]
            else:
                titulo = f"{nombre} r{op.get('radio')} × {op.get('alto')}"
                campos = [_campo("radio", "Radio", op.get("radio", 0), minimo=0.01),
                          _campo("alto", "Alto", op.get("alto", 0), minimo=0.01)]
                if forma == "cono":
                    campos.append(_campo("radio2", "Radio de arriba", op.get("radio2", 0), minimo=0))
        elif clase == "extruir_cara":
            titulo = f"Cara «{op.get('cara')}» crecida {op.get('mm')}"
            campos = [_campo("mm", "Cuánto", op.get("mm", 0))]
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
        # «De nacimiento» ya no es una posición: es que quitarlo rompería algo.
        # La pantalla esconde la × exactamente donde el motor se negaría.
        salida.append({"i": i, "id": op.get("id"), "op": clase, "titulo": titulo,
                       "campos": campos,
                       "de_nacimiento": bool(_por_que_no_se_quita(ops, i, mapa, nace))})
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
    ops = historial.asegurar_ids(operaciones)
    if not (0 <= i < len(ops)):
        raise ValueError(f"no hay una operación {i}")
    # Ancho, fondo y esquina no viven en ningún lado dentro de la operación: se
    # sacan de la caja del contorno. Por eso no son una ruta sino una cuenta.
    CALCULADAS = {"ancho": (_estirar, 0), "fondo": (_estirar, 1),
                  "x": (_correr, 0), "y": (_correr, 1)}
    for clave, valor in (campos or {}).items():
        hacer = CALCULADAS.get(clave)
        if hacer is not None:
            if ops[i].get("op") != "boceto":
                raise ValueError(f"la operación {i} no tiene «{clave}»")
            hacer[0](ops[i], hacer[1], float(valor))
            continue
        try:
            _poner(ops[i], clave, valor)
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"la operación {i} no tiene «{clave}»") from e
    return ops


def quitar_operacion(operaciones: list, i: int) -> list:
    """Quita un paso. Las de nacimiento no se quitan: sin ellas no hay pieza."""
    ops = historial.asegurar_ids(operaciones)
    if not (0 <= i < len(ops)):
        raise ValueError(f"no hay una operación {i}")
    porque = _por_que_no_se_quita(ops, i)
    if porque:
        raise ValueError(porque)
    del ops[i]
    return ops


def _por_que_no_se_quita(ops: list, i: int, mapa=None, nace=None) -> str:
    """Vacío si ese paso se puede quitar; si no, por qué no.

    Hasta la 0.18.0 la regla era por **posición**: los dos primeros no se
    quitan. Con ids eso deja de valer —un loft son dos bocetos y luego el
    loft, así que la posición 1 es un boceto que sí se puede quitar si nadie
    lo usa—. La regla ahora es la de verdad: **no se quita lo que sostiene a
    otra cosa**.
    """
    # `mapa` y `nace` se pasan hechos cuando se pregunta por todos los pasos
    # seguidos —`describir`—: calcularlos una vez por paso sería cuadrático, y
    # un historial largo es justo donde se nota.
    if mapa is None:
        mapa = historial.enlaces(ops)
    if nace is None:
        nace = historial.nace_el_solido(ops)
    id_ = str(ops[i]["id"])
    if id_ == nace:
        return "sin la operación que crea el sólido no hay pieza"
    usan = [k for k, usa in mapa.items() if id_ in usa]
    if usan:
        return f"no se puede quitar: lo usa(n) {', '.join(usan)}"
    return ""


def ops_de_barreno(centro, radio: float, mm: float, plano_ref=None) -> dict:
    """Un barreno es un círculo extruido y restado. Se guarda así —el círculo,
    no el hueco— y por eso se le puede cambiar el diámetro después."""
    if radio <= 0:
        raise ValueError("un barreno necesita un radio mayor que cero")
    return {"op": "restar",
            "entidades": [{"tipo": "circulo", "centro": [float(centro[0]), float(centro[1])],
                           "radio": float(radio)}],
            "mm": float(mm)}
