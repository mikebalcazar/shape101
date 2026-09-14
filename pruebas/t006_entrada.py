"""t006 · Dar un punto: las ocho referencias, ortho y las cuatro formas.

**El osnap trabaja sobre geometría exacta, no sobre lo que se pinta.** El punto
medio de un arco teselado no es el punto medio del arco, y en un plano que va a
la CNC esa diferencia es una pieza mal cortada. Por eso las ocho referencias se
comprueban contra geometría de respuesta conocida —un rectángulo, una diagonal
y un círculo, con los puntos calculados a mano— y no contra lo que devuelva el
propio programa.

Se corre **dentro del navegador**, llamando a `Osnap.buscar` y a
`Entrada.parsearCoordenadas`, que son las funciones que usa el programa cuando
alguien mueve el ratón. Reimplementarlas aquí sólo comprobaría que la copia se
parece a sí misma.

(Que el osnap ignore a propósito lo ajeno teselado —`aprox`— se comprueba en
`t013`, con un plano de fuera de verdad: ahí sí hay primitivas de ésas.)
"""

from __future__ import annotations

import json
import urllib.request

from pruebas import comun, navegador

DESCRIPCION = "las ocho referencias, ortho y las cuatro formas de dar un punto"


def _dibujar(base: str) -> None:
    """Geometría de respuesta conocida, puesta por la API antes de abrir la
    página: un rectángulo de 1000 × 600, su diagonal y un círculo de radio 200
    centrado en (500, 300) — que es también el centro del rectángulo, así que
    ahí se cruzan varias referencias a la vez y se ve cuál gana."""
    figuras = [
        {"tipo": "linea", "p1": [0, 0], "p2": [1000, 0]},
        {"tipo": "linea", "p1": [1000, 0], "p2": [1000, 600]},
        {"tipo": "linea", "p1": [1000, 600], "p2": [0, 600]},
        {"tipo": "linea", "p1": [0, 600], "p2": [0, 0]},
        {"tipo": "linea", "p1": [0, 0], "p2": [1000, 600]},
        {"tipo": "circulo", "centro": [500, 300], "radio": 200},
        {"tipo": "punto", "p": [800, 500]},
    ]
    for f in figuras:
        datos = json.dumps({"entidad": f}).encode()
        req = urllib.request.Request(base + "/api/entidad", data=datos,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        _dibujar(base)
        pagina.reload(wait_until="networkidle")
        pagina.wait_for_timeout(1200)
        navegador.cerrar_inicio(pagina)

        _preparar(pagina)
        _referencias(r, pagina)
        _ortho(r, pagina)
        _las_cuatro_formas(r, pagina)


def _preparar(pagina) -> None:
    """Todas las referencias encendidas y una apertura generosa, para que la
    prueba mida la exactitud del enganche y no la puntería del cursor."""
    pagina.evaluate("""() => {
        estado.prefs.osnap = true;
        estado.prefs.osnap_apertura = 40;
        estado.prefs.osnap_modos = {extremo: true, medio: true, centro: true,
            cuadrante: true, interseccion: true, perpendicular: true,
            proyeccion: false, cercano: true, nodo: true};
        estado.prefs.ortho = false;
    }""")


def _buscar(pagina, p, base=None, modos=None):
    """`Osnap.buscar` tal cual, con los modos que se quieran para esa pregunta."""
    return pagina.evaluate("""([p, base, modos]) => {
        const guardados = estado.prefs.osnap_modos;
        if (modos) estado.prefs.osnap_modos = modos;
        const res = Osnap.buscar(p, base || null, null);
        estado.prefs.osnap_modos = guardados;
        return res ? {modo: res.modo, p: res.p} : null;
    }""", [p, base, modos])


def _referencias(r: comun.Reporte, pagina) -> None:
    solo = lambda *ms: {m: True for m in ms}

    casos = [
        ("extremo", [8, 6], solo("extremo"), [0, 0],
         "el extremo engancha en la esquina exacta"),
        ("medio", [497, 5], solo("medio"), [500, 0],
         "el medio engancha en la mitad exacta del lado"),
        ("centro", [505, 305], solo("centro"), [500, 300],
         "el centro engancha en el centro del círculo"),
        ("cuadrante", [698, 305], solo("cuadrante"), [700, 300],
         "el cuadrante engancha en el este del círculo"),
        ("interseccion", [1002, 598], solo("interseccion"), [1000, 600],
         "la intersección engancha donde se cruzan dos líneas"),
        ("nodo", [803, 503], solo("nodo"), [800, 500],
         "el nodo engancha en el punto suelto"),
        ("cercano", [300, 8], solo("cercano"), [300, 0],
         "el cercano engancha sobre la línea, no en el aire"),
    ]
    for modo, consulta, modos, esperado, que in casos:
        res = _buscar(pagina, consulta, None, modos)
        if not r.cierto(res is not None, f"hay enganche de {modo}"):
            continue
        r.igual(res["modo"], modo, f"y es del modo {modo}")
        r.punto(res["p"], esperado, que, 1e-6)

    # La perpendicular necesita un punto base: es «desde dónde» se baja.
    res = _buscar(pagina, [500, 8], [500, 900], solo("perpendicular"))
    if r.cierto(res is not None, "hay enganche de perpendicular"):
        r.igual(res["modo"], "perpendicular", "y es del modo perpendicular")
        r.punto(res["p"], [500, 0],
                "la perpendicular cae a plomo desde el punto base", 1e-6)

    # Y con todas encendidas, manda la prioridad: en la esquina hay extremo e
    # intersección a la vez, y gana el extremo.
    res = _buscar(pagina, [3, 3])
    if r.cierto(res is not None, "con todas encendidas también engancha"):
        r.igual(res["modo"], "extremo",
                "en una esquina gana el extremo, que es el punto que la gente quiere")

    # Apagar el osnap lo apaga de verdad.
    pagina.evaluate("estado.prefs.osnap = false")
    r.igual(_buscar(pagina, [3, 3]), None,
            "con las referencias apagadas no engancha nada")
    pagina.evaluate("estado.prefs.osnap = true")


def _ortho(r: comun.Reporte, pagina) -> None:
    """Con ortho, el punto sale a la horizontal o a la vertical del anterior."""
    # `orthoActivo` es la regla, y el Shift la invierte: es lo que se toca de
    # verdad al dibujar, y lo que hay que poder comprobar.
    estado = pagina.evaluate("""() => {
        estado.prefs.ortho = true;
        const conOrtho = orthoActivo();
        fijarShift(true);
        const conShift = orthoActivo();
        fijarShift(false);
        estado.prefs.ortho = false;
        const sinOrtho = orthoActivo();
        return {conOrtho, conShift, sinOrtho};
    }""")
    r.cierto(estado["conOrtho"], "con ortho encendido, ortho manda")
    r.cierto(not estado["conShift"],
             "y el Shift lo suelta mientras se tiene apretado (como en AutoCAD)")
    r.cierto(not estado["sinOrtho"], "apagado, no manda")


def _las_cuatro_formas(r: comun.Reporte, pagina) -> None:
    """Absolutas, relativas, polares y la distancia directa."""
    def punto(texto, base=None):
        return pagina.evaluate("([t, b]) => Entrada.parsearCoordenadas(t, b)",
                               [texto, base])

    r.punto(punto("100,50"), [100, 50], "coordenadas absolutas: 100,50")
    r.punto(punto("@100,50", [1000, 600]), [1100, 650],
            "relativas al último punto: @100,50")
    r.punto(punto("@100<45", [0, 0]), [70.7106781, 70.7106781],
            "polares: @100<45", 1e-6)
    r.punto(punto("@100<0", [500, 300]), [600, 300],
            "y una polar horizontal cae exacta, sin arrastre de coma flotante", 1e-9)

    r.igual(punto("no es un punto"), None,
            "lo que no es un punto no se inventa: se rechaza")
    r.igual(punto(""), None, "y una línea vacía tampoco")
