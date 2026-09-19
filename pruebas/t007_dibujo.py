"""t007 · Dibujar y editar con el ratón, mirando la geometría exacta.

Las herramientas se manejan aquí como las maneja el taller: **clics de verdad
sobre el lienzo**, en píxeles, con el ratón de Playwright. Y lo que se comprueba
no es lo que se ve, sino lo que quedó en el motor, al milímetro.

Los píxeles salen de `aPX`, la misma función con la que el programa pinta, así
que un clic cae exactamente donde el programa dice que está ese punto del
mundo. Si esa cuenta se rompiera, esta prueba fallaría — que es justamente lo
que se quiere de ella.

Dos cosas que sólo se ven con el ratón en la mano:

- **El clic se engancha a la referencia**: se pica *cerca* de una esquina y la
  línea nace *en* la esquina, exacta. Ese pelo es la diferencia entre una pieza
  que cierra y una que no.
- **Un grip mueve el punto y nada más**: se arrastra un extremo y el otro se
  queda donde estaba.
"""

from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "dibujar y editar con el ratón, con geometría exacta"


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        _preparar(pagina)
        primera = _dibujar_con_el_raton(r, pagina, base)
        _el_clic_se_engancha(r, pagina, base, primera)
        _un_grip_mueve_su_punto(r, pagina, base, primera)
        _navegar_no_secuestra(r, pagina)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")


def _preparar(pagina) -> None:
    """Una vista conocida y sin ayudas que muevan el punto: la rejilla y el
    ortho se prueban aparte (t006); aquí estorbarían la medida."""
    pagina.evaluate("""() => {
        estado.prefs.osnap = false;
        estado.prefs.ortho = false;
        estado.prefs.rejilla_snap = false;
        encuadrarCaja(-100, -100, 1500, 1000);
    }""")
    pagina.wait_for_timeout(200)


def _px(pagina, p):
    """El punto del mundo, en píxeles de la ventana: la misma cuenta que pinta."""
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


def _lineas(base):
    return [t for t in navegador.trazos(base)
            if t.get("clase") == "linea" and len(t.get("puntos") or []) == 2]


def _por_id(base, id_):
    return next((t for t in _lineas(base) if t.get("id") == id_), None)


def _dibujar_con_el_raton(r: comun.Reporte, pagina, base) -> None:
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA")
    _clic(pagina, [200, 200])
    _clic(pagina, [1000, 200])
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "una línea trazada con dos clics llega al motor")

    lineas = _lineas(base)
    if not r.cierto(bool(lineas), "y se pinta"):
        return None
    trazo = lineas[-1]
    pts = trazo["puntos"]
    # Un clic tiene la resolución del píxel: a esta escala, un píxel es poco
    # más de un milímetro, y ésa es toda la tolerancia que se admite.
    tol = pagina.evaluate("1.5 / estado.vista.escala")
    r.punto(pts[0], [200, 200], "arranca donde se picó", tol)
    r.punto(pts[1], [1000, 200], "y termina donde se picó", tol)
    return trazo


def _el_clic_se_engancha(r: comun.Reporte, pagina, base, primera) -> None:
    """Con la referencia encendida se pica *cerca* y se dibuja *exacto*.

    Y «exacto» quiere decir **el vértice de verdad**, no el número redondo que
    uno tenía en la cabeza: la línea anterior se trazó a clics, así que su
    extremo cayó donde cayó, con su fracción de milímetro. Comparar contra
    (1000, 200) haría fallar la prueba por un enganche perfecto.
    """
    if primera is None:
        return
    extremo = primera["puntos"][1]
    pagina.evaluate("""() => {
        estado.prefs.osnap = true;
        estado.prefs.osnap_apertura = 30;
        estado.prefs.osnap_modos = {extremo: true};
    }""")

    px = _px(pagina, extremo)
    navegador.comando(pagina, "LINEA")
    pagina.mouse.move(px[0] + 6, px[1] + 5)
    pagina.wait_for_timeout(120)
    pagina.mouse.click(px[0] + 6, px[1] + 5)
    pagina.wait_for_timeout(150)
    _clic(pagina, [1000, 800])
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)

    nueva = _lineas(base)[-1]
    r.punto(nueva["puntos"][0], extremo,
            "picando cerca del extremo, la línea nace EXACTA en el extremo", 1e-6)

    pagina.evaluate("estado.prefs.osnap = false")


