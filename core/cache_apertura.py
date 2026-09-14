"""Caché de apertura: reabrir un plano pesado cuesta segundos, no un minuto.

Abrir el DWG de Mondelez son 53 segundos: 38 de convertirlo (LibreDWG, un
proceso aparte que no podemos acelerar), 13 de leer los 235 MB de DXF, y el
resto de importar. **Nada de eso cambia entre una apertura y la siguiente** si
el archivo no cambió. AutoCAD hace lo mismo con sus archivos de trabajo, y Rhino
con los suyos: lo que ya se calculó no se vuelve a calcular.

Lo que se guarda, por archivo:

  · el documento ya leído, en `pickle` — se recupera en 2 segundos;
  · el DXF convertido, que el documento necesita para exportar sin perder lo que
    no modelamos (ver `Documento.origen_dxf`);
  · el informe de la lectura, para que la interfaz diga lo mismo que dijo la
    primera vez;
  · el estado de sus referencias externas, para invalidar la caché el día que
    aparezca un archivo que antes faltaba.

La llave es ruta + tamaño + fecha del archivo + versión del programa: si
cualquiera cambia, no se usa. Un plano leído con una versión vieja del lector
podría tener errores que la nueva ya no comete.

Si algo falla al leer o al escribir la caché **no pasa nada**: se abre por el
camino normal. Una caché nunca puede ser motivo de que un plano no abra.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import pickle
import shutil
import time

from . import preferencias
from . import version as mod_version

CARPETA = preferencias.CARPETA / "cache"

#: Por debajo de esto no vale la pena: se abre más rápido de lo que se guarda.
MINIMO_BYTES = 2 * 1024 * 1024

#: Cuánto disco se le deja a la caché. Pasado esto se tiran los más viejos.
MAXIMO_MB = 3000

#: Se puede apagar por si acaso, sin tocar código.
APAGADA = os.environ.get("T101DRAW_SIN_CACHE", "") == "1"


def _llave(ruta: pathlib.Path) -> str:
    st = ruta.stat()
    crudo = f"{ruta.resolve()}|{st.st_size}|{st.st_mtime_ns}|{mod_version.VERSION}"
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()


def aplica(ruta: pathlib.Path) -> bool:
    if APAGADA:
        return False
    try:
        return ruta.is_file() and ruta.stat().st_size >= MINIMO_BYTES
    except OSError:
        return False


def _estado_xrefs(doc, carpeta: pathlib.Path) -> dict:
    """Qué archivo tiene cada referencia externa ahora mismo, o None."""
    from . import dxf_lector
    estado = {}
    for nombre, dicha in (getattr(doc, "xrefs", None) or {}).items():
        hallado = next((p for p in dxf_lector._candidatos_xref(carpeta, dicha)
                        if p.is_file()), None)
        try:
            estado[nombre] = (str(hallado), hallado.stat().st_mtime_ns) if hallado else None
        except OSError:
            estado[nombre] = None
    return estado


def leer(ruta: pathlib.Path):
    """El documento y el informe guardados, o None si no hay o ya no sirven."""
    if not aplica(ruta):
        return None
    try:
        base = CARPETA / _llave(ruta)
        paquete = base.with_suffix(".pkl")
        if not paquete.is_file():
            return None
        with open(paquete, "rb") as f:
            datos = pickle.load(f)
        doc, informe = datos["doc"], datos["informe"]
        # El DXF convertido tiene que seguir ahí, o el documento no podría
        # exportar sin perder lo ajeno. Sin él, mejor abrir de nuevo.
        dxf = base.with_suffix(".dxf")
        if datos.get("con_dxf") and not dxf.is_file():
            return None
        doc.origen_dxf_ruta = str(dxf) if datos.get("con_dxf") else None
        # Si apareció (o cambió) el archivo de una referencia externa que
        # antes faltaba, lo guardado ya no cuenta la verdad.
        if _estado_xrefs(doc, ruta.parent) != datos.get("xrefs", {}):
            return None
        doc.cache = {}
        doc.historial.silencio = False
        # El contador de ids arranca donde lo dejó este documento, como al leer
        # de verdad: si no, la primera línea nueva podría llevarse el id de una
        # existente.
        from . import entidades as ent_mod
        ent_mod.sembrar_contador(doc.entidades.values())
        os.utime(paquete, None)          # para que el podado sepa que se usó
        informe.avisos = [a for a in informe.avisos if not a.startswith("Abierto de la caché")]
        informe.avisos.append(
            "Abierto de la caché: el archivo no cambió desde la última vez, así "
            "que se recuperó lo ya leído en vez de convertirlo otra vez.")
        return doc, informe
    except Exception:
        return None


def guardar(ruta: pathlib.Path, doc, informe) -> bool:
    if not aplica(ruta):
        return False
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        base = CARPETA / _llave(ruta)
        con_dxf = bool(doc.origen_dxf_ruta and pathlib.Path(doc.origen_dxf_ruta).is_file())
        if con_dxf:
            shutil.copyfile(doc.origen_dxf_ruta, base.with_suffix(".dxf"))
        # Lo teselado no se guarda: se recalcula en milisegundos y pesa.
        cache_antes, doc.cache = doc.cache, {}
        try:
            datos = {"doc": doc, "informe": informe, "con_dxf": con_dxf,
                     "xrefs": _estado_xrefs(doc, ruta.parent),
                     "version": mod_version.VERSION, "cuando": time.time()}
            tmp = base.with_suffix(".pkl.tmp")
            with open(tmp, "wb") as f:
                pickle.dump(datos, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, base.with_suffix(".pkl"))
        finally:
            doc.cache = cache_antes
        podar()
        return True
    except Exception:
        return False


def podar(maximo_mb: int = MAXIMO_MB) -> None:
    """Tira lo más viejo cuando la caché pasa del tope."""
    try:
        if not CARPETA.is_dir():
            return
        paquetes = sorted(CARPETA.glob("*.pkl"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in CARPETA.iterdir() if p.is_file())
        while paquetes and total > maximo_mb * 1024 * 1024:
            viejo = paquetes.pop(0)
            for hermano in (viejo, viejo.with_suffix(".dxf")):
                if hermano.is_file():
                    total -= hermano.stat().st_size
                    hermano.unlink()
    except Exception:
        pass


def vaciar() -> None:
    shutil.rmtree(CARPETA, ignore_errors=True)
