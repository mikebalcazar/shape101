"""El historial de una pieza: verlo y tocarlo  ·  0.15.0

Mike, el 19-sep: *«la parametrización del modelo me interesa muchísimo. El
mantener algo de historial de cómo se generó un barreno (se hace un trazo de un
cilindro y se resta al volumen), pero después se quiere agrandar o achicar:
sólo se podría incrementar o disminuir el diámetro del cilindro original sin
necesidad de trazarlo todo de nuevo y volver a ejecutar la operación»*.

Eso es exactamente lo que se fija aquí, y en ese orden:

1. **El historial se lee en palabras del taller.** «Barreno ⌀40», no
   `{"op": "restar", ...}`. Si la pantalla tuviera que saber de qué está hecha
   cada operación, cada operación nueva rompería la pantalla.
2. **Cambiar un número rehace la pieza entera desde el contorno**, no parcha la
   geometría. Se mide el volumen contra la fórmula, no contra «se ve bien».
3. **Lo que se hizo después sobrevive.** Un redondeo hecho encima de un barreno
   sigue puesto cuando el barreno cambia de diámetro, y sigue puesto cuando el
   barreno se borra del historial. Eso es lo que separa un historial de una
   lista de cosas que pasaron.
4. **Un cambio imposible se niega y deja la pieza intacta.** Es lo que hace que
   tocar números no dé miedo: el peor caso es que no pase nada.
5. **El contorno y la extrusión no se borran.** Sin ellos no hay pieza.
"""
from __future__ import annotations

import math

from pruebas import comun, navegador

DESCRIPCION = "historial de la pieza: pasos en palabras, números que se tocan"

ANCHO, FONDO, ESPESOR = 600.0, 400.0, 18.0
SOLIDO = ANCHO * FONDO * ESPESOR


def _ops(ancho=ANCHO, fondo=FONDO, mm=ESPESOR):
    return [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[0, 0, 0], [ancho, 0, 0], [ancho, fondo, 0], [0, fondo, 0]],
        }]},
        {"op": "extruir", "mm": mm},
    ]


def _barreno(radio, cx=300.0, cy=200.0, mm=ESPESOR):
    return {"op": "restar",
            "entidades": [{"tipo": "circulo", "centro": [cx, cy], "radio": radio}],
            "mm": mm}


def correr(r: comun.Reporte) -> None:
    from core.solido import cuerpo, historial

    _en_palabras(r, cuerpo, historial)
    _agrandar_el_barreno(r, cuerpo, historial)
    _lo_de_encima_sobrevive(r, cuerpo, historial)
    _quitar_un_paso(r, cuerpo, historial)
    _lo_imposible_se_niega(r, cuerpo, historial)
    _en_la_pantalla(r)


def _volumen(solido) -> float:
    v = solido.volume
    return float(v() if callable(v) else v)


# --- 1. el historial en palabras -------------------------------------------

def _en_palabras(r: comun.Reporte, cuerpo, historial) -> None:
    pasos = cuerpo.describir(_ops() + [_barreno(20.0),
                                       {"op": "redondear", "aristas": ["a|b"], "r": 5.0}])
    r.igual(len(pasos), 4, "cada operación es un paso del historial")
    r.igual(pasos[1]["titulo"], "Extruir 18.0", "la extrusión se lee como lo que es")
    r.igual(pasos[2]["titulo"], "Barreno ⌀40.0",
            "y un círculo restado se lee «barreno», con su diámetro, no su radio")
    r.cierto(pasos[3]["titulo"].startswith("Redondeo r5.0"), "el redondeo dice su radio")

    r.cierto(pasos[0]["de_nacimiento"] and pasos[1]["de_nacimiento"],
             "el contorno y la extrusión vienen marcados como de nacimiento")
    r.cierto(not pasos[2]["de_nacimiento"], "y el barreno no: ése sí se puede quitar")

    claves = {c["clave"]: c for c in pasos[2]["campos"]}
    r.igual(sorted(claves), ["entidades/0/centro/0", "entidades/0/centro/1",
                             "entidades/0/radio", "mm"],
            "del barreno se puede tocar el radio, el centro y la profundidad")
    r.igual(claves["entidades/0/radio"]["valor"], 20.0, "el radio llega con su valor")
    r.igual(claves["entidades/0/radio"]["minimo"], 0.01,
            "y con su mínimo, para que la pantalla no mande un radio cero")
    r.igual(claves["mm"]["unidad"], "mm", "los números traen su unidad")


# --- 2. cambiar un número rehace la pieza ----------------------------------

