"""t009 · La hoja: escala de verdad, recorte, pie de plano y PDF.

La regla que carga todo esto es una: **la hoja se pinta con los mismos trazos
que van al PDF**. Si la pantalla y la impresora se dibujaran por caminos
distintos, la única forma de enterarse de que no coinciden sería imprimiendo.

Lo que se comprueba:

- **La escala es escala.** Una ventana a 1:20 tiene que dejar 600 mm de mueble
  en 30 mm de papel. Es la comprobación que separa un plano de un dibujito.
- **La ventana recorta.** Lo que cae fuera del marco no se pinta: si no, el
  mueble de al lado invade la viñeta del detalle.
- **Lo blanco se imprime negro.** El papel es blanco; mandarle una capa blanca
  tal cual imprime una hoja vacía. Los plotters de verdad hacen esta misma
  traducción.
- **El PDF sale**, con una página por hoja y del tamaño del papel.
"""

from __future__ import annotations

from core import entidades as ent
from core import config
from core import papel
from core.capas import Capa
from core.documento import Documento
from export import pdf as export_pdf
from pruebas import comun

DESCRIPCION = "escala real, recorte, pie de plano y PDF"


def correr(r: comun.Reporte) -> None:
    _medidas(r)
    _escala_y_recorte(r)
    _blanco_a_negro(r)
    with comun.carpeta() as tmp:
        _pdf(r, tmp)


def _dibujo_en_mm() -> Documento:
    """Un mueble de 600 × 400. En milímetros, para que las cuentas de la hoja
    se lean sin conversiones de por medio."""
    doc = Documento.nuevo()
    doc.unidades = "mm"
    with doc.transaccion("Dibujar"):
        doc.agregar(ent.Linea(p1=[0, 0], p2=[600, 0]))
        doc.agregar(ent.Linea(p1=[600, 0], p2=[600, 400]))
        doc.agregar(ent.Linea(p1=[600, 400], p2=[0, 400]))
        doc.agregar(ent.Linea(p1=[0, 400], p2=[0, 0]))
    return doc


def _medidas(r: comun.Reporte) -> None:
    a3 = papel.layout_nuevo("Plano 1", "A3")
    r.igual(papel.medidas(a3), (420.0, 297.0), "un A3 mide 420 × 297")
    a1 = papel.layout_nuevo("Plano 2", "A1")
    r.igual(papel.medidas(a1), (841.0, 594.0), "un A1 mide 841 × 594")

    # Una hoja a la medida no se cae a A3 en ningún sitio.
    medida = papel.layout_nuevo("A la medida", papel.CUSTOM)
    medida.update({"ancho": 700, "alto": 500})
    r.igual(papel.medidas(medida), (700.0, 500.0),
            "una hoja a la medida manda con sus medidas")

    x0, y0, x1, y1 = papel.area_util(a3)
    ancho_barra = papel.barra_ancho(420.0)
    r.cierto(x1 < 420 - ancho_barra,
             "el área útil deja libre la barra del pie de plano, a la derecha")
    r.cierto(x0 >= papel.MARGEN and y0 >= papel.MARGEN,
             "y respeta el margen del borde del papel")


def _escala_y_recorte(r: comun.Reporte) -> None:
    doc = _dibujo_en_mm()
    hoja = papel.layout_nuevo("Plano 1", "A3")
    # Ventana de 40 × 40 mm de papel, centrada en la esquina inferior izquierda
    # del mueble, a 1:20.
    hoja["ventanas"] = [papel.ventana_nueva(20, 20, 40, 40, centro=[0, 0], escala=20)]
    doc.layouts = [hoja]

    salida = papel.trazos_papel(doc, hoja)
    r.exige(bool(salida.get("trazos")), "la hoja produce trazos")
    puntos = _puntos_de_la_ventana(salida, 0)
    r.cierto(bool(puntos), "y los trazos traen puntos en milímetros de papel")

    # --- La escala es escala ---------------------------------------------
    # A 1:20, los 600 mm del mueble son 30 mm de papel; la ventana sólo mide
    # 40 × 40 y está centrada en (0,0), así que del mueble entran 20 mm de
    # papel hacia cada lado: el trazo de abajo tiene que llegar justo al borde.
    dentro = [p for p in puntos if 20 - 1e-6 <= p[0] <= 60 + 1e-6
              and 20 - 1e-6 <= p[1] <= 60 + 1e-6]
    r.igual(len(dentro), len(puntos),
            "**nada** se pinta fuera del marco de la ventana: la ventana recorta")

    # El origen del mueble está en el centro de la ventana.
    r.cierto(any(abs(p[0] - 40) < 1e-6 and abs(p[1] - 40) < 1e-6 for p in puntos),
             "el punto del mueble que se centró cae en el centro de la ventana")

    # Y 600 mm a 1:20 son 30 mm: el lado de abajo, que arranca en el centro,
    # llegaría a 70 mm — pero la ventana lo corta en 60. Que el corte esté justo
    # en el borde es lo que prueba las dos cosas a la vez.
    borde = [p for p in puntos if abs(p[0] - 60) < 1e-6 and abs(p[1] - 40) < 1e-6]
    r.cierto(bool(borde),
             "el lado de 600 mm sale a 1:20 y se corta exactamente en el borde")

    # Con la ventana más grande, el mueble entero entra y mide lo que debe.
    hoja["ventanas"] = [papel.ventana_nueva(20, 20, 120, 120, centro=[300, 200], escala=20)]
    salida = papel.trazos_papel(doc, hoja)
    puntos = _puntos_de_la_ventana(salida, 0)
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    r.casi(max(xs) - min(xs), 30.0,
           "el mueble de 600 mm ocupa 30 mm de papel a 1:20", 1e-6)
    r.casi(max(ys) - min(ys), 20.0,
           "y los 400 mm de fondo ocupan 20 mm", 1e-6)


