"""El boceto con cotas: teclear una medida en vez de arrastrar  ·  0.16.0

Es la etapa B, la que Mike eligió: *«hoy sólo se mueven los puntos con el
ratón; que cambiar el ancho a 900 sea teclear 900»*.

Un contorno no trae cotas escritas, trae puntos. Así que las cotas **se sacan
de la caja del contorno**, y teclear una estira el contorno hasta que la caja
mida eso. Lo que esta prueba fija:

1. **La medida que se enseña es la que se corta.** Se mide el volumen contra la
   fórmula, no contra «se ve bien».
2. **Estirar no se lleva lo que se hizo después.** Un barreno y unos redondeos
   siguen puestos al cambiar el ancho, y el barreno **sigue redondo**: en
   madera no hay barrenos ovalados.
3. **El contorno no se va de lugar.** Se estira desde la esquina de origen, que
   se queda donde está; correrla es otro campo aparte.
4. **Funciona con cualquier contorno**, no sólo con rectángulos: una L se
   estira entera.
5. **Lo imposible se niega**: medida cero o negativa, y una cota pedida a una
   operación que no es un boceto.
6. Y en la pantalla: el letrero de las tres medidas sobre la pieza señalada.
"""
from __future__ import annotations

import math

from pruebas import comun, navegador

DESCRIPCION = "boceto con cotas: teclear el ancho en vez de arrastrar puntos"

ANCHO, FONDO, ESPESOR = 600.0, 400.0, 18.0


def _ops(ancho=ANCHO, fondo=FONDO, mm=ESPESOR):
    return [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[0, 0, 0], [ancho, 0, 0], [ancho, fondo, 0], [0, fondo, 0]],
        }]},
        {"op": "extruir", "mm": mm},
    ]


def _ele():
    return [
        {"op": "boceto", "entidades": [{
            "tipo": "polilinea", "cerrada": True,
            "puntos": [[0, 0, 0], [600, 0, 0], [600, 200, 0],
                       [300, 200, 0], [300, 400, 0], [0, 400, 0]],
        }]},
        {"op": "extruir", "mm": ESPESOR},
    ]


def _volumen(solido) -> float:
    v = solido.volume
    return float(v() if callable(v) else v)


def correr(r: comun.Reporte) -> None:
    from core.solido import cuerpo, historial

    _las_cotas_se_leen(r, cuerpo)
    _teclear_una_medida(r, cuerpo, historial)
    _lo_de_encima_sobrevive(r, cuerpo, historial)
    _correr_el_contorno(r, cuerpo, historial)
    _cualquier_contorno(r, cuerpo, historial)
    _lo_imposible_se_niega(r, cuerpo)
    _en_la_pantalla(r)


# --- 1. las cotas se leen ----------------------------------------------------

def _las_cotas_se_leen(r: comun.Reporte, cuerpo) -> None:
    pasos = cuerpo.describir(_ops())
    b = pasos[0]
    r.igual(b["titulo"], "Rectángulo 600.0 × 400.0",
            "un contorno de cuatro esquinas se llama rectángulo y dice su medida")
    campos = {c["clave"]: c for c in b["campos"]}
    r.igual(sorted(campos), ["ancho", "fondo", "x", "y"],
            "y trae cuatro números: las dos medidas y dónde empieza")
    r.igual(campos["ancho"]["valor"], 600.0, "el ancho es el ancho")
    r.igual(campos["fondo"]["valor"], 400.0, "el fondo es el fondo")
    r.igual(campos["ancho"]["minimo"], 0.01,
            "con su mínimo: una pieza de ancho cero no es una pieza")

    # La L no es un rectángulo y no se dice que lo sea.
    r.cierto(cuerpo.describir(_ele())[0]["titulo"].startswith("Contorno 600.0 × 400.0"),
             "un contorno que no es rectángulo lo dice, y da su caja igual")


# --- 2. teclear la medida ----------------------------------------------------

