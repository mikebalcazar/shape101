"""t005 · El programa manejado con un navegador de verdad.

Se arranca el motor, se abre la interfaz en un Chromium y se dibuja como se
dibuja en el taller: por la línea de comando y con el ratón sobre el lienzo.

Lo que se comprueba son las cosas que sólo se ven de este lado:

- **Arranca sin un solo error en la consola.** Un error de JavaScript no truena
  la ventana: deja media interfaz muerta y la otra media funcionando, que es la
  peor forma de fallar.
- **El espacio confirma, como en AutoCAD**, salvo cuando se pide texto libre —
  porque «MESA DE TRABAJO» tiene que poder escribirse.
- **Enter en vacío termina el comando** y la polilínea se crea con lo que lleva
  en vez de perderse.
- **La barra se ancla a los cuatro lados y reparte los iconos**, sin que le
  salga nunca una barra de desplazamiento: un icono al que hay que hacerle
  scroll es un icono que no está.
- **Lo que se dibuja llega al motor**, que es donde vive el documento.
"""

from __future__ import annotations

from core.version import VERSION
from pruebas import comun, navegador

DESCRIPCION = "el programa manejado con un navegador real"


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return

    with navegador.programa() as (pagina, base):
        _arranque(r, pagina, base)
        _dibujar(r, pagina, base)
        _el_espacio_confirma(r, pagina, base)
        _texto_libre(r, pagina, base)
        _la_barra(r, pagina)
        r.igual(pagina.errores, [],
                "no hubo ni un error de JavaScript en toda la prueba")


def _arranque(r: comun.Reporte, pagina, base) -> None:
    r.cierto(pagina.locator("#inicio").is_visible(),
             "la pantalla de inicio sale al abrir")
    r.cierto(VERSION in pagina.locator("#iVersion").inner_text(),
             f"y enseña la versión que corre ({VERSION})")

    navegador.cerrar_inicio(pagina)
    r.cierto(not pagina.locator("#inicio").is_visible(),
             "se cierra y deja ver el dibujo")
    r.igual(pagina.locator("#lienzo").count(), 1, "hay un lienzo donde dibujar")

    capas = pagina.locator("#capas .capa, #capas li, #capas tr")
    r.cierto(capas.count() >= 2,
             "el panel de capas enseña las dos capas del dibujo nuevo",
             f"salieron {capas.count()}")


def _dibujar(r: comun.Reporte, pagina, base) -> None:
    """Una línea por coordenadas, que es la forma exacta de dibujar."""
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA")
    navegador.comando(pagina, "0,0")
    navegador.comando(pagina, "1000,0")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(250)

    despues = navegador.estado(base)
    r.igual(despues["entidades"], antes + 1,
            "lo dibujado por la línea de comando llega al motor")

    linea = [t for t in navegador.trazos(base) if t.get("clase") == "linea"]
    r.cierto(bool(linea), "y se pinta en el lienzo")
    if linea:
        pts = linea[-1]["puntos"]
        r.punto(pts[0], [0, 0], "arranca donde se tecleó")
        r.punto(pts[-1], [1000, 0], "y termina donde se tecleó")

    # Deshacer desde la interfaz.
    pagina.click("#b-deshacer")
    pagina.wait_for_timeout(300)
    r.igual(navegador.estado(base)["entidades"], antes,
            "el botón de deshacer deshace de verdad")


def _el_espacio_confirma(r: comun.Reporte, pagina, base) -> None:
    """Se dibuja con la izquierda en la barra espaciadora y la derecha en el
    ratón, sin cruzar el teclado a buscar el Enter."""
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "LINEA", confirmar=" ")
    navegador.comando(pagina, "0,500", confirmar=" ")
    navegador.comando(pagina, "800,500", confirmar=" ")
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(250)
    r.igual(navegador.estado(base)["entidades"], antes + 1,
            "el espacio confirma igual que el Enter: la línea se dibujó")

    # Y Enter en vacío termina el comando dejando lo que lleva: tres puntos de
    # polilínea son una polilínea, no un dibujo perdido.
    antes = navegador.estado(base)["entidades"]
    navegador.comando(pagina, "POLILINEA")
    navegador.comando(pagina, "0,900")
    navegador.comando(pagina, "400,900")
    navegador.comando(pagina, "400,1300")
    pagina.click("#cmd")
    pagina.keyboard.press("Enter")           # Enter en vacío: se acabó
    pagina.wait_for_timeout(350)
    despues = navegador.estado(base)
    r.igual(despues["entidades"], antes + 1,
            "Enter en vacío cierra el comando y la polilínea se crea con lo que lleva")

    pol = [t for t in navegador.trazos(base) if t.get("clase") == "linea"]
    r.cierto(any(len(t.get("puntos") or []) >= 3 for t in pol),
             "y es una polilínea de tres vértices, no dos líneas sueltas")


