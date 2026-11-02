"""t050 · DESFASE de splines y elipses, a una tolerancia garantizada.

El desfase de una spline o de una elipse no es una spline ni una elipse: no
tiene forma cerrada. Hasta la fase B3 DESFASE se negaba con ellas. Ahora se
aproxima como en Rhino (core/desfase.py): una B-spline que en todo su largo
está a la distancia pedida, más o menos una décima de la tolerancia del
documento. La prueba no le cree al kernel su error: lo **mide** en los dos
sentidos (cada punto de la curva nueva está a la distancia de la original, y
cada punto de la original tiene a la nueva a esa distancia).

- spline abierta y cerrada, elipse completa y arco de elipse, de los dos lados;
- el lado es el del clic (afuera de la elipse queda más grande);
- hacia adentro, más allá del radio más cerrado, se niega y dice el radio;
- la curva nueva sale al DXF (cerrada, no periódica) y AutoCAD la lee igual;
- en el programa: DESFASE de una spline con el ratón deja la curva nueva.
"""

from __future__ import annotations

import math

import ezdxf

from core import desfase as D
from core import entidades as E
from core.documento import Documento
from export import dxf as export_dxf
from pruebas import comun, navegador

DESCRIPCION = "DESFASE de splines y elipses a una tolerancia garantizada"

AJUSTE = [[0, 0], [300, 200], [600, -150], [900, 100]]
CV_CERRADA = [[0, 0], [400, -100], [600, 200], [400, 500], [0, 400], [-200, 200]]


def _densa(f, a, b, n=3000):
    return [f(a + (b - a) * i / n) for i in range(n + 1)]


def _hausdorff(nueva, original_pts, d):
    """El peor |distancia - d| en los dos sentidos, entre la curva nueva y
    puntos densos de la original."""
    a, b = nueva.dominio
    peor = 0.0
    for i in range(201):
        q = nueva.punto(a + (b - a) * i / 200)
        peor = max(peor, abs(min(math.dist(q, p) for p in original_pts) - d))
    for p in original_pts[::15]:
        peor = max(peor, abs(math.dist(nueva.cercano(p)[1], p) - d))
    return peor


