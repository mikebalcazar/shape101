"""t001 · El DXF: ida y vuelta, y lo ajeno que no se toca.

Dos cosas distintas se comprueban aquí:

**Lo nuestro sobrevive al viaje.** Se dibuja una de cada entidad modelada, se
escribe el DXF, se vuelve a leer y se compara la geometría número a número. Un
exportador que pierde el bulge de una polilínea o el ángulo de un arco no se ve
raro en pantalla: se descubre cuando la pieza llega mal cortada.

**Lo ajeno sale intacto.** Se fabrica un DXF con una spline y una cota que este
programa no modela como propias, se abre, se **edita** el dibujo, y al exportar
tienen que seguir ahí. Devolverle a un arquitecto su plano sin cotas es el error
que todo el diseño de `Cruda` existe para no cometer.
"""

from __future__ import annotations

import math

import ezdxf

from core import entidades as ent
from core.documento import Documento
from core.dxf_lector import leer
from export import dxf as export_dxf
from pruebas import comun

DESCRIPCION = "DXF: ida y vuelta, y lo ajeno intacto"


def correr(r: comun.Reporte) -> None:
    with comun.carpeta() as tmp:
        _ida_y_vuelta(r, tmp)
        _lo_ajeno(r, tmp)


# --- Lo nuestro -------------------------------------------------------------

def _ida_y_vuelta(r: comun.Reporte, tmp) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[1200, 0]))
        doc.agregar(ent.Polilinea(puntos=[[0, 0, 0], [600, 0, 0.5], [600, 400, 0]],
                                  cerrada=False))
        doc.agregar(ent.Circulo(centro=[300, 300], radio=35))
        doc.agregar(ent.Arco(centro=[0, 0], radio=250, ang_ini=30, ang_fin=150))
        doc.agregar(ent.Texto(p=[10, 500], texto="MESA DE TRABAJO", altura=7.5))
        doc.agregar(ent.TextoM(p=[10, 560], texto="Nota de taller", altura=5, ancho=200))

    ruta = tmp / "nuestro.dxf"
    res = export_dxf.escribir(doc, ruta)
    r.exige(ruta.exists(), "el DXF se escribe en disco")
    r.igual(res.escritas, 6, "se escriben las seis entidades dibujadas")

    # Que el archivo esté bien formado no lo dice que se lea: lo dice el
    # auditor de ezdxf, que es lo que detecta lo que AutoCAD rechaza.
    doc_dxf = ezdxf.readfile(str(ruta))
    from ezdxf import audit
    aud = audit.Auditor(doc_dxf)
    aud.run()
    r.igual(len(aud.errors), 0, "el auditor de ezdxf no encuentra errores")
    r.igual(doc_dxf.dxfversion, "AC1027", "el DXF sale en R2013 (AC1027)")

    r.igual(doc_dxf.header.get("$INSUNITS"), 5,
            "el DXF declara la unidad en la que se dibujó (5 = cm)")

    vuelto, informe = leer(ruta)
    tipos = sorted(e.tipo for e in vuelto.lista())
    r.igual(tipos, sorted(["linea", "polilinea", "circulo", "arco", "texto", "textom"]),
            "vuelven las seis, y del mismo tipo cada una")

    # **Todo se compara en milímetros de verdad, no en números.** Un dibujo
    # nuevo nace en centímetros y al abrir un archivo se convierte a la unidad
    # que declara su encabezado: 1 200 cm vuelven como 12 000 mm, que es el
    # mismo mueble. Comparar los números pelados haría fallar la prueba por
    # una conversión correcta, y —peor— la haría pasar el día que la
    # conversión se pierda.
    ki = doc.mm_por_unidad()
    kv = vuelto.mm_por_unidad()
    r.casi(ki, 10.0, "el dibujo nuevo nace en centímetros")
    r.casi(kv, 1.0, "el archivo vuelve en la unidad que declara (mm)")

    def mm(v):
        return [c * kv for c in v[:2]]

    por_tipo = {e.tipo: e for e in vuelto.lista()}

    linea = por_tipo.get("linea")
    if r.cierto(linea is not None, "vuelve la línea"):
        r.punto(mm(linea.p1), [0, 0], "la línea vuelve con su primer punto")
        r.punto(mm(linea.p2), [1200 * ki, 0],
                "la línea vuelve midiendo lo mismo (12 000 mm)")

    pol = por_tipo.get("polilinea")
    if r.cierto(pol is not None, "vuelve la polilínea"):
        r.igual(len(pol.puntos), 3, "la polilínea vuelve con sus tres vértices")
        r.casi(pol.puntos[1][2], 0.5,
               "el bulge del vértice curvo vuelve igual (un arco no se aplana)")

    cir = por_tipo.get("circulo")
    if r.cierto(cir is not None, "vuelve el círculo"):
        r.punto(mm(cir.centro), [300 * ki, 300 * ki], "el círculo vuelve en su centro")
        r.casi(cir.radio * kv, 35 * ki, "el círculo vuelve con su radio")

    arco = por_tipo.get("arco")
    if r.cierto(arco is not None, "vuelve el arco"):
        r.casi(arco.radio * kv, 250 * ki, "el arco vuelve con su radio")
        r.casi(arco.ang_ini % 360, 30, "el arco vuelve con su ángulo inicial", 1e-6)
        r.casi(arco.ang_fin % 360, 150, "el arco vuelve con su ángulo final", 1e-6)

    txt = por_tipo.get("texto")
    if r.cierto(txt is not None, "vuelve el texto"):
        r.igual(txt.texto, "MESA DE TRABAJO",
                "el texto vuelve con sus espacios (no se parte en palabras)")
        r.casi(txt.altura * kv, 7.5 * ki, "el texto vuelve con su altura")


