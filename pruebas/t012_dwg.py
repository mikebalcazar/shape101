"""t012 · DWG sin instalar nada: los dos motores, ida y vuelta.

El DWG es formato cerrado. Aquí viajan dos motores dentro —LibreDWG compilado a
WebAssembly y acad-ts, puerto de ACadSharp— y se prueban en cascada, más el ODA
File Converter si está instalado en la máquina.

La prueba fabrica el DWG **con un motor y lo lee con el otro**, que es la única
forma honesta de comprobarlos sin depender de AutoCAD, y compara la geometría
contra números escritos a mano. Además se comprueban las dos cosas que enseñó
`I5103.dwg`, el primer plano ajeno de verdad, y que no truenan:

- **Las capas tienen que abrir encendidas.** LibreDWG escribe el color de capa
  en negativo, y un color negativo en DXF quiere decir «capa apagada»: el plano
  abría en blanco, como si se hubiera perdido.
- **Las unidades se convierten** cuando el encabezado las declara —aquel plano
  venía en metros—, y **no** se convierten cuando el encabezado miente, porque
  `ezdxf.new()` pone metros por omisión aunque el dibujo esté en milímetros.

Si en esta máquina no hay Node —fuera de la app instalada, que trae el de
Electron— la prueba lo dice y se salta, en vez de fallar por algo que no es del
programa.
"""

from __future__ import annotations

import ezdxf

from core import dwg as mod_dwg
from core import entidades as ent
from core import unidades as mod_unidades
from core.documento import Documento
from core.dxf_lector import leer
from export import dxf as export_dxf
from pruebas import comun

DESCRIPCION = "DWG R2013 con los dos motores, capas y unidades"


def correr(r: comun.Reporte) -> None:
    _unidades(r)                     # esto no necesita motor
    if not mod_dwg.motor_disponible():
        r.cierto(True, "(sin Node en esta máquina: la parte de DWG se salta)")
        return
    with comun.carpeta() as tmp:
        _ida_y_vuelta(r, tmp)


def _ida_y_vuelta(r: comun.Reporte, tmp) -> None:
    """Se escribe con acad-ts y se lee con LibreDWG."""
    doc = Documento.nuevo()
    doc.capa_agregar(__import__("core.capas", fromlist=["Capa"]).Capa(
        "CUERPO", color="#112233", grosor=35))
    with doc.transaccion("Dibujar"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[1200, 0], capa="CUERPO"))
        doc.agregar(ent.Linea(p1=[1200, 0], p2=[1200, 700], capa="CUERPO"))
        doc.agregar(ent.Circulo(centro=[300, 300], radio=35))

    ruta = tmp / "salida.dwg"
    res = export_dxf.escribir_dwg(doc, ruta)
    r.exige(ruta.exists() and ruta.stat().st_size > 0,
            "se escribe un DWG sin instalar nada")

    vuelto, informe = leer(ruta)
    r.cierto(bool(informe.avisos),
             "el informe dice con qué motor se abrió")

    k = vuelto.mm_por_unidad()
    lineas = [e for e in vuelto.lista() if e.tipo == "linea"]
    circulos = [e for e in vuelto.lista() if e.tipo == "circulo"]
    r.igual(len(lineas), 2, "vuelven las dos líneas del DWG")
    r.igual(len(circulos), 1, "y el círculo")

    if circulos:
        r.casi(circulos[0].radio * k, 35 * doc.mm_por_unidad(),
               "el círculo vuelve con su radio, comparado en milímetros", 1e-3)
    if lineas:
        largos = sorted(round(comun.largo(e.p1, e.p2) * k, 3) for e in lineas)
        esperados = sorted([1200 * doc.mm_por_unidad(), 700 * doc.mm_por_unidad()])
        r.casi(largos[0], esperados[0], "la línea corta mide lo que medía", 1e-2)
        r.casi(largos[1], esperados[1], "la línea larga mide lo que medía", 1e-2)

    # --- Las capas abren encendidas ---------------------------------------
    apagadas = [c.nombre for c in vuelto.capas.values() if not c.visible]
    r.igual(apagadas, [],
            "el plano abre con TODAS las capas encendidas (el color negativo "
            "de LibreDWG no las apaga)")
    r.cierto(all(c.color.startswith("#") for c in vuelto.capas.values()),
             "y cada capa vuelve con un color de verdad")


def _unidades(r: comun.Reporte) -> None:
    """El plano en metros, y el encabezado que miente."""
    with comun.carpeta() as tmp:
        # 1) Un plano honesto en metros: 0.6 m de mueble son 600 mm.
        en_metros = tmp / "metros.dxf"
        d = ezdxf.new("R2013")
        d.header["$INSUNITS"] = 6                     # metros
        ms = d.modelspace()
        ms.add_line((0, 0), (6.0, 0))                 # 6 m
        ms.add_line((0, 0), (0, 2.4))                 # 2.4 m
        d.saveas(str(en_metros))

        doc, informe = leer(en_metros)
        k = doc.mm_por_unidad()
        largos = sorted(comun.largo(e.p1, e.p2) * k for e in doc.lista()
                        if e.tipo == "linea")
        r.casi(largos[1], 6000, "un plano en metros entra convertido: 6 m = 6 000 mm", 1e-3)
        r.casi(largos[0], 2400, "y el otro lado también", 1e-3)
        r.cierto(any("metro" in a.lower() or "unidad" in a.lower()
                     for a in informe.avisos),
                 "y se avisa de la conversión, no se hace a escondidas")

        # 2) El encabezado que miente: `ezdxf.new()` pone metros por omisión.
        #    Un dibujo de 1 200 «metros» sería un mueble de 1.2 km: el freno de
        #    sensatez tiene que no hacerle caso al encabezado.
        mentiroso = tmp / "mentiroso.dxf"
        d = ezdxf.new("R2013")
        d.header["$INSUNITS"] = 6                     # dice metros…
        ms = d.modelspace()
        ms.add_line((0, 0), (1200, 0))                # …pero mide 1 200 (mm)
        ms.add_line((0, 0), (0, 700))
        d.saveas(str(mentiroso))

        doc2, informe2 = leer(mentiroso)
        k2 = doc2.mm_por_unidad()
        largo_mm = max(comun.largo(e.p1, e.p2) * k2 for e in doc2.lista()
                       if e.tipo == "linea")
        r.cierto(largo_mm < mod_unidades.SENSATO_MAX,
                 "si el encabezado no cuadra con el tamaño del dibujo, no se le hace caso",
                 f"el dibujo habría quedado de {largo_mm:.0f} mm")
        r.casi(largo_mm, 1200, "el mueble sigue midiendo 1 200 mm, no 1 200 000", 1e-3)
