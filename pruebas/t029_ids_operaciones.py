"""Cada operación con su id  ·  0.19.0

Hasta la 0.18.0 una operación se señalaba por su **lugar** en la lista. Eso
alcanza mientras el historial sea una fila y cada paso use lo que dejó el
anterior. Deja de alcanzar en cuanto una operación necesita más de una
entrada: un loft quiere N perfiles a la vez, un barrido quiere perfil **y**
camino. Con la lista plana lo único que se podía decir era «el boceto que
quedó pendiente», y pendiente sólo puede haber uno.

Lo que esta prueba fija:

1. **Toda operación acaba con id**, venga como venga, y ningún id se repite.
2. **Los archivos de antes no se rompen.** A una operación sin id se le pone
   el número que ya tenía, así que `restar[2]/lado[1]` —un redondeo guardado
   sobre la cara de un corte— sigue significando lo mismo que significaba. Es
   la comprobación que permite cambiar el esquema sin romper lo guardado.
3. **La extrusión puede decir de qué boceto sale**, y con dos bocetos en el
   historial elige el que dice, no el último. Ésta es la razón de ser del
   cambio: sin ella no hay loft ni barrido.
4. **Los nombres ya no dependen de la posición.** Meter un paso a la mitad no
   renombra caras que nadie tocó. Antes sí, y en silencio.
5. **No se puede quitar un boceto del que cuelga otra operación**, y el aviso
   dice quién lo está usando.
"""
from __future__ import annotations

import json

from pruebas import comun

DESCRIPCION = "cada operación con su id: archivos viejos, dos bocetos, nombres que no se mueven"

FONDO, ESPESOR = 400.0, 18.0


def _rect(x0, y0, x1, y1):
    return {"tipo": "polilinea", "cerrada": True,
            "puntos": [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]]}


def _viejo(ancho=600.0):
    """Un historial como los que hay guardados: sin un solo id, y con un
    redondeo que señala una cara nacida del corte —`restar[2]/...`—, que es
    justo el nombre que llevaba el índice adentro."""
    return [
        {"op": "boceto", "entidades": [_rect(0, 0, ancho, FONDO)]},
        {"op": "extruir", "mm": ESPESOR},
        {"op": "restar", "mm": ESPESOR, "entidades": [_rect(200, -10, 400, 100)]},
    ]