# --- Lo ajeno ---------------------------------------------------------------

def _dxf_ajeno(ruta) -> None:
    """Un plano «de otro»: una spline y una cota nativas de AutoCAD, más una
    línea que sí modelamos. Se fabrica con ezdxf para que sea un archivo de
    verdad y no una maqueta nuestra."""
    doc_dxf = ezdxf.new("R2013", setup=True)
    ms = doc_dxf.modelspace()
    ms.add_line((0, 0), (1000, 0))
    ms.add_spline([(0, 0), (300, 200), (600, -150), (900, 100)])
    dim = ms.add_linear_dim(base=(0, -120), p1=(0, 0), p2=(1000, 0))
    dim.render()
    doc_dxf.saveas(str(ruta))


def _lo_ajeno(r: comun.Reporte, tmp) -> None:
    ajeno = tmp / "ajeno.dxf"
    _dxf_ajeno(ajeno)

    doc, informe = leer(ajeno)
    crudas = [e for e in doc.lista() if e.tipo == "cruda"]
    r.cierto(len(crudas) >= 2,
             "la spline y la cota ajenas entran como entidades conservadas",
             f"entraron {len(crudas)}")

    # Lo conservado se **ve**: guarda cómo se dibuja, sacado del propio
    # archivo. Una entidad que se conserva pero no se pinta es un plano al que
    # le faltan las cotas.
    con_dibujo = [e for e in crudas if getattr(e, "dibujo", None)]
    r.cierto(len(con_dibujo) >= 2,
             "lo conservado trae con qué dibujarse (no entra invisible)")

    # Y se puede **picar**: geometría de selección propia, marcada aprox.
    from core import geometria
    for e in crudas[:2]:
        prims = geometria.primitivas_de(doc, e)
        r.cierto(bool(prims),
                 f"lo conservado ({e.dxftype or 'ajeno'}) aporta geometría para el ratón")

    # Ahora se **edita** el plano: se agrega algo nuestro y se borra la línea
    # que sí modelamos. Es el momento en que un exportador ingenuo reconstruye
    # el archivo desde cero y se lleva por delante lo que no entiende.
    lineas = [e for e in doc.lista() if e.tipo == "linea"]
    r.exige(bool(lineas), "la línea del plano ajeno sí se modela como línea")
    with doc.transaccion("Editar plano ajeno"):
        doc.agregar(ent.Circulo(centro=[500, 300], radio=60))
        doc.borrar(lineas[0].id)

    salida = tmp / "ajeno-editado.dxf"
    export_dxf.escribir(doc, salida)
    r.exige(salida.exists(), "el plano ajeno editado se escribe")

    vuelto = ezdxf.readfile(str(salida))
    ms = vuelto.modelspace()
    tipos = [e.dxftype() for e in ms]
    r.igual(tipos.count("SPLINE"), 1,
            "la spline ajena sigue ahí después de editar el plano")
    r.igual(tipos.count("DIMENSION"), 1,
            "la cota ajena sigue ahí después de editar el plano")
    r.igual(tipos.count("CIRCLE"), 1, "lo que se agregó sí llegó al archivo")
    r.igual(tipos.count("LINE"), 0, "lo que se borró sí se fue del archivo")

    spline = next(e for e in ms if e.dxftype() == "SPLINE")
    puntos = [tuple(p)[:2] for p in spline.fit_points]
    if r.cierto(len(puntos) == 4, "la spline conserva sus cuatro puntos de ajuste"):
        r.punto(puntos[1], (300, 200),
                "la spline conserva sus puntos tal cual venían (no reteselada)")
