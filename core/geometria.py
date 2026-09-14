"""Geometría exacta de cada entidad, para las referencias a objetos.

`core/dibujo.py` tesela: convierte todo en polilíneas para pintarlas. Eso sirve
al lienzo y **no sirve al osnap**. El punto medio de un arco teselado no es el
punto medio del arco, y un extremo teselado está a medio milímetro del extremo
de verdad. En un plano que va a la CNC, medio milímetro es una pieza mal
cortada.

Así que el osnap trabaja sobre esto: cada entidad reducida a **primitivas
exactas** —segmentos, arcos y puntos— con sus parámetros originales. El
navegador calcula extremos, medios, centros, cuadrantes, intersecciones,
perpendiculares y cercanos sobre estas primitivas, no sobre los píxeles.

Es la misma lista que después usarán seleccionar por ventana (F3), recortar y
extender (F3), y las cotas asociativas (F5).
"""

from __future__ import annotations

import math

from .documento import Documento


def _arco_de_bulge(p1, p2, bulge):
    """Un tramo de polilínea con bulge, como arco exacto.

    bulge = tan(ángulo/4). Devuelve (centro, radio, ang_ini, ang_fin, antihorario).
    """
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    cuerda = math.hypot(x2 - x1, y2 - y1)
    if cuerda < 1e-12 or abs(bulge) < 1e-12:
        return None
    angulo = 4 * math.atan(bulge)
    r = cuerda / (2 * math.sin(abs(angulo) / 2))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    h = math.sqrt(max(r * r - (cuerda / 2) ** 2, 0.0))
    dx, dy = (x2 - x1) / cuerda, (y2 - y1) / cuerda
    signo = 1 if angulo > 0 else -1
    cx, cy = mx - signo * h * dy, my + signo * h * dx
    a0 = math.degrees(math.atan2(y1 - cy, x1 - cx)) % 360
    a1 = math.degrees(math.atan2(y2 - cy, x2 - cx)) % 360
    return {"tipo": "arco", "c": [cx, cy], "r": r,
            "a0": a0 if signo > 0 else a1,
            "a1": a1 if signo > 0 else a0}


def _seg(a, b):
    return {"tipo": "seg", "a": [a[0], a[1]], "b": [b[0], b[1]]}


def _de_polilinea(puntos, cerrada):
    prim = []
    n = len(puntos)
    if n < 2:
        return [{"tipo": "punto", "p": [puntos[0][0], puntos[0][1]]}] if n else []
    tramos = list(range(n - 1)) + ([n - 1] if cerrada and n > 2 else [])
    for i in tramos:
        p1 = puntos[i]
        p2 = puntos[(i + 1) % n]
        b = p1[2] if len(p1) > 2 else 0.0
        arco = _arco_de_bulge(p1, p2, b) if abs(b) > 1e-12 else None
        prim.append(arco or _seg(p1, p2))
    return prim


