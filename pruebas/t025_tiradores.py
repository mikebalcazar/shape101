"""Los tiradores de una pieza: sus vértices y sus aristas, cada uno suyo.

Desde la 0.14.0 una pieza deja de ser «un contorno levantado» a la hora de
editarla: cada vértice y cada arista del sólido se mueven solos. Mike lo pidió
así el 19-sep, viendo que en la 0.13.0 mover la esquina de arriba movía también
la de abajo, porque eran el mismo punto del boceto.

Lo que esta prueba fija, y por qué cada cosa:

1. **Los nombres sobreviven.** Un tirador viaja con un nombre derivado de las
   caras que lo forman, no con un índice. Si eso se rompe, el historial deja de
   ser un historial: cambias una cota y la esquina que jalaste se va a otro
   lado. Se comprueba contra un boceto distinto.
2. **La geometría es la que dice la fórmula**, no «se ve bien». Un modelador
   que se equivoca por medio milímetro corta mal la madera.
3. **Una cara alabeada no se infla.** El 19-sep, rellenar su contorno dejaba
   una cara de z = −39.53 a 18 en una pieza de 18 de espesor. Aquí se mide la
   caja después de mover, que es donde eso se ve.
4. **Lo imposible se niega y no deja el modelo roto.**
"""
from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "tiradores: vértices y aristas del sólido, cada uno independiente"

ANCHO, FONDO, ESPESOR = 600.0, 400.0, 18.0


def _ops(ancho=ANCHO, fondo=FONDO, mm=ESPESOR):
    return [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[0, 0, 0], [ancho, 0, 0], [ancho, fondo, 0], [0, fondo, 0]],
        }]},
        {"op": "extruir", "mm": mm},
    ]


def correr(r: comun.Reporte) -> None:
    from core.solido import historial

    _de_un_tablero(r, historial)
    _el_nombre_sobrevive_al_boceto(r, historial)
    _mover_un_vertice(r, historial)
    _mover_una_arista(r, historial)
    _encadenadas(r, historial)
    _lo_imposible_se_niega(r, historial)
    _en_los_tres_planos(r)
    _en_la_pantalla(r)


def _de_un_tablero(r: comun.Reporte, historial) -> None:
    reg = historial.regenerar(_ops())
    vs = reg.nombrador.vertices(reg.solido)
    ar = reg.nombrador.aristas(reg.solido)
    r.igual(len(vs), 8, "un tablero tiene ocho vértices, y los ocho tienen nombre")
    r.igual(len(ar), 12, "y doce aristas, todas nombradas")
    r.cierto("abajo|lado[0]|lado[1]" in vs,
             "el nombre dice qué caras forman la esquina, no dónde está")
    esquina = vs["abajo|lado[0]|lado[1]"]
    r.punto([esquina.X, esquina.Y], [ANCHO, 0.0], "y esa esquina está donde debe", 1e-6)
    # Arriba y abajo son ocho puntos distintos, no cuatro repetidos: es
    # exactamente lo que no pasaba en la 0.13.0.
    alturas = {round(v.Z, 6) for v in vs.values()}
    r.igual(sorted(alturas), [0.0, ESPESOR],
            "hay vértices arriba y abajo, y son distintos entre sí")


def _el_nombre_sobrevive_al_boceto(r: comun.Reporte, historial) -> None:
    """La comprobación que sostiene todo lo demás.

    Si el nombre de una esquina se fuera a otro lado al cambiar una cota, esto
    dejaría de ser un historial y pasaría a ser geometría suelta con pasos
    encima. Se cambia el ancho del boceto de 600 a 900 y se exige que el mismo
    nombre siga siendo la misma esquina.
    """
    nombre = "abajo|lado[0]|lado[1]"
    chico = historial.regenerar(_ops())
    grande = historial.regenerar(_ops(ancho=900))
    a = chico.nombrador.vertices(chico.solido)[nombre]
    b = grande.nombrador.vertices(grande.solido)[nombre]
    r.punto([a.X, a.Y], [600.0, 0.0], "con 600 de ancho, la esquina está en 600", 1e-6)
    r.punto([b.X, b.Y], [900.0, 0.0], "con 900, el mismo nombre está en 900", 1e-6)

    # Y con la operación encima: la esquina jalada sigue siendo esa esquina.
    movido = historial.regenerar(_ops(ancho=900) + [
        {"op": "mover_vertice", "vertice": nombre, "d": [50, 0, 0]}])
    caja = movido.solido.bounding_box()
    r.casi(caja.size.X, 950.0, "jalarla 50 sobre el boceto grande da 950 de ancho", 0.01)


