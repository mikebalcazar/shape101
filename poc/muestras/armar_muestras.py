"""Escribe los bocetos de muestra con el motor de draw101: son documentos
.t101d de verdad, con cotas, como los dibujaría alguien en draw101.

    python poc/muestras/armar_muestras.py

Se versionan (pesan 1–2 KB) para que la prueba corra sin draw101 a la mano si
hiciera falta y para que Mike pueda abrirlos en draw101.
"""
from __future__ import annotations

import math
import os
import pathlib
import sys
import tempfile

os.environ.setdefault("HOME", tempfile.mkdtemp())
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app.motor import draw101_lector as d1  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
ANCHO, ALTO, RADIO_BARRENO, RADIO_ESQUINA = 900.0, 600.0, 80.0, 20.0


def tablero(redondeado: bool):
    ent, cotas = d1.entidades(), d1.cotas()
    doc = d1.nuevo_documento()
    if not redondeado:
        pts = [[0, 0, 0], [ANCHO, 0, 0], [ANCHO, ALTO, 0], [0, ALTO, 0]]
    else:
        r = RADIO_ESQUINA
        b = math.tan(math.radians(90) / 4)      # bulge de un cuarto de vuelta antihorario
        pts = [[r, 0, 0], [ANCHO - r, 0, b], [ANCHO, r, 0], [ANCHO, ALTO - r, b],
               [ANCHO - r, ALTO, 0], [r, ALTO, b], [0, ALTO - r, 0], [0, r, b]]
    doc.agregar(ent.Polilinea(puntos=pts, cerrada=True, capa="0"))
    doc.agregar(ent.Circulo(centro=[ANCHO / 2, ALTO / 2], radio=RADIO_BARRENO, capa="0"))
    # Cotas como las pondría el taller: ancho, alto y diámetro del barreno.
    doc.agregar(cotas.encapar(doc, ent.Cota(clase="lineal", rotacion=0,
                puntos=[[0, 0], [ANCHO, 0], [ANCHO / 2, -80]])))
    doc.agregar(cotas.encapar(doc, ent.Cota(clase="lineal", rotacion=90,
                puntos=[[ANCHO, 0], [ANCHO, ALTO], [ANCHO + 80, ALTO / 2]])))
    doc.agregar(cotas.encapar(doc, ent.Cota(clase="diametro",
                puntos=[[ANCHO / 2, ALTO / 2], [ANCHO / 2 + RADIO_BARRENO, ALTO / 2]])))
    doc.nombre = "tablero-redondeado" if redondeado else "tablero"
    return doc


if __name__ == "__main__":
    for red in (False, True):
        doc = tablero(red)
        ruta = d1.guardar(doc, AQUI / (doc.nombre + ".t101d"))
        print(ruta.name, ruta.stat().st_size, "bytes")