def _puntos_de_la_ventana(salida: dict, j: int) -> list:
    """Sólo lo que se ve **dentro** de la ventana j.

    La hoja trae además el marco, el pie de plano y el propio rectángulo de la
    ventana (`id: "ventana"`, que ni siquiera se imprime). Meterlos en la cuenta
    haría que la prueba midiera el papel en vez del mueble.
    """
    return [p for t in salida["trazos"]
            if t.get("ventana") == j and t.get("id") != "ventana"
            for p in (t.get("puntos") or [])]


def _blanco_a_negro(r: comun.Reporte) -> None:
    blanco = papel.color_impresion("#FFFFFF").upper()
    r.cierto(blanco != "#FFFFFF",
             "una capa blanca NO se imprime blanca (si no, sale la hoja vacía)")
    rgb = tuple(int(blanco[i:i + 2], 16) for i in (1, 3, 5))
    r.cierto(max(rgb) < 60, "se imprime con una tinta oscura de verdad",
             f"salió {blanco}")
    r.igual(papel.color_impresion("#0080C1").upper(), "#0080C1",
            "y un color de verdad se imprime como es")


def _pdf(r: comun.Reporte, tmp) -> None:
    doc = _dibujo_en_mm()
    doc.nombre = "Mesa de trabajo"
    doc.capa_agregar(Capa("ROTULO"))

    hoja = papel.layout_nuevo("Plano 1", "A3")
    hoja["ventanas"] = [papel.ventana_nueva(20, 20, 200, 150, centro=[300, 200], escala=10)]
    hoja["rotulo"].update({"proyecto": "Mondelez", "cliente": "Taller 101",
                           "dibujo": "Mesa", "folio": "1/2", "escala": "1:10"})
    hoja2 = papel.layout_nuevo("Plano 2", "A4")
    hoja2["ventanas"] = [papel.ventana_nueva(15, 15, 150, 100, centro=[300, 200], escala=20)]
    doc.layouts = [hoja, hoja2]

    ruta = tmp / "planos.pdf"
    res = export_pdf.escribir(doc, ruta)
    r.exige(ruta.exists() and ruta.stat().st_size > 1000, "el PDF se escribe")
    r.igual(res["hojas"], 2, "salen las dos hojas en un solo PDF (feature 67)")

    crudo = ruta.read_bytes()
    r.igual(crudo[:5], b"%PDF-", "y es un PDF de verdad")

    # Se abre el PDF y se mira, en vez de buscar cadenas en el archivo: los
    # flujos van comprimidos y buscar texto crudo pasa o falla por razones que
    # no tienen que ver con el plano.
    import pypdfium2 as pdfium
    doc_pdf = pdfium.PdfDocument(str(ruta))
    r.igual(len(doc_pdf), 2, "el PDF tiene una página por hoja")

    # A3 apaisado: 420 × 297 mm = 1190.55 × 841.89 puntos.
    ancho, alto = doc_pdf[0].get_size()
    r.casi(ancho, 420 / 25.4 * 72, "la primera página mide un A3 de ancho", 0.5)
    r.casi(alto, 297 / 25.4 * 72, "y un A3 de alto", 0.5)
    ancho2, alto2 = doc_pdf[1].get_size()
    r.casi(ancho2, 297 / 25.4 * 72, "y la segunda mide un A4", 0.5)

    texto = doc_pdf[0].get_textpage().get_text_range()
    for dato in ("Mondelez", "Taller 101", "1:10"):
        r.cierto(dato in texto, f"el pie de plano lleva «{dato}»")

    # Una imagen de la hoja sale por el mismo camino que el PDF.
    png = tmp / "hoja.png"
    export_pdf.imagen(doc, png, hoja, dpi=72)
    r.cierto(png.exists() and png.stat().st_size > 500,
             "y la misma hoja sale como PNG (feature 66)")
