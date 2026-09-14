"""Convierte el documento en trazos listos para pintar en el lienzo.

La matemática vive aquí, en Python, no en el navegador: arcos, bulges, elipses
y splines salen ya convertidos en polilíneas. La interfaz sólo estira líneas.

Así la misma conversión sirve después para el PDF (F6) y para el render de
impresión, sin escribirla dos veces en dos lenguajes.
"""

from __future__ import annotations

import math

from . import capas as mod_capas
from . import cotas as mod_cotas
from .documento import Documento

# Cuántos segmentos por vuelta completa, como máximo. 72 = uno cada 5°; a la
# vista de un plano de taller no se distingue de una curva, y no ahoga al lienzo.
SEGMENTOS = 72
MIN_SEG = 6
# Medido el 13-sep-2026 (objetivo 1, fluidez, camino C): en un plano de
# 21 700 entidades, 390 000 de los 425 000 vértices que viajan al navegador
# eran círculos y arcos a 72 segmentos fijos, sin importar el radio. Un barreno
# de ⌀5 no necesita 73 puntos: la cuerda de un polígono de 16 lados a ese
# radio se separa del círculo 0.05 mm, que no se ve ni se corta. La regla:
# tantos segmentos como pida no separarse más de FLECHA_MAX mm de la curva,
# entre MIN_SEG y SEGMENTOS por vuelta. Los círculos grandes siguen a 72.
FLECHA_MAX = 0.05
# Se probó redondear las coordenadas a milésimas antes de mandarlas (13-sep):
# el JSON bajaba 40 % (19 → 12 MB en el plano de prueba) pero el redondeo en
# Python costaba 0.6 s por apertura y el navegador no ganaba nada medible.
# No se hizo. La geometría del osnap tampoco se redondea: los grips comparan
# con la entidad exacta (tolerancia 1e-6) y se rompían (t007).


def _segmentos_por_vuelta(r: float) -> int:
    if r <= 0:
        return MIN_SEG
    c = 1 - FLECHA_MAX / r
    if c <= -1:
        return MIN_SEG
    if c >= 1:
        return SEGMENTOS
    n = math.ceil(math.pi / math.acos(c))
    return max(MIN_SEG, min(SEGMENTOS, n))


def _arco_puntos(cx, cy, r, a0, a1, sentido=1):
    """a0 y a1 en radianes. sentido 1 = antihorario."""
    barrido = (a1 - a0) * sentido
    while barrido < 0:
        barrido += 2 * math.pi
    n = max(MIN_SEG, int(_segmentos_por_vuelta(r) * barrido / (2 * math.pi)) + 1)
    return [[cx + r * math.cos(a0 + sentido * barrido * i / n),
             cy + r * math.sin(a0 + sentido * barrido * i / n)]
            for i in range(n + 1)]


def _bulge(p1, p2, bulge):
    """Tramo de arco entre dos vértices de polilínea, según su bulge.

    bulge = tan(ángulo/4). Es como el DXF guarda los arcos dentro de una
    polilínea; ignorarlo convierte cada arco en una recta, que es justo el
    error que hace que una puerta redondeada salga cuadrada en la CNC.
    """
    # Siempre se devuelven puntos de dos componentes: el vértice de una
    # polilínea trae tres (x, y, bulge) y colarlo tal cual reventaba más
    # adelante, al transformar el contenido de un bloque.
    if abs(bulge) < 1e-12:
        return [[p2[0], p2[1]]]
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    cuerda = math.hypot(x2 - x1, y2 - y1)
    if cuerda < 1e-12:
        return [[p2[0], p2[1]]]
    angulo = 4 * math.atan(bulge)
    r = cuerda / (2 * math.sin(abs(angulo) / 2))
    # centro
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    h = math.sqrt(max(r * r - (cuerda / 2) ** 2, 0.0))
    dx, dy = (x2 - x1) / cuerda, (y2 - y1) / cuerda
    signo = 1 if angulo > 0 else -1
    cx, cy = mx - signo * h * dy, my + signo * h * dx
    a0 = math.atan2(y1 - cy, x1 - cx)
    a1 = math.atan2(y2 - cy, x2 - cx)
    pts = _arco_puntos(cx, cy, r, a0, a1, sentido=signo)
    return pts[1:]


