"""t015 · UNIR (el JOIN de AutoCAD).

Un contorno que llega de un plano ajeno viene hecho de veinte líneas sueltas, y
para rayarlo, desfasarlo o mandarlo a la CNC hace falta que sea **una** cosa.

Tres reglas cargan el diseño, y las tres se comprueban aquí porque las tres
fallan sin hacer ruido:

- **Los arcos no se pierden**: entran como `bulge` en el vértice donde empiezan,
  y el bulge **cambia de signo** cuando la cadena recorre el arco al revés. Sin
  esa línea, una puerta redondeada sale curvada al otro lado: no truena, no se
  ve raro, y aparece cuando la pieza llega al taller. Se prueban los cuatro
  casos de sentido y orden.
- **Los extremos tienen que tocarse de verdad**: 0.05 mm, no «lo que se vea
  cerca». Unir dos líneas separadas medio milímetro mueve el dibujo sin avisar.
- **Lo que no se une, no se toca**: se queda con su id, y un Ctrl+Z devuelve
  todas las piezas, porque la unión es una sola transacción.
"""

from __future__ import annotations

import math

from core import entidades as ent
from core import unir as mod_unir
from core.documento import Documento
from pruebas import comun

DESCRIPCION = "UNIR: cadenas, arcos en los dos sentidos, y lo que no toca"


def correr(r: comun.Reporte) -> None:
    _contorno(r)
    _arcos(r)
    _lo_que_no_toca(r)
    _una_transaccion(r)


def _contorno(r: comun.Reporte) -> None:
    """Cuatro líneas sueltas que cierran un rectángulo → una polilínea cerrada."""
    doc = Documento.nuevo()
    esquinas = [[0, 0], [600, 0], [600, 400], [0, 400]]
    with doc.transaccion("Dibujar"):
        ids = [doc.agregar(ent.Linea(p1=esquinas[i], p2=esquinas[(i + 1) % 4])).id
               for i in range(4)]

    with doc.transaccion("Unir"):
        res = mod_unir.unir(doc, ids)

    r.igual(len(res["creadas"]), 1, "las cuatro líneas se vuelven una sola polilínea")
    r.igual(len(doc.lista()), 1, "y no queda ninguna suelta")

    pol = doc.lista()[0]
    r.igual(pol.tipo, "polilinea", "lo que queda es una polilínea")
    r.cierto(pol.cerrada, "y sale cerrada, porque el contorno cierra")
    r.igual(len(pol.puntos), 4,
            "con cuatro vértices: el que cierra no se repite al final")

    # El orden en que se piquen las líneas no debería importar.
    doc2 = Documento.nuevo()
    with doc2.transaccion("Dibujar"):
        ids2 = [doc2.agregar(ent.Linea(p1=esquinas[i], p2=esquinas[(i + 1) % 4])).id
                for i in (2, 0, 3, 1)]
    with doc2.transaccion("Unir"):
        mod_unir.unir(doc2, ids2)
    r.igual(len(doc2.lista()), 1,
            "y da igual en qué orden se hayan seleccionado")


def _arco_entre(centro, radio, a0, a1) -> ent.Arco:
    return ent.Arco(centro=list(centro), radio=radio, ang_ini=a0, ang_fin=a1)