def _mover_un_vertice(r: comun.Reporte, historial) -> None:
    reg = historial.regenerar(_ops() + [
        {"op": "mover_vertice", "vertice": "abajo|lado[0]|lado[1]", "d": [50, 0, 0]}])
    caja = reg.solido.bounding_box()
    r.casi(caja.size.X, 650.0, "la pieza se hizo 50 más ancha", 0.01)
    r.casi(caja.size.Z, ESPESOR,
           "y **el espesor no cambió**: la cara alabeada no se infla", 0.01)
    # Abajo pasa a ser un cuadrilátero de 250 000 mm²; arriba sigue en 240 000.
    # El volumen es el promedio por el espesor, y eso es un número, no una
    # impresión.
    r.casi(reg.solido.volume, ESPESOR * (250000.0 + 240000.0) / 2,
           "el volumen es el que dice la fórmula", 1.0)
    r.igual(len(reg.solido.faces()), 6, "sigue teniendo seis caras")
    r.igual(len(reg.nombrador.caras), 6, "y las seis siguen con nombre")


def _mover_una_arista(r: comun.Reporte, historial) -> None:
    """Una arista se mueve entera: sus dos extremos, lo mismo."""
    reg = historial.regenerar(_ops() + [
        {"op": "mover_arista", "arista": "abajo|lado[0]", "d": [0, 0, 10]}])
    # Subir la arista de abajo del lado 0 corta una cuña de 600 × 400 × 10 / 2.
    r.casi(reg.solido.volume, ANCHO * FONDO * ESPESOR - ANCHO * FONDO * 10 / 2,
           "subir una arista 10 quita justo la cuña que se ve", 1.0)
    r.cierto(reg.solido.is_valid() if callable(reg.solido.is_valid) else reg.solido.is_valid,
             "y la pieza sigue siendo un sólido válido")


def _encadenadas(r: comun.Reporte, historial) -> None:
    ops = _ops() + [
        {"op": "mover_vertice", "vertice": "abajo|lado[0]|lado[1]", "d": [50, 0, 0]},
        {"op": "mover_vertice", "vertice": "arriba|lado[2]|lado[3]", "d": [-30, 0, 0]},
        {"op": "mover_arista", "arista": "abajo|lado[1]", "d": [0, 20, 0]},
    ]
    reg = historial.regenerar(ops)
    r.igual(len(reg.solido.faces()), 6, "tres ediciones seguidas y sigue con seis caras")
    r.cierto(reg.solido.volume > 0, "y con volumen")
    caja = reg.solido.bounding_box()
    r.casi(caja.size.Z, ESPESOR, "el espesor aguanta las tres", 0.01)


def _lo_imposible_se_niega(r: comun.Reporte, historial) -> None:
    """Mover un punto 500 mm en el espesor de una pieza de 18 no da una pieza:
    da un nudo. El motor tiene que decirlo, no entregar algo roto."""
    ops = _ops() + [
        {"op": "mover_vertice", "vertice": "abajo|lado[0]|lado[1]", "d": [0, 0, 500]}]
    try:
        historial.regenerar(ops)
        r.cierto(False, "un movimiento imposible tiene que fallar, no pasar callado")
    except Exception as e:
        r.cierto(True, f"un movimiento imposible se niega ({type(e).__name__})")
    # Y el historial de antes sigue sirviendo: no se contaminó nada.
    reg = historial.regenerar(_ops())
    r.casi(reg.solido.volume, ANCHO * FONDO * ESPESOR,
           "y la pieza de antes sigue intacta", 1.0)


