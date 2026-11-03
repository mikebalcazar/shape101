"""t056 · Análisis de curvatura: mapa de colores y cebra (el CurvatureAnalysis y el Zebra de Rhino).

El motor saca, en cada vértice de una malla más fina, la **normal exacta** y
las **curvaturas** de la superficie misma (core/solido/analisis.py). Se mide
contra lo que tiene fórmula:

- esfera de radio R: curvatura gaussiana K = 1/R² y media |H| = 1/R en todos
  lados —también en los polos, donde la parametrización es singular y la
  primera versión ponía cero—, y normales radiales;
- cilindro de radio R: K = 0 y |H| = 1/(2R);
- las caras de una caja: K = H = 0;
- una pieza que vive en otro plano: sus normales se giran con ella.

En el programa: CURVATURA pinta por curvatura (se lee el color de los píxeles:
una caja es verde, «plano») y repetirlo vuelve al estilo de antes; CEBRA pinta
franjas negras y blancas; y ESTILO sin nada sigue pasando sólo entre los tres
estilos de vista.
"""

from __future__ import annotations

import math

from core import entidades as E
from core import tolerancia
from core.documento import Documento
from core.solido import cuerpo as mod
from core.solido import rutas
from pruebas import comun, navegador

DESCRIPCION = "análisis de curvatura: K y H de libro, normales exactas, mapa y cebra en pantalla"


def _doc():
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    tolerancia.enchufar(lambda: doc)
    mod.olvidar()
    return doc


def _agregar(doc, *ents):
    with doc.transaccion("Dibujar"):
        return [doc.agregar(e).id for e in ents]


def _todos(a, clave):
    return [k for c in a["caras"] for k in c[clave]]


def correr(r: comun.Reporte) -> None:
    previo = tolerancia._doc_actual
    try:
        _motor(r)
    finally:
        tolerancia.enchufar(previo)
        mod.olvidar()
    _navegador(r)


def _motor(r: comun.Reporte) -> None:
    doc = _doc()
    R = 50.0
    ids = _agregar(doc, E.Arco(centro=[0, 0], radio=R, ang_ini=270, ang_fin=90), E.Linea(p1=[0, -100], p2=[0, 100]))
    a = rutas.analisis(rutas.revolver(rutas.Seleccion(ids=ids))["id"])
    kg, km = _todos(a, "kg"), [abs(h) for h in _todos(a, "km")]
    r.cierto(len(kg) > 100, "la esfera se analiza en una malla fina", str(len(kg)))
    r.cierto(max(abs(k - 1 / R ** 2) for k in kg) < 1e-9,
             "esfera: K = 1/R² en todos los vértices, polos incluidos", f"{min(kg):.3e}..{max(kg):.3e}")
    r.cierto(max(abs(h - 1 / R) for h in km) < 1e-9, "esfera: |H| = 1/R en todos")
    peor = 0.0
    for c in a["caras"]:
        v, n = c["v"], c["n"]
        for k in range(0, len(v), 3):
            p = v[k:k + 3]
            rr = math.sqrt(sum(x * x for x in p))
            if rr > 1e-9:
                peor = max(peor, 1 - abs(sum(p[q] / rr * n[k + q] for q in range(3))))
    r.cierto(peor < 1e-9, "y sus normales son radiales", f"{peor:.2e}")

    ids = _agregar(doc, E.Linea(p1=[50, 0], p2=[50, 100]), E.Linea(p1=[0, -10], p2=[0, 200]))
    a = rutas.analisis(rutas.revolver(rutas.Seleccion(ids=ids))["id"])
    r.cierto(max(abs(k) for k in _todos(a, "kg")) < 1e-12, "cilindro: K = 0 (es desarrollable)")
    r.cierto(max(abs(abs(h) - 1 / 100) for h in _todos(a, "km")) < 1e-9, "cilindro: |H| = 1/(2R)")

    caja = E.Polilinea(puntos=[[0, 0], [100, 0], [100, 60], [0, 60]], cerrada=True)
    a = rutas.analisis(rutas.extruir(rutas.Extruir(ids=_agregar(doc, caja), mm=18))["id"])
    r.cierto(max(abs(k) for k in _todos(a, "kg") + _todos(a, "km")) < 1e-12, "las caras de una caja: K = H = 0")

    # Otra ventana: un perfil de la Frontal girado da una pieza en XZ; sus
    # normales salen unitarias y perpendiculares a la superficie en el mundo.
    perfil = E.Linea(p1=[50, 0], p2=[50, 100])
    perfil.plano = "XZ"
    eje = E.Linea(p1=[0, -10], p2=[0, 200])
    eje.plano = "XZ"
    a = rutas.analisis(rutas.revolver(rutas.Seleccion(ids=_agregar(doc, perfil, eje)))["id"])
    unit = max(abs(math.sqrt(sum(c["n"][k + q] ** 2 for q in range(3))) - 1)
               for c in a["caras"] for k in range(0, len(c["n"]), 3))
    r.cierto(unit < 1e-9, "en una pieza de otra ventana las normales siguen unitarias (se giraron con ella)")


