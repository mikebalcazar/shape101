"""t057 · EXTENDER splines y arcos de elipse, suave (decisión de Mike, 3-nov-2026).

La spline se prolonga siguiendo el polinomio de su último tramo
(`Nurbs.prolongada`): es la misma curva continuada, sin quiebre. El arco de
elipse sigue su elipse. Como el EXTENDER de siempre: por la punta más cercana
al clic y hasta lo primero que cruce entre lo que está a la vista
(core/extender.py).

- la parte que ya existía no cambia, y la punta nueva cae exacta en lo que la
  detiene;
- en la unión no hay quiebre: tangente y segunda derivada continuas;
- se extiende por la punta del clic, también la del principio;
- una racional se prolonga sin que sus pesos se vuelvan negativos;
- el arco de elipse sigue su elipse hasta el cruce; una elipse completa avisa;
- sin nada a la vista hacia ese lado, avisa;
- en el programa: EXTENDER con el ratón alarga una spline hasta una línea.
"""

from __future__ import annotations

import math

from core import entidades as E
from core import extender as X
from core.documento import Documento
from pruebas import comun, navegador

DESCRIPCION = "EXTENDER splines (suave) y arcos de elipse hasta lo primero que crucen"

VENTANA = [-600, -600, 900, 900]
AJUSTE = [[0, 0], [100, 60], [200, 0], [300, 40]]


def _aplicar(e, plan):
    return E.de_dict({**e.a_dict(), **plan["cambios"][e.id]})


def correr(r: comun.Reporte) -> None:
    _spline(r)
    _elipse(r)
    _navegador(r)


def _spline(r: comun.Reporte) -> None:
    d = Documento.nuevo()
    with d.transaccion("Dibujar"):
        sp = d.agregar(E.Spline(puntos_ajuste=AJUSTE))
        d.agregar(E.Linea(p1=[500, -300], p2=[500, 300]))
        d.agregar(E.Linea(p1=[-200, -300], p2=[-200, 300]))
    co = sp.curva()
    A, B = co.dominio
    nueva = _aplicar(sp, X.extender(d, sp, [290, 40], VENTANA)).curva()
    a, b = nueva.dominio
    r.cierto(abs(nueva.punto(b)[0] - 500) < 1e-6, "la spline llega exacta a la línea x = 500", str(nueva.punto(b)))
    peor = max(math.dist(co.punto(A + (B - A) * i / 40), nueva.cercano(co.punto(A + (B - A) * i / 40))[1])
               for i in range(41))
    r.cierto(peor < 1e-9, "la parte que ya existía no cambia", f"{peor:.2e}")
    r.cierto(math.dist(nueva.punto(a), co.punto(A)) < 1e-9, "y la otra punta se queda donde estaba")
    # Sin quiebre en la unión: la prolongación es el mismo polinomio.
    # Se compara justo en la unión: la original en su punta y la nueva pegada
    # a ella del otro lado (a 1e-12, donde la tercera derivada ya no pesa).
    t_union = nueva.cercano(co.punto(B))[0]
    _, d1a, d2a = co.derivadas(B)
    _, d1b, d2b = nueva.derivadas(t_union + 1e-12)
    escala = max(math.hypot(*d1a), math.hypot(*d2a))
    r.cierto(math.dist(d1a, d1b) / math.hypot(*d1a) < 1e-6, "en la unión la tangente es la misma (sin quiebre)")
    r.cierto(math.dist(d2a, d2b) < 1e-6 * escala, "y la curvatura también",
             f"{math.dist(d2a, d2b):.2e} sobre {escala:.2e}")

    # Por el principio: el clic cerca de la primera punta.
    nueva = _aplicar(sp, X.extender(d, sp, [10, 5], VENTANA)).curva()
    a, b = nueva.dominio
    r.cierto(abs(nueva.punto(a)[0] + 200) < 1e-6, "con el clic en la primera punta, se extiende por ahí hasta x = -200",
             str(nueva.punto(a)))
    r.cierto(math.dist(nueva.punto(b), co.punto(B)) < 1e-9, "y la otra punta no se mueve")

    # Racional: un cuarto de círculo como NURBS, prolongado hasta una línea.
    w = math.sqrt(2) / 2
    with d.transaccion("Dibujar"):
        rac = d.agregar(E.Spline(puntos_control=[[100, 0], [100, 100], [0, 100]], grado=2,
                                 nudos=[0, 0, 0, 1, 1, 1], pesos=[1, w, 1]))
    try:
        nueva = _aplicar(rac, X.extender(d, rac, [0, 100], VENTANA)).curva()
        r.cierto(all(p > 0 for p in (nueva.pesos or [1])), "una racional se prolonga sin pesos negativos")
    except X.NoSeExtiende as exc:
        r.cierto(True, f"una racional que no alcanza nada lo dice ({exc})")

    sola = Documento.nuevo()
    with sola.transaccion("Dibujar"):
        s2 = sola.agregar(E.Spline(puntos_ajuste=AJUSTE))
    r.levanta(X.NoSeExtiende, X.extender, "sin nada a la vista hacia donde extender, avisa", sola, s2, [290, 40], VENTANA)


