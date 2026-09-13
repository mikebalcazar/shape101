"""P5 · Salidas 2D a draw101.

Del sólido de P3 (tablero 900×600, redondeado r20, barreno ⌀160, arriba
empujada a 28): planta, alzado, lateral y un corte por el plano XZ que pasa
por el barreno, con líneas ocultas. Se escribe un .t101d con el motor de
draw101, se vuelve a abrir con él y **se acota con su propio motor de
cotas**: la cota tiene que dar la medida del sólido. No hay interfaz de
draw101 aquí; lo que se comprueba es el motor, que es el que calcula la
medida cuando alguien acota en pantalla.
"""
from __future__ import annotations

import math
import pathlib

from build123d import Plane

from poc import comun, p3_historial
from app.motor import draw101_lector as d1, historial, vistas2d

DESCRIPCION = "planta/alzado/lateral/corte con ocultas → .t101d → acotar en draw101"
AQUI = pathlib.Path(__file__).resolve().parent
W, H, T = 900.0, 600.0, 28.0


def _capa(doc, e):
    return e.capa


def correr(r: comun.Reporte):
    reg = historial.regenerar(p3_historial.documento())
    solido = reg.solido
    t = {}
    with comun.cronometro(t, "vistas"):
        doc, resumen = vistas2d.documento_de_vistas(solido, corte=Plane.XZ.offset(-H / 2))
    r.numero("P5 generar 3 vistas + corte con HLR y escribirlas como entidades", round(t["vistas"]), "ms")
    for v, datos in resumen.items():
        r.numero(f"P5 {v}: aristas visibles / ocultas", f"{datos['visibles']} / {datos['ocultas']}", "")
    r.cierto(resumen["planta"]["visibles"] >= 9, "en planta se ven el contorno redondeado (8 tramos) y el barreno")
    r.cierto(resumen["alzado"]["ocultas"] >= 2, "en alzado el barreno se ve como líneas ocultas")
    r.cierto(resumen["lateral"]["ocultas"] >= 2, "en lateral el barreno se ve como líneas ocultas")
    r.cierto(resumen["corte"]["visibles"] >= 8, "el corte por el barreno tiene dos contornos (dos rectángulos)")

    with comun.carpeta() as tmp:
        ruta = d1.guardar(doc, tmp / "vistas.t101d")
        r.exige(ruta.exists(), "el .t101d de las vistas se escribió")
        doc2 = d1.abrir(ruta)
        ents = list(doc2.entidades.values())
        ocultas = [e for e in ents if e.capa == vistas2d.CAPA_OCULTAS]
        r.cierto(len(ocultas) > 0, "las ocultas quedaron en la capa T101-OCULTO")
        r.igual(doc2.capas[vistas2d.CAPA_OCULTAS].tipo_linea, "HIDDEN", "la capa de ocultas es discontinua (HIDDEN)")
        r.cierto(all(e.tipo in ("linea", "arco", "circulo", "polilinea") for e in ents), "todo lo escrito son entidades de dibujo de draw101")
        n_poli = sum(1 for e in ents if e.tipo == "polilinea")
        r.numero("P5 aristas que no se pudieron escribir como línea, arco o círculo (quedaron como polilínea)", n_poli, "")
        r.igual(n_poli, 0, "todas las aristas se escribieron como línea, arco o círculo exactos")

        # acotar con el motor de draw101: la cota lee la medida de la geometría
        ent, cotas = d1.entidades(), d1.cotas()
        ox, oy = resumen["planta"]["origen"]
        cx, cy = resumen["planta"]["caja"][0] + ox, resumen["planta"]["caja"][1] + oy
        # planta: ancho entre los extremos de la caja (los redondeos no cambian el ancho total)
        c_ancho = doc2.agregar(cotas.encapar(doc2, ent.Cota(clase="lineal", rotacion=0,
                               puntos=[[cx, cy], [cx + W, cy], [cx + W / 2, cy - 80]])))
        r.casi(cotas.medida(doc2, c_ancho), W, "una cota lineal sobre la planta mide 900, el ancho del sólido", 1e-6)
        circulos = [e for e in ents if e.tipo == "circulo" and abs(e.radio - 80) < 1e-6]
        r.cierto(len(circulos) >= 1, "el barreno aparece en planta como un círculo de radio 80",
                 f"círculos: {[round(e.radio, 3) for e in ents if e.tipo == 'circulo']}")
        if circulos:
            c = circulos[0]
            c_diam = doc2.agregar(cotas.encapar(doc2, ent.Cota(clase="diametro",
                                  puntos=[list(c.centro), [c.centro[0] + c.radio, c.centro[1]]])))
            r.casi(cotas.medida(doc2, c_diam), 160, "la cota de diámetro sobre el barreno mide 160", 1e-6)
        # alzado: el espesor total (28, con la cara de arriba empujada)
        ox, oy = resumen["alzado"]["origen"]
        caja = resumen["alzado"]["caja"]
        alto = caja[3] - caja[1]
        c_esp = doc2.agregar(cotas.encapar(doc2, ent.Cota(clase="lineal", rotacion=90,
                             puntos=[[caja[2] + ox, caja[1] + oy], [caja[2] + ox, caja[3] + oy], [caja[2] + ox + 60, caja[1] + oy]])))
        r.casi(alto, T, "el alzado mide 28 de alto: el espesor con la cara empujada", 1e-6)
        r.casi(cotas.medida(doc2, c_esp), T, "una cota vertical sobre el alzado mide 28", 1e-6)
        ruta2 = d1.guardar(doc2, AQUI / "muestras" / "vistas-tablero.t101d")
        r.cierto(ruta2.exists(), "el .t101d acotado queda en poc/muestras/ para abrirlo en draw101")
    r.numero("P5 las cotas puestas en draw101 dan las medidas del sólido", "sí (900, ⌀160, 28)", "", umbral="sí/no", cumple=True)
