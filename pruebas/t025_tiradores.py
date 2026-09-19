"""Los tiradores de una pieza: de qué se agarra y qué pasa al jalar.

Lo que se comprueba aquí es lo que hace que arrastrar una esquina sirva de
algo: que el tirador diga **exactamente** un punto que el motor sabe mover, y
que moverlo rehaga la pieza sin perder lo que se hizo después.

La trampa que esta prueba existe para cazar: enseñar un tirador sobre un punto
que `mover_punto` no sabe mover. En pantalla se vería un cuadrito perfecto que
al jalarlo no hace nada, y eso es peor que no ponerlo.
"""
from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "los tiradores de una pieza: vértices, medios de arista y lo que mueven"


class _Cuerpo:
    """Lo mínimo que `cuerpo.tiradores` mira de una entidad."""

    def __init__(self, operaciones, plano="XY", id_="c1"):
        self.operaciones = operaciones
        self.plano = plano
        self.id = id_


def _rectangulo(x0=0.0, y0=0.0, x1=600.0, y1=400.0, mm=18.0):
    return [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]],
        }]},
        {"op": "extruir", "mm": mm},
    ]


def correr(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod

    _de_un_rectangulo(r, mod)
    _cada_tirador_mueve_de_verdad(r, mod)
    _el_medio_corre_el_tramo_entero(r, mod)
    _los_arcos_no_llevan_tirador_de_medio(r, mod)
    _mover_no_borra_lo_de_despues(r, mod)
    _la_pieza_cambia_de_tamano(r, mod)
    _en_la_pantalla(r)


def _de_un_rectangulo(r: comun.Reporte, mod) -> None:
    t = mod.tiradores(_Cuerpo(_rectangulo()))
    r.igual(len(t["vertices"]), 4, "un rectángulo da cuatro tiradores de vértice")
    r.igual(len(t["segmentos"]), 4, "y cuatro de medio de tramo, contando el que cierra")
    r.igual(t["altura"], 18.0, "la altura que sale es el espesor con el que se extruyó")
    r.igual(t["plano"], "XY", "y el plano es el de la pieza")
    medios = sorted(tuple(s["uv"]) for s in t["segmentos"])
    r.igual(medios, sorted([(300.0, 0.0), (600.0, 200.0), (300.0, 400.0), (0.0, 200.0)]),
            "los medios caen justo a la mitad de cada lado")


def _cada_tirador_mueve_de_verdad(r: comun.Reporte, mod) -> None:
    """La comprobación que justifica la prueba: **todo** tirador que se enseña
    tiene que ser movible. Un tirador que no jala es una promesa rota."""
    ops = _rectangulo()
    t = mod.tiradores(_Cuerpo(ops))
    fallos = []
    for v in t["vertices"]:
        try:
            mod.mover_punto(ops, v["entidad"], v["punto"], v["uv"][0] + 1, v["uv"][1] + 1)
        except ValueError as e:
            fallos.append(f"vértice {v['entidad']}/{v['punto']}: {e}")
    for s in t["segmentos"]:
        try:
            mod.mover_segmento(ops, s["entidad"], s["a"], s["b"], 1, 1)
        except ValueError as e:
            fallos.append(f"tramo {s['entidad']}/{s['a']}-{s['b']}: {e}")
    r.igual(fallos, [], "todos los tiradores que se enseñan se pueden mover de verdad")


def _puntos(ops):
    op = next(o for o in ops if o.get("op") == "boceto")
    return [p[:2] for p in op["entidades"][0]["puntos"]]


def _el_medio_corre_el_tramo_entero(r: comun.Reporte, mod) -> None:
    ops = _rectangulo()
    # El tramo de abajo: del punto 0 al 1. Jalarlo 50 hacia −y.
    nuevas = mod.mover_segmento(ops, 0, 0, 1, 0, -50)
    p = _puntos(nuevas)
    r.igual(p[0], [0.0, -50.0], "el primer extremo del tramo se movió")
    r.igual(p[1], [600.0, -50.0], "y el segundo se movió lo mismo: la arista corre, no se dobla")
    r.igual(p[2], [600.0, 400.0], "el resto del contorno no se tocó")
    r.igual(_puntos(ops)[0], [0.0, 0.0], "y las operaciones originales quedaron intactas")


def _los_arcos_no_llevan_tirador_de_medio(r: comun.Reporte, mod) -> None:
    """Un tramo con bulge es un arco. Su medio no está donde estaría el de una
    recta, y arrastrarlo tendría que cambiar la curvatura: otra operación. Se
    queda fuera a propósito, y los vértices del arco siguen ahí."""
    ops = [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[0, 0, 0], [100, 0, 0.5], [100, 100, 0], [0, 100, 0]],
        }]},
        {"op": "extruir", "mm": 18},
    ]
    t = mod.tiradores(_Cuerpo(ops))
    r.igual(len(t["vertices"]), 4, "los cuatro vértices siguen teniendo tirador")
    r.igual(len(t["segmentos"]), 3, "pero el tramo curvo no lleva tirador de medio")
    r.cierto(all(not (s["a"] == 1 and s["b"] == 2) for s in t["segmentos"]),
             "y el que falta es justo el del arco")


