"""El grupo **model**: revolver, barrer, loft y extruir-cara  ·  0.19.0

Mike, 19-sep, definiendo el rumbo: *«**model** — Funciones básicas para
generar sólidos nuevos, extrude, revolve, sweep, loft, etc. […] aquí hay
opciones como extrude face que es un sólido nuevo a partir de una cara nueva.
no sería estirar la cara, sería aumentar un sólido a partir del perfil de la
cara»*. Y el aviso que gobierna todo: *«NO ES PARA MUEBLES, es para todo
diseño industrial»*.

Las cuatro entran ahora porque ya se pueden decir: con ids se puede señalar
**cuál** perfil, y con planos un boceto puede vivir donde no vive el otro. Un
loft de dos perfiles en el mismo plano no es un loft.

Lo que esta prueba fija:

1. Las cuatro construyen, con el volumen exacto donde hay cuenta cerrada.
2. **Ninguna deja una cara sin nombre**, que es lo que permite maquinar encima.
3. **El nombre se queda en la misma cara al cambiar un número.** Es la
   comprobación cara: sin ella el historial miente y un barreno se va a otro
   lado de la pieza sin avisar.
4. **El kernel no pregunta de dónde salió el sólido**: se barrena y se
   redondea un loft y un revolucionado igual que un tablero.
5. Lo que no se puede hacer se niega en español y no rompe nada.
"""
from __future__ import annotations

import math

from pruebas import comun

DESCRIPCION = "model: revolver, barrer, loft y extruir-cara, con sus nombres"


def _rect(x0, y0, x1, y1):
    return {"tipo": "polilinea", "cerrada": True,
            "puntos": [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]]}


def _tubo(r=30.0, pared=5.0, alto=80.0, grados=360.0):
    return [{"id": "s1", "op": "boceto", "entidades": [_rect(r, 0, r + pared, alto)]},
            {"id": "m1", "op": "revolver", "perfil": "s1",
             "eje": {"a": [0, 0], "b": [0, 1]}, "grados": grados}]


def _loft(lado=100.0, radio=25.0, alto=120.0):
    return [{"id": "s1", "op": "boceto", "entidades": [_rect(0, 0, lado, 60)]},
            {"id": "s2", "op": "boceto", "plano": {"z": alto},
             "entidades": [{"tipo": "circulo", "centro": [lado / 2, 30], "radio": radio}]},
            {"id": "m1", "op": "loft", "perfiles": ["s1", "s2"]}]


def _sin_nombre(reg) -> list:
    return [k for k, f in enumerate(reg.solido.faces())
            if reg.nombrador.nombre_de(f) is None]