def _texto_libre(r: comun.Reporte, pagina, base) -> None:
    """La excepción de la regla: pidiendo **texto libre**, el espacio es un
    espacio, porque «MESA DE TRABAJO» tiene que poder escribirse.

    Se le pide el dato al programa por su propia función —la misma que usan el
    rótulo, el nombre de una capa y el de un bloque— en vez de ir por una
    herramienta concreta: así la prueba comprueba **la regla**, y no el camino
    de una herramienta que mañana puede pedir lo suyo por un cuadro de diálogo.
    """
    # 1) Texto libre: el espacio escribe.
    pagina.evaluate("""() => {
        window.__resultado = null;
        Entrada.pedirTexto({mensaje: 'Rótulo', libre: true})
               .then(t => { window.__resultado = t; });
    }""")
    pagina.wait_for_timeout(150)
    r.cierto(pagina.evaluate("Entrada.esperandoTextoLibre"),
             "el programa sabe cuándo está pidiendo texto libre")

    pagina.click("#cmd")
    pagina.type("#cmd", "MESA DE TRABAJO", delay=15)
    r.igual(pagina.input_value("#cmd"), "MESA DE TRABAJO",
            "pidiendo texto libre, el espacio escribe un espacio y no confirma")
    pagina.keyboard.press("Enter")
    pagina.wait_for_timeout(250)
    r.igual(pagina.evaluate("window.__resultado"), "MESA DE TRABAJO",
            "y el Enter entrega el rótulo entero, con sus espacios")

    # 2) Un dato que no es texto libre: el espacio confirma, como el Enter.
    pagina.evaluate("""() => {
        window.__resultado = null;
        Entrada.pedirTexto({mensaje: 'Capa', opciones: ['0', 'COTAS'], libre: false})
               .then(t => { window.__resultado = t; });
    }""")
    pagina.wait_for_timeout(150)
    pagina.click("#cmd")
    pagina.type("#cmd", "COTAS", delay=15)
    pagina.keyboard.press("Space")
    pagina.wait_for_timeout(250)
    r.igual(pagina.evaluate("window.__resultado"), "COTAS",
            "y cuando NO es texto libre, el espacio confirma como el Enter")


def _la_barra(r: comun.Reporte, pagina) -> None:
    """La barra se ancla a los cuatro lados y **nunca** le sale scroll."""
    barra = pagina.locator("#herramientas")
    r.cierto(barra.count() == 1, "hay barra de herramientas")

    for lado in ("arriba", "abajo", "izquierda", "derecha"):
        navegador.comando(pagina, f"BARRA {lado}")
        pagina.wait_for_timeout(250)
        medidas = pagina.evaluate("""() => {
            const b = document.querySelector('#herramientas');
            const cs = getComputedStyle(b);
            return {alto: b.scrollHeight, altoVisible: b.clientHeight,
                    ancho: b.scrollWidth, anchoVisible: b.clientWidth,
                    overflow: cs.overflowX + ' ' + cs.overflowY,
                    botones: b.querySelectorAll('button').length};
        }""")
        r.cierto(medidas["botones"] > 0,
                 f"anclada {lado}, la barra conserva sus iconos")
        r.cierto(medidas["alto"] <= medidas["altoVisible"] + 1
                 and medidas["ancho"] <= medidas["anchoVisible"] + 1,
                 f"anclada {lado}, los iconos se reparten y NO le sale scroll",
                 f"{medidas['ancho']}×{medidas['alto']} dentro de "
                 f"{medidas['anchoVisible']}×{medidas['altoVisible']}")

    # La barra va por bloques con título —«separa por bloques de 2 renglones
    # por tipo de función y ponle un pequeño título a cada bloque», Mike,
    # 4-sep-2026— y cada bloque tiene que caber entero anclado a cualquier
    # lado. Un bloque más ancho que la barra es el caso que devolvía el scroll.
    bloques = pagina.evaluate("""() => {
        const b = document.querySelector('#herramientas');
        return [...b.querySelectorAll('.bloque')].map(g => ({
            et: g.dataset.et || '',
            titulo: !!g.querySelector('.titulo'),
            cabe: g.scrollWidth <= b.clientWidth + 1
        }));
    }""")
    r.cierto(len(bloques) >= 3, "la barra va por bloques de función",
             f"salieron {len(bloques)}")
    r.cierto(all(g["titulo"] for g in bloques), "y cada bloque lleva su título")
    r.igual([g["et"] for g in bloques if not g["cabe"]], [],
            "y ningún bloque se sale de la barra (que es lo que devolvía el scroll)")
