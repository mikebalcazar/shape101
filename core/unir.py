"""Unir líneas, arcos y polilíneas sueltas en una sola polilínea.

Es el `JOIN` de AutoCAD, y en un taller se usa todo el tiempo: un contorno que
llegó de un plano ajeno viene hecho de veinte líneas sueltas, y para rayarlo,
desfasarlo o mandarlo a la CNC hace falta que sea **una** cosa.

Dos decisiones que cargan el resto:

**Los arcos no se pierden.** Un arco que se une a una polilínea entra como
`bulge` en el vértice donde empieza, que es como el DXF guarda un arco dentro
de una polilínea. Aplanarlo a una recta sería más fácil de programar y
convertiría una puerta redondeada en una cuadrada.

**Los extremos tienen que tocarse de verdad.** La tolerancia es una fracción de
milímetro, no «lo que se vea cerca». Unir dos líneas que estaban a dos
milímetros mueve el dibujo sin avisar, y este programa existe para planos que se
cortan. Lo que no se toca, no se une, y se dice cuántas quedaron fuera.

La matemática vive aquí y no en el navegador por la misma razón que el resto:
así se puede probar sin abrir un navegador, y la usa igual quien la llame.
"""

from __future__ import annotations

import math

from . import entidades as ent_mod
from .documento import Documento

#: Cuánto pueden separarse dos extremos y seguir considerándose el mismo punto,
#: en milímetros. Un plano ajeno redondeado a micras cae dentro; dos líneas
#: dibujadas «casi» juntas, no.
TOLERANCIA = 0.05

#: Tipos que saben unirse. Un círculo ya está cerrado y una spline tiene nudos
#: propios que una polilínea no puede representar sin moverlos.
UNIBLES = {"linea", "arco", "polilinea"}


def _cerca(a, b, tol) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _bulge_de_arco(e) -> float:
    """El bulge que representa este arco recorrido de su inicio a su fin.

    bulge = tan(barrido / 4), con signo positivo antihorario, que es como lo
    guarda el DXF.
    """
    barrido = (e.ang_fin - e.ang_ini) % 360.0
    if barrido == 0:
        barrido = 360.0
    return math.tan(math.radians(barrido) / 4.0)


def _vertices(e) -> list[list] | None:
    """La entidad como lista de vértices `[x, y, bulge]`, en su propio sentido.

    El bulge de un vértice describe el tramo que **empieza** en él, que es el
    convenio del DXF y el que usa `core/dibujo.py`.
    """
    if e.tipo == "linea":
        return [[e.p1[0], e.p1[1], 0.0], [e.p2[0], e.p2[1], 0.0]]
    if e.tipo == "arco":
        a0 = math.radians(e.ang_ini)
        a1 = math.radians(e.ang_fin)
        ini = [e.centro[0] + e.radio * math.cos(a0), e.centro[1] + e.radio * math.sin(a0)]
        fin = [e.centro[0] + e.radio * math.cos(a1), e.centro[1] + e.radio * math.sin(a1)]
        return [[ini[0], ini[1], _bulge_de_arco(e)], [fin[0], fin[1], 0.0]]
    if e.tipo == "polilinea":
        if e.cerrada or len(e.puntos) < 2:
            return None                 # una polilínea cerrada no tiene extremos
        return [[p[0], p[1], (p[2] if len(p) > 2 else 0.0)] for p in e.puntos]
    return None


def _invertir(vs: list[list]) -> list[list]:
    """Los mismos vértices recorridos al revés.

    El bulge se mueve de vértice **y cambia de signo**: describe el tramo que
    empieza en él, y al dar la vuelta ese tramo se recorre al contrario. Sin
    esta línea, un arco unido «de espaldas» sale curvado hacia el otro lado, que
    es el error silencioso que hace que una pieza salga al revés.
    """
    n = len(vs)
    fuera = []
    for i in range(n - 1, -1, -1):
        b = -vs[i - 1][2] if i > 0 else 0.0
        fuera.append([vs[i][0], vs[i][1], b])
    return fuera