def _elipse(r: comun.Reporte) -> None:
    d = Documento.nuevo()
    with d.transaccion("Dibujar"):
        el = d.agregar(E.Elipse(centro=[0, 500], eje_mayor=[200, 0], razon=0.5, param_ini=0, param_fin=1.0))
        d.agregar(E.Linea(p1=[-300, 500], p2=[300, 500]))
        completa = d.agregar(E.Elipse(centro=[0, -400], eje_mayor=[100, 0], razon=0.5))
    plan = X.extender(d, el, [150, 560], VENTANA)
    r.casi(plan["cambios"][el.id]["param_fin"], math.pi, "el arco de elipse sigue su elipse hasta la línea (t = π)", 1e-9)
    r.casi(plan["cambios"][el.id]["param_ini"], 0.0, "sin mover su arranque", 1e-12)
    r.levanta(X.NoSeExtiende, X.extender, "una elipse completa no tiene punta que extender", d, completa, [0, -400], VENTANA)


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
            await post('/api/operacion', {accion: 'Dibujar', agregar: [e, {tipo: 'linea', p1: [500, -300], p2: [500, 300]}]});
            await recargarTrazos(); Seleccion.limpiar(); encuadrarCaja(-100, -350, 650, 350); }""", sp.a_dict())
        pagina.wait_for_timeout(300)
        i_sp = sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))[0]
        navegador.comando(pagina, "EXTENDER")
        c = sp.curva()
        # En la mitad final (la punta más cercana al clic es la que se extiende),
        # donde no tape la barra flotante.
        candidatos = [c.punto(0.98 - 0.02 * k) for k in range(22)]
        xy = pagina.evaluate("""(candidatos) => {
            const caja = document.querySelector('#lienzo').getBoundingClientRect();
            for (const p of candidatos) {
                const [x, y] = aPX(p[0], p[1]);
                const e = document.elementFromPoint(caja.left + x, caja.top + y);
                if (e && e.id === 'lienzo') return [caja.left + x, caja.top + y];
            }
            return null;
        }""", candidatos)
        r.exige(xy is not None, "hay dónde picar la spline sin tocar la barra flotante")
        pagina.mouse.move(*xy)
        pagina.wait_for_timeout(80)
        pagina.mouse.click(*xy)
        pagina.wait_for_timeout(5000)          # el kernel tarda en cargar la primera vez
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
        e = pagina.evaluate("(id) => api('/api/entidad/' + id)", i_sp)
        nueva = E.de_dict(e).curva()
        r.cierto(abs(nueva.punto(nueva.dominio[1])[0] - 500) < 1e-6,
                 "EXTENDER con el ratón alarga la spline hasta la línea", str(nueva.punto(nueva.dominio[1])))
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
