"""t052 · Sólidos: chaflán, radios que no caben y mover puntos de curvas del boceto.

Tres cosas de la fase C3:

- **CHAFLAN**, que no existía: corta la arista en plano a la distancia dada.
  Se comprueba con el volumen de la fórmula (cada canto de un prisma pierde un
  prisma triangular de d²/2 por la altura), que sus caras quedan nombradas, y
  que la distancia se cambia después en el historial.
- **Un radio o un chaflán que no cabe** decía, en inglés, «falló, prueba uno
  menor». Ahora dice cuál es el más grande que cabe, y ése sí se puede hacer.
- **Mover un punto de una spline o de una elipse del boceto** decía «todavía
  no sé». Ahora la pieza se regenera exacta: el punto movido queda sobre el
  canto del sólido nuevo.
"""

from __future__ import annotations

import re

from core.solido import cuerpo as mod
from core.solido import historial as H
from pruebas import comun

DESCRIPCION = "chaflán, radios que no caben con su máximo, y mover puntos de splines y elipses del boceto"

ANCHO, FONDO, ALTO = 100.0, 60.0, 18.0


def _caja():
    pol = {"tipo": "polilinea", "puntos": [[0, 0], [ANCHO, 0], [ANCHO, FONDO], [0, FONDO]], "cerrada": True}
    return H.asegurar_ids([{"op": "boceto", "entidades": [pol]}, {"op": "extruir", "perfil": "0", "mm": ALTO}])


def _verticales(reg):
    return sorted(a for a in reg.nombrador.aristas(reg.solido) if len(re.findall(r"lado\[", a)) == 2)


def _distancia_al_solido(solido, p) -> float:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
    return BRepExtrema_DistShapeShape(v, solido.wrapped).Value()


def correr(r: comun.Reporte) -> None:
    _chaflan(r)
    _no_caben(r)
    _mover_puntos(r)


def _chaflan(r: comun.Reporte) -> None:
    ops = _caja()
    reg = H.regenerar(ops)
    verticales = _verticales(reg)
    r.igual(len(verticales), 4, "la caja tiene cuatro aristas verticales")
    d = 5.0
    ops_c = mod.agregar(list(ops), mod.ops_de_chaflan(verticales, d))
    reg = H.regenerar(ops_c)
    esperado = ANCHO * FONDO * ALTO - 4 * (d * d / 2) * ALTO
    r.casi(reg.solido.volume, esperado, "el chaflán quita en cada canto d²/2 por la altura: el volumen de la fórmula", 1e-6)
    nombradas = [n for n in reg.nombrador.caras if n.startswith("chaflan[")]
    r.igual(len(nombradas), 4, "y sus cuatro caras nuevas quedan nombradas (para jalarlas o borrarlas después)")
    i = next(k for k, op in enumerate(ops_c) if op["op"] == "chaflan")
    reg = H.regenerar(mod.cambiar_operacion(ops_c, i, {"d": 8.0}))
    r.casi(reg.solido.volume, ANCHO * FONDO * ALTO - 4 * 32 * ALTO,
           "la distancia se cambia en el historial y la pieza se rehace", 1e-6)
    pasos = mod.describir(ops_c)
    r.cierto(any("Chaflán" in p.get("titulo", "") for p in pasos), "el historial lo describe como «Chaflán»")


def _no_caben(r: comun.Reporte) -> None:
    ops = _caja()
    reg = H.regenerar(ops)
    arista = [_verticales(reg)[0]]
    for nombre, op in (("redondeo", {"op": "redondear", "aristas": arista, "r": 80.0}),
                       ("chaflán", {"op": "chaflan", "aristas": arista, "d": 80.0})):
        try:
            H.regenerar(mod.agregar(list(ops), dict(op)))
            r.cierto(False, f"un {nombre} de 80 en una caja de 60 de fondo no debería caber")
            continue
        except ValueError as exc:
            msg = str(exc)
        m = re.search(r"el más grande que cabe es ([0-9.]+)", msg)
        r.cierto(m is not None and "Failed" not in msg,
                 f"un {nombre} que no cabe lo dice en español y da el máximo que cabe", msg)
        if m:
            maximo = float(m.group(1))
            r.cierto(0 < maximo < 80, f"el máximo del {nombre} es menor que lo pedido", str(maximo))
            campo = "r" if "r" in op else "d"
            ok = dict(op, **{campo: maximo * 0.99})
            try:
                H.regenerar(mod.agregar(list(ops), ok))
                r.cierto(True, f"y un {nombre} de ese máximo sí se hace")
            except ValueError as exc:
                r.cierto(False, f"y un {nombre} de ese máximo sí se hace", str(exc))


def _mover_puntos(r: comun.Reporte) -> None:
    sp = {"tipo": "spline", "puntos_control": [[0, 0], [400, -100], [600, 200], [400, 500], [0, 400], [-200, 200]],
          "cerrada": True}
    ops = H.asegurar_ids([{"op": "boceto", "entidades": [sp]}, {"op": "extruir", "perfil": "0", "mm": ALTO}])
    antes = H.regenerar(ops).solido.volume
    nuevas = mod.mover_punto(ops, 0, 2, 800.0, 200.0)
    reg = H.regenerar(nuevas)
    r.cierto(reg.solido.volume > antes, "mover hacia afuera un punto de control de la spline agranda la pieza",
             f"{antes:.0f} → {reg.solido.volume:.0f}")
    from core import entidades as E
    curva = E.de_dict(next(op for op in nuevas if op["op"] == "boceto")["entidades"][0]).curva()
    a, b = curva.dominio
    peor = max(_distancia_al_solido(reg.solido, curva.punto(a + (b - a) * k / 10) + [ALTO]) for k in range(10))
    r.cierto(peor < 1e-6, "y la pieza nueva lleva la spline movida exacta en su canto", f"{peor:.2e}")

    el = {"tipo": "elipse", "centro": [0, 0], "eje_mayor": [100, 0], "razon": 0.5, "param_ini": 0.0,
          "param_fin": 6.283185307179586}
    ops = H.asegurar_ids([{"op": "boceto", "entidades": [el]}, {"op": "extruir", "perfil": "0", "mm": ALTO}])
    reg = H.regenerar(mod.mover_punto(ops, 0, 0, 300.0, 50.0))
    caja = reg.solido.bounding_box()
    r.casi((caja.min.X + caja.max.X) / 2, 300.0, "una elipse del boceto se mueve por su centro", 1e-6)
