"""Cotas: medida y geometría  ·  features 50 a 59.

Una cota **no** guarda las rayitas que se ven. Guarda los puntos que mide y el
estilo con el que se dibuja; lo que se ve se calcula aquí cada vez. Así, cambiar
la altura del texto en el estilo cambia las doscientas cotas del plano, y mover
la pieza mueve su cota (feature 58) sin tener que rehacerla.

Es el mismo trato del DXF con las cotas asociativas, y la razón por la que este
módulo existe en Python y no en el navegador: la misma geometría se usa para
pintar en pantalla, para el PDF de impresión (F6) y para comprobar el valor
medido en las pruebas.
"""

from __future__ import annotations

import math

from . import capas as mod_capas
from .documento import ESTILO_COTA_T101, Documento


def _estilo(doc: Documento, cota) -> dict:
    est = dict(ESTILO_COTA_T101)
    est.update(doc.estilos_cota.get(cota.estilo, {}))
    return est


def _u(ang_grados):
    r = math.radians(ang_grados)
    return math.cos(r), math.sin(r)


def _sum(a, b, k=1.0):
    return [a[0] + b[0] * k, a[1] + b[1] * k]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _resta(a, b):
    return [a[0] - b[0], a[1] - b[1]]


def formato(valor: float, est: dict, texto: str = "") -> str:
    """El texto que va sobre la cota. Si el usuario escribió uno, manda el suyo.

    `<>` se sustituye por la medida, como en AutoCAD: así se puede escribir
    «<> APROX» o «2 A <>» sin perder el número que se recalcula solo.
    """
    # `factor_medida` traduce lo medido a la medida de verdad. Acotando sobre
    # una hoja, la cota mide milímetros de papel: 172 mm sobre una ventana a
    # 1:20 son 3 450 mm de mueble, y lo que tiene que decir el plano es 3 450.
    valor = valor * float(est.get("factor_medida", 1.0) or 1.0)
    dec = int(est.get("decimales", 0))
    medida = f"{valor:.{dec}f}" + (est.get("sufijo") or "")
    if not texto:
        return medida
    return texto.replace("<>", medida)


def _flecha(punto, direccion, est: dict, escala: float) -> list:
    """Las rayitas del extremo. La palomita de arquitectura por omisión: es la
    que se usa en planos de mueble y la que no se confunde con una línea de
    cota cuando las cotas quedan encimadas."""
    tam = est.get("tam_flecha", 2.0) * escala
    tipo = (est.get("flecha") or "ARCHTICK").upper()
    dx, dy = direccion
    if tipo == "ARCHTICK":
        # raya a 45° centrada en el punto
        c, s = math.cos(math.radians(45)), math.sin(math.radians(45))
        vx, vy = dx * c - dy * s, dx * s + dy * c
        return [[_sum(punto, (vx, vy), -tam / 2), _sum(punto, (vx, vy), tam / 2)]]
    # triángulo cerrado, dibujado con tres rayas
    nx, ny = -dy, dx
    base = _sum(punto, (dx, dy), tam)
    a = _sum(base, (nx, ny), tam * 0.18)
    b = _sum(base, (nx, ny), -tam * 0.18)
    return [[punto, a], [a, b], [b, punto]]


# =========================================================================
# Cada clase de cota
# =========================================================================

