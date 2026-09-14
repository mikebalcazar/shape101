"""t011 · El día completo, de la cocina al DXF.

Las otras pruebas miran una pieza cada una. Ésta hace el recorrido entero, que
es donde aparecen los fallos que ninguna pieza tiene por su cuenta:

    cocina de Taller 101 → dibujo → anotación a mano → el mueble cambia y se
    actualiza → hoja con pie de plano → PDF → DXF → guardar, cerrar y reabrir

Al final se comprueba lo único que de verdad importa de todo el camino: que lo
que se reabre **es lo mismo** que se guardó, y que el DXF que sale lleva las
anotaciones de la persona además de lo generado. Un plano que pierde el trabajo
de alguien por el camino no es un plano: es un susto.
"""

from __future__ import annotations

import json

import ezdxf

from core import entidades as ent
from core import papel
from core import proyecto
from core import t101x
from core.documento import Documento
from export import dxf as export_dxf
from export import pdf as export_pdf
from pruebas import comun

DESCRIPCION = "el día completo: cocina → hoja → PDF → DXF → guardar y reabrir"

PROYECTO = {
    "nombre": "Cocina Mondelez",
    "cliente": "Mondelez",
    "estandar": {},
    "gabinetes": [
        {"nombre": "B-01", "tipo": "base", "ancho": 900, "alto": 900, "prof": 600,
         "pos_x": 0, "pos_z": 0, "frentes": [{}, {}]},
        {"nombre": "B-02", "tipo": "base", "ancho": 600, "alto": 900, "prof": 600,
         "pos_x": 900, "pos_z": 0, "frentes": [{}]},
    ],
}


def correr(r: comun.Reporte) -> None:
    with comun.carpeta() as tmp:
        ruta_t101x = tmp / "cocina.t101x"
        ruta_t101x.write_text(json.dumps(PROYECTO), encoding="utf-8")

        # --- 1. Llega la cocina ------------------------------------------
        doc = Documento.nuevo()
        with doc.transaccion("Importar de Taller 101"):
            t101x.generar(doc, t101x.leer(ruta_t101x), str(ruta_t101x))
        r.igual(len(doc.bloques), 2, "entran los dos muebles como bloques")

        # --- 2. Alguien anota encima --------------------------------------
        with doc.transaccion("Anotar"):
            nota = doc.agregar(ent.Texto(p=[0, -1500], texto="HERRAJE BLUM",
                                         altura=60))
        r.cierto(nota.id in doc.entidades, "y alguien anota a mano encima")

        # --- 3. El mueble cambia allá y el plano se actualiza --------------
        cambiado = json.loads(json.dumps(PROYECTO))
        cambiado["gabinetes"][1]["ancho"] = 750
        ruta_t101x.write_text(json.dumps(cambiado), encoding="utf-8")
        with doc.transaccion("Actualizar"):
            t101x.regenerar(doc)
        r.cierto(nota.id in doc.entidades,
                 "al actualizar, la anotación a mano sigue ahí")

        # --- 4. La hoja ----------------------------------------------------
        hoja = papel.layout_nuevo("Plano 1", "A3")
        x0, y0, x1, y1 = papel.area_util(hoja)
        caja = doc.extension("")
        centro = [(caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2]
        hoja["ventanas"] = [papel.ventana_nueva(x0, y0, x1 - x0, y1 - y0,
                                                centro=centro, escala=25)]
        hoja["rotulo"].update({"proyecto": "Mondelez", "cliente": "Mondelez",
                               "dibujo": "Cocina", "escala": "1:25"})
        doc.layouts = [hoja]
        salida = papel.trazos_papel(doc, hoja)
        r.cierto(bool(salida["trazos"]), "la hoja se arma con su pie de plano")

        # --- 5. El PDF -----------------------------------------------------
        pdf = tmp / "cocina.pdf"
        res_pdf = export_pdf.escribir(doc, pdf)
        r.cierto(pdf.exists() and pdf.stat().st_size > 1000, "sale el PDF")
        r.igual(res_pdf["hojas"], 1, "con la hoja que se armó")

        # --- 6. El DXF -----------------------------------------------------
        dxf = tmp / "cocina.dxf"
        res_dxf = export_dxf.escribir(doc, dxf)
        r.cierto(dxf.exists(), "y sale el DXF, que es la entrega")

        leido = ezdxf.readfile(str(dxf))
        from ezdxf import audit
        aud = audit.Auditor(leido)
        aud.run()
        r.igual(len(aud.errors), 0, "el DXF del día completo pasa el auditor")

        textos = [e for e in leido.modelspace()
                  if e.dxftype() in ("TEXT", "MTEXT")]
        r.cierto(any("HERRAJE BLUM" in (e.plain_text() if e.dxftype() == "MTEXT"
                                        else e.dxf.text) for e in textos),
                 "y la anotación de la persona viaja dentro del DXF")

        inserciones = [e for e in leido.modelspace() if e.dxftype() == "INSERT"]
        r.igual(len(inserciones), 2, "los dos muebles salen como bloques, no explotados")

        dims = [e for e in leido.modelspace() if e.dxftype() == "DIMENSION"]
        r.cierto(bool(dims), "y las cotas salen como cotas")

        # --- 7. Guardar, cerrar, reabrir -----------------------------------
        archivo = proyecto.guardar(doc, tmp / "cocina.t101d")
        antes = doc.a_dict()
        del doc

        vuelto = proyecto.abrir(archivo)
        despues = vuelto.a_dict()

        # Se compara el documento entero, no una entidad de muestra: lo que
        # importa del día completo es que no se perdió **nada** por el camino.
        r.igual(sorted(despues["entidades"], key=lambda e: e["id"]),
                sorted(antes["entidades"], key=lambda e: e["id"]),
                "al reabrir, las entidades son exactamente las mismas")
        r.igual(sorted(despues["capas"], key=lambda c: c["nombre"]),
                sorted(antes["capas"], key=lambda c: c["nombre"]),
                "y las capas también")
        r.igual(despues["layouts"], antes["layouts"],
                "y la hoja, con su ventana y su pie de plano")
        r.igual(despues["bloques"], antes["bloques"],
                "y los bloques de los muebles")
        r.igual(despues["origen_t101x"], antes["origen_t101x"],
                "y de qué .t101x salió, para poder volver a actualizar mañana")

        # Y lo reabierto se puede seguir trabajando: se actualiza otra vez.
        cambiado["gabinetes"][0]["ancho"] = 1000
        ruta_t101x.write_text(json.dumps(cambiado), encoding="utf-8")
        with vuelto.transaccion("Actualizar otra vez"):
            hecho = t101x.regenerar(vuelto)
        r.igual(hecho["gabinetes"], 2, "y el dibujo reabierto se vuelve a actualizar")
        r.cierto(any(e.tipo == "texto" and e.texto == "HERRAJE BLUM"
                     for e in vuelto.lista()),
                 "sin perder la anotación, dos actualizaciones después")