def _encadenar(piezas: list[tuple[str, list]], tol: float) -> list[dict]:
    """Agrupa las piezas que se tocan. Devuelve cadenas con sus ids y vértices."""
    libres = list(piezas)
    cadenas = []
    while libres:
        id_, vs = libres.pop(0)
        cadena = {"ids": [id_], "vs": list(vs)}
        crecio = True
        while crecio:
            crecio = False
            for i, (otro_id, otros) in enumerate(libres):
                ini, fin = cadena["vs"][0], cadena["vs"][-1]
                o_ini, o_fin = otros[0], otros[-1]
                if _cerca(fin, o_ini, tol):
                    nuevos = otros
                elif _cerca(fin, o_fin, tol):
                    nuevos = _invertir(otros)
                elif _cerca(ini, o_fin, tol):
                    cadena["vs"] = otros[:-1] + cadena["vs"]
                    cadena["ids"].insert(0, otro_id)
                    libres.pop(i); crecio = True
                    break
                elif _cerca(ini, o_ini, tol):
                    inv = _invertir(otros)
                    cadena["vs"] = inv[:-1] + cadena["vs"]
                    cadena["ids"].insert(0, otro_id)
                    libres.pop(i); crecio = True
                    break
                else:
                    continue
                # Se pega por el final: el vértice compartido no se repite, pero
                # **su bulge sí se conserva** — es el del tramo que arranca ahí.
                cadena["vs"][-1] = [cadena["vs"][-1][0], cadena["vs"][-1][1], nuevos[0][2]]
                cadena["vs"].extend(nuevos[1:])
                cadena["ids"].append(otro_id)
                libres.pop(i)
                crecio = True
                break
        cadenas.append(cadena)
    return cadenas


def unir(doc: Documento, ids, tol: float = TOLERANCIA) -> dict:
    """Une lo que se toca. Devuelve qué se creó, qué se borró y qué quedó fuera.

    No se toca nada que no se haya podido unir: una pieza suelta se queda como
    estaba, con su id. Así un UNIR que sólo acierta con la mitad no obliga a
    deshacer para recuperar la otra.
    """
    piezas = []
    fuera = []
    for id_ in dict.fromkeys(ids):
        e = doc.entidades.get(id_)
        if e is None:
            continue
        vs = _vertices(e) if e.tipo in UNIBLES else None
        if vs is None:
            fuera.append(e.tipo)
            continue
        piezas.append((id_, vs))

    cadenas = [c for c in _encadenar(piezas, tol) if len(c["ids"]) > 1]
    creadas, borradas = [], []
    for c in cadenas:
        vs = c["vs"]
        cerrada = len(vs) > 2 and _cerca(vs[0], vs[-1], tol)
        if cerrada:
            # El último vértice es el primero: se quita, pero su bulge —el del
            # tramo de cierre— se guarda en el que ahora queda al final.
            b = vs[-2][2]
            vs = vs[:-1]
            vs[-1] = [vs[-1][0], vs[-1][1], b]

        modelo = doc.entidades[c["ids"][0]]
        nueva = ent_mod.Polilinea(
            capa=modelo.capa, color=modelo.color, grosor=modelo.grosor,
            tipo_linea=modelo.tipo_linea, escala_tl=modelo.escala_tl,
            puntos=[[v[0], v[1], v[2]] for v in vs], cerrada=cerrada)
        for id_ in c["ids"]:
            doc.borrar(id_)
            borradas.append(id_)
        doc.agregar(nueva)
        creadas.append({"id": nueva.id, "vertices": len(nueva.puntos),
                        "cerrada": cerrada, "de": len(c["ids"])})

    sueltas = len(piezas) - sum(len(c["ids"]) for c in cadenas)
    return {"creadas": creadas, "borradas": borradas,
            "sueltas": sueltas, "no_unibles": fuera}