def _polilinea(puntos, cerrada):
    if not puntos:
        return []
    salida = [[puntos[0][0], puntos[0][1]]]
    for i in range(len(puntos) - 1):
        b = puntos[i][2] if len(puntos[i]) > 2 else 0.0
        salida.extend(_bulge(puntos[i], puntos[i + 1], b))
    if cerrada and len(puntos) > 2:
        b = puntos[-1][2] if len(puntos[-1]) > 2 else 0.0
        salida.extend(_bulge(puntos[-1], puntos[0], b))
    return salida


def _elipse(e):
    cx, cy = e.centro[0], e.centro[1]
    ax, ay = e.eje_mayor[0], e.eje_mayor[1]
    a = math.hypot(ax, ay)
    b = a * e.razon
    rot = math.atan2(ay, ax)
    t0, t1 = e.param_ini, e.param_fin
    barrido = t1 - t0
    if barrido <= 0:
        barrido += 2 * math.pi
    n = max(MIN_SEG, int(_segmentos_por_vuelta(max(a, b)) * barrido / (2 * math.pi)) + 1)
    pts = []
    for i in range(n + 1):
        t = t0 + barrido * i / n
        x, y = a * math.cos(t), b * math.sin(t)
        pts.append([cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)])
    return pts


def _spline(puntos, cerrada=False):
    """Curva suave que pasa por los puntos dados (Catmull–Rom).

    Se dibuja la curva, no el zigzag entre los puntos: una spline que en
    pantalla parece una polilínea engaña al que la dibuja, que la ve recta y la
    da por buena. Al DXF sale como SPLINE de verdad, con sus puntos de ajuste.
    """
    pts = [[p[0], p[1]] for p in puntos]
    if len(pts) < 3:
        return pts
    if cerrada:
        pts = pts + [pts[0]]
    ext = [pts[0]] + pts + [pts[-1]]
    salida = [pts[0]]
    POR_TRAMO = 12
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(1, POR_TRAMO + 1):
            t = k / POR_TRAMO
            t2, t3 = t * t, t * t * t
            salida.append([
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)])
    return salida


def _bspline(control, grado=3, cerrada=False):
    """Curva por **puntos de control** (B-spline uniforme sujeta, De Boor).

    Es la curva «orgánica» que pidió Mike el 6-sep —la de Bézier de Illustrator
    y la de puntos de control de Rhino—: no pasa por los puntos, se deja jalar
    por ellos. Pasar por ellos con Catmull-Rom, como se hacía, la deformaba: en
    AutoCAD la misma spline se veía distinta. Sujeta en los extremos para que
    arranque y termine en el primero y el último punto, como el SPLINE CV de
    AutoCAD.
    """
    pts = [[p[0], p[1]] for p in control]
    if cerrada and len(pts) > 2:
        pts = pts + pts[:grado]
    n = len(pts)
    if n < 2:
        return pts
    k = max(1, min(grado, n - 1))
    # Nudos: sujetos (k+1 repetidos en cada punta) y uniformes en medio.
    interiores = n - k - 1
    nudos = [0.0] * (k + 1) + [(i + 1) / (interiores + 1) for i in range(interiores)] + [1.0] * (k + 1)

    def de_boor(t):
        # Tramo donde cae t.
        s = k
        while s < n - 1 and t >= nudos[s + 1]:
            s += 1
        d = [pts[j + s - k][:] for j in range(k + 1)]
        for r in range(1, k + 1):
            for j in range(k, r - 1, -1):
                den = nudos[j + 1 + s - r] - nudos[j + s - k]
                a = 0.0 if den == 0 else (t - nudos[j + s - k]) / den
                d[j] = [(1 - a) * d[j - 1][0] + a * d[j][0], (1 - a) * d[j - 1][1] + a * d[j][1]]
        return d[k]

    POR_TRAMO = 10
    total = max(1, n - k) * POR_TRAMO
    salida = [de_boor(i / total) for i in range(total)]
    salida.append(pts[-1] if not cerrada else salida[0])
    return salida


def _transformar(pts, px, py, sx, sy, rot_grados):
    r = math.radians(rot_grados)
    cos, sen = math.cos(r), math.sin(r)
    out = []
    for x, y in pts:
        x, y = x * sx, y * sy
        out.append([px + x * cos - y * sen, py + x * sen + y * cos])
    return out