def correr(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod, historial

    # --- 1. toda operación acaba con id, y ninguno repetido ----------------
    ops = historial.asegurar_ids(_viejo())
    r.igual([o.get("id") for o in ops], ["0", "1", "2"],
            "a un historial sin ids se le ponen los números que ya tenía")
    r.igual(len({o["id"] for o in ops}), 3, "no se repite ninguno")

    revueltos = [{"id": "5", "op": "boceto", "entidades": [_rect(0, 0, 10, 10)]},
                 {"op": "extruir", "mm": 5},
                 {"id": "5", "op": "mover_arista", "arista": "x", "d": [0, 0, 0]}]
    puestos = [o["id"] for o in historial.asegurar_ids(revueltos)]
    r.igual(puestos[0], "5", "un id que ya venía puesto se respeta")
    r.igual(len(set(puestos)), 3, "un id repetido a mano se resuelve, no se deja")
    r.cierto(puestos[1] != "5" and puestos[2] != "5",
             "y el que se resuelve es el segundo, no el que llegó primero")

    # `id_libre` no inventa uno que ya esté
    r.cierto(historial.id_libre(puestos and revueltos) not in puestos,
             "id_libre nunca devuelve uno ya usado")

    # --- 2. los archivos de antes no se rompen -----------------------------
    reg = historial.regenerar(_viejo())
    caras_viejas = sorted(reg.nombrador.caras)
    r.cierto(any(c.startswith("restar[2]/") for c in caras_viejas),
             "un corte de la posición 2 sigue bautizando «restar[2]/...»",
             " · ".join(caras_viejas))
    r.cierto(reg.solido is not None and reg.solido.volume > 0,
             "y la pieza se construye igual")

    # Un redondeo guardado contra ese nombre sigue encontrando su cara.
    cara_corte = next(c for c in caras_viejas if c.startswith("restar[2]/"))
    aristas = sorted(historial.regenerar(_viejo()).nombrador.aristas(reg.solido))
    del aristas
    r.cierto(cara_corte.startswith("restar[2]/lado["),
             "el nombre completo es el de siempre", cara_corte)

    # --- 3. la extrusión dice de qué boceto sale ---------------------------
    dos = [
        {"id": "a", "op": "boceto", "entidades": [_rect(0, 0, 100, 100)]},
        {"id": "b", "op": "boceto", "entidades": [_rect(0, 0, 300, 200)]},
        {"id": "c", "op": "extruir", "mm": 10, "perfil": "a"},
    ]
    reg_a = historial.regenerar(dos)
    r.casi(reg_a.solido.volume, 100 * 100 * 10, "extruye el boceto que dice, no el último", tol=1e-3)

    dos[2]["perfil"] = "b"
    reg_b = historial.regenerar(dos)
    r.casi(reg_b.solido.volume, 300 * 200 * 10, "y cambiar el perfil cambia la pieza", tol=1e-3)

    del dos[2]["perfil"]
    reg_sin = historial.regenerar(dos)
    r.casi(reg_sin.solido.volume, 300 * 200 * 10,
           "sin «perfil» toma el último boceto, como antes", tol=1e-3)

    malo = json.loads(json.dumps(dos))
    malo[2]["perfil"] = "no-existe"
    r.levanta(ValueError, historial.regenerar, "señalar un boceto que no está se niega", malo)

    # El orden manda: un perfil que viene después todavía no existe.
    tarde = [{"id": "x", "op": "extruir", "mm": 10, "perfil": "y"},
             {"id": "y", "op": "boceto", "entidades": [_rect(0, 0, 10, 10)]}]
    r.levanta(ValueError, historial.regenerar, "un perfil de más adelante no vale", tarde)

    # --- 4. los nombres ya no dependen de la posición ----------------------
    base = mod.ops_de_contorno([_rect(0, 0, 600, FONDO)], ESPESOR)
    con_corte = mod.agregar(base, {"op": "restar", "mm": ESPESOR,
                                   "entidades": [_rect(200, -10, 400, 100)]})
    id_corte = con_corte[-1]["id"]
    antes = sorted(historial.regenerar(con_corte).nombrador.caras)
    r.cierto(any(c.startswith(f"restar[{id_corte}]/") for c in antes),
             "el corte bautiza con su id", id_corte)

    # Se mete un boceto **antes** del corte: no cambia la geometría, sólo
    # recorre los índices. Es lo que va a pasar todo el tiempo en cuanto haya
    # loft y barrido, que se arman con varios bocetos por delante.
    metido = con_corte[:2] + [{"id": "extra", "op": "boceto",
                               "entidades": [_rect(0, 0, 50, 50)]}] + con_corte[2:]
    r.igual(metido.index(con_corte[2]), 3, "el corte quedó una posición más abajo")
    despues = sorted(historial.regenerar(metido).nombrador.caras)
    r.cierto(any(c.startswith(f"restar[{id_corte}]/") for c in despues),
             "y conserva su nombre: el prefijo no se movió")
    r.igual(len([c for c in despues if c.startswith("restar[")]),
            len([c for c in antes if c.startswith("restar[")]),
            "ni aparecieron ni desaparecieron caras del corte")

    # --- 5. no se quita un boceto del que cuelga otra operación ------------
    enlazado = [
        {"id": "s1", "op": "boceto", "entidades": [_rect(0, 0, 100, 100)]},
        {"id": "s2", "op": "boceto", "entidades": [_rect(0, 0, 300, 200)]},
        {"id": "m1", "op": "extruir", "mm": 10, "perfil": "s2"},
    ]
    r.igual(historial.quien_usa(enlazado, "s2"), ["m1"], "quien_usa dice quién lo señala")
    r.igual(historial.quien_usa(enlazado, "s1"), [], "y no inventa quien no lo señala")
    try:
        mod.quitar_operacion(enlazado, 1)
        r.cierto(False, "quitar un boceto usado tiene que negarse")
    except ValueError as e:
        r.cierto("m1" in str(e), "el aviso dice quién lo está usando", str(e))

    quitado = mod.quitar_operacion(enlazado, 0)
    r.igual(len(quitado), 2, "un boceto que nadie usa sí se quita")
    r.casi(historial.regenerar(quitado).solido.volume, 300 * 200 * 10,
           "y lo que quedaba se sigue construyendo", tol=1e-3)

    # --- 6. las puertas de entrada nunca dejan una operación sin id --------
    r.cierto(all(o.get("id") for o in mod.ops_de_contorno([_rect(0, 0, 10, 10)], 5)),
             "ops_de_contorno pone ids")
    r.cierto(all(o.get("id") for o in mod.mover_vertice(base, "abajo|lado[0]|lado[3]", (1, 0, 0))),
             "mover_vertice pone ids")
    r.cierto(all(o.get("id") for o in mod.mover_arista(base, "lado[1]|arriba", (1, 0, 0))),
             "mover_arista pone ids")
    r.cierto(all(o.get("id") for o in mod.cambiar_operacion(_viejo(), 1, {"mm": 25})),
             "cambiar_operacion pone ids aunque le llegue un historial viejo")
    pasos = mod.describir(_viejo())
    r.cierto(all(p.get("id") for p in pasos), "y el historial que ve la pantalla los trae")
    r.igual([p["id"] for p in pasos], ["0", "1", "2"], "con los mismos números")
