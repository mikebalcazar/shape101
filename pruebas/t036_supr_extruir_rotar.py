"""Tres cosas del backlog de Mike, 24-sep  ·  0.21.3

1. *«No puedo borrar sólidos. Selecciono pero no se pueden borrar con SUPR»*.
   Señalar una cara no mete la pieza en la selección, y Supr sólo miraba la
   selección. Medido: cara señalada `e2 · arriba`, selección vacía, Supr, y la
   pieza seguía ahí.

2. *«Quiero rotarlo 90° desde la vista lateral y no puedo»*: ROTAR giraba
   siempre dentro del plano de la entidad. Ahora, desde otra ventana, gira
   alrededor del eje de esa ventana y el dibujo cambia de plano (de 90 en 90).

3. *«Cuando ingreso el comando de extruir, lo siguiente luego luego debe ser
   ingresar el valor, pero tengo que hacer un enter más»*. Medido: EXTRUIR,
   `50`, Enter abría la cajita con `18` y **tiraba el 50**; el segundo Enter
   levantaba 18, no 50.

Todo con el teclado y el ratón de verdad, como lo hace él.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "Supr borra la pieza señalada · EXTRUIR + valor + Enter · ROTAR entre planos"


def _cuerpos(pagina):
    return pagina.evaluate("async () => (await fetch('/api/cuerpo/lista').then((x) => x.json())).ids")


def _cara_bien_adentro(pagina):
    return pagina.evaluate("""() => {
      const v = Ventanas.la(1); const g = estado.vista; estado.vista = v;
      const caja = lienzo.getBoundingClientRect();
      const mismo = (x, y, cara) => { const c = Cuerpos.caraEn(x, y); return c && c.cara === cara; };
      let hit = null;
      for (let y = v.oy + 40; y < v.oy + v.h - 10 && !hit; y += 4)
        for (let x = v.ox + 10; x < v.ox + v.w - 10 && !hit; x += 4) {
          const cc = Cuerpos.caraEn(x, y); if (!cc) continue;
          if (![[4,0],[-4,0],[0,4],[0,-4]].every(([a, b]) => mismo(x + a, y + b, cc.cara))) continue;
          const el = document.elementFromPoint(Math.round(caja.left + x), Math.round(caja.top + y));
          if (el && el.id === 'lienzo') hit = { px: Math.round(caja.left + x), py: Math.round(caja.top + y) };
        }
      estado.vista = g; return hit; }""")


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")
        persp = pagina.evaluate("() => { const v = Ventanas.la(1); return {x: v.ox + v.w / 2, y: v.oy + v.h / 2 + 30}; }")

        # --- 3 · EXTRUIR, el valor, Enter ------------------------------------
        pagina.evaluate("""async () => {
          const id = await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY',
            puntos: [[0,0,0],[600,0,0],[600,400,0],[0,400,0]] }, 'base');
          Seleccion.alternar(id, false);
        }""")
        pagina.mouse.move(caja["x"] + persp["x"], caja["y"] + persp["y"], steps=4)
        pagina.keyboard.type("EXTRUIR", delay=15); pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(300)
        pagina.keyboard.type("50", delay=30)
        pagina.keyboard.press("Enter"); pagina.wait_for_timeout(1500)
        ids = _cuerpos(pagina)
        r.igual(len(ids), 1, "EXTRUIR, «50», Enter: la pieza se levanta a la primera")
        if ids:
            m = pagina.evaluate(f"async () => await fetch('/api/cuerpo/{ids[0]}/malla').then((x) => x.json())")
            r.casi(m["caja"][2], 50, "y mide 50 de alto: se tomó lo tecleado, no el valor por omisión", 0.01)
        r.cierto(not pagina.evaluate("() => document.querySelector('#dinamica').classList.contains('si')"),
                 "sin cajita abierta pidiendo el valor otra vez")

        # --- 1 · señalar una cara y Supr --------------------------------------
        pagina.evaluate("async () => { estado.sel.clear(); encuadrar(); await new Promise((k) => setTimeout(k, 400)); }")
        p = _cara_bien_adentro(pagina)
        if r.cierto(p is not None, "hay una cara que picar en la Perspectiva"):
            pagina.mouse.click(p["px"], p["py"]); pagina.wait_for_timeout(400)
            s = pagina.evaluate("() => TresD.senalada()")
            r.cierto(bool(s), "el clic señala la pieza", str(s))
            r.igual(pagina.evaluate("() => estado.sel.size"), 0, "(y la selección sigue vacía: por eso Supr no la veía)")
            pagina.keyboard.press("Delete"); pagina.wait_for_timeout(1200)
            r.igual(_cuerpos(pagina), [], "Supr borra la pieza señalada")
            r.igual(pagina.evaluate("() => TresD.senalada()"), None, "y ya no queda nada señalado")

        # --- 2 · ROTAR entre planos, desde la Lateral --------------------------
        pagina.evaluate("""async () => {
          const a = await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY',
            puntos: [[100,0,0],[700,0,0],[700,400,0],[100,400,0]] }, 'r');
          const b = await crearEntidad({ tipo: 'arco', centro: [200, 100], radio: 40, ang_ini: 0, ang_fin: 90, plano: 'XY' }, 'a');
          window._ids = [a, b];
          Seleccion.alternar(a, false); Seleccion.alternar(b, true);
          Ventanas.activar(3); pintar();
        }""")
        pagina.wait_for_timeout(200)
        r.igual(pagina.evaluate("() => Ventanas.laActiva().plano"), "YZ", "se gira desde la Lateral (YZ)")
        pagina.keyboard.type("ROTAR", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        pagina.keyboard.type("0,0", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(300)
        # el ratón recto hacia arriba del centro de giro: 90°
        c0 = pagina.evaluate("() => { const g = estado.vista; estado.vista = Ventanas.la(3); const q = aPX(0, 0, 0); estado.vista = g; return {x: q[0], y: q[1]}; }")
        pagina.mouse.move(caja["x"] + c0["x"], caja["y"] + c0["y"] - 80, steps=4); pagina.wait_for_timeout(250)
        f = pagina.evaluate("() => { const h = estado.hule; return h && h.fantasma ? [...new Set(h.fantasma.map((t) => t.plano))] : null; }")
        r.igual(f, ["XZ"], "el fantasma enseña el dibujo ya parado en la Frontal (XZ)")
        pagina.keyboard.type("90", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(800)
        ents = pagina.evaluate("async () => (await fetch('/api/entidades/varias', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: window._ids})}).then((x) => x.json())).entidades")
        r.igual([e["plano"] for e in ents], ["XZ", "XZ"], "las dos entidades pasaron a XZ")
        pol = next((e for e in ents if e["tipo"] == "polilinea"), None)
        r.cierto(pol and [q[:2] for q in pol["puntos"]] == [[100, 0], [700, 0], [700, 400], [100, 400]],
                 "girar 90° alrededor de X por el origen deja las mismas (u, v) en la pared",
                 str(pol and pol["puntos"]))
        arco = next((e for e in ents if e["tipo"] == "arco"), None)
        r.cierto(arco and (arco["ang_ini"], arco["ang_fin"]) == (0, 90),
                 "y el arco conserva su barrido (no hubo espejo)", str(arco))

        # el giro de siempre, dentro del plano, sigue igual: la entidad está en
        # XZ y se gira desde la Frontal, que es XZ
        pagina.evaluate("() => { Seleccion.alternar(window._ids[0], false); Ventanas.activar(2); pintar(); }")
        pagina.wait_for_timeout(200)
        r.igual(pagina.evaluate("() => Ventanas.laActiva().plano"), "XZ", "ahora se gira desde la Frontal (XZ), el plano de la entidad")
        pagina.keyboard.type("ROTAR", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        r.cierto("90 en 90" not in (pagina.evaluate("() => estado.captura && estado.captura.mensaje") or ""),
                 "y ROTAR pide el ángulo de siempre, sin hablar de planos")
        pagina.keyboard.type("0,0", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(300)
        pagina.keyboard.type("90", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(800)
        e = pagina.evaluate("async () => (await fetch('/api/entidades/varias', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: [window._ids[0]]})}).then((x) => x.json())).entidades[0]")
        r.igual(e["plano"], "XZ", "un giro desde la ventana de su plano no cambia el plano")
        r.cierto([[round(k) for k in q[:2]] for q in e["puntos"]] == [[0, 100], [0, 700], [-400, 700], [-400, 100]],
                 "y gira 90° dentro de su plano, como siempre", str(e["puntos"]))

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