def correr(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(E.Spline(puntos_ajuste=AJUSTE))
        sc = doc.agregar(E.Spline(puntos_control=CV_CERRADA, cerrada=True))
        el = doc.agregar(E.Elipse(centro=[0, 0], eje_mayor=[300, 0], razon=0.5))
        ae = doc.agregar(E.Elipse(centro=[0, 0], eje_mayor=[300, 0], razon=0.5, param_ini=0, param_fin=2.0))
    tol = D.mod_tolerancia.de(doc) / 10

    c = sp.curva()
    pts_sp = _densa(c.punto, *c.dominio)
    cc = sc.curva()
    pts_sc = _densa(cc.punto, *cc.dominio)
    elip = lambda t: [300 * math.cos(t), 150 * math.sin(t)]
    pts_el = _densa(elip, 0, 2 * math.pi)
    pts_ae = _densa(elip, 0, 2.0)

    casos = [("spline abierta, arriba", sp, [300, 300], 20, pts_sp),
             ("spline abierta, abajo", sp, [300, 0], 20, pts_sp),
             ("spline cerrada, adentro", sc, [200, 200], 15, pts_sc),
             ("spline cerrada, afuera", sc, [1000, 200], 15, pts_sc),
             ("elipse, adentro", el, [0, 0], 20, pts_el),
             ("elipse, afuera", el, [0, 400], 20, pts_el),
             ("arco de elipse, afuera", ae, [400, 300], 25, pts_ae)]
    for nombre, e, clic, dist, pts in casos:
        res = D.desfasar(doc, e, dist, clic)
        n = E.de_dict(res["entidad"])
        cn = n.curva()
        peor = _hausdorff(cn, pts, dist)
        r.cierto(peor <= tol + 1e-6, f"{nombre}: a {dist} de la original en todo su largo (±{tol})",
                 f"peor {peor:.5f}")
        # Del lado del clic: el clic queda más cerca de la nueva que de la original.
        cerca_nueva = math.dist(cn.cercano(clic)[1], clic)
        cerca_orig = min(math.dist(clic, p) for p in pts)
        r.cierto(cerca_nueva < cerca_orig, f"{nombre}: del lado del clic")
        if e is el:
            r.cierto(n.cerrada, "el desfase de una elipse completa sale cerrado")

    r.levanta(D.NoSeDesfasa, D.desfasar, "hacia adentro más allá del radio más cerrado se niega (haría un lazo)",
              doc, sp, 500, [300, 300])
    try:
        D.desfasar(doc, el, 100, [0, 0])
    except D.NoSeDesfasa as exc:
        r.cierto("75.00" in str(exc), "y dice el radio: en la elipse 300 × 150 es b²/a = 75",
                 str(exc))
    else:
        r.cierto(False, "la elipse hacia adentro a 100 (más que su radio de 75) se niega")

    # Al DXF: la cerrada de nudos sujetos sale cerrada pero no periódica.
    res = D.desfasar(doc, sc, 15, [1000, 200])
    with doc.transaccion("Desfase"):
        nueva = doc.agregar(E.de_dict(res["entidad"]))
    with comun.carpeta() as tmp:
        export_dxf.escribir(doc, tmp / "t050.dxf")
        s = next(x for x in ezdxf.readfile(str(tmp / "t050.dxf")).modelspace()
                 if x.dxftype() == "SPLINE" and len(x.control_points) == len(nueva.puntos_control))
        r.cierto(s.closed and not s.dxf.flags & 2, "la cerrada sale al DXF cerrada, sin marca de periódica")
        bs = s.construction_tool()
        cn = nueva.curva()
        a, b = cn.dominio
        peor = max(math.dist(cn.punto(a + (b - a) * i / 100), list(bs.point(a + (b - a) * i / 100))[:2])
                   for i in range(101))
        r.cierto(peor < 1e-6, "y AutoCAD (vía ezdxf) la lee igual", f"{peor:.2e}")

    _navegador(r)


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    sp = E.Spline(puntos_ajuste=AJUSTE)
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""async (e) => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            await post('/api/operacion', {accion: 'Dibujar', agregar: [e]});
            await recargarTrazos(); Seleccion.limpiar(); encuadrarCaja(-200, -400, 1100, 500); }""", sp.a_dict())
        pagina.wait_for_timeout(300)
        antes = len({t["id"] for t in navegador.trazos(base)})
        navegador.comando(pagina, "DESFASE")
        navegador.comando(pagina, "20")
        pagina.wait_for_timeout(200)

        def libre(candidatos):
            return pagina.evaluate("""(candidatos) => {
                const caja = document.querySelector('#lienzo').getBoundingClientRect();
                for (const p of candidatos) {
                    const [x, y] = aPX(p[0], p[1]);
                    const e = document.elementFromPoint(caja.left + x, caja.top + y);
                    if (e && e.id === 'lienzo') return [caja.left + x, caja.top + y];
                }
                return null;
            }""", candidatos)

        c = sp.curva()
        sobre = [c.punto(t) for t in (0.5, 0.3, 0.7, 0.8, 0.2)]
        for p in (libre(sobre), libre([[q[0], q[1] + 150] for q in sobre])):
            r.exige(p is not None, "hay dónde picar sin tocar la barra flotante")
            pagina.mouse.move(*p)
            pagina.wait_for_timeout(80)
            pagina.mouse.click(*p)
            pagina.wait_for_timeout(500)
        pagina.wait_for_timeout(4000)          # el kernel tarda en cargar la primera vez
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
        r.igual(len({t["id"] for t in navegador.trazos(base)}), antes + 1,
                "DESFASE con el ratón deja una spline nueva")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
