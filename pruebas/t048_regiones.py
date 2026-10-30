"""t048 · Regiones: UNION, RESTA e INTERSECCION de contornos cerrados, exactas.

Es el CurveBoolean de Rhino: dos o más contornos cerrados se combinan y queda
el borde del resultado (core/regiones.py, con OpenCASCADE). La prueba no le
cree al kernel el área —con B-splines la da con errores de unidades—: la calcula
aparte, exacta, por Green sobre la curva (`area_de_contorno`), y la compara con
la de la fórmula. Y comprueba la geometría, no sólo el número:

- rectángulo y círculo: la unión, la resta y la intersección salen como **una
  polilínea con su arco** (bulge), con el arco del lado correcto;
- un círculo adentro sale como hueco, y dos piezas separadas salen como dos;
- con una spline de por medio, la spline del resultado **es** la de entrada
  (sobre ella a una millonésima), las piezas quedan agrupadas, y unión +
  intersección suman exactamente las dos áreas;
- elipse: área de la fórmula;
- lo que no se puede (abierto, arco de elipse, intersección vacía) avisa;
- en el programa: el comando UNION con lo seleccionado reemplaza los dos
  contornos por uno, y Ctrl+Z los devuelve.
"""

from __future__ import annotations

import math

from core import entidades as E
from core import regiones as R
from core.documento import Documento
from pruebas import comun, navegador

DESCRIPCION = "regiones: UNION, RESTA e INTERSECCION exactas de contornos cerrados"

RECT = [[0, 0], [600, 0], [600, 400], [0, 400]]
SPLINE = [[500, 100], [800, 50], [850, 250], [550, 300]]
TOL = 1e-6


def _doc():
    d = Documento.nuevo()
    with d.transaccion("Dibujar"):
        ents = {
            "rect": d.agregar(E.Polilinea(puntos=RECT, cerrada=True)),
            "circ": d.agregar(E.Circulo(centro=[600, 200], radio=150)),
            "adentro": d.agregar(E.Circulo(centro=[200, 200], radio=50)),
            "lejos": d.agregar(E.Circulo(centro=[2000, 200], radio=50)),
            "spline": d.agregar(E.Spline(puntos_control=SPLINE, cerrada=True)),
            "elipse": d.agregar(E.Elipse(centro=[0, 200], eje_mayor=[100, 0], razon=0.5)),
            "abierta": d.agregar(E.Polilinea(puntos=[[0, 0], [100, 100], [200, 0]], cerrada=False)),
            "arco_el": d.agregar(E.Elipse(centro=[0, 0], eje_mayor=[100, 0], razon=0.5, param_ini=0, param_fin=1)),
        }
    return d, ents


def _medio_del_arco(pol):
    """El punto medio del único tramo curvo de la polilínea."""
    pts = pol["puntos"]
    for i, p in enumerate(pts):
        if len(p) > 2 and abs(p[2]) > 1e-12:
            q = pts[(i + 1) % len(pts)]
            ang = 4 * math.atan(p[2])
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            cuerda = math.dist(p[:2], q[:2])
            flecha = cuerda / 2 * math.tan(abs(ang) / 4)
            dx, dy = (q[0] - p[0]) / cuerda, (q[1] - p[1]) / cuerda
            sg = 1 if ang > 0 else -1
            return [mx + sg * flecha * dy, my - sg * flecha * dx]
    return None


def correr(r: comun.Reporte) -> None:
    _rect_y_circulo(r)
    _huecos_y_piezas(r)
    _con_spline(r)
    _avisos(r)
    _navegador(r)


def _rect_y_circulo(r: comun.Reporte) -> None:
    d, e = _doc()
    medio = math.pi * 150 ** 2 / 2
    casos = {"union": (240000 + medio, [750, 200]),
             "resta": (240000 - medio, [450, 200]),
             "interseccion": (medio, [450, 200])}       # lo común es la mitad izquierda del círculo
    for op, (area, arco_en) in casos.items():
        p = R.combinar(d, [e["rect"].id, e["circ"].id], op)
        r.igual([[x["tipo"] for x in c] for c in p["contornos"]], [["polilinea"]],
                f"{op}: sale una sola polilínea cerrada")
        r.casi(p["area"], area, f"{op}: con el área de la fórmula", TOL)
        pol = p["contornos"][0][0]
        r.cierto(pol["cerrada"], f"{op}: cerrada")
        m = _medio_del_arco(pol)
        r.cierto(m is not None and math.dist(m, arco_en) < TOL,
                 f"{op}: el arco es del círculo y va por el lado correcto (pasa por {arco_en})", str(m))


