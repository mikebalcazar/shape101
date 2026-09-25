"""ROTAR con puntos de referencia  ·  0.21.8

Mike, 25-sep: *«Hay que poner los puntos de referencia para la rotación y que
a partir de esos puntos se rote la pieza a los grados que se desee»*.

Como ESCALAR y como AutoCAD: centro → punto de referencia sobre la pieza →
punto nuevo (adónde va esa referencia). El giro es el ángulo entre los dos.
Tecleando grados en el segundo paso se gira a secas (como antes); tecleando
grados en el tercero, la referencia queda a ese ángulo.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "ROTAR: centro, punto de referencia y punto nuevo (o los grados a los que debe quedar)"


def _linea(pagina, id_):
    return pagina.evaluate("async (i) => (await fetch('/api/entidades/varias', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: [i]})}).then((x) => x.json())).entidades[0]", id_)


def _teclear(pagina, *textos):
    for t in textos:
        pagina.keyboard.type(t, delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(350)


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.evaluate("""async () => {
          estado.prefs.rejilla = false;
          const a = await crearEntidad({ tipo: 'linea', p1: [100, 100], p2: [400, 100], plano: 'XY' }, 'l');
          window._id = a; Seleccion.alternar(a, false); Ventanas.activar(0); pintar();
        }""")
        pagina.wait_for_timeout(200)

        # 1 · Referencia y punto nuevo: la línea que va de (100,100) a (400,100),
        # con centro en su extremo, referencia en el otro extremo y punto nuevo
        # recto hacia arriba, queda vertical.
        pagina.keyboard.type("ROTAR", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        _teclear(pagina, "100,100", "400,100", "100,400")
        pagina.wait_for_timeout(500)
        e = _linea(pagina, pagina.evaluate("() => window._id"))
        r.casi(e["p2"][0], 100, "la referencia (400,100) fue al punto nuevo: x = 100", 1e-6)
        r.casi(e["p2"][1], 400, "…y = 400: giró 90°", 1e-6)
        r.casi(e["p1"][0], 100, "el centro no se movió", 1e-6)

        # 2 · Grados a secas en el segundo paso: −90 la regresa.
        pagina.evaluate("() => { Seleccion.alternar(window._id, false); }")
        pagina.keyboard.type("ROTAR", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        _teclear(pagina, "100,100", "-90")
        pagina.wait_for_timeout(500)
        e = _linea(pagina, pagina.evaluate("() => window._id"))
        r.casi(e["p2"][0], 400, "tecleando −90 en el segundo paso gira a secas: vuelve a (400,100)", 1e-6)
        r.casi(e["p2"][1], 100, "…y = 100", 1e-6)

        # 3 · Referencia y grados tecleados en el tercer paso: la referencia
        # queda a ese ángulo (AutoCAD). Con la línea a 0°, «a 30» la deja a 30°.
        pagina.evaluate("() => { Seleccion.alternar(window._id, false); }")
        pagina.keyboard.type("ROTAR", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        _teclear(pagina, "100,100", "400,100", "30")
        pagina.wait_for_timeout(500)
        e = _linea(pagina, pagina.evaluate("() => window._id"))
        import math
        r.casi(e["p2"][0], 100 + 300 * math.cos(math.radians(30)), "tecleando 30 en el tercer paso la referencia queda a 30°: x", 1e-4)
        r.casi(e["p2"][1], 100 + 300 * math.sin(math.radians(30)), "…y", 1e-4)

        # 4 · El hule del tercer paso enseña la referencia, la liga al cursor y el fantasma.
        pagina.evaluate("() => { Seleccion.alternar(window._id, false); }")
        pagina.keyboard.type("ROTAR", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        _teclear(pagina, "100,100", "400,100")
        caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")
        q = pagina.evaluate("() => { const g = estado.vista; estado.vista = Ventanas.la(0); const q = aPX(100, 400, 0); estado.vista = g; return q; }")
        pagina.mouse.move(caja["x"] + q[0], caja["y"] + q[1], steps=5); pagina.wait_for_timeout(300)
        h = pagina.evaluate("() => { const h = estado.hule; return h && { partes: h.partes && h.partes.length, fantasma: h.fantasma && h.fantasma.length }; }")
        r.igual(h, {"partes": 2, "fantasma": 1}, "el hule enseña las dos ligas (referencia y cursor) y el fantasma de la línea")
        pagina.keyboard.press("Escape"); pagina.wait_for_timeout(200)

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
