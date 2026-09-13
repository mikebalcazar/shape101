"""P4 · Vista 3D y empujar cara.

Una página Three.js (poc/vista/) recibe del motor la malla teselada **por
cara** y las aristas. Se mide con un Chromium de verdad (Playwright):

1. Picking: raycast a la cara bajo el ratón; se comprueba que devuelve el
   nombre correcto y que se resalta.
2. Clic + arrastre en la normal → empujar_cara al motor → malla nueva en
   pantalla. Ida y vuelta medida desde la página. Umbral: < 100 ms con un
   modelo de 50 caras (con caché por operación, como haría la app; también
   se mide sin caché, regenerando todo).
3. 500 caras (un mueble de 84 piezas sueltas): fps al orbitar. Umbral: > 30.

Ojo con el 3: el Chromium de la sesión pinta por software (sin GPU). Los fps
que salgan aquí son el suelo, no lo que verá un taller con tarjeta gráfica;
se anota así.
"""
from __future__ import annotations

from build123d import Box, Compound, Location

from poc import comun, motor_http, p3_historial
from app.motor import historial

DESCRIPCION = "Three.js: elegir cara, arrastrar = empujar, y 500 caras orbitando"
VIEWPORT = {"width": 1200, "height": 800}


def _doc_50_caras():
    """Tablero con 11 cajeados rectangulares pasantes: 6 + 11×4 = 50 caras."""
    ops = [{"op": "boceto", "entidades": p3_historial.rect(900, 600)}, {"op": "extruir", "mm": 18}]
    for k in range(11):
        x, y = 60 + (k % 6) * 140, 80 + (k // 6) * 260
        ops.append({"op": "restar", "mm": 18, "entidades": [{"tipo": "polilinea", "cerrada": True,
                    "puntos": [[x, y, 0], [x + 80, y, 0], [x + 80, y + 120, 0], [x, y + 120, 0]]}]})
    return ops


def _mueble_500_caras():
    """84 tableros sueltos (18 mm) acomodados como un mueble: 504 caras."""
    piezas, nombres = [], {}
    k = 0
    for i in range(7):
        for j in range(12):
            b = Box(400, 18, 300).moved(Location((i * 420, j * 40, 0)))
            piezas.append(b)
            for c, f in enumerate(b.faces()):
                nombres[f"pieza[{k}]/cara[{c}]"] = f
            k += 1
    return Compound(piezas), nombres


def _abrir(pw, url):
    nav = pw.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pag = nav.new_page(viewport=VIEWPORT)
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(url)
    pag.wait_for_function("window.__lista === true", timeout=30000)
    return nav, pag, errores


def correr(r: comun.Reporte):
    from playwright.sync_api import sync_playwright
    motor = motor_http.Motor()
    motor.cargar(p3_historial.documento())
    with motor_http.Servidor(motor) as srv, sync_playwright() as pw:
        nav, pag, errores = _abrir(pw, srv.url)
        try:
            caras = pag.evaluate("window.shape101.caras()")
            r.igual(len(caras), len(motor.reg.solido.faces()), "la página recibió todas las caras del tablero, cada una con su nombre")
            r.cierto("arriba" in caras and "lado[1]" in caras, "los nombres del motor llegan a la página")

            # 1 · picking
            xy = pag.evaluate("window.shape101.puntoEnPantalla('arriba')")
            hit = pag.evaluate(f"window.shape101.elegir({xy[0]}, {xy[1]})")
            r.igual(hit and hit["nombre"], "arriba", "un raycast sobre la cara de arriba devuelve «arriba»")
            r.igual(pag.evaluate("window.shape101.marcada()"), "arriba", "la cara elegida queda resaltada")
            xy2 = pag.evaluate("window.shape101.puntoEnPantalla('lado[1]')")
            hit2 = pag.evaluate(f"window.shape101.elegir({xy2[0]}, {xy2[1]})")
            r.igual(hit2 and hit2["nombre"], "lado[1]", "un raycast sobre el lado derecho devuelve «lado[1]»")
            r.cierto(pag.evaluate("window.shape101.elegir(2, 2)") is None, "un raycast al vacío no elige nada")

            # 2a · empujar por API de la página (ida y vuelta medida en la página)
            z0 = motor.reg.solido.bounding_box().size.Z
            res = pag.evaluate("window.shape101.empujar('arriba', 10)")
            r.casi(motor.reg.solido.bounding_box().size.Z, z0 + 10, "empujar «arriba» 10 deja el sólido 10 mm más alto", 1e-6)
            n_solido = len(motor.reg.solido.faces())
            r.igual(res["n_caras"], n_solido, "tras empujar, todas las caras del sólido tienen nombre")
            continuaciones = [n for n in motor.reg.nombrador.caras if "~" in n]
            r.numero("P4 caras que el kernel no fundió tras empujar «arriba» (misma superficie que un redondeo)", len(continuaciones), "",
                     umbral="", cumple=None)
            r.numero("P4 ida y vuelta empujar cara, 11 caras (con caché por operación)", round(res["ms_total"]), "ms")

            # 2b · con clic y arrastre de verdad
            n_ops = len(motor.ops)
            xy = pag.evaluate("window.shape101.puntoEnPantalla('lado[1]')")
            pag.mouse.move(xy[0], xy[1]); pag.mouse.down(); pag.mouse.move(xy[0] + 40, xy[1], steps=5); pag.mouse.up()
            pag.wait_for_function("window.__ultimo_empuje !== undefined", timeout=15000)
            ue = pag.evaluate("window.__ultimo_empuje")
            r.igual(len(motor.ops), n_ops + 1, "el arrastre mandó una operación empujar_cara al motor")
            r.igual(motor.ops[-1]["cara"], "lado[1]", "la operación lleva el nombre de la cara arrastrada")
            r.cierto(motor.ops[-1]["mm"] != 0, "la operación lleva un desplazamiento distinto de cero", f"mm={motor.ops[-1]['mm']}")
            r.cierto(motor.reg.solido.is_valid, "el sólido sigue siendo válido tras el arrastre")
            r.numero("P4 arrastre → motor → malla nueva, 11 caras", round(ue["ms_total"]), "ms")

            # 2c · 50 caras: con caché (app) y sin caché (regenerar todo)
            motor.cargar(_doc_50_caras())
            pag.evaluate("window.shape101.cargar()")
            n50 = len(motor.reg.solido.faces())
            r.igual(pag.evaluate("window.shape101.caras().length"), n50, "la página recibe todas las caras del modelo de 50")
            r.igual(n50, 50, "el modelo de prueba tiene 50 caras (6 + 11 cajeados × 4)")
            motor.incremental = True
            con = pag.evaluate("window.shape101.empujar('arriba', 2)")
            # empujar la pared de UN cajeado: cambia esa pared y sus vecinas, no las 50
            pared = pag.evaluate("window.shape101.empujar('restar[2]/lado[0]', 2)")
            r.numero("P4 ida y vuelta empujar la pared de un cajeado, 50 caras, con caché", round(pared["ms_total"]), "ms",
                     umbral="< 100 ms", cumple=pared["ms_total"] < 100)
            r.numero("P4   de eso, motor (regenerar + teselar)", f"{pared['ms_regenerar']} + {pared['ms_teselar']}", "ms")
            r.numero("P4   caras reteseladas de 50 al empujar una pared", pared.get("reteseladas", "?"), "")
            motor.incremental = False
            sin = pag.evaluate("window.shape101.empujar('arriba', 2)")
            motor.incremental = True
            r.numero("P4 ida y vuelta empujar «arriba» (cambian las 50 caras), 50 caras, con caché por operación", round(con["ms_total"]), "ms",
                     umbral="< 100 ms", cumple=con["ms_total"] < 100)
            r.numero("P4   de eso, motor (regenerar + teselar)", f"{con['ms_regenerar']} + {con['ms_teselar']}", "ms")
            r.numero("P4   caras reteseladas de 50 al empujar «arriba» (crecen todas las paredes)", con.get("reteseladas", "?"), "")
            r.numero("P4 ida y vuelta empujar cara, 50 caras, regenerando las 13 operaciones", round(sin["ms_total"]), "ms")

            # 3 · fps
            fps11 = pag.evaluate("window.shape101.fps(2000)")
            forma, nombres_c = _mueble_500_caras()
            motor.cargar_forma(forma, nombres_c)
            pag.evaluate("window.shape101.cargar()")
            n = pag.evaluate("window.shape101.caras().length")
            r.igual(n, 504, "el mueble de prueba tiene 504 caras")
            fps500 = pag.evaluate("window.shape101.fps(3000)")
            pag.evaluate("window.shape101.vaciar()")
            fps0 = pag.evaluate("window.shape101.fps(2000)")
            r.numero("P4 fps con la escena VACÍA (el suelo del Chromium por software, sin GPU)", round(fps0), "fps")
            r.numero("P4 fps orbitando 50 caras (Chromium por software, sin GPU)", round(fps11), "fps")
            r.numero("P4 fps orbitando 504 caras (Chromium por software, sin GPU)", round(fps500), "fps",
                     umbral="> 30 fps: NO MEDIBLE aquí, el suelo sin GPU es menor que el umbral", cumple=None)
            r.igual(errores, [], "la página no tiró ningún error de JavaScript")
        finally:
            nav.close()