def _trazos_de(doc: Documento, e, base: dict, transformar=None) -> list[dict]:
    """Devuelve los trazos de una entidad. `base` trae color, grosor y patrón."""
    t = e.tipo
    lineas: list[list] = []
    textos: list[dict] = []

    if t == "linea":
        lineas.append([[e.p1[0], e.p1[1]], [e.p2[0], e.p2[1]]])
    elif t == "polilinea":
        lineas.append(_polilinea(e.puntos, e.cerrada))
    elif t == "circulo":
        lineas.append(_arco_puntos(e.centro[0], e.centro[1], e.radio, 0, 2 * math.pi))
    elif t == "arco":
        lineas.append(_arco_puntos(e.centro[0], e.centro[1], e.radio,
                                   math.radians(e.ang_ini), math.radians(e.ang_fin)))
    elif t == "elipse":
        lineas.append(_elipse(e))
    elif t == "spline":
        # Con puntos de ajuste, pasa por ellos; sólo con los de control, se deja
        # jalar por ellos (ver _bspline). Son dos curvas distintas a propósito.
        if e.puntos_ajuste:
            lineas.append(_spline(e.puntos_ajuste, e.cerrada))
        else:
            lineas.append(_bspline(e.puntos_control, e.grado or 3, e.cerrada))
    elif t == "punto":
        d = 1.0
        lineas.append([[e.p[0] - d, e.p[1]], [e.p[0] + d, e.p[1]]])
        lineas.append([[e.p[0], e.p[1] - d], [e.p[0], e.p[1] + d]])
    elif t == "solido":
        pts = [[p[0], p[1]] for p in e.puntos]
        if pts:
            lineas.append(pts + [pts[0]])
    elif t == "rayado":
        for ruta in e.rutas:
            lineas.append(_polilinea(ruta, True))
        # El patrón, de verdad (0.20.0). Un sólido viaja como relleno aparte;
        # un patrón de rayas, como rayas recortadas al contorno.
        from . import rayado as mod_rayado
        patron = (e.patron or "SOLID").upper()
        if e.solido or patron == "SOLID":
            salida = []
            for pts in lineas:
                if len(pts) >= 2:
                    salida.append(dict(base, clase="linea", puntos=pts))
            poligonos = [mod_rayado._teselar(r) for r in e.rutas if len(r) >= 2]
            if poligonos:
                salida.append(dict(base, clase="relleno", poligonos=poligonos))
            return salida
        for par in mod_rayado.rayas(e.rutas, patron, e.escala or 1.0, e.angulo or 0.0,
                                    doc.mm_por_unidad()):
            lineas.append(par)
    elif t == "texto":
        textos.append({"p": [e.p[0], e.p[1]], "texto": e.texto, "altura": e.altura,
                       "rotacion": e.rotacion, "alineacion": e.alineacion})
    elif t == "textom":
        textos.append({"p": [e.p[0], e.p[1]], "texto": e.texto, "altura": e.altura,
                       "rotacion": e.rotacion, "alineacion": "IZQ"})
    elif t == "insercion":
        bl = doc.bloques.get(e.bloque)
        if bl is None:
            return []
        if es_pesado(doc, e.bloque):
            # Un solo trazo-instancia: el lienzo pinta la definición del
            # bloque (que viaja una vez) con esta transformación. Ver
            # `definicion_bloque` y, del otro lado, `dibujarPlano` en vista.js.
            return [dict(base, clase="insercion", bloque=e.bloque,
                         p=[e.p[0], e.p[1]], escala=[e.escala[0], e.escala[1]],
                         rotacion=e.rotacion, caja=list(doc.caja_de(e)))]
        salida = []
        for sub in bl.entidades:
            base_sub = dict(base)
            if sub.color:
                base_sub["color"] = sub.color
            for tr in _trazos_de(doc, sub, base_sub):
                if tr.get("puntos"):
                    tr["puntos"] = _transformar(
                        tr["puntos"], e.p[0] - bl.base[0] * e.escala[0],
                        e.p[1] - bl.base[1] * e.escala[1],
                        e.escala[0], e.escala[1], e.rotacion)
                if tr.get("texto"):
                    tr["p"] = _transformar([tr["p"]], e.p[0], e.p[1],
                                           e.escala[0], e.escala[1], e.rotacion)[0]
                    # **La letra también escala.** Un bloque metido al doble
                    # movía su texto al doble de distancia pero lo dejaba del
                    # mismo tamaño: el rótulo se salía de su cuadro. El texto
                    # gira con el bloque por la misma razón.
                    f = (abs(e.escala[0]) + abs(e.escala[1])) / 2
                    if f and abs(f - 1) > 1e-9:
                        tr["altura"] = tr.get("altura", 2.5) * f
                    if e.rotacion:
                        tr["rotacion"] = tr.get("rotacion", 0) + e.rotacion
                salida.append(tr)
        return salida
    elif t == "cota":
        # La cota se calcula, no se guarda dibujada: ver core/cotas.py.
        g = mod_cotas.geometria(doc, e)
        for par in g["lineas"]:
            lineas.append([[par[0][0], par[0][1]], [par[1][0], par[1][1]]])
        if g["texto"] and g["texto"]["texto"]:
            textos.append(g["texto"])
    elif t == "imagen":
        return [dict(base, clase="imagen", id=e.id, p=[e.p[0], e.p[1]],
                     ancho=e.ancho, alto=e.alto, opacidad=e.opacidad,
                     archivo=e.archivo)]
    elif t == "cruda":
        # No sabemos *editarla*, pero sí sabemos cómo se ve: el archivo lo dice
        # y se guardó al abrir. Se pinta. Un plano ajeno sin sus cotas parece un
        # plano al que le faltan las cotas, y no es el caso: están enteras y
        # salen intactas al exportar.
        salida = []
        for pts in (e.dibujo or []):
            if len(pts) >= 2:
                salida.append(dict(base, clase="linea", puntos=[[p[0], p[1]] for p in pts],
                                   dxftype=e.dxftype, ajena=True))
        for tx in (e.textos or []):
            salida.append(dict(base, clase="texto", p=[tx["p"][0], tx["p"][1]],
                               texto=tx.get("texto", ""), altura=tx.get("altura", 2.5),
                               rotacion=tx.get("rotacion", 0.0),
                               alineacion=tx.get("alineacion", "IZQ"),
                               dxftype=e.dxftype, ajena=True))
        if not salida:
            # Ni siquiera eso se pudo sacar: se marca el lugar, para que quien
            # mire sepa que ahí hay algo que el archivo sí lleva.
            return [dict(base, clase="ajena", puntos=[], dxftype=e.dxftype)]
        return salida
    else:
        return []

    salida = []
    for pts in lineas:
        if len(pts) >= 2:
            salida.append(dict(base, clase="linea", puntos=pts))
    for tx in textos:
        salida.append(dict(base, clase="texto", **tx))
    return salida


