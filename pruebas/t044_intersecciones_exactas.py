"""t044 · Intersecciones exactas con curvas libres: osnap, cercano, perpendicular y RECORTAR.

El navegador recibe una spline o una elipse en trozos rectos. Hasta la fase A2
el osnap cruzaba esos trozos y daba el cruce de las **cuerdas**: hasta la
flecha de distancia de la curva de verdad. Recortar una línea contra una
spline dejaba la punta ahí, fuera de la curva, y esa pieza no cierra en la CNC.

Ahora cada trozo viaja con su curva exacta y ui/curvas.js recalcula sobre ella.
Se comprueba en el programa de verdad, con las primitivas que manda el
servidor, contra cruces calculados aquí aparte (bisección sobre la NURBS de
core/nurbs.py, que no comparte código con el navegador):

- recta × spline, recta × elipse, arco × spline y spline × spline: el cruce
  del osnap cae sobre las dos curvas a menos de una millonésima;
- el cercano y el pie de la perpendicular están sobre la curva exacta;
- RECORTAR una línea contra una spline deja la punta **sobre** la spline.
"""

from __future__ import annotations

import json
import math
import urllib.request

from core import entidades as ent
from core import nurbs
from pruebas import comun, navegador

DESCRIPCION = "intersecciones exactas con splines y elipses: osnap, cercano, perpendicular y RECORTAR"

AJUSTE = [[0, 0], [300, 200], [600, -150], [900, 100], [1200, 0]]
AJUSTE_2 = [[100, 300], [400, -250], [800, 250], [1100, -200]]
ELIPSE = {"centro": [600, 700], "eje_mayor": [300, 80], "razon": 0.45}
TOL = 1e-6


def _entidad(base: str, id_: str) -> dict:
    with urllib.request.urlopen(base + f"/api/entidad/{id_}", timeout=5) as f:
        return json.loads(f.read().decode("utf-8"))


def _ids(base) -> list[str]:
    return sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))


def _agregar(pagina, entidades: list[dict]) -> list[str]:
    antes = set(_ids(pagina.base))
    pagina.evaluate("async (e) => { await post('/api/operacion', {accion: 'Dibujar', agregar: e}); await recargarTrazos(); }",
                    entidades)
    pagina.wait_for_timeout(300)
    return [i for i in _ids(pagina.base) if i not in antes]


def _cruces_navegador(pagina, id_a: str, id_b: str) -> list[list[float]]:
    """Lo que da el osnap: Osnap.interseccion entre cada primitiva de una y de otra."""
    return pagina.evaluate("""([a, b]) => {
        const A = estado.geometria.filter((p) => p.id === a && p.tipo !== 'punto');
        const B = estado.geometria.filter((p) => p.id === b && p.tipo !== 'punto');
        const out = [];
        for (const x of A) for (const y of B) for (const q of Osnap.interseccion(x, y)) out.push(q);
        return out;
    }""", [id_a, id_b])


def _sobre(curva, q) -> float:
    return math.dist(curva.cercano(q)[1], q)


def _distancia_a_recta(q, a, b) -> float:
    ux, uy = b[0] - a[0], b[1] - a[1]
    return abs(ux * (q[1] - a[1]) - uy * (q[0] - a[0])) / math.hypot(ux, uy)


