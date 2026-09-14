"""t019 · RECORTAR sobre polilíneas.

Mike (10-sep-2026): «cuando uso trim sobre una polilínea, corta la polilínea
en donde se trimea, generando nuevos endpoints». Antes RECORTAR rechazaba las
polilíneas. Ahora se quita sólo el trozo entre los dos cruces que rodean el
clic y lo que queda sigue siendo polilínea: un rectángulo cerrado se abre por
ahí; una abierta con el trozo en medio queda en dos; un tramo curvo se corta
como arco exacto con su bulge parcial.

Se dibuja con comandos, se pica con el ratón en el trozo a quitar, y se
comprueba contra el motor (vértices, bulges, cerrada).
"""

from __future__ import annotations

import json
import math
import urllib.request

from pruebas import comun, navegador

DESCRIPCION = "RECORTAR quita un trozo de polilínea y deja polilíneas"


def _entidad(base: str, id_: str) -> dict:
    with urllib.request.urlopen(base + f"/api/entidad/{id_}", timeout=5) as f:
        return json.loads(f.read().decode("utf-8"))


def _cmd(pagina, *textos):
    for t in textos:
        pagina.click("#cmd")
        pagina.keyboard.press("Control+A")
        pagina.keyboard.press("Backspace")
        pagina.type("#cmd", t, delay=10)
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(250)


def _clic(pagina, p) -> None:
    x, y = pagina.evaluate("""(p) => {
        const [x, y] = aPX(p[0], p[1]);
        const caja = document.querySelector('#lienzo').getBoundingClientRect();
        return [caja.left + x, caja.top + y];
    }""", list(p))
    pagina.mouse.move(x, y)
    pagina.wait_for_timeout(80)
    pagina.mouse.click(x, y)
    pagina.wait_for_timeout(400)


def _ids(base) -> list[str]:
    return sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))


def _polilineas(base) -> list[dict]:
    salida = []
    for i in _ids(base):
        e = _entidad(base, i)
        if e.get("tipo") == "polilinea":
            salida.append(e)
    return salida


def _limpiar(pagina, base) -> None:
    ids = _ids(base)
    if ids:
        pagina.evaluate("(ids) => post('/api/operacion', {accion: 'limpiar', borrar: ids})", ids)
        pagina.evaluate("async () => { await recargarTrazos(); Seleccion.limpiar(); }")   # sin selección vieja: pedirUna la usaría
        pagina.wait_for_timeout(300)


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""() => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            encuadrarCaja(-500, -1200, 2500, 1500);
        }""")
        pagina.wait_for_timeout(200)
        _rectangulo_cerrado(r, pagina, base)
        _limpiar(pagina, base)
        _abierta_en_medio(r, pagina, base)
        _limpiar(pagina, base)
        _con_bulge(r, pagina, base)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")


def _rectangulo_cerrado(r: comun.Reporte, pagina, base) -> None:
    """Rectángulo 500,300–1400,900 y una línea vertical en x=800 que lo cruza
    por abajo y por arriba. Se pica el lado de abajo entre 500 y 800: se quita
    ese trozo y el rectángulo se abre: (800,300)→(1400,300)→(1400,900)→(800,900)."""
    _cmd(pagina, "RECTANGULO", "500,300", "1400,900")
    pagina.keyboard.press("Escape")
    _cmd(pagina, "LINEA", "800,200", "800,1000")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(200)
    _cmd(pagina, "RECORTAR")
    _clic(pagina, [650, 300])
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    polis = _polilineas(base)
    if r.igual(len(polis), 1, "cerrada: sigue habiendo UNA polilínea"):
        e = polis[0]
        r.cierto(not e.get("cerrada"), "y ya no es cerrada")
        r.igual(len(e["puntos"]), 4, "con cuatro vértices")
        r.punto(e["puntos"][0][:2], [800, 300], "arranca en el cruce de abajo")
        r.punto(e["puntos"][-1][:2], [800, 900], "y termina en el cruce de arriba: dio la vuelta por la derecha")


def _abierta_en_medio(r: comun.Reporte, pagina, base) -> None:
    """Polilínea (0,0)→(1000,0)→(1000,500)→(2000,500) y dos líneas verticales
    en x=300 y x=600. Se pica en (450,0): quedan dos polilíneas."""
    _cmd(pagina, "POLILINEA", "0,0", "1000,0", "1000,500", "2000,500")
    pagina.keyboard.press("Escape")
    _cmd(pagina, "LINEA", "300,-200", "300,200")
    pagina.keyboard.press("Escape")
    _cmd(pagina, "LINEA", "600,-200", "600,200")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(200)
    r.igual(len(_polilineas(base)), 1, "abierta: una polilínea antes")
    _cmd(pagina, "RECORTAR")
    _clic(pagina, [450, 0])
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    polis = _polilineas(base)
    if r.igual(len(polis), 2, "en medio: quedan DOS polilíneas, no líneas sueltas"):
        polis.sort(key=lambda e: e["puntos"][0][0])
        a, b = polis
        r.igual(len(a["puntos"]), 2, "la primera va del origen al cruce")
        r.punto(a["puntos"][-1][:2], [300, 0], "y termina en x=300")
        r.igual(len(b["puntos"]), 4, "la segunda arranca en el cruce y conserva sus tres vértices")
        r.punto(b["puntos"][0][:2], [600, 0], "empieza en x=600")
        r.punto(b["puntos"][-1][:2], [2000, 500], "y termina donde terminaba")


def _con_bulge(r: comun.Reporte, pagina, base) -> None:
    """Polilínea de un solo tramo curvo (bulge 1 = media vuelta) de (0,0) a
    (1000,0), radio 500, centro (500,0). Una vertical en x=500 la cruza en el
    punto más bajo. Se pica cerca del arranque: queda el cuarto de vuelta del
    cruce a (1000,0), con bulge tan(90°/4)."""
    pagina.evaluate("""async () => {
        await post('/api/operacion', {accion: 'arco', agregar: [
            {tipo: 'polilinea', puntos: [[0, 0, 1], [1000, 0]], cerrada: false}]});
        await recargarTrazos();
    }""")
    _cmd(pagina, "LINEA", "500,-1000", "500,1000")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(200)
    e0 = _polilineas(base)[0]
    r.igual(len(e0["puntos"]), 2, "curva: la polilínea tiene dos vértices y un bulge")
    # el arco con bulge positivo va antihorario de (0,0): pasa por (500,-500)
    _cmd(pagina, "RECORTAR")
    _clic(pagina, [500 - 500 * math.cos(math.radians(30)), -500 * math.sin(math.radians(30))])
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    polis = _polilineas(base)
    if r.igual(len(polis), 1, "curva: sigue siendo una polilínea"):
        e = polis[0]
        r.igual(len(e["puntos"]), 2, "de dos vértices")
        r.punto(e["puntos"][0][:2], [500, -500], "que arranca en el cruce (el punto más bajo)", 0.01)
        r.punto(e["puntos"][-1][:2], [1000, 0], "y termina donde terminaba", 0.01)
        b = e["puntos"][0][2] if len(e["puntos"][0]) > 2 else 0
        r.cierto(abs(b - math.tan(math.pi / 8)) < 1e-6, f"con bulge tan(22.5°)=0.4142 (se obtuvo {b:.4f}): un cuarto de vuelta exacto")