# --- Bloques pesados: se mandan una vez, se instancian ---------------------
#
# El A8-501 de Mike (6-sep): 664 palmeras de 8 000 trazos cada una. Explotar
# cada inserción a sus trazos daba 559 MB de JSON y 2.7 millones de
# primitivas: el navegador no lo podía ni leer («estado.trazos is not
# iterable»). AutoCAD no lo hace así: la definición vive una vez y cada
# inserción es un punto, una escala y un giro. Aquí igual, para los bloques
# que lo ameritan: los chicos siguen explotados, que es lo que esperan la
# selección, el osnap y las pruebas.

#: Un bloque es «pesado» si su definición pasa de tantos vértices, o si
#: definición × usos pasa del segundo tope. Un mueble de 200 vértices puesto
#: 30 veces no lo es; una palmera de 57 000, sí, aunque esté una sola vez.
PESADO_VERTICES = 4000
PESADO_TOTAL = 150_000


def _vertices_definicion(doc: Documento, nombre: str, _visto=None) -> int:
    bl = doc.bloques.get(nombre)
    if bl is None:
        return 0
    _visto = _visto or set()
    if nombre in _visto:
        return 0
    _visto.add(nombre)
    n = 0
    for sub in bl.entidades:
        if sub.tipo == "insercion":
            n += _vertices_definicion(doc, sub.bloque, _visto)
        else:
            for tr in _trazos_de(doc, sub, {}):
                n += len(tr.get("puntos") or []) or 1
    return n


