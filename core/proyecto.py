"""El archivo de trabajo `.t101d`, autoguardado y recuperación · features 5 y 9.

Por qué existe un formato propio si ya guardamos DXF: el DXF **no** guarda el
historial de deshacer, ni la liga de una cota con la pieza que mide (feature
58), ni de qué `.t101x` de Taller 101 vino el dibujo (feature 72). El DXF es la
**entrega**; el `.t101d` es el trabajo.

Es un ZIP con JSON adentro, no un JSON pelón: así se le pueden meter después la
miniatura, los layouts y las imágenes de fondo sin cambiar de formato ni dejar
huérfanos los archivos ya guardados.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import zipfile

from . import config
from .documento import Documento

FORMATO = 1
CARPETA_USUARIO = config.carpeta_usuario()
CARPETA_AUTO = CARPETA_USUARIO / "autoguardado"


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", texto or "sin-titulo").strip("-").lower()
    return s or "sin-titulo"


# --- Guardar / abrir -------------------------------------------------------

def guardar(doc: Documento, ruta: str | pathlib.Path) -> pathlib.Path:
    """Escribe el `.t101d`. Primero a un temporal, luego se reemplaza.

    Un guardado que truena a la mitad no debe dejar el archivo anterior roto:
    es la forma más tonta y más común de perder un día de trabajo.
    """
    ruta = pathlib.Path(ruta)
    if ruta.suffix.lower() != config.EXT_PROYECTO:
        ruta = ruta.with_suffix(config.EXT_PROYECTO)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "formato": FORMATO,
        "app": config.APP_NOMBRE,
        "guardado": dt.datetime.now().isoformat(timespec="seconds"),
        "unidad": doc.unidad,
    }
    tmp = tempfile.NamedTemporaryFile(
        delete=False, dir=str(ruta.parent), suffix=".tmp")
    tmp.close()
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
            z.writestr("documento.json",
                       json.dumps(doc.a_dict(), ensure_ascii=False))
        os.replace(tmp.name, ruta)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    doc.sucio = False
    return ruta


def abrir(ruta: str | pathlib.Path) -> Documento:
    ruta = pathlib.Path(ruta)
    with zipfile.ZipFile(ruta, "r") as z:
        meta = json.loads(z.read("meta.json").decode("utf-8"))
        if int(meta.get("formato", 1)) > FORMATO:
            raise ValueError(
                f"Este archivo lo hizo una versión más nueva de {config.APP_NOMBRE}. "
                "Actualiza el programa para abrirlo.")
        datos = json.loads(z.read("documento.json").decode("utf-8"))
    doc = Documento.de_dict(datos)
    if not doc.nombre or doc.nombre == "Sin título":
        doc.nombre = ruta.stem
    return doc


# --- Autoguardado  ·  feature 9 -------------------------------------------

def autoguardar(doc: Documento, ruta_original: str | pathlib.Path | None) -> pathlib.Path | None:
    """Copia de respaldo aparte del archivo del usuario.

    Nunca escribe encima de lo que el usuario guardó: si el programa se cae con
    el dibujo a medias, la recuperación es una **opción**, no un hecho
    consumado.
    """
    if not doc.sucio:
        return None
    CARPETA_AUTO.mkdir(parents=True, exist_ok=True)
    base = _slug(pathlib.Path(ruta_original).stem if ruta_original else doc.nombre)
    sello = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = CARPETA_AUTO / f"{base}-{sello}{config.EXT_PROYECTO}"

    guardar(doc, destino)
    doc.sucio = True          # autoguardar no es guardar: el trabajo sigue sucio

    marca = destino.with_suffix(".origen")
    marca.write_text(str(ruta_original or ""), encoding="utf-8")

    _podar(base)
    return destino


def _podar(base: str) -> None:
    copias = sorted(CARPETA_AUTO.glob(f"{base}-*{config.EXT_PROYECTO}"))
    for viejo in copias[:-config.AUTOGUARDADO_MAX]:
        try:
            viejo.unlink()
            viejo.with_suffix(".origen").unlink(missing_ok=True)
        except OSError:
            pass


def recuperables(ruta_original: str | pathlib.Path | None = None) -> list[dict]:
    """Autoguardados más nuevos que el archivo guardado del usuario.

    Es lo que se ofrece al abrir. Si el archivo en disco es más reciente que el
    autoguardado, no hay nada que recuperar y no se molesta a nadie.
    """
    if not CARPETA_AUTO.exists():
        return []
    salida = []
    for copia in sorted(CARPETA_AUTO.glob(f"*{config.EXT_PROYECTO}"), reverse=True):
        marca = copia.with_suffix(".origen")
        origen = marca.read_text(encoding="utf-8").strip() if marca.exists() else ""
        if ruta_original and origen != str(ruta_original):
            continue
        edad = copia.stat().st_mtime
        if origen and pathlib.Path(origen).exists():
            if pathlib.Path(origen).stat().st_mtime >= edad:
                continue        # lo guardado es más nuevo: no hay qué recuperar
        salida.append({
            "ruta": str(copia),
            "origen": origen,
            "cuando": dt.datetime.fromtimestamp(edad).isoformat(timespec="seconds"),
            "bytes": copia.stat().st_size,
        })
    return salida


def descartar_recuperacion(ruta: str | pathlib.Path) -> None:
    """Tirar esa copia **y sus hermanas** (mismo dibujo).

    Antes se tiraba sólo la que se ofreció, y como se guardan hasta cinco por
    dibujo, el aviso volvía a salir en el siguiente arranque con la siguiente.
    Era el «siempre, no importa qué» de Mike. Decir que no es decir que no a
    todas las de ese dibujo.
    """
    ruta = pathlib.Path(ruta)
    marca = ruta.with_suffix(".origen")
    origen = marca.read_text(encoding="utf-8").strip() if marca.exists() else None
    base = ruta.stem.rsplit("-", 2)[0]      # nombre-AAAAMMDD-HHMMSS → nombre
    for copia in list(CARPETA_AUTO.glob(f"{base}-*{config.EXT_PROYECTO}")) if CARPETA_AUTO.exists() else []:
        m = copia.with_suffix(".origen")
        o = m.read_text(encoding="utf-8").strip() if m.exists() else None
        if copia == ruta or o == origen:
            copia.unlink(missing_ok=True)
            m.unlink(missing_ok=True)


# --- ¿Se cerró bien la vez pasada?  ·  6-sep, Mike ---------------------------
#
# *«Siempre que abro shape101 dice que hay un documento que no se guardó»*. Lo
# que decidió Mike: (1) si el programa se cerró **sin** pasar por la X de la
# ventana, eso es la señal de que se cayó y hay qué recuperar; (2) si se cerró
# por la X, se pregunta si guardar y, diga sí o no, ya no queda nada para
# recuperar.
#
# Se hace con una marca en disco: al arrancar el motor se escribe
# `sesion.abierta`; al cerrar bien (Electron avisa antes de matar el motor) se
# borra junto con todos los autoguardados. Si al arrancar la marca **ya está**,
# la vez pasada no se cerró bien: los autoguardados se quedan y se ofrecen.

NOMBRE_MARCA = "sesion.abierta"


def _marca_sesion() -> pathlib.Path:
    # Se calcula al momento: las pruebas desvían CARPETA_AUTO.
    return CARPETA_AUTO / NOMBRE_MARCA


def iniciar_sesion() -> bool:
    """Al arrancar. Devuelve True si la sesión anterior se cayó."""
    CARPETA_AUTO.mkdir(parents=True, exist_ok=True)
    se_cayo = _marca_sesion().exists()
    if not se_cayo:
        # Cierre limpio la vez pasada (o primer arranque): lo que haya en
        # autoguardado es basura de una versión que no limpiaba.
        _tirar_autoguardados()
    try:
        _marca_sesion().write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except OSError:
        pass
    return se_cayo


def cerrar_sesion() -> None:
    """Al cerrar por la X, ya contestado si se guarda o no: no queda nada."""
    _tirar_autoguardados()
    _marca_sesion().unlink(missing_ok=True)


def _tirar_autoguardados() -> None:
    if not CARPETA_AUTO.exists():
        return
    for copia in CARPETA_AUTO.glob(f"*{config.EXT_PROYECTO}"):
        try:
            copia.unlink()
            copia.with_suffix(".origen").unlink(missing_ok=True)
        except OSError:
            pass