def _agrandar_el_barreno(r: comun.Reporte, cuerpo, historial) -> None:
    """El ejemplo de Mike, medido."""
    ops = _ops() + [_barreno(20.0)]
    antes = historial.regenerar(ops)
    r.casi(_volumen(antes.solido), SOLIDO - math.pi * 20 ** 2 * ESPESOR,
           "un barreno ⌀40 quita exactamente su cilindro", 1.0)

    # Sólo el número, sin volver a trazar el círculo ni repetir la resta.
    nuevas = cuerpo.cambiar_operacion(ops, 2, {"entidades/0/radio": 40.0})
    despues = historial.regenerar(nuevas)
    r.casi(_volumen(despues.solido), SOLIDO - math.pi * 40 ** 2 * ESPESOR,
           "cambiar el radio a 40 da ⌀80 exacto, sin trazar nada", 1.0)
    r.igual(ops[2]["entidades"][0]["radio"], 20.0,
            "y el historial viejo no se tocó: se devuelve uno nuevo")

    movido = historial.regenerar(cuerpo.cambiar_operacion(ops, 2,
                                 {"entidades/0/centro/0": 100.0}))
    r.casi(_volumen(movido.solido), _volumen(antes.solido),
           "mover el centro del barreno no cambia cuánto quita", 1.0)


# --- 3. lo de encima sobrevive ---------------------------------------------

def _lo_de_encima_sobrevive(r: comun.Reporte, cuerpo, historial) -> None:
    """La prueba que separa un historial de una lista de cosas que pasaron."""
    base = historial.regenerar(_ops())
    verticales = [n for n in base.nombrador.aristas(base.solido)
                  if n.count("lado[") == 2][:2]
    if not r.igual(len(verticales), 2, "un tablero tiene aristas verticales que redondear"):
        return

    ops = _ops() + [_barreno(20.0), {"op": "redondear", "aristas": verticales, "r": 20.0}]
    con = historial.regenerar(ops)
    caras = len(con.solido.faces())
    r.cierto(caras > 6, "con barreno y redondeos la pieza tiene más de seis caras")

    # El barreno cambia de tamaño; los redondeos siguen ahí.
    grande = historial.regenerar(cuerpo.cambiar_operacion(ops, 2, {"entidades/0/radio": 40.0}))
    r.igual(len(grande.solido.faces()), caras,
            "agrandar el barreno no se lleva los redondeos hechos después")
    r.casi(_volumen(grande.solido) - _volumen(con.solido),
           -math.pi * (40 ** 2 - 20 ** 2) * ESPESOR,
           "y quita justo el cilindro de más, ni un milímetro cúbico más", 1.0)

    # El radio del redondeo también se toca después, sin volver a elegir aristas.
    otro = historial.regenerar(cuerpo.cambiar_operacion(ops, 3, {"r": 40.0}))
    r.igual(len(otro.solido.faces()), caras,
            "cambiar el radio del redondeo no cambia de qué está hecha la pieza")
    r.cierto(_volumen(otro.solido) < _volumen(con.solido),
             "un redondeo más grande quita más material")


# --- 4. quitar un paso ------------------------------------------------------

def _quitar_un_paso(r: comun.Reporte, cuerpo, historial) -> None:
    base = historial.regenerar(_ops())
    verticales = [n for n in base.nombrador.aristas(base.solido)
                  if n.count("lado[") == 2][:2]
    ops = _ops() + [_barreno(20.0), {"op": "redondear", "aristas": verticales, "r": 20.0}]
    con = historial.regenerar(ops)

    sin = historial.regenerar(cuerpo.quitar_operacion(ops, 2))
    r.casi(_volumen(sin.solido) - _volumen(con.solido), math.pi * 20 ** 2 * ESPESOR,
           "quitar el barreno de en medio devuelve exactamente su material", 1.0)
    r.igual(len(sin.solido.faces()), len(con.solido.faces()) - 1,
           "y los redondeos siguen aplicados: sólo se fue la cara del barreno")

    r.levanta(ValueError, cuerpo.quitar_operacion,
              "el contorno no se puede quitar: sin él no hay pieza", ops, 0)
    r.levanta(ValueError, cuerpo.quitar_operacion,
              "la extrusión tampoco", ops, 1)
    r.levanta(ValueError, cuerpo.quitar_operacion,
              "ni un paso que no existe", ops, 99)


# --- 5. lo imposible ---------------------------------------------------------