def bloques_pesados(doc: Documento) -> set[str]:
    """Los nombres de bloque que se instancian. En caché del documento; se
    tira con `olvidar()` sin ids (cambios de bloques) o al cambiar `sucio`."""
    cache = doc.__dict__.setdefault("_pesados_cache", {})
    llave = (len(doc.bloques), len(doc.entidades))
    if cache.get("llave") == llave:
        return cache["pesados"]
    usos: dict[str, int] = {}
    for e in doc.entidades.values():
        if e.tipo == "insercion":
            usos[e.bloque] = usos.get(e.bloque, 0) + 1
    pesados = set()
    for nombre, n in usos.items():
        v = _vertices_definicion(doc, nombre)
        if v > PESADO_VERTICES or v * n > PESADO_TOTAL:
            pesados.add(nombre)
    cache["llave"] = llave
    cache["pesados"] = pesados
    return pesados


def es_pesado(doc: Documento, nombre: str) -> bool:
    return nombre in bloques_pesados(doc)


def _adelgazar(puntos, tol):
    """Quitar vértices que no se distinguen del anterior a menos de `tol`.

    Los bloques que vienen de Revit o de catálogos traen una palmera con
    57 000 vértices en un metro: a cualquier escala de plóter son la misma
    línea. Se conservan siempre el primero y el último."""
    if len(puntos) < 3 or tol <= 0:
        return puntos
    salida = [puntos[0]]
    ux, uy = puntos[0][0], puntos[0][1]
    t2 = tol * tol
    for q in puntos[1:-1]:
        dx, dy = q[0] - ux, q[1] - uy
        if dx * dx + dy * dy >= t2:
            salida.append(q)
            ux, uy = q[0], q[1]
    salida.append(puntos[-1])
    return salida


#: Un bloque se manda con esta resolución respecto a su tamaño: 1/2000 de su
#: diagonal (0.5 mm en un mueble de un metro). Más fino no se ve ni en papel.
FINURA_BLOQUE = 1 / 2000


def definicion_bloque(doc: Documento, nombre: str) -> dict | None:
    """La definición de un bloque pesado, en coordenadas locales (relativas a
    su punto base), para que el lienzo la pinte una vez por inserción.

    Los colores: los que el sub-elemento trae fijos van puestos; los que van
    «por bloque» van en null y el lienzo pone el de la inserción. Los bloques
    anidados se aplanan aquí mismo: una definición es una lista de trazos."""
    bl = doc.bloques.get(nombre)
    if bl is None:
        return None
    trazos: list[dict] = []
    x0 = y0 = float("inf"); x1 = y1 = float("-inf")

    def meter(b, px, py, sx, sy, rot, profundidad):
        nonlocal x0, y0, x1, y1
        if profundidad > 6:
            return
        for sub in b.entidades:
            if sub.tipo == "insercion":
                sb = doc.bloques.get(sub.bloque)
                if sb is None:
                    continue
                # Componer: el sub-bloque se coloca dentro de éste.
                r = math.radians(rot)
                cos, sen = math.cos(r), math.sin(r)
                lx = (sub.p[0] - sb.base[0] * sub.escala[0]) * sx
                ly = (sub.p[1] - sb.base[1] * sub.escala[1]) * sy
                meter(sb, px + lx * cos - ly * sen, py + lx * sen + ly * cos,
                      sx * sub.escala[0], sy * sub.escala[1], rot + sub.rotacion, profundidad + 1)
                continue
            base = {"color": sub.color or None,
                    "grosor": (sub.grosor if getattr(sub, "grosor", 0) else 0) / 100.0,
                    "patron": mod_capas.TIPOS_LINEA.get(getattr(sub, "tipo_linea", "") or "", {}).get("patron", []),
                    "escala_tl": getattr(sub, "escala_tl", 1.0)}
            for tr in _trazos_de(doc, sub, base):
                if tr.get("puntos"):
                    tr["puntos"] = _transformar(tr["puntos"], px, py, sx, sy, rot)
                    for q in tr["puntos"]:
                        if q[0] < x0: x0 = q[0]
                        if q[0] > x1: x1 = q[0]
                        if q[1] < y0: y0 = q[1]
                        if q[1] > y1: y1 = q[1]
                elif tr.get("texto"):
                    tr["p"] = _transformar([tr["p"]], px, py, sx, sy, rot)[0]
                    f = (abs(sx) + abs(sy)) / 2
                    if f and abs(f - 1) > 1e-9:
                        tr["altura"] = tr.get("altura", 2.5) * f
                    if rot:
                        tr["rotacion"] = tr.get("rotacion", 0) + rot
                    x0 = min(x0, tr["p"][0]); x1 = max(x1, tr["p"][0])
                    y0 = min(y0, tr["p"][1]); y1 = max(y1, tr["p"][1])
                trazos.append(tr)

    meter(bl, -bl.base[0], -bl.base[1], 1.0, 1.0, 0.0, 0)
    if x0 == float("inf"):
        x0 = y0 = x1 = y1 = 0.0
    # Adelgazar y redondear: es lo que viaja y lo que se pinta cientos de veces.
    tol = math.hypot(x1 - x0, y1 - y0) * FINURA_BLOQUE
    vertices = 0
    for tr in trazos:
        if tr.get("puntos"):
            tr["puntos"] = [[round(q[0], 3), round(q[1], 3)] for q in _adelgazar(tr["puntos"], tol)]
            vertices += len(tr["puntos"])
    return {"nombre": nombre, "trazos": trazos, "caja": [x0, y0, x1, y1], "vertices": vertices}


