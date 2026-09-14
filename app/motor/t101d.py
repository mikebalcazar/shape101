"""Leer un dibujo de draw101 (`.t101d`) **sin draw101**  ·  bloque 2.

Hasta ahora el único lector (`draw101_lector.py`) importaba el `core` de
draw101: sirve en la carpeta de desarrollo, donde draw101 está al lado, pero
no en la máquina del taller, donde shape101 está instalado solo. Aquí se lee
el archivo tal cual es: un ZIP con `meta.json` y `documento.json`
(`core/proyecto.py` de draw101). Sin importar nada de draw101, sin copiarle
código.

Dos cosas que este lector hace y que se pasan por alto fácil:

- **Unidades.** Un dibujo de draw101 puede estar en mm, cm o m, y sus
  coordenadas van en esa unidad. shape101 trabaja en milímetros. Un tablero
  dibujado en centímetros que entrara sin convertir saldría diez veces más
  chico, y el error sólo se vería ya cortado.
- **Qué es geometría y qué no.** Del dibujo sólo se toman líneas, arcos,
  círculos y polilíneas **del modelo** (no de las hojas de impresión), en capa
  visible y no apagadas. Cotas, textos, rayados y bloques se cuentan y se
  reportan, pero no entran al boceto.

El `bulge` de una polilínea (convención DXF, `tan(θ/4)`) es adimensional: al
convertir unidades se escalan las coordenadas y el bulge NO. Escalarlo
cambiaría la curvatura del arco, no su tamaño.
"""
from __future__ import annotations

import json
import pathlib
import zipfile

FORMATO_MAX = 1
MM_POR_UNIDAD = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
GEOMETRIA = ("linea", "circulo", "arco", "polilinea")


def _escalar_punto(p, f: float):
    """[x, y] o [x, y, bulge] → escalado en x, y; el bulge se queda igual."""
    out = [p[0] * f, p[1] * f]
    if len(p) > 2:
        out.append(p[2])
    return out


def _escalar(entidad: dict, f: float) -> dict:
    if f == 1.0:
        return entidad
    e = dict(entidad)
    t = e.get("tipo")
    if t == "linea":
        e["p1"], e["p2"] = _escalar_punto(e["p1"], f), _escalar_punto(e["p2"], f)
    elif t in ("circulo", "arco"):
        e["centro"] = _escalar_punto(e["centro"], f)
        e["radio"] = e["radio"] * f                 # los ángulos del arco no se tocan
    elif t == "polilinea":
        e["puntos"] = [_escalar_punto(p, f) for p in e["puntos"]]
    return e


def leer(ruta) -> dict:
    """El dibujo como boceto de shape101, ya en milímetros.

    Devuelve `{archivo, dibujo, unidades, factor_mm, entidades, ignoradas,
    tipos_ignorados}`. Un archivo que no existe, que no es un ZIP o que no
    trae los dos JSON adentro levanta `ValueError` con el nombre del archivo:
    es lo que la API convierte en un 400 con un mensaje que se entiende.
    """
    ruta = pathlib.Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"no existe el archivo {ruta}")
    try:
        with zipfile.ZipFile(ruta) as z:
            meta = json.loads(z.read("meta.json").decode("utf-8"))
            datos = json.loads(z.read("documento.json").decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"{ruta.name} no es un dibujo de draw101 (.t101d)") from e
    if int(meta.get("formato", 1)) > FORMATO_MAX:
        raise ValueError(f"{ruta.name} lo hizo una versión más nueva de draw101 (formato {meta['formato']})")

    unidades = datos.get("unidades") if datos.get("unidades") in MM_POR_UNIDAD else "mm"
    factor = MM_POR_UNIDAD[unidades]

    capas = datos.get("capas") or []
    apagadas = {c.get("nombre") for c in capas if not c.get("visible", True)}

    entidades, ignoradas, tipos = [], 0, set()
    for e in datos.get("entidades") or []:
        if not isinstance(e, dict):
            continue
        if e.get("espacio", "") != "":          # lo que vive en una hoja de impresión no es la pieza
            ignoradas += 1
            tipos.add("hoja")
            continue
        if not e.get("visible", True) or e.get("capa") in apagadas:
            ignoradas += 1
            tipos.add("apagada")
            continue
        if e.get("tipo") not in GEOMETRIA:
            ignoradas += 1
            tipos.add(str(e.get("tipo")))
            continue
        entidades.append(_escalar(e, factor))

    return {"archivo": str(ruta), "dibujo": datos.get("nombre") or ruta.stem,
            "unidades": unidades, "factor_mm": factor, "entidades": entidades,
            "ignoradas": ignoradas, "tipos_ignorados": sorted(tipos)}