def primitivas_de(doc: Documento, e, transf=None) -> list[dict]:
    """Primitivas exactas de una entidad, en coordenadas del dibujo."""
    t = e.tipo
    if t == "linea":
        return [_seg(e.p1, e.p2)]
    if t == "polilinea":
        return _de_polilinea(e.puntos, e.cerrada)
    if t == "circulo":
        return [{"tipo": "arco", "c": [e.centro[0], e.centro[1]], "r": e.radio,
                 "a0": 0.0, "a1": 360.0}]
    if t == "arco":
        return [{"tipo": "arco", "c": [e.centro[0], e.centro[1]], "r": e.radio,
                 "a0": e.ang_ini % 360, "a1": e.ang_fin % 360}]
    if t == "elipse":
        # La elipse se aproxima por segmentos: el osnap sobre elipse sólo
        # promete centro y cercano, y para eso alcanza. Sus ejes van aparte.
        from . import dibujo
        pts = dibujo._elipse(e)
        prim = [_seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        prim.append({"tipo": "punto", "p": [e.centro[0], e.centro[1]], "clase": "centro"})
        return prim
    if t == "spline":
        pts = e.puntos_ajuste or e.puntos_control
        return [_seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if t == "punto":
        return [{"tipo": "punto", "p": [e.p[0], e.p[1]], "clase": "nodo"}]
    if t == "solido":
        pts = e.puntos
        return [_seg(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))] if pts else []
    if t in ("texto", "textom"):
        return [{"tipo": "punto", "p": [e.p[0], e.p[1]], "clase": "insercion"}]
    if t == "insercion":
        bl = doc.bloques.get(e.bloque)
        salida = [{"tipo": "punto", "p": [e.p[0], e.p[1]], "clase": "insercion"}]
        if bl is None:
            return salida
        from . import dibujo as _dib
        if _dib.es_pesado(doc, e.bloque):
            # Pesado: se engancha y se pica por su caja, no por sus 50 000
            # segmentos. Las esquinas y los medios de la caja sirven de osnap.
            c = doc.caja_de(e)
            if c and c[2] > c[0] and c[3] > c[1]:
                esq = [[c[0], c[1]], [c[2], c[1]], [c[2], c[3]], [c[0], c[3]]]
                for i in range(4):
                    salida.append(_seg(esq[i], esq[(i + 1) % 4]))
            return salida
        r = math.radians(e.rotacion)
        cos, sen = math.cos(r), math.sin(r)
        sx, sy = e.escala[0], e.escala[1]
        ox = e.p[0] - bl.base[0] * sx
        oy = e.p[1] - bl.base[1] * sy

        def mover(p):
            x, y = p[0] * sx, p[1] * sy
            return [ox + x * cos - y * sen, oy + x * sen + y * cos]

        for sub in bl.entidades:
            for pr in primitivas_de(doc, sub):
                if pr["tipo"] == "seg":
                    salida.append(_seg(mover(pr["a"]), mover(pr["b"])))
                elif pr["tipo"] == "arco":
                    # una escala no uniforme deja de dar un arco; se ignora ese
                    # caso a propósito en vez de dar un centro que miente
                    if abs(sx - sy) < 1e-9:
                        salida.append({"tipo": "arco", "c": mover(pr["c"]),
                                       "r": pr["r"] * abs(sx),
                                       "a0": (pr["a0"] + e.rotacion) % 360,
                                       "a1": (pr["a1"] + e.rotacion) % 360})
                else:
                    salida.append({"tipo": "punto", "p": mover(pr["p"]),
                                   "clase": pr.get("clase", "nodo")})
        return salida
    if t == "rayado":
        prim = []
        for ruta in e.rutas:
            prim.extend(_de_polilinea(ruta, True))
        return prim
    if t == "cota":
        # **Ésta es la razón de fondo del punto 8 de Mike**, y no era la
        # tolerancia: una cota no tenía *ninguna* primitiva. No se podía picar
        # por sus rayas ni atraparla con una ventana; lo único que la agarraba
        # era el número, por su caja de texto. De ahí lo de *«hasta que no hago
        # zoom y le doy justo encima»*.
        #
        # Van `aprox`, igual que lo ajeno: sirven para picarla y para meterla en
        # una ventana de selección, y el osnap las ignora. Engancharse al punto
        # medio de una línea de cota no significa nada —esa raya no es una
        # pieza, es una anotación sobre una pieza— y arrastraría el dibujo a
        # medidas que nadie puso.
        from . import cotas as mod_cotas
        prim = []
        g = mod_cotas.geometria(doc, e)
        for par in g["lineas"]:
            prim.append(dict(_seg(par[0], par[1]), aprox=True))
        # La **línea de cota** va además exacta y marcada `cota`: el osnap la
        # ignora salvo cuando se está colocando otra cota (Mike, 9-sep-2026:
        # «al definir qué tan larga es la extensión del trazo de cota, haya
        # OSNAP también, para alinear cotas sobre un mismo eje»). Así una fila
        # de cotas cae en el mismo renglón sin tantear, y el resto del tiempo
        # una raya de anotación no jala el dibujo.
        lc = g.get("linea_cota")
        if lc:
            prim.append(dict(_seg(lc[0], lc[1]), cota=True))
        tx = g.get("texto")
        if tx and tx.get("p"):
            prim.append({"tipo": "punto", "p": [tx["p"][0], tx["p"][1]],
                         "clase": "nodo", "aprox": True})
        # Los puntos de definición, como grips: jalar el tercero mueve la
        # línea de cota; jalar uno de los medidos lo despega de la pieza.
        for q in e.puntos:
            prim.append({"tipo": "punto", "p": [q[0], q[1]], "clase": "definicion", "aprox": True})
        return prim
    if t == "cruda":
        # De una entidad ajena no sabemos su geometría exacta —una cota tiene
        # nudos y reglas que no modelamos— pero sí **por dónde pasa**, porque el
        # archivo lo dice y se guardó al abrir. Con eso alcanza para poder
        # picarla, seleccionarla y borrarla.
        #
        # Van marcadas `aprox`: el osnap las ignora. Enganchar el punto medio de
        # una raya teselada de una cota ajena daría un punto que no es el punto,
        # y en un plano que va a la CNC esa diferencia es una pieza mal cortada.
        # Seleccionar no necesita exactitud; medir sí.
        prim = []
        for linea in (getattr(e, "dibujo", None) or []):
            for pr in _de_polilinea(linea, False):
                pr["aprox"] = True
                prim.append(pr)
        for tx in (getattr(e, "textos", None) or []):
            if tx.get("p"):
                prim.append({"tipo": "punto", "p": [tx["p"][0], tx["p"][1]],
                             "clase": "nodo", "aprox": True})
        return prim
    return []      # de lo demás no sabemos ni por dónde pasa


def primitivas_marcadas(doc: Documento, e) -> list[dict]:
    """Las primitivas de una entidad, con su id y su capa puestos.

    Va por caché (ver `Documento.olvidar`): teselar es lo caro y la mayoría de
    las veces se pide de entidades que no cambiaron.
    """
    cabe = doc.cacheable(e)
    guardado = doc.cache.get(e.id) if cabe else None
    if guardado is not None and "geometria" in guardado:
        return guardado["geometria"]
    salida = []
    for pr in primitivas_de(doc, e):
        pr["id"] = e.id
        pr["capa"] = e.capa
        salida.append(pr)
    if cabe:
        doc.cache.setdefault(e.id, {})["geometria"] = salida
    return salida


def indice(doc: Documento, espacio: str = "") -> list[dict]:
    """Todas las primitivas visibles de un espacio, con el id de su entidad."""
    salida = []
    for e in doc.visibles(espacio):
        salida.extend(primitivas_marcadas(doc, e))
    return salida