def definiciones_usadas(doc: Documento, espacio: str = "") -> dict:
    """Las definiciones de los bloques pesados que se instancian en el espacio."""
    pesados = bloques_pesados(doc)
    if not pesados:
        return {}
    nombres = {e.bloque for e in doc.visibles(espacio) if e.tipo == "insercion" and e.bloque in pesados}
    return {n: definicion_bloque(doc, n) for n in sorted(nombres)}


def trazos_de(doc: Documento, e) -> list[dict]:
    """Los trazos de **una** entidad. Es la unidad de trabajo del parche.

    Existe separado de `trazos()` porque después de borrar una línea no hace
    falta volver a teselar las otras mil ochocientas: sólo hay que quitar las
    de esa. Ver `server.py`, `/api/operacion`.
    """
    cabe = doc.cacheable(e)
    guardado = doc.cache.get(e.id) if cabe else None
    if guardado is not None and "trazos" in guardado:
        return guardado["trazos"]
    base = {
        "id": e.id,
        "capa": e.capa,
        "color": doc.color_efectivo(e),
        "grosor": doc.grosor_efectivo(e) / 100.0,      # a milímetros
        "patron": mod_capas.TIPOS_LINEA.get(
            doc.tipo_linea_efectivo(e), {}).get("patron", []),
        "escala_tl": e.escala_tl,
    }
    # El grupo viaja con el trazo para que el lienzo sepa, sin preguntar, que
    # picar esto es picar el grupo entero.
    if getattr(e, "grupo", ""):
        base["grupo"] = e.grupo
    salida = _trazos_de(doc, e, base)
    if cabe:
        doc.cache.setdefault(e.id, {})["trazos"] = salida
    return salida


def trazos_cota(doc: Documento, e, escala_forzada: float) -> list[dict]:
    """Los trazos de una cota con un tamaño impuesto (el de una hoja)  ·  0.20.0.

    No pasa por la caché: el mismo modelo se ve por ventanas a escalas
    distintas y cada hoja pide su tamaño (ver `papel.trazos_papel`).
    """
    base = {
        "id": e.id, "capa": e.capa, "color": doc.color_efectivo(e),
        "grosor": doc.grosor_efectivo(e) / 100.0,
        "patron": mod_capas.TIPOS_LINEA.get(doc.tipo_linea_efectivo(e), {}).get("patron", []),
        "escala_tl": e.escala_tl,
    }
    g = mod_cotas.geometria(doc, e, escala_forzada)
    salida = []
    for par in g["lineas"]:
        salida.append(dict(base, clase="linea", puntos=[[par[0][0], par[0][1]], [par[1][0], par[1][1]]]))
    if g["texto"] and g["texto"]["texto"]:
        salida.append(dict(base, clase="texto", **g["texto"]))
    return salida


def trazos(doc: Documento, espacio: str = "") -> list[dict]:
    """Todo lo visible de un espacio, listo para el lienzo.

    `espacio` es `""` para el modelo o el nombre de una hoja. Ver
    `Entidad.espacio`.
    """
    salida: list[dict] = []
    for e in doc.visibles(espacio):
        salida.extend(trazos_de(doc, e))
    return salida