def _lineal(doc, cota, est, escala):
    """Cota lineal y alineada  ·  features 50 y 51.

    `puntos` = [origen 1, origen 2, punto por el que pasa la línea de cota].
    `rotacion` es la dirección en que se mide: 0 horizontal, 90 vertical, y
    para la alineada, la del propio segmento.
    """
    p1, p2, pl = cota.puntos[0], cota.puntos[1], cota.puntos[2]
    if cota.clase == "alineada":
        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
    else:
        ang = cota.rotacion
    d = _u(ang)
    n = (-d[1], d[0])

    # los orígenes se proyectan sobre la línea de cota que pasa por pl
    t1 = _dot(_resta(p1, pl), d)
    t2 = _dot(_resta(p2, pl), d)
    q1 = _sum(pl, d, t1)
    q2 = _sum(pl, d, t2)
    medida = abs(t2 - t1)

    hueco = est.get("hueco_origen", 0.625) * escala
    sobra = est.get("ext_linea", 1.25) * escala
    lineas = []

    # líneas de extensión: del origen a la línea de cota, con su hueco y su
    # sobresalida. El hueco existe para que la cota no toque la pieza.
    for origen, q in ((p1, q1), (p2, q2)):
        v = _resta(q, origen)
        largo = math.hypot(v[0], v[1])
        if largo < 1e-9:
            continue
        u = (v[0] / largo, v[1] / largo)
        lineas.append([_sum(origen, u, hueco), _sum(q, u, sobra)])

    # línea de cota
    lineas.append([q1, q2])

    # flechas, apuntando cada una hacia afuera
    signo = 1 if t2 >= t1 else -1
    lineas.extend(_flecha(q1, (-d[0] * signo, -d[1] * signo), est, escala))
    lineas.extend(_flecha(q2, (d[0] * signo, d[1] * signo), est, escala))

    altura = est.get("altura_texto", 2.5) * escala
    medio = [(q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2]
    # El texto va encima de la línea, y el ángulo se endereza para que nunca
    # quede de cabeza: una cota que se lee al revés no se lee.
    ang_texto = ang % 360
    if 90 < ang_texto <= 270:
        ang_texto = (ang_texto + 180) % 360
    base = _sum(medio, n, altura * 0.45 * (1 if (90 < ang % 360 <= 270) else 1))
    texto = {"p": base, "texto": formato(medida, est, cota.texto),
             "altura": altura, "rotacion": ang_texto, "alineacion": "CENTRO"}
    # La línea de cota, aparte: es a lo que se engancha el osnap al colocar
    # otra cota en el mismo renglón (Mike, 9-sep-2026). Ver core/geometria.py.
    return lineas, texto, medida, [q1, q2]


def _angular(doc, cota, est, escala):
    """Cota angular  ·  feature 53.  puntos = [vértice, p1, p2, punto del arco]."""
    v, p1, p2 = cota.puntos[0], cota.puntos[1], cota.puntos[2]
    pa = cota.puntos[3] if len(cota.puntos) > 3 else p1
    r = math.hypot(pa[0] - v[0], pa[1] - v[1])
    a1 = math.degrees(math.atan2(p1[1] - v[1], p1[0] - v[0])) % 360
    a2 = math.degrees(math.atan2(p2[1] - v[1], p2[0] - v[0])) % 360
    barrido = (a2 - a1) % 360
    if barrido > 180:
        a1, a2 = a2, a1
        barrido = 360 - barrido
    medida = barrido

    lineas = []
    sobra = est.get("ext_linea", 1.25) * escala
    for p, a in ((p1, a1), (p2, a2)):
        largo = math.hypot(p[0] - v[0], p[1] - v[1])
        u = _u(a)
        lineas.append([_sum(v, u, min(largo, r) * 0.0 + est.get("hueco_origen", 0.625) * escala),
                       _sum(v, u, r + sobra)])

    # el arco de la cota, en trocitos
    n = max(6, int(barrido / 5) + 1)
    pts = [_sum(v, _u(a1 + barrido * i / n), r) for i in range(n + 1)]
    for i in range(n):
        lineas.append([pts[i], pts[i + 1]])

    for a, sentido in ((a1, -1), (a2, 1)):
        u = _u(a)
        tang = (-u[1] * sentido, u[0] * sentido)
        lineas.extend(_flecha(_sum(v, u, r), tang, est, escala))

    altura = est.get("altura_texto", 2.5) * escala
    medio = _sum(v, _u(a1 + barrido / 2), r + altura * 0.7)
    texto = {"p": medio, "texto": formato(medida, est, cota.texto) + "°",
             "altura": altura, "rotacion": 0, "alineacion": "CENTRO"}
    return lineas, texto, medida


def _radial(doc, cota, est, escala):
    """Radio y diámetro  ·  feature 54.  puntos = [centro, punto del borde]."""
    c, p = cota.puntos[0], cota.puntos[1]
    r = math.hypot(p[0] - c[0], p[1] - c[1])
    diam = cota.clase == "diametro"
    medida = r * 2 if diam else r

    v = _resta(p, c)
    largo = math.hypot(v[0], v[1]) or 1
    u = (v[0] / largo, v[1] / largo)
    altura = est.get("altura_texto", 2.5) * escala

    inicio = _sum(c, u, -r) if diam else list(c)
    lineas = [[inicio, p]]
    lineas.extend(_flecha(p, u, est, escala))
    if diam:
        lineas.extend(_flecha(inicio, (-u[0], -u[1]), est, escala))

    prefijo = "⌀" if diam else "R"
    fuera = _sum(p, u, altura * 1.2)
    ang = math.degrees(math.atan2(u[1], u[0])) % 360
    if 90 < ang <= 270:
        ang = (ang + 180) % 360
    texto = {"p": fuera, "texto": prefijo + formato(medida, est, cota.texto),
             "altura": altura, "rotacion": ang, "alineacion": "IZQ"}
    return lineas, texto, medida


def _directriz(doc, cota, est, escala):
    """Directriz con texto  ·  feature 55.  puntos = [punta, codo, texto]."""
    pts = cota.puntos
    lineas = []
    for i in range(len(pts) - 1):
        lineas.append([pts[i], pts[i + 1]])
    if len(pts) >= 2:
        v = _resta(pts[0], pts[1])
        largo = math.hypot(v[0], v[1]) or 1
        lineas.extend(_flecha(pts[0], (v[0] / largo, v[1] / largo), est, escala))
    altura = est.get("altura_texto", 2.5) * escala
    fin = pts[-1]
    hacia_derecha = len(pts) < 2 or fin[0] >= pts[-2][0]
    texto = {"p": [fin[0] + (altura * 0.4 if hacia_derecha else -altura * 0.4),
                   fin[1] + altura * 0.25],
             "texto": cota.texto or "", "altura": altura, "rotacion": 0,
             "alineacion": "IZQ" if hacia_derecha else "DER"}
    return lineas, texto, 0.0


CLASES = {
    "lineal": _lineal, "alineada": _lineal,
    "angular": _angular,
    "radio": _radial, "diametro": _radial,
    "directriz": _directriz,
}


def tamano_hoja(doc: Documento, nombre_hoja: str) -> float:
    """Por cuánto se multiplica el estilo (a 1:1) en una hoja  ·  0.20.0.

    Mike (9-sep-2026): «cada página de plano tiene su propio tamaño de cota».
    La hoja guarda `tam_cotas`: la altura del texto de cota **en mm de papel**.
    Lo que se conserva es el valor medido —la geometría vive en el modelo—; lo
    que cambia por hoja es la presentación. Sin `tam_cotas`, la hoja usa la
    altura del estilo tal cual (2.5 mm de papel), que es lo de siempre.
    """
    for L in getattr(doc, "layouts", None) or []:
        if L.get("nombre") == nombre_hoja:
            tam = L.get("tam_cotas")
            if tam:
                est = dict(ESTILO_COTA_T101)
                est.update(doc.estilos_cota.get("T101", {}))
                base = float(est.get("altura_texto", 2.5) or 2.5)
                return float(tam) / base
            return 1.0
    return 1.0


def escala_efectiva(doc: Documento, cota, escala_forzada: float | None = None) -> float:
    """Por cuánto se multiplica el estilo para **esta** cota.

    `escala_forzada` es lo que pide una hoja al pintar el modelo por su
    ventana (ver core/papel.py): ahí mandan los mm de papel de la hoja, y el
    factor propio de la cota sólo cuenta si está encadenada al base.
    """
    est = _estilo(doc, cota)
    ft = float(getattr(cota, "factor_tamano", 1.0) or 1.0)
    encadenada = bool(getattr(cota, "encadenada", True))
    if escala_forzada is not None:
        return escala_forzada * (ft if encadenada else 1.0)
    en_hoja = getattr(cota, "espacio", "") or ""
    if en_hoja:
        # **Sobre una hoja el estilo no se escala.** El `factor_escala` (el
        # DIMSCALE) existe para que una cota dibujada en el modelo se imprima
        # legible después de encogerla en la ventana. Una cota puesta
        # directamente sobre el papel ya está a tamaño de papel: aplicarle el
        # mismo factor sacaría letras de tres centímetros en un A3. Lo que sí
        # sigue es el tamaño de cotas **de esa hoja** (`tam_cotas`).
        base = tamano_hoja(doc, en_hoja)
    else:
        base = float(est.get("factor_escala", 1.0)) or 1.0
    # Encadenada: proporción sobre el base del documento. Suelta: tamaño
    # absoluto propio, el estilo a 1:1 por su factor.
    return base * ft if encadenada else ft


def geometria(doc: Documento, cota, escala_forzada: float | None = None) -> dict:
    """Todo lo que se ve de una cota: rayas, texto y la medida que anuncia."""
    est = _estilo(doc, cota)
    escala = escala_efectiva(doc, cota, escala_forzada)
    fm = float(getattr(cota, "factor_medida", 1.0) or 1.0)
    if fm != 1.0:
        est = {**est, "factor_medida": fm}
    fn = CLASES.get(cota.clase)
    if fn is None:
        return {"lineas": [], "texto": None, "medida": 0.0}
    try:
        salida = fn(doc, cota, est, escala)
    except (IndexError, TypeError, ValueError):
        # Una cota mal formada no debe impedir abrir el plano.
        return {"lineas": [], "texto": None, "medida": 0.0}
    lineas, texto, medida = salida[0], salida[1], salida[2]
    g = {"lineas": lineas, "texto": texto, "medida": medida * fm}
    if len(salida) > 3:
        g["linea_cota"] = salida[3]
    return g


def medida(doc: Documento, cota) -> float:
    return geometria(doc, cota)["medida"]


# =========================================================================
# Asociatividad  ·  feature 58
# =========================================================================
# `cota.liga` es una lista paralela a `cota.puntos`: para cada punto, o `null`
# —el usuario lo puso a mano y ahí se queda— o {id, campo, indice}, que dice de
# qué entidad y de qué parte suya salió.
#
# Cuando esa entidad se mueve, el punto de la cota se mueve con ella y la medida
# se recalcula sola. Es la diferencia entre un plano que se mantiene solo y un
# plano en el que hay que revisar cada cota después de cada cambio.

def _punto_de(ent, campo: str, indice) -> list | None:
    try:
        if campo == "puntos" and indice is not None:
            v = ent.puntos[int(indice)]
            return [v[0], v[1]]
        valor = getattr(ent, campo, None)
        if valor is None:
            return None
        if campo in ("p", "p1", "p2", "centro"):
            return [valor[0], valor[1]]
        if isinstance(valor, list) and len(valor) >= 2 and not isinstance(valor[0], list):
            return [valor[0], valor[1]]
    except (IndexError, TypeError, ValueError):
        return None
    return None


def actualizar_ligadas(doc: Documento, ids_movidos) -> list[str]:
    """Recorre las cotas y mueve los puntos que colgaban de lo que cambió."""
    movidos = set(ids_movidos)
    tocadas = []
    for cota in list(doc.entidades.values()):
        if cota.tipo != "cota" or not cota.liga:
            continue
        cambio = False
        puntos = [list(p) for p in cota.puntos]
        desplazamientos = []          # (dx, dy) de cada punto ligado que se movió
        seguidos = set()
        for i, liga in enumerate(cota.liga):
            if not liga or i >= len(puntos):
                continue
            if liga.get("id") not in movidos:
                continue
            ent = doc.entidades.get(liga["id"])
            if ent is None:
                continue
            seguidos.add(i)
            nuevo = _punto_de(ent, liga.get("campo", ""), liga.get("indice"))
            if not nuevo:
                continue
            d = (nuevo[0] - puntos[i][0], nuevo[1] - puntos[i][1])
            # El desplazamiento se apunta **aunque sea cero**. Es lo que
            # distingue un traslado de un estirado: al estirar una pieza por un
            # extremo, el otro punto ligado se mueve (0, 0) y el de abajo
            # (300, 0). Sin el cero apuntado, la lista queda con un solo
            # desplazamiento, «todos iguales» se cumple sola, y la línea de
            # cota se va 300 de lado siguiendo un traslado que nunca ocurrió
            # (lo cazó `t008`).
            desplazamientos.append(d)
            if abs(d[0]) > 1e-9 or abs(d[1]) > 1e-9:
                puntos[i] = nuevo
                cambio = True
        if cambio:
            # Mike (7-sep-2026): «las cotas se deben de mover con referencia a la
            # entidad de la que se referencian». Si la pieza se **trasladó**
            # —todos sus puntos ligados se movieron lo mismo—, la línea de cota,
            # el texto y el codo de la directriz se van con ella, para que la
            # cota quede igual respecto de la pieza. Si la pieza se estiró o
            # giró, sólo siguen los puntos ligados, como antes.
            libres = [i for i in range(len(puntos)) if i not in seguidos
                      and not (i < len(cota.liga) and cota.liga[i])]
            todos_ligados = {i for i, l in enumerate(cota.liga) if l and i < len(puntos)}
            if libres and desplazamientos and todos_ligados <= seguidos and all(
                    abs(d[0] - desplazamientos[0][0]) < 1e-6 and abs(d[1] - desplazamientos[0][1]) < 1e-6
                    for d in desplazamientos):
                dx, dy = desplazamientos[0]
                for i in libres:
                    puntos[i] = [puntos[i][0] + dx, puntos[i][1] + dy]
            doc.modificar(cota.id, {"puntos": puntos})
            tocadas.append(cota.id)
    return tocadas


def limpiar_ligas(doc: Documento, ids_borrados) -> None:
    """Si se borra la pieza, la cota deja de seguirla pero **no** se borra:
    borrar cotas por detrás sería peor que dejarlas quietas."""
    borrados = set(ids_borrados)
    for cota in doc.entidades.values():
        if cota.tipo != "cota" or not cota.liga:
            continue
        nueva = [None if (l and l.get("id") in borrados) else l for l in cota.liga]
        if nueva != cota.liga:
            cota.liga = nueva


# =========================================================================
# En qué capa vive una cota
# =========================================================================

def encapar(doc: Documento, entidad):
    """Manda la entidad a la capa de cotas si es una cota. Devuelve la entidad.

    **Toda cota nace en `COTAS`**, dé igual en qué capa se esté trabajando. Es
    una decisión de Mike y es la costumbre de cualquier taller: las cotas son
    una capa que se apaga entera para ver el dibujo limpio, o se imprime aparte,
    y eso deja de funcionar en cuanto una se queda regada en la capa de muros.
    Moverla después es un clic; encontrar la que se quedó fuera, no.

    Se impone **aquí, en el motor**, y no en la interfaz: así vale igual para la
    cota que dibuja alguien, la que llega importada de Taller 101 y la que entre
    por la API el día que haya una. Una regla que hay que acordarse de aplicar
    en tres sitios no es una regla.

    Si la capa no existe todavía —un DWG ajeno, por ejemplo— se crea del
    catálogo, en azul Taller 101.
    """
    if getattr(entidad, "tipo", None) != "cota":
        return entidad
    entidad.capa = mod_capas.asegurar(doc, mod_capas.CAPA_COTAS)
    return entidad
