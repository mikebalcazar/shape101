"""t043 · Curvas exactas: la spline es su NURBS, en pantalla, en el osnap y en el DXF.

Hasta 0.21.9 la spline no guardaba nudos ni pesos. Se pintaba con Catmull-Rom,
el osnap la veía como la poligonal de sus puntos de ajuste, y al DXF salía con
los puntos solos para que cada programa la volviera a interpolar a su modo:
tres curvas distintas con el mismo nombre, separadas hasta 63 unidades en una
curva de un metro. La que se cortaba no era la que se veía.

Aquí se comprueba, contra referencias que no son nuestras (ezdxf evalúa e
interpola por su cuenta), que ahora las tres son la misma:

- **La matemática**: evaluar, interpolar abierta y cerrada, derivadas exactas,
  y un círculo racional que da el radio exacto en todos lados.
- **El punto más cercano** en curvas al azar, incluidas las que casi se tocan
  a sí mismas, que es donde se equivocaba la primera versión.
- **Lo que no cambia**: una spline CV abierta de un archivo viejo sale idéntica.
- **Lo que se pinta** no se separa de la curva más que la flecha.
- **El osnap**: extremos y medio exactos, y ningún extremo falso a media curva.
- **El DXF**: lo que lee AutoCAD (vía ezdxf) es punto por punto lo mismo.
"""

from __future__ import annotations

import math
import random

import ezdxf
from ezdxf.math import BSpline, fit_points_to_cad_cv

from core import dibujo
from core import entidades as ent
from core import geometria
from core import nurbs
from core.documento import Documento
from export import dxf as export_dxf
from pruebas import comun

DESCRIPCION = "curvas exactas: la spline es su NURBS en pantalla, osnap y DXF"

AJUSTE = [[0, 0], [300, 200], [600, -150], [900, 100], [1000, 400]]
CONTROL = [[0, 0], [150, 300], [450, 320], [600, 0], [800, -200], [1000, 100]]


def correr(r: comun.Reporte) -> None:
    _matematica(r)
    _cercano(r)
    _lo_viejo_no_cambia(r)
    _pintado(r)
    _osnap(r)
    _dxf(r)


def _muestras(c, n=400):
    a, b = c.dominio
    return [a + (b - a) * i / n for i in range(n + 1)]


