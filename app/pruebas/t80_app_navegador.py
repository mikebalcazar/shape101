"""t80 · La pantalla de la versión inicial, manejada con un navegador de verdad.

La escribe Jr. (no es una prueba de aceptación del chat de shape101: por eso
va con número aparte). Arranca el motor con su pantalla, y con Playwright hace
lo que haría Mike al instalarla: pieza nueva, tablero, barreno, corte,
redondear esquinas, empujar una cara con clic y con arrastre, editar y borrar
del historial, guardar, reabrir y exportar STEP. Cada paso se comprueba
contra el motor (volumen de fórmula, caras, historial), no contra la pantalla
sola.
"""
from __future__ import annotations

import json
import math

from app.motor import servidor
from poc import comun

DESCRIPCION = "la pantalla 0.1.0 con Playwright: pieza, tablero, barreno, redondeo, empujar, guardar"
W, H, T, D, R = 900.0, 600.0, 18.0, 160.0, 20.0


def _abrir(pw, url):
    nav = pw.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    pag = nav.new_page(viewport={"width": 1280, "height": 820})
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(url)
    pag.wait_for_function("window.__lista === true", timeout=30000)
    pag.evaluate("document.querySelectorAll('details').forEach((d) => { d.open = true; })")   # los formularios plegados, abiertos
    return nav, pag, errores


def _espera_estado(pag, texto, r=None):
    """Espera a que la barra de estado diga `texto`. Si la pantalla enseña un
    error antes, la prueba se corta con ese mensaje (no con un timeout mudo)."""
    import time
    t0 = time.perf_counter()
    try:
        pag.wait_for_function(
            f"(() => {{ const t = document.getElementById('estado').textContent;"
            f" return t.includes({json.dumps(texto)}) || (t.startsWith('No se pudo') && !{json.dumps(texto == 'No se pudo')}); }})()",
            timeout=120000)
    except Exception:
        estado = pag.evaluate("document.getElementById('estado').textContent")
        if r is not None:
            r.cierto(False, f"esperando «{texto}», la pantalla se quedó en: «{estado}»")
        raise comun.Fallo(f"esperando «{texto}», la pantalla se quedó en: «{estado}»")
    estado = pag.evaluate("document.getElementById('estado').textContent")
    if texto != "No se pudo" and estado.startswith("No se pudo"):
        if r is not None:
            r.cierto(False, f"esperando «{texto}», la pantalla dio error", estado)
        raise comun.Fallo(estado)
    print(f"        [t80] {texto}: {(time.perf_counter() - t0) * 1000:.0f} ms", flush=True)


