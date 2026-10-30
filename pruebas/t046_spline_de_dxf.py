"""t046 · La SPLINE de un DXF entra nativa cuando trae su NURBS, y no se mueve un pelo.

Hasta la fase A4 toda SPLINE de un plano ajeno entraba «conservada»: se veía y
se podía picar, pero no se le hacía osnap ni se podía editar. Era a propósito:
reescribir una spline con nudos propios la movía un pelo. Desde A1 la spline de
shape101 **es** su NURBS (grado, nudos, pesos, puntos de control), así que la
que trae todo eso en el archivo se puede guardar tal cual.

Lo que se comprueba, contra ezdxf (que lee el archivo por su cuenta):

- entran nativas la CV abierta, la racional, la cerrada periódica y la que trae
  puntos de control y además de ajuste; y la curva es punto por punto la del
  archivo;
- se quedan conservadas la de sólo puntos de ajuste (cada programa la
  interpola a su modo), la que no está en el plano XY y la de nudos rotos;
- editar el plano y volver a escribirlo no las mueve: mismos puntos, nudos y
  pesos, y los de ajuste siguen ahí;
- un plano en centímetros las trae a milímetros, escaladas, con los mismos nudos;
- se jalan por sus puntos de control, y dentro de un bloque no regalan
  extremos falsos ni nodos en sus puntos de control.
"""

from __future__ import annotations

import math

import ezdxf
from ezdxf.math import fit_points_to_cad_cv

from core import entidades as ent
from core import geometria
from core.dxf_lector import leer
from export import dxf as export_dxf
from pruebas import comun

DESCRIPCION = "SPLINE de un DXF: nativa y exacta si trae su NURBS; conservada si no"

CV = [(0, 0, 0), (150, 300, 0), (450, 320, 0), (600, 0, 0), (800, -200, 0), (1000, 100, 0)]
AJUSTE = [(0, 500, 0), (300, 700, 0), (600, 350, 0), (900, 600, 0)]


def _plano(ruta, insunits: int = 4) -> None:
    d = ezdxf.new("R2013")
    d.header["$INSUNITS"] = insunits
    ms = d.modelspace()
    ms.add_open_spline(CV, degree=3)                                   # 1 · CV abierta
    w = math.sqrt(2) / 2
    ms.add_rational_spline([(0, 0, 0), (100, 100, 0), (200, 0, 0)],    # 2 · racional (un arco)
                           [1, w, 1], degree=2)
    cerrada = ms.add_spline(dxfattribs={"layer": "CERRADA"})           # 3 · cerrada periódica
    lazo = [(0, -400), (300, -300), (400, -600), (100, -700)]
    pts = lazo + lazo[:3]
    cerrada.dxf.degree = 3
    cerrada.control_points = [(x, y, 0) for x, y in pts]
    cerrada.knots = list(range(len(pts) + 4))
    cerrada.closed = True
    ambas = ms.add_spline(AJUSTE, dxfattribs={"layer": "AMBAS"})        # 4 · ajuste + control
    bs = fit_points_to_cad_cv(AJUSTE)
    ambas.control_points = bs.control_points
    ambas.knots = list(bs.knots())
    ms.add_spline([(0, 900, 0), (300, 1100, 0), (600, 800, 0)],         # 5 · sólo ajuste
                  dxfattribs={"layer": "SOLO_AJUSTE"})
    ms.add_open_spline([(0, 0, 0), (100, 100, 50), (200, 0, 0), (300, 50, 0)],  # 6 · 3D
                       dxfattribs={"layer": "TRESD"})
    rota = ms.add_spline(dxfattribs={"layer": "ROTA"})                  # 7 · nudos rotos
    rota.dxf.degree = 3
    rota.control_points = CV
    rota.knots = [0, 0, 0, 0, 1, 1, 1, 1]                               # faltan dos
    ms.add_line((0, 0), (1000, 0))
    d.saveas(str(ruta))