def _matematica(r: comun.Reporte) -> None:
    # Evaluar: contra el B-spline de ezdxf con los mismos nudos y pesos.
    random.seed(7)
    ctrl = [[random.uniform(0, 800), random.uniform(0, 500)] for _ in range(9)]
    pesos = [random.uniform(0.4, 2.5) for _ in ctrl]
    c = nurbs.Nurbs(3, ctrl, nurbs.sujeta_uniforme(ctrl).nudos, pesos)
    ref = BSpline([(x, y, 0) for x, y in ctrl], order=4, knots=c.nudos, weights=pesos)
    peor = max(math.dist(c.punto(t), list(ref.point(t))[:2]) for t in _muestras(c))
    r.cierto(peor < 1e-9, "una NURBS racional evalúa igual que la de ezdxf",
             f"diferencia {peor:.2e}")

    # Un círculo es una NURBS racional de grado 2 (nueve puntos, pesos √2/2 en
    # las esquinas). Es la prueba de que las cónicas caben exactas, como en Rhino.
    w = math.sqrt(2) / 2
    R = 250.0
    cuadrado = [[R, 0], [R, R], [0, R], [-R, R], [-R, 0], [-R, -R], [0, -R], [R, -R], [R, 0]]
    circulo = nurbs.Nurbs(2, cuadrado, [0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4],
                          [1, w, 1, w, 1, w, 1, w, 1])
    peor = max(abs(math.hypot(*circulo.punto(t)) - R) for t in _muestras(circulo))
    r.cierto(peor < 1e-9, "un círculo NURBS racional tiene el radio exacto en toda la vuelta",
             f"desviación {peor:.2e}")

    # Derivadas exactas: contra diferencias centradas, con margen de diferencias.
    for nombre, cur in (("interpolada", nurbs.interpolar_cad(AJUSTE)), ("racional", c)):
        peor = 0.0
        for t in _muestras(cur, 60)[1:-1]:
            h = (cur.dominio[1] - cur.dominio[0]) * 1e-6
            p0, p1 = cur.punto(t - h), cur.punto(t + h)
            fd = [(p1[j] - p0[j]) / (2 * h) for j in range(2)]
            d1 = cur.derivada(t)
            peor = max(peor, math.dist(d1, fd) / max(1.0, math.hypot(*d1)))
        r.cierto(peor < 1e-5, f"la derivada exacta de la {nombre} cuadra con la numérica",
                 f"error relativo {peor:.2e}")

    # Interpolar como AutoCAD: igual a la de ezdxf, que imita a AutoCAD/BricsCAD.
    c = nurbs.interpolar_cad(AJUSTE)
    ref = fit_points_to_cad_cv([(x, y, 0) for x, y in AJUSTE])
    peor = max(math.dist(c.punto(t), list(ref.point(t))[:2]) for t in _muestras(c))
    r.cierto(peor < 1e-9, "la spline por puntos se interpola como en AutoCAD",
             f"diferencia {peor:.2e}")
    peor = max(math.dist(c.cercano(p)[1], p) for p in AJUSTE)
    r.cierto(peor < 1e-9, "y pasa por cada uno de sus puntos de ajuste", f"{peor:.2e}")

    # Cerrada por puntos: pasa por ellos y la costura no tiene pico.
    c = nurbs.interpolar_cerrada(AJUSTE)
    peor = max(math.dist(c.cercano(p)[1], p) for p in AJUSTE)
    r.cierto(peor < 1e-9, "la spline cerrada por puntos pasa por todos", f"{peor:.2e}")
    a, b = c.dominio
    r.cierto(math.dist(c.punto(a), c.punto(b)) < 1e-9, "y cierra: empieza donde termina")
    ta, tb = c.derivada(a), c.derivada(b)
    r.cierto(math.dist(ta, tb) / math.hypot(*ta) < 1e-9,
             "sin pico en la costura: la tangente de salida es la de llegada")

    # CV cerrada: lo mismo. La de antes cerraba con un segmento recto.
    c = nurbs.periodica_uniforme(CONTROL)
    a, b = c.dominio
    ta, tb = c.derivada(a), c.derivada(b)
    r.cierto(math.dist(c.punto(a), c.punto(b)) < 1e-9
             and math.dist(ta, tb) / math.hypot(*ta) < 1e-9,
             "la spline CV cerrada da la vuelta suave, sin pico ni tramo recto")


def _cercano(r: comun.Reporte) -> None:
    """Sobre la curva misma, el cercano tiene que dar error cero. La primera
    versión fallaba hasta 22 unidades donde la curva casi se toca a sí misma
    o hace un lazo, y 0.13 junto a una cúspide."""
    peor = 0.0
    casos = 0
    for semilla in range(24):
        random.seed(semilla)
        ctrl = [[random.uniform(0, 500), random.uniform(0, 300)]
                for _ in range(random.randint(4, 12))]
        c = (nurbs.sujeta_uniforme(ctrl), nurbs.interpolar_cad(ctrl),
             nurbs.interpolar_cerrada(ctrl), nurbs.periodica_uniforme(ctrl))[semilla % 4]
        for t in _muestras(c, 60):
            p = c.punto(t)
            peor = max(peor, math.dist(p, c.cercano(p)[1]))
            casos += 1
    r.cierto(peor < 1e-7, f"el punto más cercano es exacto en {casos} puntos de curvas al azar",
             f"peor {peor:.2e}")