def _cruces_recta_exactos(curva, a, b) -> list[list[float]]:
    """Cruces de la recta ab con la curva, aparte del navegador: cambio de signo
    sobre una teselación fina y bisección sobre la NURBS."""
    ux, uy = b[0] - a[0], b[1] - a[1]
    f = lambda t: (lambda q: ux * (q[1] - a[1]) - uy * (q[0] - a[0]))(curva.punto(t))
    pares = curva._teselar_t(0.01)
    salida = []
    for (t0, _), (t1, _) in zip(pares, pares[1:]):
        f0, f1 = f(t0), f(t1)
        if f0 == 0 or f0 * f1 < 0:
            for _ in range(200):
                m = (t0 + t1) / 2
                if f(t0) * f(m) <= 0:
                    t1 = m
                else:
                    t0 = m
            salida.append(curva.punto((t0 + t1) / 2))
    return salida


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return
    with navegador.programa() as (pagina, base):
        pagina.base = base
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""() => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            encuadrarCaja(-200, -600, 1500, 1100);
        }""")
        pagina.wait_for_timeout(200)
        _cruces(r, pagina)
        _cercano_y_perpendicular(r, pagina)
        _recortar(r, pagina, base)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")


def _cruces(r: comun.Reporte, pagina) -> None:
    sp = ent.Spline(puntos_ajuste=AJUSTE)
    sp2 = ent.Spline(puntos_ajuste=AJUSTE_2)
    el = ent.Elipse(**ELIPSE)
    curva, curva2 = sp.curva(), sp2.curva()
    recta = ([-100, 40], [1300, 60])
    recta_el = ([200, 650], [1000, 760])
    ids = _agregar(pagina, [
        sp.a_dict(), sp2.a_dict(), el.a_dict(),
        {"tipo": "linea", "p1": recta[0], "p2": recta[1]},
        {"tipo": "linea", "p1": recta_el[0], "p2": recta_el[1]},
        {"tipo": "arco", "centro": [600, 0], "radio": 250, "ang_ini": 0, "ang_fin": 180},
    ])
    r.exige(len(ids) == 6, "se dibujan las seis entidades", str(ids))
    i_sp, i_sp2, i_el, i_rec, i_rec_el, i_arco = ids

    # Recta × spline: contra los cruces calculados aquí, uno por uno.
    nav = _cruces_navegador(pagina, i_rec, i_sp)
    exactos = _cruces_recta_exactos(curva, *recta)
    r.cierto(len(exactos) >= 3, "la recta cruza la spline varias veces (el caso no es trivial)",
             str(len(exactos)))
    faltan = [q for q in exactos if not any(math.dist(q, n) < TOL for n in nav)]
    r.cierto(not faltan, f"recta × spline: el osnap da los {len(exactos)} cruces exactos",
             f"faltan {faltan[:2]}; dio {nav[:4]}")
    peor = max((_sobre(curva, q) for q in nav), default=0)
    r.cierto(peor < TOL, "y ninguno queda fuera de la curva", f"{peor:.2e}")

    # Recta × elipse: sobre la recta y sobre la elipse, con su ecuación.
    nav = _cruces_navegador(pagina, i_rec_el, i_el)
    c, u = ELIPSE["centro"], ELIPSE["eje_mayor"]
    a = math.hypot(*u)
    b = a * ELIPSE["razon"]
    ang = math.atan2(u[1], u[0])

    def en_elipse(q):
        x, y = q[0] - c[0], q[1] - c[1]
        xl = x * math.cos(ang) + y * math.sin(ang)
        yl = -x * math.sin(ang) + y * math.cos(ang)
        return abs(math.hypot(xl / a, yl / b) - 1) * b      # ~ distancia, en unidades

    r.igual(len(nav), 2, "recta × elipse: dos cruces")
    peor = max((max(en_elipse(q), _distancia_a_recta(q, *recta_el)) for q in nav), default=1)
    r.cierto(peor < TOL, "y los dos están sobre la elipse y sobre la recta", f"{peor:.2e}")

    # Arco × spline.
    nav = _cruces_navegador(pagina, i_arco, i_sp)
    r.cierto(len(nav) >= 1, "arco × spline: hay cruce", str(len(nav)))
    peor = max((max(_sobre(curva, q), abs(math.dist(q, [600, 0]) - 250)) for q in nav), default=1)
    r.cierto(peor < TOL, "y cae sobre el arco y sobre la spline", f"{peor:.2e}")

    # Spline × spline.
    nav = _cruces_navegador(pagina, i_sp, i_sp2)
    r.cierto(len(nav) >= 3, "spline × spline: se cruzan varias veces", str(len(nav)))
    peor = max((max(_sobre(curva, q), _sobre(curva2, q)) for q in nav), default=1)
    r.cierto(peor < TOL, "y cada cruce está sobre las dos curvas", f"{peor:.2e}")

    pagina.evaluate("(ids) => post('/api/operacion', {accion: 'limpiar', borrar: ids}).then(recargarTrazos)", ids)
    pagina.wait_for_timeout(300)


def _cercano_y_perpendicular(r: comun.Reporte, pagina) -> None:
    sp = ent.Spline(puntos_ajuste=AJUSTE)
    curva = sp.curva()
    ids = _agregar(pagina, [sp.a_dict()])
    puntos = [[150, 160], [450, 20], [700, -120], [1000, 140], [1150, -30]]
    res = pagina.evaluate("""([id, puntos]) => {
        const prims = estado.geometria.filter((p) => p.id === id && p.tipo === 'seg');
        const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
        return puntos.map((p) => {
            let mejor = null;
            for (const pr of prims) { const q = Osnap.sobre(pr, p); if (!mejor || d(q, p) < d(mejor, p)) mejor = q; }
            const pies = prims.map((pr) => Osnap.perpendicular(pr, p)).filter(Boolean);
            return { cercano: mejor, pies };
        });
    }""", [ids[0], puntos])
    peor = max(_sobre(curva, x["cercano"]) for x in res)
    r.cierto(peor < TOL, "el cercano del osnap está sobre la curva exacta", f"{peor:.2e}")
    peor_opt = 0.0
    for p, x in zip(puntos, res):
        t, q = curva.cercano(p)
        peor_opt = max(peor_opt, abs(math.dist(p, x["cercano"]) - math.dist(p, q)))
    r.cierto(peor_opt < TOL, "y es el más cercano de verdad, no sólo uno sobre la curva",
             f"{peor_opt:.2e}")
    pies = [(p, q) for p, x in zip(puntos, res) for q in x["pies"]]
    r.cierto(len(pies) >= len(puntos), "hay pie de perpendicular desde cada punto", str(len(pies)))
    peor = 0.0
    for p, q in pies:
        t, _ = curva.cercano(q)
        d1 = curva.derivada(t)
        coseno = abs((q[0] - p[0]) * d1[0] + (q[1] - p[1]) * d1[1]) / (
            max(math.dist(p, q), 1e-12) * math.hypot(*d1))
        peor = max(peor, max(_sobre(curva, q), coseno * 1e3))
    r.cierto(peor < 1e-3, "y cada pie está sobre la curva y a escuadra con su tangente", f"{peor:.2e}")
    pagina.evaluate("(ids) => post('/api/operacion', {accion: 'limpiar', borrar: ids}).then(recargarTrazos)", ids)
    pagina.wait_for_timeout(300)


def _recortar(r: comun.Reporte, pagina, base) -> None:
    """Una línea vertical en x=450 atraviesa la spline. Se recorta el pedazo
    de abajo: la punta que queda tiene que estar sobre la spline."""
    sp = ent.Spline(puntos_ajuste=AJUSTE)
    curva = sp.curva()
    ids = _agregar(pagina, [sp.a_dict(), {"tipo": "linea", "p1": [450, -400], "p2": [450, 400]}])
    i_lin = ids[1]
    pagina.evaluate("() => Seleccion.limpiar()")
    pagina.click("#cmd")
    pagina.type("#cmd", "RECORTAR", delay=10)
    pagina.keyboard.press("Enter")
    pagina.wait_for_timeout(250)
    x, y = pagina.evaluate("""(p) => {
        const [x, y] = aPX(p[0], p[1]);
        const caja = document.querySelector('#lienzo').getBoundingClientRect();
        return [caja.left + x, caja.top + y];
    }""", [450, -300])
    pagina.mouse.move(x, y)
    pagina.wait_for_timeout(80)
    pagina.mouse.click(x, y)
    pagina.wait_for_timeout(500)
    pagina.keyboard.press("Escape")
    pagina.wait_for_timeout(300)
    lin = _entidad(base, i_lin)
    r.cierto(lin["p1"][1] > -399, "RECORTAR quitó el pedazo de abajo de la línea", str(lin["p1"]))
    exacto = _cruces_recta_exactos(curva, [450, -400], [450, 400])
    r.exige(exacto, "la línea cruza la spline")
    r.cierto(math.dist(lin["p1"][:2], exacto[0]) < TOL,
             "y la punta nueva es el cruce exacto con la spline", f"{lin['p1']} vs {exacto[0]}")
    r.cierto(_sobre(curva, lin["p1"][:2]) < TOL, "o sea: está sobre la curva, no sobre una cuerda",
             f"{_sobre(curva, lin['p1'][:2]):.2e}")
