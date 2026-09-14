"""Importar un PDF vectorial como fondo  ·  feature 7.

Un plano de arquitecto llega casi siempre en PDF. Si ese PDF es vectorial —lo
es cuando salió de un CAD— sus líneas están ahí dentro, con coordenadas
exactas, y se pueden traer al dibujo para calcar encima con referencias a
objeto de verdad en vez de a ojo sobre una imagen.

Se leen con **pypdfium2** (PDFium, licencia BSD/Apache): hasta la 0.19.1 se
usaba PyMuPDF, que es AGPL y obligaría a licencia comercial el día que el
programa salga del taller.

Se traen a una capa propia y **bloqueada**: son referencia, no material de
trabajo. Quien quiera moverlas, desbloquea la capa a propósito.

Si el PDF es un escaneo no hay vectores que traer. En ese caso se dice y se
ofrece meterlo como imagen de referencia (feature 8), que es lo honesto: fingir
que se «vectorizó» una foto produce basura con pinta de plano.
"""

from __future__ import annotations

import math
import pathlib

from . import entidades as ent_mod
from .capas import Capa
from .documento import Documento

PUNTO_A_MM = 25.4 / 72.0
CAPA = "REF-PDF"


class PDFSinVectores(RuntimeError):
    pass


def _abrir(ruta):
    import pypdfium2
    return pypdfium2.PdfDocument(str(ruta))


def _matriz_total(obj):
    """Matriz que lleva los puntos del trazo al espacio de la página.

    pdfium da cada trazo en su propio espacio; si el trazo vive dentro de un
    formulario (XObject), el formulario tiene otra matriz encima, y así hasta
    la página. Se componen de adentro hacia afuera."""
    m = obj.get_matrix()
    c = obj.container
    while c is not None:
        m = m.multiply(c.get_matrix())
        c = c.container
    return m


def _caminos(pag):
    """Trazos vectoriales de la página como listas de segmentos, en puntos PDF.

    Cada camino es una lista de subcaminos; cada subcaminos es
    ``{"puntos": [(x, y), ...], "cerrado": bool}`` con las Bézier ya muestreadas.
    """
    import pypdfium2.raw as r
    caminos = []
    for obj in pag.get_objects(filter=[r.FPDF_PAGEOBJ_PATH]):
        m = _matriz_total(obj)
        n = r.FPDFPath_CountSegments(obj)
        subs, actual, ctrl = [], None, []
        for i in range(n):
            seg = r.FPDFPath_GetPathSegment(obj, i)
            x, y = r.c_float(), r.c_float()
            if not r.FPDFPathSegment_GetPoint(seg, x, y):
                continue
            pt = m.on_point(x.value, y.value)
            tipo = r.FPDFPathSegment_GetType(seg)
            if tipo == r.FPDF_SEGMENT_MOVETO:
                actual = {"puntos": [pt], "cerrado": False}
                subs.append(actual)
                ctrl = []
            elif actual is None:
                continue
            elif tipo == r.FPDF_SEGMENT_LINETO:
                actual["puntos"].append(pt)
            elif tipo == r.FPDF_SEGMENT_BEZIERTO:
                ctrl.append(pt)
                if len(ctrl) == 3:
                    p0 = actual["puntos"][-1]
                    for k in range(1, 9):
                        t = k / 8
                        u = 1 - t
                        actual["puntos"].append((
                            u ** 3 * p0[0] + 3 * u * u * t * ctrl[0][0] + 3 * u * t * t * ctrl[1][0] + t ** 3 * ctrl[2][0],
                            u ** 3 * p0[1] + 3 * u * u * t * ctrl[0][1] + 3 * u * t * t * ctrl[1][1] + t ** 3 * ctrl[2][1]))
                    ctrl = []
            if r.FPDFPathSegment_GetClose(seg):
                actual["cerrado"] = True
        if subs:
            caminos.append(subs)
    return caminos


def paginas(ruta) -> list[dict]:
    doc = _abrir(ruta)
    try:
        salida = []
        for i in range(len(doc)):
            p = doc[i]
            ancho, alto = p.get_size()
            salida.append({"numero": i + 1,
                           "ancho": round(ancho * PUNTO_A_MM, 1),
                           "alto": round(alto * PUNTO_A_MM, 1),
                           "trazos": len(_caminos(p))})
            p.close()
        return salida
    finally:
        doc.close()


def importar(doc_dib: Documento, ruta, pagina: int = 1,
             escala: float = 1.0, origen=(0.0, 0.0)) -> dict:
    """Trae las líneas de una página a la capa REF-PDF.

    `escala` multiplica: un PDF impreso a 1:50 se trae con escala 50 para que
    el dibujo quede a tamaño real, que es como hay que medirlo.
    """
    ruta = pathlib.Path(ruta)
    pdf = _abrir(ruta)
    try:
        if not (1 <= pagina <= len(pdf)):
            raise ValueError(f"El PDF tiene {len(pdf)} página(s)")
        pag = pdf[pagina - 1]
        caminos = _caminos(pag)
        pag.close()
        if not caminos:
            raise PDFSinVectores(
                "Este PDF no trae vectores: es un escaneo o una imagen. "
                "Se puede meter como imagen de referencia y calcar encima.")

        if CAPA not in doc_dib.capas:
            doc_dib.capa_agregar(Capa(CAPA, "#8A93A1", 13, "CONTINUOUS",
                                      bloqueada=False, imprime=False,
                                      descripcion=f"Fondo importado de {ruta.name}"))

        k = PUNTO_A_MM * float(escala)

        def punto(p):
            # pdfium ya da la Y hacia arriba, como el dibujo
            return [origen[0] + p[0] * k, origen[1] + p[1] * k]

        creadas = 0
        for subs in caminos:
            for sub in subs:
                pts = [punto(p) for p in sub["puntos"]]
                # puntos repetidos seguidos no aportan nada
                limpios = [pts[0]]
                for q in pts[1:]:
                    if math.dist(q, limpios[-1]) > 1e-9:
                        limpios.append(q)
                if len(limpios) < 2:
                    continue
                # Un camino que vuelve a su origen (un círculo de Bézier, por
                # ejemplo) es cerrado aunque el PDF no lo marque.
                cerrado = bool(sub["cerrado"]) or (len(limpios) > 2 and math.dist(limpios[0], limpios[-1]) < 1e-6)
                if len(limpios) == 2 and not cerrado:
                    doc_dib.agregar(ent_mod.Linea(capa=CAPA, p1=limpios[0], p2=limpios[1]))
                else:
                    if cerrado and len(limpios) > 2 and math.dist(limpios[0], limpios[-1]) < 1e-6:
                        limpios.pop()
                    doc_dib.agregar(ent_mod.Polilinea(
                        capa=CAPA, cerrada=cerrado,
                        puntos=[[q[0], q[1], 0] for q in limpios]))
                creadas += 1

        # La capa se bloquea al final: si se bloquea antes, no deja meter nada.
        doc_dib.capa_modificar(CAPA, {"bloqueada": True})
        return {"entidades": creadas, "capa": CAPA,
                "pagina": pagina, "archivo": str(ruta)}
    finally:
        pdf.close()
