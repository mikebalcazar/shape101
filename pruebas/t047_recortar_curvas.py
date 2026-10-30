"""t047 · RECORTAR sobre splines y elipses.

Hasta la fase B1, RECORTAR rechazaba la spline y la elipse: sólo sabía de
líneas, arcos y polilíneas. Ahora la curva se parte exacta (core/recortar.py
sobre core/nurbs.py): el pedazo que queda **es** la curva de antes en ese tramo,
no una aproximación, y termina justo en el cruce.

Se comprueba:

- spline abierta con cruces a los dos lados del clic: quedan dos splines, cada
  una idéntica a la original en su tramo, empezando y terminando en los cruces;
- con un solo cruce: se acorta hasta él;
- spline cerrada: con dos cruces queda una abierta, la del otro lado, también
  cuando ese lado pasa por la costura;
- elipse completa y arco de elipse, con sus parámetros exactos;
- un cruce pegado a la punta (dentro de la tolerancia) no es corte;
- lo recortado se escribe en el DXF tal cual;
- en el programa: RECORTAR con el ratón parte la spline en el cruce exacto, y
  un Ctrl+Z la devuelve entera.
"""

from __future__ import annotations

import json
import math
import urllib.request

import ezdxf

from core import entidades as ent
from core import nurbs
from core import recortar as mod_recortar
from core.documento import Documento
from export import dxf as export_dxf
from pruebas import comun, navegador

DESCRIPCION = "RECORTAR splines y elipses: la curva se parte exacta en el cruce"

AJUSTE = [[0, 0], [300, 200], [600, -150], [900, 100], [1200, 0]]
CV_CERRADA = [[0, 0], [400, -100], [600, 200], [400, 500], [0, 400], [-200, 200]]


def _cruce_vertical(c, x, cerca_de=None):
    """El punto de la curva con esa x, por bisección sobre la curva exacta."""
    pares = c._teselar_t(0.01)
    raices = []
    for (t0, p0), (t1, p1) in zip(pares, pares[1:]):
        if (p0[0] - x) * (p1[0] - x) <= 0 and p0[0] != p1[0]:
            for _ in range(200):
                m = (t0 + t1) / 2
                if (c.punto(t0)[0] - x) * (c.punto(m)[0] - x) <= 0:
                    t1 = m
                else:
                    t0 = m
            raices.append(c.punto((t0 + t1) / 2))
    if cerca_de is not None:
        raices.sort(key=lambda q: math.dist(q, cerca_de))
    return raices


def _sobre(c, q) -> float:
    return math.dist(c.cercano(q)[1], q)


def _pedazo_sobre(r, original, pedazo, que):
    a, b = pedazo.dominio
    peor = max(_sobre(original, pedazo.punto(a + (b - a) * i / 60)) for i in range(61))
    r.cierto(peor < 1e-7, que, f"se separa {peor:.2e}")


def correr(r: comun.Reporte) -> None:
    _abierta(r)
    _cerrada(r)
    _elipses(r)
    _bordes(r)
    _navegador(r)


