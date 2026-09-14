"""Fabrica un plano sintético del tamaño de un plano real grande (≈ 21 700
entidades, como el Mondelez), para medir abrir, recargar, índice y ediciones
sin depender de un archivo de cliente. Determinista (semilla fija).

    python pruebas/carga/sintetico.py /tmp/sintetico.t101d
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from core.documento import Documento          # noqa: E402
from core.entidades import de_dict            # noqa: E402
from core import proyecto                     # noqa: E402

W, H = 60000.0, 40000.0


def fabricar(semilla: int = 7) -> Documento:
    rnd = random.Random(semilla)
    doc = Documento.nuevo()

    def P():
        return [rnd.uniform(0, W), rnd.uniform(0, H)]

    def seg(n=800.0):
        a = P(); ang = rnd.random() * 2 * math.pi; L = rnd.uniform(50, n)
        return a, [a[0] + L * math.cos(ang), a[1] + L * math.sin(ang)]

    capas = ["0", "MUROS", "MUEBLES", "COTAS"]
    for _ in range(12000):
        a, b = seg()
        doc.agregar(de_dict({"tipo": "linea", "p1": a, "p2": b, "capa": rnd.choice(capas)}))
    for _ in range(4000):
        a = P()
        pts = [[a[0] + rnd.uniform(-600, 600), a[1] + rnd.uniform(-600, 600), (0.5 if i in (1, 4) else 0.0)] for i in range(6)]
        doc.agregar(de_dict({"tipo": "polilinea", "puntos": pts, "cerrada": rnd.random() < 0.5, "capa": "MUEBLES"}))
    for _ in range(2000):
        doc.agregar(de_dict({"tipo": "circulo", "centro": P(), "radio": rnd.uniform(10, 300)}))
    for _ in range(1500):
        doc.agregar(de_dict({"tipo": "arco", "centro": P(), "radio": rnd.uniform(10, 300), "ang_ini": 0, "ang_fin": rnd.uniform(30, 300)}))
    for _ in range(1500):
        doc.agregar(de_dict({"tipo": "texto", "p": P(), "texto": f"P-{rnd.randint(1, 999)} mueble {rnd.randint(1, 99)}", "altura": rnd.choice([25, 35, 50])}))
    for _ in range(700):
        a, b = seg(3000)
        doc.agregar(de_dict({"tipo": "cota", "clase": "lineal", "puntos": [a, b, [a[0], a[1] + 400]], "capa": "COTAS"}))
    return doc


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sintetico.t101d"
    doc = fabricar()
    proyecto.guardar(doc, ruta)
    print(f"{len(doc.entidades)} entidades → {ruta}")
