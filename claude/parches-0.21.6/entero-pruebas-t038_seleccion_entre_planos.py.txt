"""Seleccionar desde cualquier ventana, y el recuadro de selección en pantalla  ·  0.21.5 / 0.21.6

Mike, 24-sep: *«Cuando quiero seleccionar los objetos 2d desde la vista
lateral o frontal no me deja»* y, por eso mismo, *«sigo sin poder rotar los
objetos desde la vista lateral»*. Y: *«La ventana de selección se dibuja sobre
el plano en la vista de perspectiva. Esa SÍ debe dibujarse sobre la pantalla
porque es el área de selección, no un dibujo»*.

Lo que era: el índice guarda cada primitiva en las (u, v) de **su** plano, y
el cursor llega en las (u, v) del plano de la ventana. Un dibujo del suelo
visto desde la Lateral está de canto y sus (u, v) no tienen nada que ver con
las de la ventana: no se podía picar ni encajonar. Medido en main: clic sobre
la raya de canto en la Lateral, selección vacía.

Ahora lo de otro plano se pica llevándolo al espacio de la ventana por el
mundo, y la caja de selección se arma y se decide **en píxeles**, en todas
las ventanas: en las ortogonales es lo mismo que en mm, y en la Perspectiva es
lo único que tiene sentido. El recuadro es de pantalla.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "seleccionar de canto desde la Lateral, encajonar en pantalla, y rotar lo seleccionado a la pared"


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        pagina.evaluate("""async () => {
          window._ids = [];
          window._ids.push(await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY', puntos: [[100,600,0],[700,600,0],[700,900,0],[100,900,0]] }, 'suelo'));
          window._ids.push(await crearEntidad({ tipo: 'circulo', centro: [400, 750], radio: 60, plano: 'XY' }, 'suelo2'));
          window._ids.push(await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XZ', puntos: [[100,0,0],[700,0,0],[700,400,0],[100,400,0]] }, 'pared'));
          estado.prefs.rejilla = false; encuadrar();
          await new Promise((k) => setTimeout(k, 400));
        }""")
        caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")

        def px(ventana, m):
            return pagina.evaluate("([i, m]) => { const v = Ventanas.la(i); const g = estado.vista; estado.vista = v; const q = aPX(m[0], m[1], m[2]); estado.vista = g; return q; }", [ventana, m])

        def sel():
            return sorted(pagina.evaluate("() => [...estado.sel]"))

        def arrastre(a, b):
            pagina.evaluate("() => Seleccion.limpiar()")
            pagina.mouse.move(caja["x"] + a[0], caja["y"] + a[1], steps=3); pagina.wait_for_timeout(100)
            pagina.mouse.down()
            pagina.mouse.move(caja["x"] + (a[0] + b[0]) / 2, caja["y"] + (a[1] + b[1]) / 2, steps=3); pagina.wait_for_timeout(100)
            hule = pagina.evaluate("() => estado.hule && estado.hule.tipo")
            pagina.mouse.move(caja["x"] + b[0], caja["y"] + b[1], steps=3); pagina.wait_for_timeout(100)
            pagina.mouse.up(); pagina.wait_for_timeout(300)
            return hule

        # --- 1 · un clic de canto desde la Lateral ------------------------------
        # Sólo la pared está en XZ; de canto desde la Lateral es la raya x=0…
        # no: la pared vista desde la Lateral (YZ) es la raya y=0, z=0..400.
        pagina.evaluate("() => { Seleccion.limpiar(); Ventanas.activar(3); pintar(); }")
        q = px(3, [0, 0, 200])
        pagina.mouse.move(caja["x"] + q[0], caja["y"] + q[1], steps=3); pagina.wait_for_timeout(120)
        pagina.mouse.click(caja["x"] + q[0], caja["y"] + q[1]); pagina.wait_for_timeout(300)
        r.igual(sel(), ["e3"], "un clic sobre la pared vista de canto desde la Lateral la selecciona")

        # --- 2 · caja desde la Lateral: los dos del suelo, de canto ---------------
        a = px(3, [0, 550, 30]); b = px(3, [0, 950, -30])
        hule = arrastre(b, a)
        r.igual(hule, "cajaPantalla", "el recuadro de selección es de pantalla")
        r.igual(sel(), ["e1", "e2"], "una caja por cruce sobre la raya de canto atrapa el rectángulo y el círculo del suelo")
        arrastre(a, b)
        r.igual(sel(), ["e1", "e2"], "y una ventana alrededor de la raya, también")

        # --- 3 · el recuadro en la Perspectiva es de pantalla y decide en pantalla
        esq = [px(1, [x, 0, z]) for x in (100, 700) for z in (0, 400)]
        x0 = min(e[0] for e in esq) - 12; x1 = max(e[0] for e in esq) + 12
        y0 = min(e[1] for e in esq) - 12; y1 = max(e[1] for e in esq) + 12
        hule = arrastre([x0, y0], [x1, y1])
        r.igual(hule, "cajaPantalla", "en la Perspectiva el recuadro también es de pantalla")
        r.igual(sel(), ["e3"], "y una ventana de pantalla alrededor de la pared la selecciona (y sólo a ella)")
        h = pagina.evaluate("() => { Seleccion.limpiar(); return null; }")

        # --- 4 · el flujo de Mike: seleccionar desde la Lateral y ROTAR 90° -----
        pagina.evaluate("() => { Ventanas.activar(3); pintar(); }")
        arrastre(b, a)
        r.igual(sel(), ["e1", "e2"], "seleccionado el suelo desde la Lateral…")
        # El centro de giro **fuera del origen**, como lo pica uno con el ratón:
        # (y = 300, z = 50) en la Lateral. Girado 90° alrededor de ese eje, el
        # dibujo caería en una pared a y = 350, que no existe: se queda en XZ
        # por el origen, con el giro hecho, y se avisa. Mike (0.21.5): «Ese
        # giro no deja el dibujo en ningún plano».
        pagina.keyboard.type("ROTAR", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        pagina.keyboard.type("300,50", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(300)
        pagina.keyboard.type("90", delay=15); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(900)
        ents = pagina.evaluate("async () => (await fetch('/api/entidades/varias', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: [window._ids[0], window._ids[1]]})}).then((x) => x.json())).entidades")
        r.igual([e["plano"] for e in ents], ["XZ", "XZ"], "…ROTAR 90° con el centro fuera del origen lo para en la pared: las dos entidades quedan en XZ")
        # (u, v, 0) − (0, 300, 50) girado 90° sobre X: (u, 50, v − 300) + centro = (u, 350, v − 250)
        r.cierto(any(e["tipo"] == "circulo" and abs(e["centro"][0] - 400) < 1e-6 and abs(e["centro"][1] - 500) < 1e-6 for e in ents),
                 "el círculo giró alrededor de ese eje: su centro pasó de (400, 750) a (400, 500)", str([e.get("centro") for e in ents]))
        ecos = pagina.evaluate("() => [...document.querySelectorAll('#cmd-historial .eco')].slice(-2).map((e) => e.textContent)")
        r.cierto(any("por el origen" in e and "350" in e for e in ecos),
                 "y avisa que la pared a 350 mm no existe y quedó en el plano por el origen", str(ecos))

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
