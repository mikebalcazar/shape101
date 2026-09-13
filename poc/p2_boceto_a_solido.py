"""P2 · Boceto de draw101 → sólido.

Lee los .t101d de muestra (dibujados con el motor de draw101, con cotas),
convierte sus entidades a una cara de build123d, extruye 18 mm y exporta STEP.
Se comprueba con números: caja, volumen contra la fórmula, y que el STEP
vuelva a abrir con las mismas medidas.

El documento pide «sí/no: el STEP abre en FreeCAD». Aquí no hay FreeCAD: se
abre con el lector STEP de OpenCascade y se mide. Los STEP quedan en
poc/salida/ (no se versionan: regla del .gitignore) por si alguien los abre.
"""
from __future__ import annotations

import math
import pathlib

from build123d import import_step, export_step

from poc import comun
from app.motor import draw101_lector as d1, boceto

DESCRIPCION = "boceto .t101d (draw101) → cara → extruir 18 → STEP → reabrir"
AQUI = pathlib.Path(__file__).resolve().parent
ESPESOR = 18.0
ANCHO, ALTO, R_BARRENO, R_ESQ = 900.0, 600.0, 80.0, 20.0


def _caso(r: comun.Reporte, nombre: str, area_esperada: float, aristas_esperadas: int):
    t = {}
    with comun.cronometro(t, "leer"):
        ents = d1.leer(AQUI / "muestras" / f"{nombre}.t101d")
    r.cierto(any(e["tipo"] == "cota" for e in ents), f"{nombre}: el .t101d trae cotas (se ignoran al modelar)")
    with comun.cronometro(t, "cara"):
        cara = boceto.cara_de(ents)
    r.casi(cara.area, area_esperada, f"{nombre}: el área de la cara es la del boceto", tol=1e-6)
    with comun.cronometro(t, "extruir"):
        solido = boceto.solido_de(ents, ESPESOR)
    bb = solido.bounding_box()
    r.casi(bb.size.X, ANCHO, f"{nombre}: el sólido mide {ANCHO:.0f} de ancho", tol=1e-6)
    r.casi(bb.size.Y, ALTO, f"{nombre}: el sólido mide {ALTO:.0f} de alto", tol=1e-6)
    r.casi(bb.size.Z, ESPESOR, f"{nombre}: el sólido mide {ESPESOR:.0f} de espesor", tol=1e-6)
    r.casi(solido.volume, area_esperada * ESPESOR, f"{nombre}: el volumen es área × espesor", tol=1e-3)
    r.igual(len(solido.edges()), aristas_esperadas, f"{nombre}: número de aristas del sólido")
    (AQUI / "salida").mkdir(exist_ok=True)
    ruta = AQUI / "salida" / f"{nombre}.step"
    with comun.cronometro(t, "step"):
        export_step(solido, str(ruta))
    r.exige(ruta.exists() and ruta.stat().st_size > 0, f"{nombre}: el STEP se escribió")
    with comun.cronometro(t, "reabrir"):
        otra = import_step(str(ruta))
    bb2 = otra.bounding_box()
    r.casi(bb2.size.X, ANCHO, f"{nombre}: el STEP reabierto mide {ANCHO:.0f} de ancho", tol=1e-4)
    r.casi(bb2.size.Y, ALTO, f"{nombre}: el STEP reabierto mide {ALTO:.0f} de alto", tol=1e-4)
    r.casi(otra.volume, area_esperada * ESPESOR, f"{nombre}: el STEP reabierto tiene el mismo volumen", tol=1e-2)
    r.numero(f"P2 {nombre}: leer .t101d + cara + extruir", round(t["leer"] + t["cara"] + t["extruir"], 1), "ms")
    r.numero(f"P2 {nombre}: exportar STEP", round(t["step"], 1), "ms")
    r.numero(f"P2 {nombre}: STEP", ruta.stat().st_size, "bytes")
    r.numero(f"P2 {nombre}: reabrir el STEP y medir", round(t["reabrir"], 1), "ms")


def correr(r: comun.Reporte):
    r.numero("P2: formato leído", ".t101d (documento de draw101; «.t101x» es el proyecto de Taller 101)", "")
    # Tablero recto: 900×600 con barreno ⌀160. Aristas: 12 de la caja + 3 del cilindro (2 círculos + 1 costura).
    _caso(r, "tablero", ANCHO * ALTO - math.pi * R_BARRENO ** 2, 12 + 3)
    # Redondeado r=20 en las cuatro esquinas: 8 tramos arriba, 8 abajo, 8 verticales = 24, + 3 del barreno.
    area_red = ANCHO * ALTO - (4 - math.pi) * R_ESQ ** 2 - math.pi * R_BARRENO ** 2
    _caso(r, "tablero-redondeado", area_red, 24 + 3)
    # En sentido contrario: un boceto abierto no puede hacer cara, y se dice.
    try:
        boceto.cara_de([{"tipo": "linea", "p1": [0, 0], "p2": [100, 0]}])
        r.cierto(False, "un boceto sin contorno cerrado se rechaza")
    except ValueError as e:
        r.cierto("cerrado" in str(e), "un boceto sin contorno cerrado se rechaza diciendo por qué")
    r.numero("P2: el STEP abre con las medidas del boceto", "sí (reabierto con OpenCascade; FreeCAD no está en esta máquina)", "",
             umbral="sí/no", cumple=True)