def _abierta(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(ent.Spline(puntos_ajuste=AJUSTE))
    c = sp.curva()
    q1 = _cruce_vertical(c, 300)[0]
    q2 = _cruce_vertical(c, 800)[0]
    plan = mod_recortar.recortar(doc, sp, c.punto(0.5), [q1, q2])
    r.igual(len(plan["agregar"]), 1, "con cruces a los dos lados quedan dos splines")
    izq = ent.de_dict({**plan["cambios"][sp.id], "tipo": "spline"})
    der = ent.de_dict(plan["agregar"][0])
    ci, cd = izq.curva(), der.curva()
    _pedazo_sobre(r, c, ci, "la de la izquierda es la curva de antes en su tramo")
    _pedazo_sobre(r, c, cd, "y la de la derecha también")
    r.punto(ci.punto(ci.dominio[0]), AJUSTE[0], "la izquierda arranca donde arrancaba la original")
    r.punto(ci.punto(ci.dominio[1]), q1, "y termina en el cruce exacto de x=300")
    r.punto(cd.punto(cd.dominio[0]), q2, "la derecha arranca en el cruce de x=800")
    r.punto(cd.punto(cd.dominio[1]), AJUSTE[-1], "y termina donde terminaba la original")
    r.igual((izq.puntos_ajuste, bool(izq.nudos)), ([], True),
            "los pedazos guardan su NURBS y sueltan los puntos de ajuste (ya no pasan por todos)")

    # Un solo cruce: se acorta hasta él, por el lado del clic.
    plan = mod_recortar.recortar(doc, sp, c.punto(0.05), [q1])
    resto = ent.de_dict({**plan["cambios"][sp.id], "tipo": "spline"}).curva()
    r.igual(plan["agregar"], [], "con un solo cruce no se agrega nada")
    r.punto(resto.punto(resto.dominio[0]), q1, "y se quita desde la punta hasta el cruce")
    r.punto(resto.punto(resto.dominio[1]), AJUSTE[-1], "dejando lo del otro lado entero")

    # Y lo recortado va al DXF tal cual. (Aquí se le ponen los campos a mano;
    # en el programa los aplica /api/operacion, como se ve abajo.)
    e = doc.entidades[sp.id]
    for k in ("puntos_control", "nudos", "pesos", "puntos_ajuste", "grado", "cerrada"):
        setattr(e, k, plan["cambios"][sp.id][k])
    with comun.carpeta() as tmp:
        export_dxf.escribir(doc, tmp / "t047.dxf")
        s = next(x for x in ezdxf.readfile(str(tmp / "t047.dxf")).modelspace() if x.dxftype() == "SPLINE")
        bs = s.construction_tool()
        a, b = resto.dominio
        peor = max(math.dist(resto.punto(a + (b - a) * i / 100), list(bs.point(a + (b - a) * i / 100))[:2])
                   for i in range(101))
        r.cierto(peor < 1e-6, "la spline recortada sale al DXF igual", f"{peor:.2e}")


def _cerrada(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(ent.Spline(puntos_control=CV_CERRADA, cerrada=True))
    c = sp.curva()
    a, b = c.dominio
    # Dos cruces con x=200: uno arriba y otro abajo.
    arriba, abajo = sorted(_cruce_vertical(c, 200), key=lambda q: -q[1])[:2]
    t_arriba, t_abajo = c.cercano(arriba)[0], c.cercano(abajo)[0]
    for lado, clic in (("derecho", [600, 200]), ("izquierdo", [-200, 200])):
        plan = mod_recortar.recortar(doc, sp, clic, [arriba, abajo])
        resto = ent.de_dict({**plan["cambios"][sp.id], "tipo": "spline"})
        cr = resto.curva()
        r.cierto(not resto.cerrada, f"quitando el lado {lado}, la cerrada queda abierta")
        _pedazo_sobre(r, c, cr, f"y lo que queda es la curva de antes (lado {lado} fuera)")
        puntas = [cr.punto(cr.dominio[0]), cr.punto(cr.dominio[1])]
        r.cierto(all(min(math.dist(p, q) for q in (arriba, abajo)) < 1e-7 for p in puntas),
                 f"con sus puntas en los dos cruces (lado {lado} fuera)")
        r.cierto(_sobre(cr, clic if _sobre(c, clic) < 1 else c.cercano(clic)[1]) > 50,
                 f"y el lado {lado}, el del clic, ya no está")
    r.cierto(min(t_arriba, t_abajo) > a and max(t_arriba, t_abajo) < b,
             "(uno de los dos casos pasa por la costura de la curva cerrada)")


def _elipses(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        el = doc.agregar(ent.Elipse(centro=[0, 0], eje_mayor=[300, 0], razon=0.5))
    P = lambda t: [300 * math.cos(t), 150 * math.sin(t)]
    cruces = [P(math.radians(60)), P(math.radians(300))]
    plan = mod_recortar.recortar(doc, el, P(0), cruces)        # se quita el lado derecho
    cam = plan["cambios"][el.id]
    r.casi(cam["param_ini"] % (2 * math.pi), math.radians(60), "la elipse completa queda en arco desde 60°")
    r.casi(cam["param_fin"] % (2 * math.pi), math.radians(300), "hasta 300°: se fue el lado del clic")

    with doc.transaccion("Dibujar"):
        arco = doc.agregar(ent.Elipse(centro=[0, 0], eje_mayor=[300, 0], razon=0.5,
                                      param_ini=0, param_fin=math.pi))
    plan = mod_recortar.recortar(doc, arco, P(math.radians(90)), [P(math.radians(45)), P(math.radians(135))])
    r.igual(len(plan["agregar"]), 1, "un arco de elipse con cruces a los dos lados queda en dos")
    r.casi(plan["cambios"][arco.id]["param_fin"], math.radians(45), "el primero termina a 45°")
    r.casi(plan["agregar"][0]["param_ini"], math.radians(135), "y el segundo arranca a 135°")


def _bordes(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(ent.Spline(puntos_ajuste=AJUSTE))
    c = sp.curva()
    r.levanta(mod_recortar.NoSeRecorta, mod_recortar.recortar, "sin cruces no hay recorte",
              doc, sp, c.punto(0.5), [])
    casi_punta = c.punto(c.dominio[1] - 1e-7)          # a micras de la punta: es la punta
    r.levanta(mod_recortar.NoSeRecorta, mod_recortar.recortar,
              "un cruce pegado a la punta (dentro de la tolerancia) no es corte",
              doc, sp, c.punto(0.9), [casi_punta])
    lejos = [5000, 5000]
    r.levanta(mod_recortar.NoSeRecorta, mod_recortar.recortar,
              "un «cruce» que no está sobre la curva se ignora", doc, sp, c.punto(0.5), [lejos])


def _ids(base) -> list[str]:
    return sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))


def _entidad(base, id_):
    with urllib.request.urlopen(base + f"/api/entidad/{id_}", timeout=5) as f:
        return json.loads(f.read().decode("utf-8"))


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    sp = ent.Spline(puntos_ajuste=AJUSTE)
    c = sp.curva()
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""() => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            encuadrarCaja(-100, -400, 1300, 400);
        }""")
        pagina.wait_for_timeout(200)
        pagina.evaluate("""async (e) => { await post('/api/operacion', {accion: 'Dibujar', agregar: e});
                                          await recargarTrazos(); Seleccion.limpiar(); }""",
                        [sp.a_dict(), {"tipo": "linea", "p1": [300, -400], "p2": [300, 400]},
                         {"tipo": "linea", "p1": [800, -400], "p2": [800, 400]}])
        pagina.wait_for_timeout(300)
        ids = _ids(base)
        i_sp = ids[0]
        clic = c.punto(c.cercano([550, 0])[0])
        navegador.comando(pagina, "RECORTAR")
        x, y = pagina.evaluate("""(p) => {
            const [x, y] = aPX(p[0], p[1]);
            const caja = document.querySelector('#lienzo').getBoundingClientRect();
            return [caja.left + x, caja.top + y];
        }""", clic)
        pagina.mouse.move(x, y)
        pagina.wait_for_timeout(80)
        pagina.mouse.click(x, y)
        pagina.wait_for_timeout(600)
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
        despues = _ids(base)
        r.igual(len(despues), 4, "RECORTAR con el ratón deja dos splines y las dos líneas")
        izq = ent.de_dict(_entidad(base, i_sp))
        ci = izq.curva()
        q1 = _cruce_vertical(c, 300)[0]
        r.cierto(math.dist(ci.punto(ci.dominio[1]), q1) < 1e-6,
                 "la spline se parte en el cruce exacto con x=300",
                 f"{ci.punto(ci.dominio[1])} vs {q1}")
        pagina.keyboard.press("Control+z")
        pagina.wait_for_timeout(600)
        vuelta = ent.de_dict(_entidad(base, i_sp))
        r.igual((len(_ids(base)), vuelta.puntos_ajuste), (3, AJUSTE),
                "y Ctrl+Z la devuelve entera, con sus puntos de ajuste")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