def _teclear_una_medida(r: comun.Reporte, cuerpo, historial) -> None:
    ops = _ops()
    nuevas = cuerpo.cambiar_operacion(ops, 0, {"ancho": 900})
    reg = historial.regenerar(nuevas)
    r.casi(_volumen(reg.solido), 900 * FONDO * ESPESOR,
           "teclear 900 en el ancho da una pieza de 900 exactos", 1.0)
    r.igual(cuerpo.describir(nuevas)[0]["titulo"], "Rectángulo 900.0 × 400.0",
            "y el historial ya se lee con la medida nueva")
    r.igual(ops[0]["entidades"][0]["puntos"][1][0], 600.0,
            "el historial viejo no se tocó: se devuelve uno nuevo")

    caja = reg.solido.bounding_box()
    r.casi(caja.min.X, 0.0, "la esquina de origen se quedó donde estaba", 1e-6)
    r.casi(caja.max.X, 900.0, "y el contorno creció hacia el otro lado", 1e-6)

    # Las dos a la vez, en una sola llamada: es como llega del panel.
    dos = historial.regenerar(cuerpo.cambiar_operacion(ops, 0, {"ancho": 900, "fondo": 500}))
    r.casi(_volumen(dos.solido), 900 * 500 * ESPESOR,
           "cambiar ancho y fondo juntos también cuadra", 1.0)

    # Achicar, no sólo crecer.
    chico = historial.regenerar(cuerpo.cambiar_operacion(ops, 0, {"ancho": 300}))
    r.casi(_volumen(chico.solido), 300 * FONDO * ESPESOR, "y achicar también", 1.0)


# --- 3. lo de encima sobrevive ----------------------------------------------

def _lo_de_encima_sobrevive(r: comun.Reporte, cuerpo, historial) -> None:
    """Lo que separa una cota de un escalado: lo de arriba se vuelve a aplicar."""
    con = _ops() + [{"op": "restar", "mm": ESPESOR, "entidades": [
        {"tipo": "circulo", "centro": [300.0, 200.0], "radio": 20.0}]}]
    base = historial.regenerar(con)
    verticales = [n for n in base.nombrador.aristas(base.solido)
                  if n.count("lado[") == 2][:2]
    if not r.igual(len(verticales), 2, "el tablero tiene aristas verticales que redondear"):
        return
    con = con + [{"op": "redondear", "aristas": verticales, "r": 20.0}]
    antes = historial.regenerar(con)

    anchas = cuerpo.cambiar_operacion(con, 0, {"ancho": 900})
    despues = historial.regenerar(anchas)
    r.igual(len(despues.solido.faces()), len(antes.solido.faces()),
            "cambiar el ancho no se lleva el barreno ni los redondeos")

    # Y el barreno sigue siendo un círculo, no una elipse: se mide quitándolo.
    sin = historial.regenerar(cuerpo.quitar_operacion(anchas, 2))
    r.casi(_volumen(sin.solido) - _volumen(despues.solido),
           math.pi * 20 ** 2 * ESPESOR,
           "y el barreno sigue redondo: quita el mismo cilindro de antes", 1.0)

    # El centro del barreno es suyo y no se mueve con el estirado: está en
    # coordenadas de la pieza, no en fracciones de ella.
    r.igual(anchas[2]["entidades"][0]["centro"], [300.0, 200.0],
            "el centro del barreno se queda en su milímetro")


# --- 4. correr el contorno ---------------------------------------------------

def _correr_el_contorno(r: comun.Reporte, cuerpo, historial) -> None:
    ops = _ops()
    reg = historial.regenerar(cuerpo.cambiar_operacion(ops, 0, {"x": 100, "y": 50}))
    caja = reg.solido.bounding_box()
    r.punto([caja.min.X, caja.min.Y], [100.0, 50.0],
            "correr la esquina lleva la pieza a donde se dice", 1e-6)
    r.casi(_volumen(reg.solido), ANCHO * FONDO * ESPESOR,
           "y correrla no la deforma: mide lo mismo", 1.0)


# --- 5. cualquier contorno ---------------------------------------------------

