"""El osnap desde la Frontal y la Lateral  ·  0.21.7

Mike, 25-sep: *«El Osnap no funciona para dibujar en las vistas frontal y
lateral. Cuando estoy en esa ventana, debería poder dibujar sobre ese plano.
Como 2D.»*

Medido en main, con una pared en XZ y un suelo en XY, desde la Frontal:
la esquina de la pared daba referencia (mismo plano); la esquina del suelo
visto de canto **no daba nada**; y donde el suelo no está —en el punto que
sale de leer sus (u, v) como si fueran (x, z)— daba «extremo». Es el mismo
origen que la selección de la 0.21.5: el índice guarda cada primitiva en las
(u, v) de su plano.

Ahora el osnap sólo lee tal cual lo del plano de la ventana, y lo de otro
plano lo trae ya llevado a ese plano por el mundo (`Indice.enPlano`). Con eso
se dibuja en la Frontal pegado a lo que se ve ahí, y lo dibujado nace en XZ.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "osnap desde la Frontal y la Lateral: pega a lo de canto y no inventa referencias"


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        pagina.evaluate("""async () => {
          await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XZ', puntos: [[100,0,0],[700,0,0],[700,400,0],[100,400,0]] }, 'pared');
          await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY', puntos: [[1000,600,0],[1600,600,0],[1600,900,0],[1000,900,0]] }, 'suelo');
          estado.prefs.rejilla = false; encuadrar();
          await new Promise((k) => setTimeout(k, 400));
          Ventanas.activar(2); pintar();
        }""")
        caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")

        def sonda(ventana, mundo):
            q = pagina.evaluate("([i, m]) => { const g = estado.vista; estado.vista = Ventanas.la(i); const q = aPX(m[0], m[1], m[2]); estado.vista = g; return q; }", [ventana, mundo])
            # Primero lejos de todo, para que la referencia anterior se suelte;
            # luego al punto. Sin esto, a veces se leía la referencia vieja.
            pagina.mouse.move(caja["x"] + q[0] + 60, caja["y"] + q[1] + 60, steps=3)
            pagina.wait_for_timeout(150)
            pagina.mouse.move(caja["x"] + q[0] + 5, caja["y"] + q[1] + 4, steps=4)
            pagina.wait_for_timeout(300)
            return pagina.evaluate("() => estado.ref && { modo: estado.ref.modo, p: estado.ref.p.map((k) => +k.toFixed(1)), id: estado.ref.id }")

        pagina.keyboard.type("LINEA", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(300)
        s = sonda(2, [700, 0, 400])
        r.cierto(s and s["modo"] == "extremo" and s["id"] == "e1", "Frontal: la esquina de la pared (mismo plano) da «extremo», como siempre", str(s))
        s = sonda(2, [1600, 0, 0])
        r.cierto(s and s["modo"] == "extremo" and s["id"] == "e2" and s["p"] == [1600, 0],
                 "Frontal: la esquina del suelo visto de canto da «extremo» en (1600, 0)", str(s))
        s = sonda(2, [1000, 0, 600])
        r.igual(s, None, "Frontal: donde el suelo NO está (sus (u, v) leídas como (x, z)) no hay referencia")
        s = sonda(3, [0, 900, 0])
        r.cierto(s and s["modo"] == "extremo" and s["id"] == "e2", "Lateral: la esquina del suelo de canto da «extremo»", str(s))
        s = sonda(3, [0, 0, 400])
        r.cierto(s and s["modo"] == "extremo" and s["id"] == "e1", "Lateral: la esquina de la pared de canto da «extremo»", str(s))

        # Y se dibuja ahí, pegado a esa esquina, sobre el plano de la ventana.
        pagina.evaluate("() => { Ventanas.activar(2); pintar(); }")
        sonda(2, [1600, 0, 0])
        pagina.mouse.click(caja["x"] + pagina.evaluate("() => estado.cursor.px"), caja["y"] + pagina.evaluate("() => estado.cursor.py"))
        pagina.wait_for_timeout(200)
        pagina.keyboard.type("@0,300", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        pagina.keyboard.press("Escape"); pagina.wait_for_timeout(200)
        ent = pagina.evaluate("async () => { const ids = [...(await fetch('/api/entidades/varias', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: ['e3']})}).then((x) => x.json())).entidades]; return ids[0]; }")
        r.cierto(ent and ent["tipo"] == "linea", "la línea dibujada en la Frontal existe", str(ent))
        r.igual(ent and ent.get("plano"), "XZ", "y nace en XZ: se dibuja sobre el plano de la ventana, como 2D")
        r.cierto(ent and abs(ent["p1"][0] - 1600) < 1e-6 and abs(ent["p1"][1]) < 1e-6,
                 "arrancando exactamente en la esquina del suelo de canto (1600, 0)", str(ent and ent["p1"]))

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