def _arcos(r: comun.Reporte) -> None:
    """Una línea y un arco, en los cuatro cruces de sentido y orden.

    El arco va de (600,0) a (600,400) por la derecha (centro en (600,200)); la
    línea cierra por la derecha. Se une en los dos órdenes y con el arco
    definido en los dos sentidos, y en los cuatro casos la polilínea tiene que
    curvarse **hacia donde curva el arco**, que es lo único que ve el que corta
    la pieza.
    """
    for arco_primero in (True, False):
        for al_reves in (True, False):
            doc = Documento.nuevo()
            arco = (_arco_entre([600, 200], 200, 270, 90) if not al_reves
                    else _arco_entre([600, 200], 200, 90, 270))
            linea = ent.Linea(p1=[600, 400], p2=[600, 0])
            with doc.transaccion("Dibujar"):
                piezas = ([doc.agregar(arco).id, doc.agregar(linea).id]
                          if arco_primero else
                          [doc.agregar(linea).id, doc.agregar(arco).id])
            with doc.transaccion("Unir"):
                mod_unir.unir(doc, piezas)

            caso = f"arco {'primero' if arco_primero else 'después'}, " \
                   f"{'al revés' if al_reves else 'de frente'}"
            quedan = doc.lista()
            if not r.igual(len(quedan), 1, f"({caso}) la línea y el arco se unen"):
                continue
            pol = quedan[0]
            bulges = [p[2] for p in pol.puntos if abs(p[2]) > 1e-9]
            if not r.igual(len(bulges), 1, f"({caso}) el arco no se aplanó a una recta"):
                continue
            # Un bulge de 1 es media vuelta: el semicírculo de radio 200.
            r.casi(abs(bulges[0]), 1.0,
                   f"({caso}) el bulge es el del semicírculo", 1e-6)

            # Y que la curva quede **del lado que dice el arco**. Los ángulos
            # se leen en sentido antihorario: 270°→90° pasa por el 0, o sea por
            # la derecha (x = 800); 90°→270° pasa por el 180, por la izquierda
            # (x = 400). Con el bulge de signo cambiado saldría espejeada: una
            # puerta redondeada hacia el otro lado, que no truena y no se ve
            # raro hasta que la pieza llega al taller.
            esperado = 400.0 if al_reves else 800.0
            medio = _punto_medio_del_bulge(pol)
            r.casi(medio[0], esperado,
                   f"({caso}) la curva sale hacia el lado que dice el arco", 1e-6)


def _punto_medio_del_bulge(pol) -> list:
    """Dónde cae la mitad del tramo curvo, según el bulge guardado."""
    for i, p in enumerate(pol.puntos):
        if abs(p[2]) <= 1e-9:
            continue
        sig = pol.puntos[(i + 1) % len(pol.puntos)]
        x1, y1, b = p[0], p[1], p[2]
        x2, y2 = sig[0], sig[1]
        # sagita = bulge * (cuerda / 2), perpendicular a la cuerda
        dx, dy = x2 - x1, y2 - y1
        largo = math.hypot(dx, dy)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # Bulge positivo = arco **antihorario** de p1 a p2, y ése cae al
        # lado derecho de la cuerda (perpendicular (dy, -dx)). Con el signo al
        # revés la prueba pasaría con el arco espejeado, que es justo el error
        # que viene a cazar.
        return [mx + dy / largo * (b * largo / 2), my - dx / largo * (b * largo / 2)]
    return [float("nan"), float("nan")]


def _lo_que_no_toca(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        a = doc.agregar(ent.Linea(p1=[0, 0], p2=[100, 0]))
        # medio milímetro de separación: **no** se une
        b = doc.agregar(ent.Linea(p1=[100.5, 0], p2=[200, 0]))
        # dentro de la tolerancia de 0.05: sí se une
        c = doc.agregar(ent.Linea(p1=[200.02, 0], p2=[300, 0]))
        suelta = doc.agregar(ent.Circulo(centro=[0, 500], radio=20))

    with doc.transaccion("Unir"):
        res = mod_unir.unir(doc, [a.id, b.id, c.id, suelta.id])

    ids_finales = {e.id for e in doc.lista()}
    r.cierto(a.id in ids_finales,
             "dos líneas separadas medio milímetro NO se unen (no se mueve el dibujo)")
    r.cierto(suelta.id in ids_finales,
             "lo que no se puede unir se queda como estaba, con su id")
    r.igual(res.get("no_unibles"), ["circulo"],
             "y el mensaje dice qué quedó fuera y por qué (un círculo no se une)")
    r.cierto(res.get("sueltas", 0) >= 1,
             "y cuántas piezas quedaron sueltas")
    r.igual(len(res["creadas"]), 1,
            "las que sí se tocan (0.02 mm) sí se unen")


def _una_transaccion(r: comun.Reporte) -> None:
    """Un Ctrl+Z devuelve **todas** las piezas."""
    doc = Documento.nuevo()
    esquinas = [[0, 0], [600, 0], [600, 400], [0, 400]]
    with doc.transaccion("Dibujar"):
        ids = [doc.agregar(ent.Linea(p1=esquinas[i], p2=esquinas[(i + 1) % 4])).id
               for i in range(4)]
    with doc.transaccion("Unir"):
        mod_unir.unir(doc, ids)
    r.igual(len(doc.lista()), 1, "quedó la polilínea")

    doc.deshacer()
    r.igual(sorted(e.id for e in doc.lista()), sorted(ids),
            "un solo Ctrl+Z devuelve las cuatro líneas, con sus ids")