def _cualquier_contorno(r: comun.Reporte, cuerpo, historial) -> None:
    ele = _ele()
    antes = _volumen(historial.regenerar(ele).solido)
    r.casi(antes, (600 * 400 - 300 * 200) * ESPESOR,
           "la L mide lo que dice la fórmula", 1.0)
    estirada = historial.regenerar(cuerpo.cambiar_operacion(ele, 0, {"ancho": 900}))
    r.casi(_volumen(estirada.solido), antes * 1.5,
           "estirar una L de 600 a 900 la estira entera, sin romperla", 1.0)


# --- 6. lo imposible ---------------------------------------------------------

def _lo_imposible_se_niega(r: comun.Reporte, cuerpo) -> None:
    ops = _ops()
    r.levanta(ValueError, cuerpo.cambiar_operacion,
              "una medida de cero se niega", ops, 0, {"ancho": 0})
    r.levanta(ValueError, cuerpo.cambiar_operacion,
              "una medida negativa también", ops, 0, {"fondo": -100})
    r.levanta(ValueError, cuerpo.cambiar_operacion,
              "y pedirle el ancho a una extrusión no tiene sentido", ops, 1, {"ancho": 900})
    r.levanta(ValueError, cuerpo.cambiar_operacion,
              "un campo inventado se sigue negando", ops, 0, {"largo_de_onda": 3})


# --- 7. y en la pantalla -----------------------------------------------------