def correr(r: comun.Reporte) -> None:
    from core.solido import historial

    # --- 1. revolver -------------------------------------------------------
    reg = historial.regenerar(_tubo())
    esperado = math.pi * ((35.0 ** 2) - (30.0 ** 2)) * 80.0
    r.casi(reg.solido.volume, esperado, "un tubo torneado mide lo que dice la cuenta", tol=1.0)
    r.igual(_sin_nombre(reg), [], "el torneado no deja caras sin nombre")
    r.igual(sorted(reg.nombrador.caras), ["abajo", "arriba", "lado[0]", "lado[1]"],
            "y se llaman por dónde están, no por qué arista las hizo")

    medio = historial.regenerar(_tubo(grados=90.0))
    r.casi(medio.solido.volume, esperado / 4.0, "girar 90° da la cuarta parte", tol=1.0)
    r.igual(_sin_nombre(medio), [], "un revolucionado a medias tampoco deja caras sueltas")

    # El nombre se queda en la misma cara: `lado[0]` siempre el cilindro de
    # adentro, `lado[1]` el de afuera, a cualquier radio.
    from build123d import Vector

    from core.solido import nombres as nom_mod
    for radio in (30.0, 45.0, 70.0, 120.0):
        reg_k = historial.regenerar(_tubo(r=radio))
        centro, eje = nom_mod._centro_de(reg_k.solido), Vector(0, 1, 0)
        dentro = nom_mod._radio_max(reg_k.nombrador.cara("lado[0]"), centro, eje)
        fuera = nom_mod._radio_max(reg_k.nombrador.cara("lado[1]"), centro, eje)
        r.casi(dentro, radio, f"r={radio}: lado[0] sigue siendo la pared de adentro", tol=1e-6)
        r.casi(fuera, radio + 5.0, f"r={radio}: lado[1] sigue siendo la de afuera", tol=1e-6)

    # --- 2. loft -----------------------------------------------------------
    reg = historial.regenerar(_loft())
    r.cierto(reg.solido.volume > 0, "un loft rectángulo→círculo se construye")
    r.igual(_sin_nombre(reg), [], "y no deja caras sin nombre")
    caja = reg.solido.bounding_box()
    r.casi(caja.size.Z, 120.0, "va de un plano al otro", tol=1e-6)

    mismo = [{"id": "s1", "op": "boceto", "entidades": [_rect(0, 0, 100, 60)]},
             {"id": "s2", "op": "boceto", "entidades": [_rect(0, 0, 50, 30)]},
             {"id": "m1", "op": "loft", "perfiles": ["s1", "s2"]}]
    try:
        historial.regenerar(mismo)
        r.cierto(False, "dos perfiles en el mismo plano no hacen un loft")
    except Exception:
        r.cierto(True, "dos perfiles en el mismo plano no hacen un loft")

    uno = [{"id": "s1", "op": "boceto", "entidades": [_rect(0, 0, 100, 60)]},
           {"id": "m1", "op": "loft", "perfiles": ["s1"]}]
    r.levanta(ValueError, historial.regenerar, "un loft de un solo perfil se niega", uno)

    # --- 3. barrer ---------------------------------------------------------
    barrido = [
        {"id": "s1", "op": "boceto", "entidades": [_rect(-15, -10, 15, 10)]},
        {"id": "s2", "op": "boceto",
         "plano": {"origen": [0, 0, 0], "normal": [1, 0, 0], "x": [0, 1, 0]},
         "entidades": [{"tipo": "polilinea", "cerrada": False,
                        "puntos": [[0, 0, 0], [0, 200, 0]]}]},
        {"id": "m1", "op": "barrer", "perfil": "s1", "camino": "s2"},
    ]
    reg = historial.regenerar(barrido)
    r.casi(reg.solido.volume, 30.0 * 20.0 * 200.0, "un barrido recto es el perfil por el largo", tol=1e-3)
    r.igual(_sin_nombre(reg), [], "el barrido no deja caras sin nombre")

    sin_camino = [barrido[0], barrido[1], {"id": "m1", "op": "barrer", "perfil": "s1"}]
    r.levanta(ValueError, historial.regenerar, "un barrido sin camino se niega", sin_camino)

    perdido = [barrido[0], barrido[1],
               {"id": "m1", "op": "barrer", "perfil": "s1", "camino": "no-existe"}]
    r.levanta(ValueError, historial.regenerar, "un camino que no está se niega", perdido)

    # --- 4. maquinar encima: al kernel no le importa de dónde salió --------
    con_barreno = _loft() + [
        {"id": "k1", "op": "restar", "mm": -40, "plano": {"cara": "arriba"},
         "entidades": [{"tipo": "circulo", "centro": [0, 0], "radio": 10}]}]
    limpio = historial.regenerar(_loft()).solido.volume
    reg = historial.regenerar(con_barreno)
    r.casi(reg.solido.volume, limpio - math.pi * 100.0 * 40.0,
           "un barreno sobre la tapa de un loft quita justo su cilindro", tol=1.0)
    r.igual(_sin_nombre(reg), [], "y después del barreno siguen todas nombradas")

    con_redondeo = _tubo() + [{"id": "k1", "op": "redondear", "aristas": ["arriba|lado[1]"], "r": 2.0}]
    reg = historial.regenerar(con_redondeo)
    r.cierto(reg.solido.volume < historial.regenerar(_tubo()).solido.volume,
             "redondear el filo de un torneado le quita material")
    r.igual(_sin_nombre(reg), [], "y no deja caras sin nombre")

    # --- 5. extruir_cara: material nuevo sobre una cara --------------------
    from core.solido import cuerpo as mod
    base = mod.ops_de_contorno([_rect(0, 0, 100, 60)], 18.0)
    crecido = mod.agregar(base, {"op": "extruir_cara", "cara": "arriba", "mm": 25.0})
    reg = historial.regenerar(crecido)
    r.casi(reg.solido.volume, 100 * 60 * 18 + 100 * 60 * 25,
           "extruir una cara agrega material, no estira la pieza", tol=1e-3)
    r.casi(reg.solido.bounding_box().size.X, 100.0, "y no cambia lo ancho que es", tol=1e-6)

    suelto = mod.agregar(base, {"op": "extruir_cara", "cara": "arriba", "mm": 25.0, "unir": False})
    reg = historial.regenerar(suelto)
    r.casi(reg.solido.volume, 100 * 60 * 25, "sin unir queda sólo el pedazo nuevo", tol=1e-3)

    cero = mod.agregar(base, {"op": "extruir_cara", "cara": "arriba", "mm": 0})
    r.levanta(ValueError, historial.regenerar, "extruir cero se niega", cero)

    # --- 6. lo que sostiene a otra cosa no se quita ------------------------
    ops = _loft()
    r.igual(sorted(historial.enlaces(ops)["m1"]), ["s1", "s2"],
            "el loft dice que usa sus dos perfiles")
    try:
        mod.quitar_operacion(ops, 0)
        r.cierto(False, "un perfil del loft no se puede quitar")
    except ValueError as e:
        r.cierto("m1" in str(e), "y el aviso dice quién lo usa", str(e))
    r.igual(historial.nace_el_solido(ops), "m1", "el loft es el nacimiento de la pieza")