def correr(r: comun.Reporte):
    from playwright.sync_api import sync_playwright
    with servidor.Servidor(puerto=0) as s, sync_playwright() as pw, comun.carpeta() as d:
        nav, pag, errores = _abrir(pw, s.url)
        try:
            r.cierto(pag.evaluate("document.getElementById('version').textContent") != "", "la pantalla enseña la versión del motor")
            # pieza y tablero
            pag.fill("#p-nombre", "Tablero de prueba"); pag.fill("#p-material", "MDF"); pag.fill("#p-espesor", str(T))
            pag.click("#b-nuevo"); _espera_estado(pag, "pieza nueva", r)
            pag.fill("#t-ancho", str(W)); pag.fill("#t-fondo", str(H)); pag.click("#b-tablero"); _espera_estado(pag, "extruir", r)
            m = s.motor
            r.igual(len(m.doc.operaciones), 2, "«Poner tablero» deja dos operaciones: boceto y extruir")
            r.casi(m.reg.solido.volume, W * H * T, "el tablero tiene el volumen de la fórmula", 1e-2)
            r.igual(pag.evaluate("window.shape101.mallas().length"), 6, "el 3D enseña las 6 caras del tablero")
            # barreno
            pag.fill("#h-x", str(W / 2)); pag.fill("#h-y", str(H / 2)); pag.fill("#h-d", str(D)); pag.click("#b-barreno"); _espera_estado(pag, "barreno", r)
            r.casi(m.reg.solido.volume, (W * H - math.pi * (D / 2) ** 2) * T, "el barreno quita justo π·r²·espesor", 1e-2)
            # corte rectangular
            pag.fill("#c-x", "60"); pag.fill("#c-y", "60"); pag.fill("#c-ancho", "120"); pag.fill("#c-alto", "80"); pag.click("#b-corte"); _espera_estado(pag, "corte", r)
            r.casi(m.reg.solido.volume, (W * H - math.pi * (D / 2) ** 2 - 120 * 80) * T, "el corte quita justo ancho·alto·espesor", 1e-2)
            # redondear
            pag.fill("#r-radio", str(R)); pag.click("#b-redondear"); _espera_estado(pag, "redondear", r)
            vol_red = (W * H - math.pi * (D / 2) ** 2 - 120 * 80 - (4 - math.pi) * R ** 2) * T
            r.casi(m.reg.solido.volume, vol_red, "redondear las 4 esquinas quita (4−π)·r²·espesor", 1e-2)
            r.igual(sum(1 for n in m.reg.nombrador.caras if n.startswith("redondeo")), 4, "hay 4 caras de redondeo")
            # empujar con clic + medida
            xy = pag.evaluate("window.shape101.puntoEnPantalla('arriba')")
            pag.mouse.click(xy[0], xy[1])
            r.igual(pag.evaluate("document.getElementById('e-cara').value"), "arriba", "un clic en la cara de arriba la elige y la enseña por su nombre")
            pag.fill("#e-mm", "10"); pag.click("#b-empujar"); _espera_estado(pag, "empujar", r)
            r.casi(m.reg.solido.bounding_box().size.Z, T + 10, "empujar «arriba» 10 mm deja la pieza de 28", 1e-6)
            # empujar con arrastre
            n_antes = len(m.doc.operaciones)
            xy = pag.evaluate("window.shape101.puntoEnPantalla('lado[1]')")
            pag.mouse.move(xy[0], xy[1]); pag.mouse.down(); pag.mouse.move(xy[0] + 40, xy[1], steps=5); pag.mouse.up()
            pag.wait_for_function(f"document.getElementById('historial').children.length === {n_antes + 1}", timeout=60000)
            r.igual(m.doc.operaciones[-1]["op"], "empujar_cara", "arrastrar una cara agrega una operación empujar_cara")
            r.igual(m.doc.operaciones[-1]["cara"], "lado[1]", "la operación lleva el nombre de la cara arrastrada")
            # historial: editar y borrar
            n = len(m.doc.operaciones)
            r.igual(pag.evaluate("document.getElementById('historial').children.length"), n, "el historial de la pantalla tiene todas las operaciones")
            pag.click(f"#historial li:nth-child({n})")
            pag.fill("#ed-json", json.dumps({**m.doc.operaciones[-1], "mm": 5}))
            pag.click("#b-aplicar"); _espera_estado(pag, "editada", r)
            r.casi(m.doc.operaciones[-1]["mm"], 5, "editar la operación desde la pantalla cambia la medida", 1e-9)
            pag.click(f"#historial li:nth-child({n})"); pag.click("#b-borrar"); _espera_estado(pag, "borrada", r)
            r.igual(len(m.doc.operaciones), n - 1, "borrar desde la pantalla quita la operación")
            r.casi(m.reg.solido.bounding_box().size.X, W, "sin ese empuje el ancho vuelve a 900", 1e-6)
            # guardar, reabrir, exportar (sin cascarón: la ruta se pide con prompt)
            ruta = str(d / "prueba.s101")
            pag.once("dialog", lambda dlg: dlg.accept(ruta)); pag.click("#b-guardar-como"); _espera_estado(pag, "guardado", r)
            r.cierto((d / "prueba.s101").exists(), "guardar como… deja el .s101 en la ruta dada")
            pag.click("#b-nuevo"); _espera_estado(pag, "pieza nueva", r)
            pag.once("dialog", lambda dlg: dlg.accept(ruta)); pag.click("#b-abrir"); _espera_estado(pag, "abierto", r)
            r.igual(len(m.doc.operaciones), n - 1, "reabierto, el historial es el que se guardó")
            r.igual(m.doc.pieza["nombre"], "Tablero de prueba", "reabierto, la pieza conserva su nombre")
            r.casi(m.reg.solido.bounding_box().size.Z, T + 10, "reabierto, el sólido se regeneró con el empuje de arriba", 1e-6)
            step = str(d / "prueba.step")
            pag.once("dialog", lambda dlg: dlg.accept(step)); pag.click("#b-step"); _espera_estado(pag, "exportado", r)
            r.cierto((d / "prueba.step").stat().st_size > 1000, "exportar STEP deja un archivo con contenido")
            # un error del motor se enseña, no rompe la pantalla
            pag.fill("#r-radio", "5000"); pag.click("#b-redondear"); _espera_estado(pag, "No se pudo")
            r.cierto(pag.evaluate("document.getElementById('estado').className") == "error", "un redondeo imposible se avisa en rojo y la pantalla sigue")
            r.igual(errores, [], "la pantalla no tiró ningún error de JavaScript")
        finally:
            nav.close()
    r.numero("t80 comprobaciones de la pantalla 0.1.0", r.hechas, "")