def _en_los_tres_planos(r: comun.Reporte) -> None:
    """Una pieza dibujada en la Frontal o en la Lateral se jala igual: el
    tirador llega girado al mundo y el arrastre se gira de vuelta."""
    from core import entidades as E
    from core.documento import Documento
    from core.solido import cuerpo as mod, rutas

    esperado = {"XY": [50, 0, 0], "XZ": [50, 0, 0], "YZ": [0, 50, 0]}
    for plano, d in esperado.items():
        doc = Documento.nuevo()
        rutas.enchufar(lambda: doc)
        mod.olvidar()
        poli = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, FONDO, 0], [0, FONDO, 0]],
                           cerrada=True)
        if hasattr(poli, "plano"):
            poli.plano = plano
        doc.agregar(poli)
        m = rutas.extruir(rutas.Extruir(ids=[poli.id], mm=ESPESOR))
        cid = m["id"]
        t = rutas.tiradores(cid)
        r.igual(len(t["vertices"]), 8, f"{plano}: llegan los ocho vértices al mundo")
        v = next(q for q in t["vertices"] if q["nombre"] == "abajo|lado[0]|lado[1]")
        antes = list(v["p"])
        m2 = rutas.mover_vertice(cid, rutas.MoverEnElMundo(nombre=v["nombre"], d=d))
        r.igual(m2["caja"], [650.0, 400.0, 18.0], f"{plano}: la pieza se hizo 50 más ancha")
        t2 = rutas.tiradores(cid)
        v2 = next((q for q in t2["vertices"] if q["nombre"] == v["nombre"]), None)
        if r.cierto(v2 is not None, f"{plano}: el tirador conserva su nombre tras moverlo"):
            movido = [round(v2["p"][k] - antes[k], 3) for k in range(3)]
            r.igual(movido, [float(k) for k in d],
                    f"{plano}: y quedó exactamente donde se le pidió, en el mundo")