def _un_grip_mueve_su_punto(r: comun.Reporte, pagina, base, primera) -> None:
    """Se agarra un extremo y se arrastra: ese punto se mueve, el otro no."""
    # Se selecciona la primera línea picándola por su mitad.
    _clic(pagina, [600, 200])
    pagina.wait_for_timeout(200)
    seleccionadas = pagina.evaluate("estado.sel ? [...estado.sel] : []")
    if not r.cierto(bool(seleccionadas), "picar la línea la selecciona"):
        return
    r.cierto(pagina.evaluate("Seleccion.gripsDe ? true : false"),
             "y una entidad seleccionada enseña sus grips")

    if primera is None:
        return
    arranque = list(primera["puntos"][0])
    desde = _px(pagina, primera["puntos"][1])
    hasta = _px(pagina, [1000, 600])
    pagina.mouse.move(desde[0], desde[1])
    pagina.wait_for_timeout(80)
    pagina.mouse.down()
    pagina.mouse.move(hasta[0], hasta[1], steps=8)
    pagina.wait_for_timeout(80)
    pagina.mouse.up()
    pagina.wait_for_timeout(400)

    tol = pagina.evaluate("2.0 / estado.vista.escala")
    linea = _por_id(base, primera.get("id"))
    if r.cierto(linea is not None, "la línea sigue ahí después de jalar el grip"):
        r.punto(linea["puntos"][0], arranque,
                "el extremo que no se tocó se queda exactamente donde estaba", 1e-6)
        r.punto(linea["puntos"][1], [1000, 600],
                "y el que se jaló va a donde se soltó", tol)

    # Y un Ctrl+Z lo devuelve.
    pagina.keyboard.press("Control+z")
    pagina.wait_for_timeout(400)
    linea = _por_id(base, primera.get("id"))
    if linea:
        r.punto(linea["puntos"][1], primera["puntos"][1],
                "y Ctrl+Z devuelve el extremo a donde estaba", tol)


def _navegar_no_secuestra(r: comun.Reporte, pagina) -> None:
    """Pan, zoom u órbita en una ventana que no es la activa: el repintado que
    ocurre a mitad del gesto no debe cambiar de ventana activa ni reencuadrar.

    En 0.12.0 sí lo hacía. `adoptar()` —la que la primera vez convierte la
    cámara de siempre en la ventana Superior— se creía sin estrenar cada vez
    que `estado.vista` no era la ventana activa, y durante la navegación es
    justo así: `estado.vista` apunta a la ventana bajo el cursor. Entonces
    secuestraba el gesto. Tres síntomas, un solo defecto.
    """
    datos = pagina.evaluate("""() => {
        Ventanas.activar(0);
        const f = Ventanas.la(2);                      // la Frontal, abajo a la izquierda
        const antes = { x: f.x, y: f.y, escala: f.escala };
        const navego = Ventanas.navegarEn(f.ox + f.w / 2, f.oy + f.h / 2);
        const tomo = estado.vista === f;
        Ventanas.adoptar([[0, 0, 0], [100, 100, 100]]);    // el repintado de a mitad
        const salida = {
            navego, tomo,
            activa: Ventanas.activa,
            sigueEnLaDeAbajo: estado.vista === f,
            seMovio: f.x !== antes.x || f.y !== antes.y || f.escala !== antes.escala,
        };
        Ventanas.terminarNavegacion();
        salida.vuelveALaActiva = estado.vista === Ventanas.laActiva();
        return salida;
    }""")
    r.cierto(datos["navego"] and datos["tomo"],
             "el botón central sobre otra ventana navega en ella")
    r.igual(datos["activa"], 0, "y la ventana activa no cambia sola")
    r.cierto(datos["sigueEnLaDeAbajo"],
             "el gesto sigue mandando en la ventana de abajo del cursor")
    r.cierto(not datos["seMovio"], "y nadie reencuadra a media navegación")
    r.cierto(datos["vuelveALaActiva"], "al soltar, el mando vuelve a la activa")
