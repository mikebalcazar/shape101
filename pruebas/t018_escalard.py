"""t018 · ESCALARD: escalar en una sola dirección.

Mike (12-sep-2026): «agregar la función de scale en 1 plano/dirección: sólo se
incrementa escala en el vector que se seleccionó el origen y referencia».

Se dibuja un mueble de 900 × 600 (rectángulo), su diagonal y un círculo en el
centro; se escala sobre el eje X de 900 a 1000. El alto no cambia, la diagonal
llega a la esquina nueva y el círculo se vuelve la elipse exacta. Se comprueba
contra el motor.
"""

from __future__ import annotations

import json
import urllib.request

from pruebas import comun, navegador

DESCRIPCION = "ESCALARD escala sólo sobre el eje base→referencia"


def _entidad(base: str, id_: str) -> dict:
    with urllib.request.urlopen(base + f"/api/entidad/{id_}", timeout=5) as f:
        return json.loads(f.read().decode("utf-8"))


def _cmd(pagina, *textos):
    """Como navegador.comando, pero sin `fill("")`: vaciar la caja con Playwright
    dispara un Delete que, con entidades seleccionadas, corre BORRAR."""
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
    pagina.mouse.click(x, y)
    pagina.wait_for_timeout(150)


def _seleccionar(pagina, *puntos) -> None:
    """Con el comando ya pidiendo selección: se pican las entidades por un
    punto de cada una y Enter termina (como Mike, no como un script)."""
    # Sumar a la selección es con Shift (Mike, 4-sep); sin Shift cada clic
    # reemplaza lo anterior.
    pagina.keyboard.down("Shift")
    for p in puntos:
        _clic(pagina, p)
    pagina.keyboard.up("Shift")
    _cmd(pagina, "")


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""() => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            encuadrarCaja(-200, -200, 2000, 1200);
        }""")
        pagina.wait_for_timeout(200)

        _cmd(pagina, "RECTANGULO", "500,300", "1400,900")
        pagina.keyboard.press("Escape")
        _cmd(pagina, "LINEA", "500,300", "1400,900")
        pagina.keyboard.press("Escape")
        _cmd(pagina, "CIRCULO", "950,600", "100")
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
        r.igual(navegador.estado(base)["entidades"], 3, "mueble: rectángulo, diagonal y círculo")
        ids = sorted({t["id"] for t in navegador.trazos(base)})

        # Eje X: base (500,300) → referencia (1400,300) mide 900; nuevo (1500,300) = 1000.
        _cmd(pagina, "ESCALARD")
        _seleccionar(pagina, [950, 300], [800, 500], [1050, 600])   # borde bajo, diagonal, borde del círculo
        r.igual(pagina.evaluate("estado.sel.size"), 3, "picadas las tres")
        _cmd(pagina, "500,300", "1400,300", "@1000,0")   # «1500,300» se leería como factor 1500.3: relativo a la base
        pagina.wait_for_timeout(400)

        r.igual(navegador.estado(base)["entidades"], 3, "siguen siendo tres entidades (el círculo se cambió por una elipse)")
        trazos = navegador.trazos(base)
        rect = [t for t in trazos if len(t.get("puntos") or []) == 5][-1]
        xs = [p[0] for p in rect["puntos"]]
        ys = [p[1] for p in rect["puntos"]]
        r.punto([min(xs), min(ys)], [500, 300], "el rectángulo arranca donde estaba", 0.01)
        r.punto([max(xs), max(ys)], [1500, 900], "ancho 1000 y el alto sigue en 600", 0.01)
        diag = [t for t in trazos if len(t.get("puntos") or []) == 2][-1]
        r.punto(diag["puntos"][1], [1500, 900], "la diagonal llega a la esquina nueva", 0.01)

        tipos = {}
        for i in ids + [t["id"] for t in trazos]:
            try:
                e = _entidad(base, i)
                tipos[e.get("tipo")] = e
            except Exception:
                pass
        r.cierto("circulo" not in tipos, "ya no hay círculo")
        if r.cierto("elipse" in tipos, "hay una elipse"):
            e = tipos["elipse"]
            r.punto(e["centro"], [1000, 600], "centrada en 1000,600 (el centro se corrió con el eje)", 0.01)
            r.punto(e["eje_mayor"], [100 * 10 / 9, 0], "eje mayor 111.1 sobre X", 0.01)
            r.igual(round(e["razon"], 6), 0.9, "razón 0.9: el eje Y sigue midiendo 100")

        # Factor tecleado en vez de punto, y sobre un eje inclinado: sólo se
        # mueve la componente sobre ese eje.
        _cmd(pagina, "ESCALARD")
        _seleccionar(pagina, [1000, 600])                     # la diagonal nueva pasa por (1000,600)
        _cmd(pagina, "500,300", "500,900", "2")               # eje Y, ×2
        pagina.wait_for_timeout(300)
        diag2 = [t for t in navegador.trazos(base) if len(t.get("puntos") or []) == 2][-1]
        r.punto(diag2["puntos"][1], [1500, 1500], "×2 sobre Y: la X no se toca, la Y se dobla desde la base", 0.01)

        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
