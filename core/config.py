"""Constantes de shape101: identidad, unidades y parámetros del DXF.

Todo lo que se pueda tocar sin abrir el motor vive aquí.
"""

from __future__ import annotations

# --- Identidad Taller 101 --------------------------------------------------
# Mismos valores que core/marca.py de Taller 101. Si la identidad cambia, se
# cambia aquí y en ui/styles.css, en ningún otro lado.
AZUL = "#0080C1"
AZUL_CLARO = "#3AA3DC"
SOMBRA = "#122733"
CANTO = "#C8813A"
ADVERTENCIA = "#C9694A"

APP_NOMBRE = "shape101"      # así, con minúscula: lo decidió Mike el 6-sep-2026

# Dónde viven las versiones y los avisos de toda la familia *101 (shape101,
# nest101…): un repositorio público de GitHub, `descargas`. Los JSON se leen
# de raw.githubusercontent.com y los instaladores van en Releases
# (build/publicar_github.py). `GITHUB_USUARIO` es la cuenta de Taller 101.
GITHUB_USUARIO = "mikebalcazar"
GITHUB_REPO = "descargas"
URL_DESCARGAS = f"https://raw.githubusercontent.com/{GITHUB_USUARIO}/{GITHUB_REPO}/main"
# Cómo se llamó antes: DIBUJADOR hasta la 0.16.1, t101draw de la 0.17.0 a la
# 0.18.2. El más reciente primero: es del que conviene heredar la carpeta.
APP_NOMBRES_VIEJOS = ()          # shape101 no hereda la carpeta de nadie: es otro programa
APP_NOMBRE_VIEJO = ""
# El APP_ID **no** cambia con el nombre: es lo que Windows y macOS usan para
# saber que el instalador nuevo es el mismo programa y actualizar en su lugar.
APP_ID = "mx.taller101.shape101"
EXT_PROYECTO = ".101s"


def carpeta_usuario() -> "pathlib.Path":
    """`~/Taller 101/shape101`: preferencias, autoguardado, bloques, caché.

    Cuando el programa se llamaba t101draw (o antes, DIBUJADOR) esa carpeta
    llevaba ese nombre. La primera vez que corre con el nombre nuevo, si
    la vieja existe y la nueva no, se **copia** entera —no se mueve: si algo
    sale mal a medias, el usuario no pierde nada— y a partir de ahí se usa la
    nueva. La vieja se queda; no es nuestra para borrarla.
    """
    import pathlib, shutil
    base = pathlib.Path.home() / "Taller 101"
    nueva = base / APP_NOMBRE
    if not nueva.exists():
        for viejo in APP_NOMBRES_VIEJOS:
            vieja = base / viejo
            if vieja.is_dir():
                try:
                    shutil.copytree(vieja, nueva, ignore=shutil.ignore_patterns("cache"))
                except Exception:
                    pass
                break
    return nueva

# El número vive en core/version.py, que es también lo que lee el armador del
# instalador. Se reexporta aquí para no tener que importar dos módulos.
from .version import VERSION, FECHA as VERSION_FECHA  # noqa: E402

# --- DXF -------------------------------------------------------------------
# R2013 (AC1027). Lo abren AutoCAD 2013+, Rhino, BricsCAD, LibreCAD, QCAD,
# Illustrator, Inkscape y Fusion, y soporta MTEXT, HATCH, DIMENSION, bloques,
# layouts y viewports — todo lo que necesita la hoja de ruta.
DXF_VERSION = "R2013"

# Unidades del dibujo. 4 = milímetros en el código $INSUNITS del DXF.
INSUNITS_MM = 4
UNIDAD = "mm"

# Grosores válidos en DXF, en centésimas de milímetro. -1 = por capa,
# -2 = por bloque, -3 = por omisión. Cualquier otro valor lo rechaza AutoCAD.
GROSORES = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80,
            90, 100, 106, 120, 140, 158, 200, 211]
GROSOR_POR_CAPA = -1
GROSOR_POR_BLOQUE = -2
GROSOR_OMISION = -3

# --- Autoguardado ----------------------------------------------------------
AUTOGUARDADO_SEG = 120
AUTOGUARDADO_MAX = 5  # cuántas copias se conservan por proyecto

# --- Historial -------------------------------------------------------------
HISTORIAL_MAX = 500  # operaciones de deshacer

# Unidad de trabajo de un dibujo **nuevo** (Mike, 9-sep-2026: «quiero que las
# medidas por default de shape101 sean cm»). Los archivos abiertos conservan
# la suya; un DXF ajeno se trae a milímetros como siempre. Ver core/unidades.py.
UNIDADES_OMISION = "cm"