def _en_la_pantalla(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte de pantalla se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate("typeof CotasPieza !== 'undefined'"),
                 "el letrero de cotas se carga con el programa")
        r.cierto(pagina.evaluate("Comandos.existe('COTAPIEZA')"),
                 "y se puede apagar con COTAPIEZA")

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

        medidas = pagina.evaluate("""(id) => {
            Ventanas.activar(0);
            Cuerpos.senalar({ id, cara: 'arriba' });
            const k = CotasPieza.caja(id);
            return { caja: Cuerpos.medidas(id).caja,
                     lo: k && k.lo.map((v) => Math.round(v * 1000) / 1000),
                     hi: k && k.hi.map((v) => Math.round(v * 1000) / 1000) };
        }""", id_)
        r.igual(medidas["caja"], [600.0, 400.0, 18.0],
                "la pieza en pantalla mide lo que se pidió")
        # El letrero saca la caja de la malla que ya está pintada, no de una
        # llamada nueva: si se equivocara, acotaría lo que no es.
        r.igual(medidas["lo"], [0.0, 0.0, 0.0],
                "el letrero encuentra dónde empieza la pieza")
        r.igual(medidas["hi"], [600.0, 400.0, 18.0],
                "y dónde acaba: acota la pieza, no una caja inventada")

        # Que pinte de verdad, sin tronar, y que el interruptor mande.
        pintado = pagina.evaluate("""() => {
            const antes = CotasPieza.encendido;
            pintarYa ? pintarYa() : pintar();
            const off = CotasPieza.alternar(false);
            pintarYa ? pintarYa() : pintar();
            const on = CotasPieza.alternar(true);
            return { antes, off, on };
        }""")
        r.cierto(pintado["antes"], "las cotas vienen encendidas de fábrica")
        r.cierto(not pintado["off"],
                 "COTAPIEZA las apaga")
        r.cierto(pintado["on"], "y las vuelve a encender")

        # El panel del historial ya deja teclear la medida: es lo que pidió Mike.
        tecleado = pagina.evaluate("""async (id) => {
            await Historial.traer();
            const campos = Historial.pasos[0].campos.map((c) => c.clave);
            const r = await fetch(`/api/cuerpo/${id}/paso/0`, {
                method: 'PUT', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ campos: { ancho: 900 } }),
            });
            const j = await r.json();
            await Cuerpos.refrescarUna(id);
            await Historial.traer();
            return { campos, ok: r.ok, caja: j.caja,
                     titulo: Historial.pasos[0].titulo,
                     enPantalla: Cuerpos.medidas(id).caja };
        }""", id_)
        r.igual(tecleado["campos"], ["ancho", "fondo", "x", "y"],
                "el panel ofrece las cotas del contorno")
        r.cierto(tecleado["ok"], "teclear 900 se acepta")
        r.igual(tecleado["caja"], [900.0, 400.0, 18.0],
                "y la pieza pasa a medir 900 sin trazar nada")
        r.igual(tecleado["titulo"], "Rectángulo 900.0 × 400.0",
                "el historial lo dice con la medida nueva")
        r.igual(tecleado["enPantalla"], [900.0, 400.0, 18.0],
                "y lo que está en pantalla es la pieza nueva, no la de antes")

        # Picar el número y teclear la medida: lo que Mike llamó «UI intuitiva
        # sin necesidad de comandos complejos».
        picar = pagina.evaluate("""(id) => {
            Cuerpos.senalar({ id, cara: 'arriba' });
            const ts = CotasPieza.tramos(id);
            const anchura = ts.find((t) => t.que === 'ancho');
            const b = CotasPieza.blanco(anchura);
            const dentro = CotasPieza.cotaEn(b.x + b.w / 2, b.y + b.h / 2);
            const fuera = CotasPieza.cotaEn(b.x + 400, b.y + 400);
            CotasPieza.alternar(false);
            const apagada = CotasPieza.cotaEn(b.x + b.w / 2, b.y + b.h / 2);
            CotasPieza.alternar(true);
            return { cuantas: ts.map((t) => t.que),
                     medidas: ts.map((t) => Math.round(t.medida * 100) / 100),
                     dentro: dentro && dentro.que, fuera: !!fuera, apagada: !!apagada };
        }""", id_)
        r.igual(picar["cuantas"], ["ancho", "fondo", "espesor"],
                "la pieza enseña sus tres medidas y ninguna más")
        r.igual(picar["medidas"], [900.0, 400.0, 18.0],
                "y son las de la pieza que hay ahora, no las de antes")
        r.igual(picar["dentro"], "ancho", "picando el número del ancho, se agarra el ancho")
        r.cierto(not picar["fuera"], "picando lejos no se agarra ninguna cota")
        r.cierto(not picar["apagada"],
                 "con COTAPIEZA apagado el clic pasa de largo, a los tiradores")

        # Qué número del historial manda cada medida. Se busca por lo que el
        # paso ofrece, no por su número: si eso se rompiera, picar el espesor
        # cambiaría el ancho.
        manda = pagina.evaluate("""async (id) => {
            const pasos = (await fetch(`/api/cuerpo/${id}/historial`)
                            .then((x) => x.json())).pasos;
            return { ancho: CotasPieza.donde(pasos, 'ancho'),
                     fondo: CotasPieza.donde(pasos, 'fondo'),
                     espesor: CotasPieza.donde(pasos, 'espesor') };
        }""", id_)
        r.igual(manda["ancho"], {"i": 0, "clave": "ancho"}, "el ancho lo manda el contorno")
        r.igual(manda["fondo"], {"i": 0, "clave": "fondo"}, "el fondo también")
        r.igual(manda["espesor"], {"i": 1, "clave": "mm"},
                "y el espesor lo manda la extrusión, no el contorno")

        # Y el camino completo hasta la pieza, que es lo que hace el clic.
        grueso = pagina.evaluate("""async (id) => {
            const r = await fetch(`/api/cuerpo/${id}/paso/1`, {
                method: 'PUT', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ campos: { mm: 30 } }),
            });
            const j = await r.json();
            await Cuerpos.refrescarUna(id);
            return { ok: r.ok, caja: j.caja,
                     cotas: CotasPieza.tramos(id).map((t) => Math.round(t.medida * 100) / 100) };
        }""", id_)
        r.cierto(grueso["ok"], "cambiar el espesor por ese camino se acepta")
        r.igual(grueso["caja"], [900.0, 400.0, 30.0], "la pieza pasa a 30 de espesor")
        r.igual(grueso["cotas"], [900.0, 400.0, 30.0],
                "y el letrero de la pantalla ya dice 30: no se quedó con el 18")

        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