def correr(r: comun.Reporte) -> None:
    with comun.carpeta() as tmp:
        ruta = tmp / "ajeno.dxf"
        _plano(ruta)
        doc, _ = leer(ruta)
        nativas = [e for e in doc.lista() if e.tipo == "spline"]
        crudas = [e for e in doc.lista() if e.tipo == "cruda" and e.dxftype == "SPLINE"]
        r.igual(len(nativas), 4, "entran nativas las cuatro que traen su NURBS")
        r.igual(len(crudas), 3, "y se quedan conservadas la de sólo ajuste, la 3D y la de nudos rotos")
        r.igual(sorted(e.capa for e in crudas), ["ROTA", "SOLO_AJUSTE", "TRESD"],
                "son exactamente ésas tres")

        # Punto por punto la del archivo, leída por ezdxf.
        originales = [e for e in ezdxf.readfile(str(ruta)).modelspace() if e.dxftype() == "SPLINE"]
        por_handle = {e.dxf.handle: e for e in originales}
        for e in nativas:
            o = por_handle[e.handle_origen].construction_tool()
            c = e.curva()
            a, b = c.dominio
            peor = max(math.dist(c.punto(a + (b - a) * i / 300), list(o.point(a + (b - a) * i / 300))[:2])
                       for i in range(301))
            # Una micra: el DXF guarda en texto los puntos de control calculados.
            r.cierto(peor < 1e-6, f"la spline de la capa «{e.capa}» es la curva del archivo",
                     f"diferencia {peor:.2e}")
        racional = next(e for e in nativas if e.pesos)
        c = racional.curva()
        # Con esos tres puntos y peso √2/2 en el de en medio, es el cuarto de
        # círculo de centro (100, -100) y radio 100·√2.
        peor = max(abs(math.dist(c.punto(t / 100), [100, -100]) - 100 * math.sqrt(2)) for t in range(101))
        r.cierto(peor < 1e-9, "la racional es un arco de círculo exacto (los pesos entraron)",
                 f"{peor:.2e}")
        ambas = next(e for e in nativas if e.capa == "AMBAS")
        r.igual(len(ambas.puntos_ajuste), 4, "la que trae puntos de ajuste los guarda también")
        cerrada = next(e for e in nativas if e.capa == "CERRADA")
        r.cierto(cerrada.cerrada, "la cerrada entra cerrada")

        # Editar el plano y escribirlo: no se mueven.
        lineas = [e for e in doc.lista() if e.tipo == "linea"]
        with doc.transaccion("Editar"):
            doc.borrar(lineas[0].id)
            doc.agregar(ent.Circulo(centro=[500, 300], radio=60))
        salida = tmp / "editado.dxf"
        export_dxf.escribir(doc, salida)
        vuelto = ezdxf.readfile(str(salida))
        splines = [e for e in vuelto.modelspace() if e.dxftype() == "SPLINE"]
        r.igual(len(splines), 7, "después de editar siguen las siete splines")
        por_capa = {}
        for s in splines:
            por_capa.setdefault(s.dxf.layer, s)
        for capa in ("0", "CERRADA", "AMBAS"):
            antes = next(o for o in originales if o.dxf.layer == capa and len(o.control_points))
            despues = por_capa.get(capa)
            if not r.cierto(despues is not None, f"la de la capa «{capa}» sigue ahí"):
                continue
            iguales = (len(despues.control_points) == len(antes.control_points)
                       and max(math.dist(p, q) for p, q in zip(despues.control_points, antes.control_points)) < 1e-9
                       and max(abs(x - y) for x, y in zip(despues.knots, antes.knots)) < 1e-12
                       and despues.dxf.degree == antes.dxf.degree)
            r.cierto(iguales, f"«{capa}» sale con los mismos puntos de control, nudos y grado")
        r.igual(len(por_capa["AMBAS"].fit_points), 4, "y la que traía puntos de ajuste los conserva")
        r.igual(len(vuelto.audit().errors), 0, "el DXF editado pasa la auditoría de ezdxf")

        # Un plano en centímetros: a milímetros, escalada, con los mismos nudos.
        # (En metros, un dibujo de mil unidades sería de un kilómetro, y el
        # freno de core/unidades.py no le cree al encabezado: con razón.)
        en_cm = tmp / "centimetros.dxf"
        _plano(en_cm, insunits=5)
        doc_m, _ = leer(en_cm)
        cv = next(e for e in doc_m.lista() if e.tipo == "spline" and e.capa == "0" and not e.pesos)
        r.punto(cv.puntos_control[1], [1500, 3000], "un plano en centímetros trae la spline a milímetros")
        cv_mm = next(e for e in nativas if e.capa == "0" and not e.pesos)
        r.igual(cv.nudos, cv_mm.nudos, "con los mismos nudos: escalar no cambia el parámetro")

        # Se jala por sus puntos de control.
        prims = geometria.primitivas_de(doc, cv_mm)
        grips = [p["p"] for p in prims if p.get("clase") == "definicion"]
        r.igual(len(grips), len(CV), "se jala por sus puntos de control")

        # Dentro de un bloque: sin extremos falsos ni nodos en los puntos de control.
        bl = ent.Bloque(nombre="CON_SPLINE", base=[0, 0],
                        entidades=[ent.Spline(puntos_control=[list(p[:2]) for p in CV],
                                              nudos=list(cv_mm.nudos))])
        doc.bloque_agregar(bl)
        with doc.transaccion("Insertar"):
            ins = doc.agregar(ent.Insercion(bloque="CON_SPLINE", p=[5000, 0]))
        prims = geometria.primitivas_de(doc, ins)
        segs = [p for p in prims if p["tipo"] == "seg"]
        r.cierto(segs and all(p.get("curva") for p in segs),
                 "en la inserción, los trozos de la spline siguen marcados `curva`")
        r.cierto(not any(p.get("def") for p in segs),
                 "y no llevan la def del bloque, que está en otras coordenadas")
        nodos = [p for p in prims if p["tipo"] == "punto" and p.get("clase") in ("nodo", "definicion")
                 and not p.get("aprox")]
        r.igual(len(nodos), 0, "ni sus puntos de control aparecen como nodos enganchables")
        extremos = [p["p"] for p in prims if p.get("clase") == "extremo"]
        r.cierto(len(extremos) == 2 and all(min(math.dist(q, [5000 + x, y]) for x, y, _ in (CV[0], CV[-1])) < 1e-9
                                             for q in extremos),
                 "sus dos extremos sí, exactos y en su lugar")