def _lo_viejo_no_cambia(r: comun.Reporte) -> None:
    """Una spline CV abierta de un archivo de 0.21.9 (sin nudos) abre igual."""
    vieja = ent.de_dict({"tipo": "spline", "puntos_control": CONTROL, "grado": 3})
    r.igual(vieja.nudos, [], "un archivo viejo no trae nudos y abre igual")
    c = vieja.curva()
    # La de antes: B-spline sujeta y uniforme, la misma que arma ezdxf así.
    n, k = len(CONTROL), 3
    nudos = [0.0] * (k + 1) + [(i + 1) / (n - k) for i in range(n - k - 1)] + [1.0] * (k + 1)
    ref = BSpline([(x, y, 0) for x, y in CONTROL], order=k + 1, knots=nudos)
    peor = max(math.dist(c.punto(t), list(ref.point(t))[:2]) for t in _muestras(c))
    r.cierto(peor < 1e-9, "la spline CV abierta conserva su forma de siempre",
             f"diferencia {peor:.2e}")


def _pintado(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(ent.Spline(puntos_ajuste=AJUSTE))
    trazos = dibujo.trazos_de(doc, sp)
    lineas = [t["puntos"] for t in trazos if t.get("puntos")]
    r.exige(lineas, "la spline se pinta")
    c = sp.curva()
    pintados = [p for ln in lineas for p in ln]
    peor = max(math.dist(p, c.cercano(p)[1]) for p in pintados)
    r.cierto(peor < 1e-7, "cada vértice pintado está sobre la curva exacta", f"{peor:.2e}")
    # Y al revés: ningún punto de la curva queda lejos de lo pintado.
    peor = max(min(nurbs._distancia_a_segmento(c.punto(t), ln[i], ln[i + 1])
                   for ln in lineas for i in range(len(ln) - 1))
               for t in _muestras(c, 300))
    r.cierto(peor <= dibujo.FLECHA_SPLINE + 1e-9,
             f"lo pintado no se separa de la curva más que la flecha ({dibujo.FLECHA_SPLINE})",
             f"{peor:.4f}")


def _osnap(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        sp = doc.agregar(ent.Spline(puntos_ajuste=AJUSTE))
        el = doc.agregar(ent.Elipse(centro=[100, 50], eje_mayor=[300, 100], razon=0.4,
                                    param_ini=0.3, param_fin=2.5))
    prim = geometria.primitivas_de(doc, sp)
    clase = lambda k: [p["p"] for p in prim if p.get("tipo") == "punto" and p.get("clase") == k]
    r.igual(len(clase("extremo")), 2, "la spline abierta da exactamente dos extremos")
    r.cierto(sorted(map(tuple, clase("extremo"))) == sorted([tuple(AJUSTE[0]), tuple(AJUSTE[-1])])
             or all(min(math.dist(p, q) for q in (AJUSTE[0], AJUSTE[-1])) < 1e-9
                    for p in clase("extremo")),
             "y son sus puntas exactas")
    trozos = [p for p in prim if p.get("tipo") == "seg"]
    r.cierto(trozos and all(p.get("curva") for p in trozos),
             "todos sus trozos van marcados `curva`: el osnap no les saca extremos ni medios")
    c = sp.curva()
    medio = clase("medio")
    r.igual(len(medio), 1, "y un solo punto medio")
    if medio:
        r.cierto(math.dist(c.cercano(medio[0])[1], medio[0]) < 1e-7, "el medio cae sobre la curva")
        t_m = c.cercano(medio[0])[0]
        a, b = c.dominio
        izq = nurbs.Nurbs(c.grado, c.control, c.nudos)._teselar_t(1e-4)
        l1 = sum(math.dist(izq[i][1], izq[i + 1][1]) for i in range(len(izq) - 1) if izq[i + 1][0] <= t_m)
        total = c.longitud()
        r.cierto(abs(l1 - total / 2) < total * 1e-3,
                 "y está a media longitud, no a medio parámetro",
                 f"{l1:.2f} de {total:.2f}")
    peor = max(min(nurbs._distancia_a_segmento(c.punto(t), s["a"], s["b"]) for s in trozos)
               for t in _muestras(c, 300))
    r.cierto(peor <= geometria.FLECHA_OSNAP + 1e-9,
             f"los trozos del osnap no se separan de la curva más de {geometria.FLECHA_OSNAP}",
             f"{peor:.5f}")
    definicion = [p["p"] for p in prim if p.get("clase") == "definicion"]
    r.igual(len(definicion), len(AJUSTE), "los puntos de ajuste salen como grips")
    r.cierto(all(p.get("aprox") for p in prim if p.get("clase") == "definicion"),
             "y van `aprox`: el osnap no se pega a un punto de definición")

    # Elipse: centro, cuadrantes dentro del arco, extremos y medio exactos.
    prim = geometria.primitivas_de(doc, el)
    ext = [p["p"] for p in prim if p.get("clase") == "extremo"]
    ax, ay = el.eje_mayor
    bx, by = -ay * el.razon, ax * el.razon
    P = lambda t: [100 + ax * math.cos(t) + bx * math.sin(t), 50 + ay * math.cos(t) + by * math.sin(t)]
    r.cierto(len(ext) == 2 and math.dist(ext[0], P(0.3)) < 1e-9 and math.dist(ext[1], P(2.5)) < 1e-9,
             "el arco de elipse da sus dos extremos exactos")
    cuad = [p["p"] for p in prim if p.get("clase") == "cuadrante"]
    r.cierto(len(cuad) == 1 and math.dist(cuad[0], P(math.pi / 2)) < 1e-9,
             "y sólo el cuadrante que cae dentro del arco")
    trozos = [p for p in prim if p.get("tipo") == "seg"]
    peor = max(min(nurbs._distancia_a_segmento(P(0.3 + 2.2 * i / 400), s["a"], s["b"]) for s in trozos)
               for i in range(401))
    r.cierto(all(p.get("curva") for p in trozos) and peor <= geometria.FLECHA_OSNAP + 1e-9,
             "los trozos de la elipse van `curva` y dentro de la flecha del osnap", f"{peor:.5f}")


def _dxf(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    w = math.sqrt(2) / 2
    with doc.transaccion("Dibujar"):
        casos = {
            "por puntos": doc.agregar(ent.Spline(puntos_ajuste=AJUSTE)),
            "por puntos cerrada": doc.agregar(ent.Spline(puntos_ajuste=AJUSTE, cerrada=True)),
            "CV": doc.agregar(ent.Spline(puntos_control=CONTROL)),
            "CV cerrada": doc.agregar(ent.Spline(puntos_control=CONTROL, cerrada=True)),
            "racional": doc.agregar(ent.Spline(
                puntos_control=[[0, 0], [100, 100], [200, 0]], grado=2,
                nudos=[0, 0, 0, 1, 1, 1], pesos=[1, w, 1])),
        }
    with comun.carpeta() as carpeta:
        ruta = carpeta / "t043.dxf"
        export_dxf.escribir(doc, ruta)
        leido = ezdxf.readfile(str(ruta))
    splines = [e for e in leido.modelspace() if e.dxftype() == "SPLINE"]
    r.igual(len(splines), len(casos), "salen todas como SPLINE")
    for (nombre, e), s in zip(casos.items(), splines):
        c = e.curva()
        bs = s.construction_tool()
        a, b = c.dominio
        peor = max(math.dist(c.punto(t), list(bs.point(t))[:2]) for t in _muestras(c, 300))
        # Una micra: el DXF guarda los números en texto, con dieciséis cifras.
        r.cierto(peor < 1e-6, f"«{nombre}»: lo que lee AutoCAD es punto por punto lo que se ve",
                 f"diferencia {peor:.2e}")
        if e.cerrada:
            r.cierto(s.closed, f"«{nombre}» sale marcada cerrada")
        if e.puntos_ajuste:
            r.igual(len(s.fit_points), len(e.puntos_ajuste),
                    f"«{nombre}» lleva también sus puntos de ajuste, para editarla en AutoCAD")
    auditoria = leido.audit()
    r.igual(len(auditoria.errors), 0, "el DXF pasa la auditoría de ezdxf sin errores")