def _lo_imposible_se_niega(r: comun.Reporte, cuerpo, historial) -> None:
    ops = _ops() + [_barreno(20.0)]
    r.levanta(ValueError, cuerpo.cambiar_operacion,
              "un campo que la operación no tiene se niega antes de tocar nada",
              ops, 2, {"radio_de_la_luna": 3})

    # Un barreno más grande que la pieza: el motor tiene que decirlo, no sacar
    # una pieza rota. Lo que importa es que se entere quien llama.
    enormes = cuerpo.cambiar_operacion(ops, 2, {"entidades/0/radio": 5000.0})
    try:
        reg = historial.regenerar(enormes)
        roto = _volumen(reg.solido) <= 0
    except Exception:
        roto = True
    r.cierto(roto, "un barreno más grande que la pieza no devuelve una pieza válida")
    r.casi(_volumen(historial.regenerar(ops).solido),
           SOLIDO - math.pi * 20 ** 2 * ESPESOR,
           "y el historial de verdad sigue dando la pieza de siempre", 1.0)


# --- 6. y en el programa -----------------------------------------------------

def _en_la_pantalla(r: comun.Reporte) -> None:
    """El panel: que salga al señalar, que diga los pasos y que al teclear un
    número la pieza cambie de verdad."""
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte de pantalla se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate("typeof Historial !== 'undefined'"),
                 "el panel del historial se carga con el programa")
        r.cierto(pagina.evaluate("!!document.querySelector('#props-historial')"),
                 "y tiene su lugar en el panel de la derecha")
        r.cierto(pagina.evaluate("Comandos.existe('BARRENO') && Comandos.existe('REDONDEAR')"),
                 "BARRENO y REDONDEAR ya se pueden teclear")

        id_ = pagina.evaluate("""async () => {
            estado.prefs.osnap = false;
            const poli = await crearEntidad({
                tipo: 'polilinea', cerrada: true,
                puntos: [[0,0,0],[600,0,0],[600,400,0],[0,400,0]],
            }, 'tablero de prueba');
            if (!poli) return null;
            const m = await fetch('/api/cuerpo/extruir', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ids: [poli], mm: 18}),
            }).then((x) => x.json());
            await Cuerpos.refrescar();
            return m.id || null;
        }""")
        if not r.cierto(bool(id_), "se levanta un tablero de 600 × 400 × 18"):
            return

        # Señalar una cara es decir «de ésta quiero ver cómo se hizo».
        visible = pagina.evaluate("""async (id) => {
            Cuerpos.senalar({ id, cara: 'arriba' });
            await new Promise((s) => setTimeout(s, 300));
            const caja = document.querySelector('#props-historial');
            return { abierto: !caja.hidden,
                     pasos: Historial.pasos.map((p) => p.titulo),
                     filas: document.querySelectorAll('#hist-pasos .paso').length,
                     cerrar: document.querySelectorAll('#hist-pasos .cerrar').length };
        }""", id_)
        r.cierto(visible["abierto"], "al señalar una cara, el panel se abre solo")
        r.igual(visible["pasos"], ["Contorno · 1 entidad(es), 4 punto(s)", "Extruir 18.0"],
                "y dice con qué se hizo la pieza, en palabras")
        r.igual(visible["filas"], 2, "un bloque por paso")
        r.igual(visible["cerrar"], 0,
                "sin botón de quitar en los de nacimiento: quitarlos deja sin pieza")

        # Un barreno desde el programa, y su número tocado desde el panel.
        tras = pagina.evaluate("""async (id) => {
            await fetch(`/api/cuerpo/${id}/barreno`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ centro: [300, 200, 0], radio: 20 }),
            }).then((x) => x.json());
            await Historial.traer();
            return { pasos: Historial.pasos.length,
                     titulo: Historial.pasos[2].titulo,
                     cerrar: document.querySelectorAll('#hist-pasos .cerrar').length };
        }""", id_)
        r.igual(tras["pasos"], 3, "el barreno entra al historial como un paso más")
        r.igual(tras["titulo"], "Barreno ⌀40.0", "y se lee por su diámetro")
        r.igual(tras["cerrar"], 1, "ése sí trae su botón de quitar")

        # Lo que Mike pidió, tecleado en la cajita: sólo el número.
        cambio = pagina.evaluate("""async (id) => {
            const inp = [...document.querySelectorAll('#hist-pasos .paso')][2]
                          .querySelectorAll('input')[0];
            const etiqueta = [...document.querySelectorAll('#hist-pasos .paso')][2]
                          .querySelector('label').textContent;
            inp.value = '40';
            inp.dispatchEvent(new Event('change'));
            await new Promise((s) => setTimeout(s, 600));
            const m = await fetch(`/api/cuerpo/${id}/malla`).then((x) => x.json());
            return { etiqueta, titulo: Historial.pasos[2].titulo,
                     caras: new Set(m.caras || (m.triangulos || []).map((t) => t.cara)).size };
        }""", id_)
        r.igual(cambio["etiqueta"], "Radio", "la primera cajita del barreno es su radio")
        r.igual(cambio["titulo"], "Barreno ⌀80.0",
                "tecleando 40 en el radio, el barreno pasa a ⌀80 sin trazar nada")

        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
