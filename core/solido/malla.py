"""Del sólido a lo que ve el navegador: una malla POR CARA (con su nombre,
para poder elegirla con un raycast), las aristas, y el glTF para presentación.

Una cara que no cambió (misma superficie, misma área, mismo centro) no se
vuelve a teselar: la caché la lleva quien llama (el servidor o el motor de la
PoC) y aquí sólo se consulta y se rehace. Lo mismo lo usan la API de la app y
la de la prueba de concepto: una sola copia.
"""
from __future__ import annotations

import pathlib
import tempfile
import time

from build123d import export_gltf

from core.solido import nombres


def malla_de(reg, cache: dict | None = None, tolerancia: float = 0.5, angular: float = 0.3,
             ms_regenerar: float = 0.0) -> tuple[dict, dict]:
    """(modelo, caché nueva). `reg` es un Regenerado con .solido y .nombrador."""
    cache = cache or {}
    t = time.perf_counter()
    caras, nueva = [], {}
    reteseladas = 0
    for nombre, f in reg.nombrador.caras.items():
        c = f.center()
        clave = (nombre, tuple(round(x, 6) if isinstance(x, float) else x for x in nombres.superficie(f)),
                 round(f.area, 4), round(c.X, 4), round(c.Y, 4), round(c.Z, 4))
        m = cache.get(clave)
        if m is None:
            vs, tris = f.tessellate(tolerancia, angular)
            m = {"nombre": nombre, "v": [k for v in vs for k in (v.X, v.Y, v.Z)], "i": [k for t3 in tris for k in t3]}
            reteseladas += 1
        nueva[clave] = m
        caras.append(m)
    aristas = []
    for e in reg.solido.edges():
        n = 2 if e.geom_type.name == "LINE" else 24
        aristas.append([[p.X, p.Y, p.Z] for p in (e.position_at(k / n) for k in range(n + 1))])
    modelo = {"caras": caras, "aristas": aristas, "n_caras": len(caras),
              "n_triangulos": sum(len(c["i"]) // 3 for c in caras), "reteseladas": reteseladas,
              "ms_regenerar": round(ms_regenerar, 1), "ms_teselar": round((time.perf_counter() - t) * 1000, 1)}
    return modelo, nueva


def gltf_de(solido, ruta=None, binario: bool = True) -> bytes:
    """El sólido teselado como glTF (binario .glb si `binario`). Devuelve los bytes."""
    ruta = pathlib.Path(ruta) if ruta else pathlib.Path(tempfile.mkdtemp()) / ("modelo.glb" if binario else "modelo.gltf")
    export_gltf(solido, str(ruta), binary=binario, linear_deflection=0.5, angular_deflection=0.3)
    return ruta.read_bytes()
