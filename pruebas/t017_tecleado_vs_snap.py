"""t017 · Lo tecleado manda sobre el snap.

Mike (12-sep-2026): «cuando meto un valor para trazar una línea, si el mouse
está sobre el camino de la línea no respeta el valor. El valor debe ser el
valor final, no importa ángulo, dirección o snaps». Y del 10-sep: con la X del
rectángulo tecleada, agarrar un snap borraba el valor.

Causa única: `puntoDelCursor` devolvía el snap antes de llegar al bloqueo. Ahora
el snap sólo aporta dirección (o la otra coordenada) cuando hay algo tecleado.

Se planta una línea auxiliar cuyos extremos sirven de snap, se pone el ratón
justo encima de un extremo y se teclea la medida. Se comprueba en el motor.
"""

from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "el valor tecleado manda sobre el snap (línea y rectángulo)"


def _preparar(pagina) -> None:
    pagina.evaluate("""() => {
        estado.prefs.osnap = true;
        estado.prefs.ortho = false;
        estado.prefs.snap_rejilla = false;
        estado.prefs.dinamica = false;
        encuadrarCaja(-200, -200, 1500, 1000);
    }""")
    pagina.wait_for_timeout(200)


def _mover(pagina, p) -> None:
    x, y = pagina.evaluate("""(p) => {
        const [x, y] = aPX(p[0], p[1]);
        const caja = document.querySelector('#lienzo').getBoundingClientRect();
        return [caja.left + x, caja.top + y];
    }""", list(p))
    pagina.mouse.move(x, y)
    pagina.wait_for_timeout(150)


def _auxiliar(pagina, a, b) -> None:
    navegador.comando(pagina, "LINEA")
    navegador.comando(pagina, f"{a[0]},{a[1]}")
    navegador.comando(pagina, f"{b[0]},{b[1]}")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(200)


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        _preparar(pagina)
        _linea(r, pagina, base)
        _rectangulo(r, pagina, base)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")


def _linea(r: comun.Reporte, pagina, base) -> None:
    """Auxiliar de (500,300) a (650,300). LINEA desde (500,300), ratón sobre el
    endpoint (650,300) —que está en el camino— y «200» tecleado: la línea
    termina en (700,300), no en el snap."""
    _auxiliar(pagina, (500, 300), (650, 300))
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA")
    navegador.comando(pagina, "500,300")
    _mover(pagina, [650, 300])
    r.cierto(pagina.evaluate("!!estado.ref"), "el snap al endpoint (650,300) está agarrado")
    navegador.comando(pagina, "200")
    navegador.comando(pagina, "")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1, "línea: se crea con «200» y el snap en el camino")
    lineas = [t for t in navegador.trazos(base) if len(t.get("puntos") or []) == 2]
    t = lineas[-1]
    r.punto(t["puntos"][0], [500, 300], "arranca en el origen", 0.01)
    r.punto(t["puntos"][1], [700, 300], "y mide 200: el snap a 150 sólo dio la dirección", 0.01)

    # Snap fuera del camino: da la dirección, la medida sigue siendo la tecleada.
    _auxiliar(pagina, (500, 300), (800, 700))       # endpoint a 500 de distancia, 53.13°
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA")
    navegador.comando(pagina, "500,300")
    _mover(pagina, [800, 700])
    navegador.comando(pagina, "100")
    navegador.comando(pagina, "")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)
    r.igual(navegador.estado(base)["entidades"], antes + 1, "línea: se crea con «100» y el snap fuera del camino")
    lineas = [t for t in navegador.trazos(base) if len(t.get("puntos") or []) == 2]
    t = lineas[-1]
    r.punto(t["puntos"][1], [560, 380], "mide 100 en la dirección del snap (3-4-5)", 0.01)


def _rectangulo(r: comun.Reporte, pagina, base) -> None:
    """Auxiliar con endpoint en (900,600). RECTÁNGULO desde (500,300), «300»
    en X, ratón sobre el snap y Enter: X queda en 800 (lo tecleado), Y en 600
    (la del snap)."""
    _auxiliar(pagina, (900, 600), (1200, 600))
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "RECTANGULO")
    navegador.comando(pagina, "500,300")
    _mover(pagina, [900, 600])
    r.cierto(pagina.evaluate("!!estado.ref"), "el snap al endpoint (900,600) está agarrado")
    navegador.comando(pagina, "300")
    navegador.comando(pagina, "")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1, "rectángulo: se crea con «300» en X y el snap")
    rects = [t for t in navegador.trazos(base) if len(t.get("puntos") or []) >= 4]
    t = rects[-1]
    xs = [p[0] for p in t["puntos"]]
    ys = [p[1] for p in t["puntos"]]
    r.punto([min(xs), min(ys)], [500, 300], "esquina de origen", 0.01)
    r.punto([max(xs), max(ys)], [800, 600], "X = 500+300 tecleada, Y = 600 del snap proyectado", 0.01)
