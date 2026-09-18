"""Planos por ventana · un contorno dibujado en la Frontal se extruye hacia quien mira.

Mike (17-sep): «cuando dibujas en la ventana de la vista superior, dibuja
sobre X-Y en Z = 0, y así según la vista». Cada línea sabe en qué plano vive y
la pieza sale a donde debe. El kernel sigue trabajando en XY —donde los
nombres de caras están probados— y la pieza se rota al salir.
"""
from __future__ import annotations

from core import entidades as E
from core.documento import Documento
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "extruir sobre XZ y YZ: la pieza sale a donde debe"

ANCHO, ALTO, ESPESOR = 900.0, 600.0, 18.0


def caja(malla):
    xs, ys, zs = [], [], []
    for c in malla["caras"]:
        v = c["v"]
        for k in range(0, len(v), 3):
            xs.append(v[k]); ys.append(v[k + 1]); zs.append(v[k + 2])
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def correr(r: comun.Reporte):
    from core.solido import cuerpo as mod
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    mod.olvidar()

    # Dibujado en la Frontal: (u, v) son (x, z). Se extruye hacia −Y.
    frontal = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, ALTO, 0], [0, ALTO, 0]], cerrada=True)
    frontal.plano = "XZ"
    doc.agregar(frontal)
    m = rutas.extruir(rutas.Extruir(ids=[frontal.id], mm=ESPESOR))
    r.igual(doc.entidades[m["id"]].plano, "XZ", "la pieza recuerda el plano del contorno")
    (x0, x1), (y0, y1), (z0, z1) = caja(m)
    r.casi(x1 - x0, ANCHO, "en la Frontal el ancho va sobre X", 1e-6)
    r.casi(z1 - z0, ALTO, "en la Frontal el alto va sobre Z", 1e-6)
    r.casi(y1 - y0, ESPESOR, "el espesor va sobre Y", 1e-6)
    r.casi(y1, 0.0, "y crece hacia quien mira: la pieza queda en Y negativa", 1e-6)
    r.casi(m["volumen_mm3"], ANCHO * ALTO * ESPESOR, "el volumen no cambia por rotar", 1.0)

    # Dibujado en la Lateral: (u, v) son (y, z). Se extruye hacia +X.
    lateral = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, ALTO, 0], [0, ALTO, 0]], cerrada=True)
    lateral.plano = "YZ"
    doc.agregar(lateral)
    m2 = rutas.extruir(rutas.Extruir(ids=[lateral.id], mm=ESPESOR))
    (x0, x1), (y0, y1), (z0, z1) = caja(m2)
    r.casi(y1 - y0, ANCHO, "en la Lateral el ancho va sobre Y", 1e-6)
    r.casi(z1 - z0, ALTO, "en la Lateral el alto va sobre Z", 1e-6)
    r.casi(x1 - x0, ESPESOR, "el espesor va sobre X", 1e-6)
    r.casi(x0, 0.0, "y crece hacia +X", 1e-6)

    # Un archivo viejo no trae plano y vale XY.
    vieja = E.de_dict({"tipo": "linea", "p1": [0, 0], "p2": [100, 0]})
    r.igual(getattr(vieja, "plano", None), "XY", "una entidad sin plano vale XY")