def _mover_no_borra_lo_de_despues(r: comun.Reporte, mod) -> None:
    """Lo que hace que valga la pena guardar cómo se hizo la pieza: mover una
    esquina no se lleva por delante la cara que se jaló después."""
    ops = _rectangulo() + [{"op": "empujar_cara", "cara": "arriba", "mm": 5}]
    nuevas = mod.mover_segmento(ops, 0, 0, 1, 0, -25)
    r.igual([o["op"] for o in nuevas], ["boceto", "extruir", "empujar_cara"],
            "las operaciones de después siguen ahí, en su orden")
    r.igual(nuevas[-1]["mm"], 5, "y con lo que decían")


def _la_pieza_cambia_de_tamano(r: comun.Reporte, mod) -> None:
    """Y la prueba de fuego: el sólido que sale mide lo que tiene que medir.

    Sin esto, todo lo de arriba sería mover números en un diccionario. Aquí se
    regenera de verdad, con el kernel.
    """
    antes = _Cuerpo(_rectangulo(), id_="tam-antes")
    m0 = mod.malla(antes)
    r.igual(m0["caja"], [600.0, 400.0, 18.0], "la pieza de partida mide 600 × 400 × 18")
    # El tramo de la derecha (puntos 1→2) corrido 100 hacia +x: 100 más de ancho.
    ops = mod.mover_segmento(antes.operaciones, 0, 1, 2, 100, 0)
    despues = _Cuerpo(ops, id_="tam-despues")
    m1 = mod.malla(despues)
    r.igual(m1["caja"], [700.0, 400.0, 18.0], "al correr la arista derecha 100, mide 700 de ancho")
    r.cierto(m1["volumen_mm3"] > m0["volumen_mm3"],
             "y la pieza tiene más volumen que antes")


def _en_la_pantalla(r: comun.Reporte) -> None:
    """Y en el programa de verdad: que los tiradores se carguen, caigan donde
    deben y se dejen agarrar con el ratón.

    Todo lo de arriba puede estar bien y aun así no servir de nada si el módulo
    no se carga, si el mapeo al plano se equivoca o si el radio de agarre no
    alcanza. Eso no se comprueba leyendo el código: se comprueba abriendo el
    programa.
    """
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte de pantalla se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate("typeof Tiradores !== 'undefined'"),
                 "el módulo de tiradores se carga con el programa")

        # Un tablero levantado, por el mismo camino que usa la app: la entidad
        # se crea como la crea cualquier herramienta de dibujo.
        id_ = pagina.evaluate("""async () => {
            estado.prefs.osnap = false;
            const poli = await crearEntidad({
                tipo: 'polilinea', cerrada: true,
                puntos: [[0,0,0],[600,0,0],[600,400,0],[0,400,0]],
            }, 'rectangulo de prueba');
            if (!poli) return null;
            const m = await fetch('/api/cuerpo/extruir', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ids: [poli], mm: 18}),
            }).then((x) => x.json());
            await Cuerpos.refrescar();
            encuadrarCaja(-200, -200, 900, 700);
            return m.id || null;
        }""")
        if not r.cierto(bool(id_), "se levanta una pieza de 600 × 400 × 18"):
            return

        conteo = pagina.evaluate("""async (id) => {
            await Tiradores.cargar(id);
            return Tiradores.delMundo(id).length;
        }""", id_)
        # Cuatro esquinas × tres alturas (abajo, medio de la arista vertical,
        # arriba) + cuatro tramos × dos alturas. Si este número cambia, cambió
        # el reparto, y eso se decide a propósito: no se descubre instalando.
        r.igual(conteo, 4 * 3 + 4 * 2, "la pieza da 20 tiradores: 12 de esquina y 8 de arista")

        agarre = pagina.evaluate("""(id) => {
            Ventanas.activar(0);
            Cuerpos.senalar({ id, cara: 'arriba' });
            const t = Tiradores.delMundo(id).find((x) => x.tipo === 'vertice');
            const q = aPX(t.p[0], t.p[1], t.p[2]);
            const cerca = Tiradores.bajo(q[0], q[1]);
            return { hay: !!cerca, tipo: cerca ? cerca.tipo : null,
                     lejos: !!Tiradores.bajo(q[0] + 200, q[1] + 200) };
        }""", id_)
        r.cierto(agarre["hay"], "picando justo encima de un tirador, se agarra")
        r.igual(agarre["tipo"], "vertice", "y el de una esquina es de vértice")
        r.cierto(not agarre["lejos"], "picando lejos no se agarra nada")

        # Los tiradores se pintan en las cuatro ventanas, cada una desde su
        # ángulo: es el mismo error que costó la 0.11.0 y la 0.12.0, y no se
        # va a repetir en silencio.
        repartidos = pagina.evaluate("""(id) => {
            const puestos = [];
            for (let i = 0; i < 4; i++) {
                const v = Ventanas.la(i);
                const guardada = estado.vista;
                estado.vista = v;
                const t = Tiradores.delMundo(id)[0];
                const q = aPX(t.p[0], t.p[1], t.p[2]);
                estado.vista = guardada;
                puestos.push([Math.round(q[0]), Math.round(q[1])]);
            }
            return puestos;
        }""", id_)
        distintos = {tuple(p) for p in repartidos}
        r.cierto(len(distintos) >= 3,
                 "el mismo tirador cae en sitios distintos en cada ventana: cada una lo "
                 "proyecta desde su ángulo")

        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