def _huecos_y_piezas(r: comun.Reporte) -> None:
    d, e = _doc()
    p = R.combinar(d, [e["rect"].id, e["adentro"].id], "resta")
    r.igual([[x["tipo"] for x in c] for c in p["contornos"]], [["polilinea"], ["circulo"]],
            "un círculo adentro deja el borde y un hueco (el círculo)")
    r.casi(p["area"], 240000 - math.pi * 2500, "y el área descuenta el hueco", TOL)
    p = R.combinar(d, [e["rect"].id, e["lejos"].id], "union")
    r.igual(p["piezas"], 2, "dos contornos separados unidos siguen siendo dos piezas")
    p = R.combinar(d, [e["rect"].id, e["elipse"].id], "union")
    r.casi(p["area"], 240000 + math.pi * 100 * 50 / 2, "rectángulo con media elipse: área de la fórmula", TOL)
    r.cierto(any(x["tipo"] == "elipse" for x in p["contornos"][0]),
             "y la elipse sale como arco de elipse, no como polilínea")


def _con_spline(r: comun.Reporte) -> None:
    d, e = _doc()
    a_rect = 240000.0
    a_sp = R.area_de_contorno([e["spline"].a_dict()])
    un = R.combinar(d, [e["rect"].id, e["spline"].id], "union")
    inter = R.combinar(d, [e["rect"].id, e["spline"].id], "interseccion")
    r.casi(un["area"] + inter["area"], a_rect + a_sp,
           "unión + intersección = las dos áreas, exacto (con una spline de por medio)", TOL)
    borde = un["contornos"][0]
    r.cierto(len(borde) >= 2 and {x["tipo"] for x in borde} == {"polilinea", "spline"},
             "el borde de la unión sale en piezas: polilínea y spline", str([x["tipo"] for x in borde]))
    original = e["spline"].curva()
    sp = E.de_dict(next(x for x in borde if x["tipo"] == "spline")).curva()
    a, b = sp.dominio
    peor = max(math.dist(original.cercano(sp.punto(a + (b - a) * i / 100))[1], sp.punto(a + (b - a) * i / 100))
               for i in range(101))
    r.cierto(peor < TOL, "la spline del resultado es la de entrada, no una aproximación", f"{peor:.2e}")
    poli = next(x for x in borde if x["tipo"] == "polilinea")
    sobre_rect = all(abs(q[0]) < TOL or abs(q[0] - 600) < TOL or abs(q[1]) < TOL or abs(q[1] - 400) < TOL
                     for q in poli["puntos"])
    r.cierto(sobre_rect, "y la polilínea va sobre el rectángulo")
    sp_res = E.de_dict(next(x for x in inter["contornos"][0] if x["tipo"] == "spline"))
    puntas = [sp_res.curva().punto(t) for t in sp_res.curva().dominio]
    r.cierto(all(abs(q[0] - 600) < TOL for q in puntas),
             "la intersección corta la spline justo en el lado del rectángulo (x = 600)",
             str(puntas))


def _avisos(r: comun.Reporte) -> None:
    d, e = _doc()
    r.levanta(R.NoSeCombina, R.combinar, "una polilínea abierta no se combina",
              d, [e["rect"].id, e["abierta"].id], "union")
    r.levanta(R.NoSeCombina, R.combinar, "un arco de elipse tampoco",
              d, [e["rect"].id, e["arco_el"].id], "union")
    r.levanta(R.NoSeCombina, R.combinar, "la intersección de dos que no se tocan avisa que queda vacía",
              d, [e["rect"].id, e["lejos"].id], "interseccion")
    r.levanta(R.NoSeCombina, R.combinar, "con un solo contorno no hay nada que combinar",
              d, [e["rect"].id], "union")


def _ids(base) -> list[str]:
    return sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""async () => {
            await post('/api/operacion', {accion: 'Dibujar', agregar: [
                {tipo: 'polilinea', puntos: [[0,0],[600,0],[600,400],[0,400]], cerrada: true},
                {tipo: 'circulo', centro: [600, 200], radio: 150}]});
            await recargarTrazos(); Seleccion.limpiar(); }""")
        pagina.wait_for_timeout(300)
        antes = _ids(base)
        pagina.evaluate("(ids) => { for (const i of ids) estado.sel.add(i); }", antes)
        navegador.comando(pagina, "UNION")
        pagina.wait_for_timeout(4000)          # el kernel tarda en cargar la primera vez
        despues = _ids(base)
        r.igual(len(despues), 1, "UNION con los dos seleccionados deja un solo contorno")
        r.cierto(not set(despues) & set(antes), "y es uno nuevo: los dos de antes se fueron")
        pagina.keyboard.press("Control+z")
        pagina.wait_for_timeout(600)
        r.igual(sorted(_ids(base)), sorted(antes), "Ctrl+Z devuelve el rectángulo y el círculo")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
