"""t016 · Medidas negativas: «-300» es hacia la izquierda, diga lo que diga el ratón.

Mike (12-sep-2026): «cuando estoy dibujando un rectángulo y quiero meter una
medida negativa, -4, no me la acepta. Muchas veces necesito que dibuje hacia la
izquierda». Antes la caja X/Y y la línea de comandos sólo admitían números
positivos y el signo lo decidía el cursor; ahora el signo tecleado manda y, sin
signo, sigue mandando el cursor (para no romper la costumbre de teclear el
tamaño y apuntar).

Se corre **dentro del navegador**, tecleando de verdad en la línea de comandos
y en la cajita dinámica, y se comprueba contra el motor: las esquinas del
rectángulo y el extremo de la línea son los que se pidieron.
"""

from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "medidas negativas en rectángulo (cajita y comandos) y en línea"


def _preparar(pagina, dinamica: bool) -> None:
    pagina.evaluate("""(dinamica) => {
        estado.prefs.osnap = false;
        estado.prefs.ortho = false;
        estado.prefs.rejilla_snap = false;
        estado.prefs.snap_rejilla = false;
        estado.prefs.dinamica = dinamica;
        encuadrarCaja(-200, -200, 1500, 1000);
    }""", dinamica)
    pagina.wait_for_timeout(200)


def _px(pagina, p):
    return pagina.evaluate("""(p) => {
        const [x, y] = aPX(p[0], p[1]);
        const caja = document.querySelector('#lienzo').getBoundingClientRect();
        return [caja.left + x, caja.top + y];
    }""", list(p))


def _clic(pagina, p) -> None:
    x, y = _px(pagina, p)
    pagina.mouse.move(x, y)
    pagina.wait_for_timeout(60)
    pagina.mouse.click(x, y)
    pagina.wait_for_timeout(150)


def _mover(pagina, p) -> None:
    x, y = _px(pagina, p)
    pagina.mouse.move(x, y)
    pagina.wait_for_timeout(120)


def _ultimo(base, minimo_puntos: int) -> dict | None:
    candidatos = [t for t in navegador.trazos(base)
                  if len(t.get("puntos") or []) >= minimo_puntos]
    return candidatos[-1] if candidatos else None


def _caja(trazo) -> tuple[float, float, float, float]:
    xs = [p[0] for p in trazo["puntos"]]
    ys = [p[1] for p in trazo["puntos"]]
    return min(xs), min(ys), max(xs), max(ys)


def _teclear_en_lienzo(pagina, texto: str) -> None:
    """Teclear con el foco en el lienzo, como hace Mike: el primer carácter
    manda el foco a la cajita dinámica y lo demás cae ahí."""
    pagina.keyboard.type(texto, delay=30)
    pagina.wait_for_timeout(80)
    pagina.keyboard.press("Enter")
    pagina.wait_for_timeout(200)


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        _rectangulo_por_comandos(r, pagina, base)
        _rectangulo_por_cajita(r, pagina, base)
        _linea_negativa(r, pagina, base)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")


def _rectangulo_por_comandos(r: comun.Reporte, pagina, base) -> None:
    """Línea de comandos, ratón arriba a la derecha del origen. «-300» va a la
    izquierda aunque el ratón esté a la derecha; «200» sube porque el ratón
    está arriba (sin signo, manda el cursor)."""
    _preparar(pagina, dinamica=False)
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "RECTANGULO")
    navegador.comando(pagina, "500,300")   # origen exacto, sin el píxel del clic
    _mover(pagina, [900, 700])
    navegador.comando(pagina, "-300")
    navegador.comando(pagina, "200")
    pagina.keyboard.press("Escape")      # RECTANGULO se queda esperando otro
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "comandos: «-300» Enter «200» Enter crea el rectángulo")
    t = _ultimo(base, 4)
    if r.cierto(t is not None, "y se pinta"):
        x0, y0, x1, y1 = _caja(t)
        r.punto([x0, y0], [200, 300], "va de x=200 (300 a la izquierda del origen)", 0.01)
        r.punto([x1, y1], [500, 500], "hasta (500, 500): el alto sin signo siguió al ratón", 0.01)

    # Y al revés: ratón a la izquierda, ancho sin signo → crece a la izquierda
    # (como siempre); alto «-200» baja aunque el ratón esté arriba.
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "RECTANGULO")
    navegador.comando(pagina, "1000,300")
    _mover(pagina, [700, 700])
    navegador.comando(pagina, "300")
    navegador.comando(pagina, "-200")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)
    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "comandos: «300» Enter «-200» Enter crea el rectángulo")
    t = _ultimo(base, 4)
    if r.cierto(t is not None, "y se pinta"):
        x0, y0, x1, y1 = _caja(t)
        r.punto([x0, y0], [700, 100], "el ancho siguió al ratón (izquierda) y el alto bajó por el signo", 0.01)
        r.punto([x1, y1], [1000, 300], "con el origen en la esquina de arriba a la derecha", 0.01)


def _rectangulo_por_cajita(r: comun.Reporte, pagina, base) -> None:
    """Cajita dinámica (X / Y), que es donde Mike teclea: «-300» Enter «200»
    Enter, con el ratón arriba a la derecha."""
    _preparar(pagina, dinamica=True)
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "RECTANGULO")
    navegador.comando(pagina, "500,300")
    pagina.evaluate("document.activeElement.blur()")   # el foco vuelve al lienzo, como tras un clic
    _mover(pagina, [900, 700])
    _teclear_en_lienzo(pagina, "-300")     # cae en X y pasa a Y
    _teclear_en_lienzo(pagina, "200")      # remata
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "cajita: «-300» Enter «200» Enter crea el rectángulo")
    t = _ultimo(base, 4)
    if r.cierto(t is not None, "y se pinta"):
        x0, y0, x1, y1 = _caja(t)
        r.punto([x0, y0], [200, 300], "va de x=200: el signo tecleado manda sobre el ratón", 0.01)
        r.punto([x1, y1], [500, 500], "hasta (500, 500)", 0.01)


def _linea_negativa(r: comun.Reporte, pagina, base) -> None:
    """LINEA con longitud «-200» y el ratón a la derecha: la línea sale de 200
    hacia la izquierda. La misma regla, para que no dependa del comando."""
    _preparar(pagina, dinamica=False)
    # Con ortho la dirección del ratón es exactamente 0°: lo que se prueba es
    # el signo, no la puntería del píxel.
    pagina.evaluate("estado.prefs.ortho = true")
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA")
    navegador.comando(pagina, "500,300")
    _mover(pagina, [900, 300])
    navegador.comando(pagina, "-200")     # fija la longitud (con signo)
    navegador.comando(pagina, "")         # Enter en vacío: acepta en la dirección del ratón
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "línea: «-200» Enter Enter crea la línea")
    lineas = [t for t in navegador.trazos(base) if len(t.get("puntos") or []) == 2]
    t = lineas[-1] if lineas else None
    if r.cierto(t is not None, "y se pinta"):
        r.punto(t["puntos"][0], [500, 300], "arranca en el origen", 0.01)
        r.punto(t["puntos"][1], [300, 300], "y termina 200 a la IZQUIERDA, al revés del ratón", 0.01)