def _en_la_pantalla(r: comun.Reporte) -> None:
    """Y en el programa de verdad: que los tiradores se carguen, caigan donde
    deben y se dejen agarrar."""
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte de pantalla se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate("typeof Tiradores !== 'undefined'"),
                 "el módulo de tiradores se carga con el programa")

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
            encuadrarCaja(-200, -200, 900, 700);
            return m.id || null;
        }""")
        if not r.cierto(bool(id_), "se levanta un tablero de 600 × 400 × 18"):
            return

        cuenta = pagina.evaluate("""async (id) => {
            await Tiradores.cargar(id);
            const t = Tiradores.delMundo(id);
            return { total: t.length,
                     vertices: t.filter((x) => x.tipo === 'vertice').length,
                     aristas: t.filter((x) => x.tipo === 'arista').length };
        }""", id_)
        r.igual(cuenta["vertices"], 8, "en pantalla salen los ocho vértices")
        r.igual(cuenta["aristas"], 12, "y las doce aristas")

        agarre = pagina.evaluate("""(id) => {
            Ventanas.activar(0);
            Cuerpos.senalar({ id, cara: 'arriba' });
            const t = Tiradores.delMundo(id).find((x) => x.tipo === 'vertice');
            const q = aPX(t.p[0], t.p[1], t.p[2]);
            const cerca = Tiradores.bajo(q[0], q[1]);
            return { hay: !!cerca, tipo: cerca ? cerca.tipo : null,
                     nombre: cerca ? cerca.nombre : null,
                     lejos: !!Tiradores.bajo(q[0] + 200, q[1] + 200),
                     plano: Tiradores.planoDeArrastre() };
        }""", id_)
        r.cierto(agarre["hay"], "picando justo encima de un tirador, se agarra")
        r.igual(agarre["tipo"], "vertice", "y el de una esquina es de vértice")
        r.cierto("|" in (agarre["nombre"] or ""), "que llega con su nombre de caras")
        r.cierto(not agarre["lejos"], "picando lejos no se agarra nada")
        r.igual(agarre["plano"], "XY", "en la Superior se arrastra sobre el suelo")

        # Cada ventana arrastra sobre su plano: es lo que quita la ambigüedad.
        planos = pagina.evaluate("""() => {
            const out = [];
            const guardada = estado.vista;
            for (let i = 0; i < 4; i++) {
                estado.vista = Ventanas.la(i);
                out.push([Ventanas.la(i).nombre, Tiradores.planoDeArrastre()]);
            }
            estado.vista = guardada;
            return out;
        }""")
        r.igual(dict(planos).get("Frontal"), "XZ", "en la Frontal se arrastra sobre XZ")
        r.igual(dict(planos).get("Lateral"), "YZ", "en la Lateral, sobre YZ")
        r.igual(dict(planos).get("Perspectiva"), "XY",
                "y en la Perspectiva sobre el suelo, que es lo único decidible solo")

        # --- elegir aristas con Ctrl+clic  ·  0.18.0 -------------------------
        #
        # Antes REDONDEAR tomaba **todas** las verticales, que era un apaño: en
        # una pieza de taller casi nunca se redondean las cuatro. Ctrl y no un
        # clic pelón porque el clic pelón ya significa «jalar esta arista», que
        # es el gesto que más se usa.
        elegir = pagina.evaluate("""(id) => {
            Ventanas.activar(0);
            Cuerpos.senalar({ id, cara: 'arriba' });
            const aristas = Tiradores.delMundo(id).filter((t) => t.tipo === 'arista');
            const a = aristas[0], b = aristas[1];
            const vacio = Tiradores.aristasElegidas(id);
            Tiradores.alternarElegida(id, a.nombre);
            Tiradores.alternarElegida(id, b.nombre);
            const dos = Tiradores.aristasElegidas(id);
            Tiradores.alternarElegida(id, a.nombre);            // otra vez: se quita
            const una = Tiradores.aristasElegidas(id);
            return { vacio, dos, una, sigue: Tiradores.estaElegida(id, b.nombre),
                     ordenado: dos.join('|') === [...dos].sort().join('|') };
        }""", id_)
        r.igual(elegir["vacio"], [], "de entrada no hay ninguna arista elegida")
        r.igual(len(elegir["dos"]), 2, "Ctrl+clic en dos aristas elige las dos")
        r.igual(len(elegir["una"]), 1, "y volver a picar una la quita")
        r.cierto(elegir["sigue"], "quitar una no se lleva a la otra")
        r.cierto(elegir["ordenado"],
                 "las elegidas salen ordenadas: el historial no depende del orden en que se picaron")

        # El clic de verdad: con Ctrl elige, sin Ctrl jala. Son dos gestos
        # distintos sobre el mismo tirador, y si se confundieran no habría
        # manera de elegir sin mover la pieza.
        clics = pagina.evaluate("""(id) => {
            Tiradores.soltarElegidas(id);
            // Una arista que de verdad se agarre desde esta ventana. En la
            // Superior, una arista **vertical** se proyecta justo encima de su
            // esquina, y a igualdad gana el vértice: ésas no se pueden picar
            // desde aquí, hay que girar la vista o usar otra ventana.
            const t = Tiradores.delMundo(id).filter((x) => x.tipo === 'arista')
              .find((x) => {
                const p = aPX(x.p[0], x.p[1], x.p[2]);
                const b = Tiradores.bajo(p[0], p[1]);
                return b && b.tipo === 'arista' && b.nombre === x.nombre;
              });
            if (!t) return null;
            const q = aPX(t.p[0], t.p[1], t.p[2]);
            const caja = document.getElementById('lienzo').getBoundingClientRect();
            const hacer = (ctrl) => Tiradores.abajo(new MouseEvent('mousedown', {
                button: 0, ctrlKey: ctrl,
                clientX: caja.left + q[0], clientY: caja.top + q[1] }));
            const conCtrl = hacer(true);
            const traeCtrl = { tomado: conCtrl, elegidas: Tiradores.aristasElegidas(id).length,
                               arrastrando: Tiradores.arrastrando() };
            const sinCtrl = hacer(false);
            const traeSin = { tomado: sinCtrl, arrastrando: Tiradores.arrastrando() };
            Tiradores.arriba(new MouseEvent('mouseup', { button: 0 }));
            Tiradores.soltarElegidas(id);
            return { traeCtrl, traeSin, tras: Tiradores.aristasElegidas(id).length };
        }""", id_)
        if not r.cierto(clics is not None,
                        "en la Superior hay aristas que se pueden picar (las horizontales)"):
            return
        r.cierto(clics["traeCtrl"]["tomado"], "Ctrl+clic sobre una arista se toma")
        r.igual(clics["traeCtrl"]["elegidas"], 1, "y la elige")
        r.cierto(not clics["traeCtrl"]["arrastrando"],
                 "y NO empieza a arrastrarla: elegir no mueve la pieza")
        r.cierto(clics["traeSin"]["arrastrando"],
                 "sin Ctrl, el mismo clic sí empieza a jalarla")
        r.igual(clics["tras"], 0, "y soltarlas las suelta")

        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