def _pixel(pagina, punto):
    return pagina.evaluate("""(p) => {
        const lienzo = document.querySelector('#lienzo');
        const [x, y] = aPX(p[0], p[1], p[2]);
        const k = window.devicePixelRatio || 1;
        const d = lienzo.getContext('2d').getImageData(Math.round(x * k), Math.round(y * k), 1, 1).data;
        return [d[0], d[1], d[2]];
    }""", punto)


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate("() => { const v = Cuerpos.colorCurvatura(1, 1), a = Cuerpos.colorCurvatura(-1, 1), "
                                 "g = Cuerpos.colorCurvatura(0, 1); return v.startsWith('rgb(225') && a.startsWith('rgb(50') && g === 'rgb(70,190,90)'; }"),
                 "la escala: domo rojo, silla azul, plano verde")
        pagina.evaluate("""async () => {
            await post('/api/operacion', {accion: 'Dibujar', agregar: [
                {tipo: 'polilinea', puntos: [[0,0],[300,0],[300,200],[0,200]], cerrada: true}]});
            await recargarTrazos(); }""")
        pagina.wait_for_timeout(300)
        ids = sorted({t["id"] for t in navegador.trazos(base)})
        pagina.evaluate("""async (ids) => {
            await fetch('/api/cuerpo/extruir', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ids, mm: 40})});
            await Cuerpos.refrescar(); encuadrarCaja(-100, -100, 400, 300); }""", ids)
        pagina.wait_for_timeout(4000)
        centro = [150, 100, 40]
        # Las pruebas comparten la carpeta del usuario: el estilo que dejó otra
        # (t042 deja «alambrico») es el que tiene que volver.
        previo = pagina.evaluate("() => Cuerpos.estilo()")
        navegador.comando(pagina, "CURVATURA")
        pagina.wait_for_timeout(3000)
        pagina.evaluate("() => { if (window.invalidarPlano) invalidarPlano(); if (window.pintar) pintar(); }")
        pagina.wait_for_timeout(500)
        r.igual(pagina.evaluate("() => estado.prefs.estilo_3d"), "curvatura", "CURVATURA enciende el mapa")
        r.cierto(pagina.evaluate("() => Cuerpos.analisis.size") >= 1, "y trae el análisis de la pieza")
        px = _pixel(pagina, centro)
        r.cierto(px[1] > px[0] + 60 and px[1] > px[2] + 60,
                 "la tapa de una caja se pinta verde (plano)", str(px))
        navegador.comando(pagina, "CURVATURA")
        pagina.wait_for_timeout(300)
        r.igual(pagina.evaluate("() => estado.prefs.estilo_3d"), previo, "repetir CURVATURA vuelve al estilo de antes")
        navegador.comando(pagina, "CEBRA")
        pagina.wait_for_timeout(1500)
        pagina.evaluate("() => { if (window.invalidarPlano) invalidarPlano(); if (window.pintar) pintar(); }")
        pagina.wait_for_timeout(300)
        px = _pixel(pagina, centro)
        r.cierto(max(px) - min(px) < 12 and (max(px) < 40 or min(px) > 225),
                 "CEBRA pinta en franjas negras y blancas", str(px))
        navegador.comando(pagina, "ESTILO")
        pagina.wait_for_timeout(300)
        r.cierto(pagina.evaluate("() => estado.prefs.estilo_3d") in ("basico", "alambrico", "renderizado"),
                 "ESTILO sin nada vuelve a los estilos de vista (el análisis no entra al ciclo)")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
