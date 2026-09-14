"""Buscar e instalar versiones nuevas de shape101  ·  0.19.2.

Mike, 7-sep-2026: *«hay que implementar un checador de actualizaciones de
versión. Eso quiere decir que en algún lugar hay que ir subiendo la última
versión, para también ir probando el actualizador»*.

Cómo funciona, y por qué así:

  · **El lugar** es un repositorio público de GitHub de Taller 101,
    `descargas` (`config.URL_DESCARGAS`), compartido por toda la familia *101.
    Ahí vive `shape101.json`, que dice cuál es la última versión, cuánto pesa,
    su sha256 y de dónde se baja; el instalador va en GitHub Releases (hasta
    2 GB por archivo, descarga libre). `build/publicar_github.py` sube todo
    por API: nadie arrastra nada. El JSON admite `url` (un archivo) o
    `partes` (pedazos que se unen), por si algún día toca otro sitio.

  · **La app revisa** al arrancar (unos segundos después, sin estorbar) y una
    vez al día mientras esté abierta; también a mano con ACTUALIZAR o Ayuda ▾
    → Buscar actualizaciones. La revisión es un JSON de un kilobyte con 5
    segundos de espera: sin internet no se nota.

  · **Bajar e instalar** es decisión del usuario, siempre. Se bajan los
    pedazos a `~/Taller 101/shape101/descargas/`, se unen, se comprueba el
    sha256 —si no cuadra, no se instala— y se corre el instalador con su
    ventana. El instalador quita la versión anterior solo (ver
    `build/armar_paquete.py`). La app se cierra para dejarlo trabajar.

  · Una versión se puede **ignorar** («no me vuelvas a decir de la 0.20.0»);
    la siguiente sí se avisa. Y `actualizaciones_auto: false` apaga la
    revisión automática; la manual sigue.

El puntero se puede cambiar con la variable de entorno `SHAPE101_PUNTERO`
(las pruebas levantan un servidor local y apuntan ahí).
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.request

from . import config, preferencias
from .version import VERSION

PUNTERO = os.environ.get("SHAPE101_PUNTERO") or f"{config.URL_DESCARGAS}/{config.APP_NOMBRE}.json"
ESPERA_RED = 5
AGENTE = f"shape101/{VERSION} (Taller 101)"

_estado = {"fase": "nada", "pct": 0, "mensaje": "", "version": "", "ruta": ""}
_hilo: threading.Thread | None = None
_candado = threading.Lock()
_ultima_revision: dict = {"cuando": 0.0, "datos": None}


def _leer_url(url: str, espera: int = ESPERA_RED) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return r.read()


def es_de_pruebas(v: str = "") -> bool:
    """¿Esta versión es de la línea de pruebas («X.0.1»)?

    Las entregas de prueba no llevan número de la serie publicada, así que
    compararlas contra el sitio no tiene sentido: `mas_nueva` sólo mira los
    dígitos, y «X.0.1» se leería como «0.1» — más viejo que todo lo publicado,
    y la app nagearía con «hay versión nueva» en cada arranque. Una entrega de
    pruebas **no se actualiza sola**: se instala a mano, que es justo lo que se
    está probando.
    """
    v = (v or VERSION).strip()
    return not v[:1].isdigit()


def mas_nueva(a: str, b: str) -> bool:
    """¿`a` es más nueva que `b`? «0.19.2» > «0.19.1»; «0.19» == «0.19.0»."""
    def partes(v):
        return [int(x) for x in re.findall(r"\d+", v or "")]
    pa, pb = partes(a), partes(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return pa > pb


def _plataforma() -> str:
    return "windows" if sys.platform == "win32" else ("mac" if sys.platform == "darwin" else "linux")


def _consultar(espera: int = ESPERA_RED) -> dict | None:
    """Va al puntero y guarda lo que diga. None si no contestó."""
    try:
        datos = json.loads(_leer_url(PUNTERO, espera).decode("utf-8"))
    except Exception:
        return None
    r = _interpretar(datos)
    if r is not None:
        _ultima_revision.update({"cuando": time.time(), "datos": r})
    return r


_vigilante: threading.Thread | None = None


def iniciar_vigilancia() -> None:
    """Consulta el sitio **en un hilo aparte** desde que arranca el motor  ·  0.20.1.

    Mike (9-sep-2026): «cuando arranco el programa se tarda muchísimo en
    avisarme que hay nueva versión, o muchas veces ni me avisa». Pasaban dos
    cosas: la interfaz esperaba 12 s y luego la consulta se hacía en la
    petición misma (hasta 5 s con el sitio lento); y si la red no estaba lista
    al arrancar, no se volvía a intentar hasta 24 h después. Ahora el hilo
    pregunta a los 2 s de arrancar, reintenta cada 3 minutos hasta que el
    sitio conteste, y luego repite cada 6 h. La interfaz sólo lee lo guardado.
    """
    global _vigilante
    if _vigilante is not None:
        return

    def correr():
        time.sleep(2)
        while True:
            r = _consultar(espera=15)
            try:
                from . import avisos as _av
                _av.traer(forzar=True)
            except Exception:
                pass
            time.sleep(6 * 3600 if r is not None else 180)

    _vigilante = threading.Thread(target=correr, name="shape101-actualizaciones", daemon=True)
    _vigilante.start()


def ultimo(forzar: bool = False) -> dict | None:
    """Lo que dice el puntero de Taller 101, o None si no contestó.

    Sin `forzar` se devuelve lo que trajo el vigilante (o la última consulta,
    si es de hace menos de 6 h): la interfaz pregunta varias veces (arranque,
    menú, consola) y nunca debe quedarse esperando a la red. Con `forzar`
    (ACTUALIZAR a mano) se consulta ahí mismo.
    """
    if not forzar and _ultima_revision["datos"] is not None and time.time() - _ultima_revision["cuando"] < 6 * 3600:
        return _ultima_revision["datos"]
    if not forzar and _vigilante is not None:
        return _ultima_revision["datos"]          # el hilo se encarga; no se espera aquí
    return _consultar()


def _interpretar(datos: dict) -> dict | None:
    d = datos.get("shape101") or {}
    if not d.get("version"):
        return None
    # Si el JSON no trae sección para este sistema, se usa la de Windows: es
    # la única con instalador hoy; en otros sistemas no se instala desde aquí
    # (`se_puede_instalar`), pero sí se puede ver y bajar.
    plat = d.get(_plataforma()) or d.get("windows") or {}
    r = {
        "version": str(d["version"]),
        "fecha": d.get("fecha", ""),
        "notas": list(d.get("notas") or []),
        "bytes": int(plat.get("bytes") or d.get("bytes") or 0),
        "sha256": str(plat.get("sha256") or d.get("sha256") or "").lower(),
        "archivo": plat.get("archivo") or "",
        "partes": list(plat.get("partes") or []),
        "url": plat.get("url") or "",
        "pagina": d.get("pagina") or "",
    }
    return r


def resumen(con_red: bool = True, forzar: bool = False) -> dict:
    """Lo que enseña la interfaz: qué corre, cuál es la última, si conviene."""
    prefs = preferencias.leer()
    ult = ultimo(forzar) if con_red else None
    hay = bool(ult and not es_de_pruebas() and mas_nueva(ult["version"], VERSION))
    ignorada = bool(hay and prefs.get("version_ignorada") == ult["version"])
    se_puede = bool(hay and sys.platform == "win32" and (ult["partes"] or ult["url"]))
    return {
        "actual": VERSION,
        "ultimo": ult,
        "hay_nueva": hay,
        "ignorada": ignorada,
        "se_puede_instalar": se_puede,
        "auto": bool(prefs.get("actualizaciones_auto", True)),
        "estado": dict(_estado),
        "consulto": ult is not None,
    }


def ignorar(version: str) -> dict:
    preferencias.guardar({"version_ignorada": str(version or "")})
    return {"ok": True, "version_ignorada": version}


# --- Bajar ------------------------------------------------------------------

def estado() -> dict:
    return dict(_estado)


def _poner(fase: str, pct: float = 0, mensaje: str = "", version: str | None = None, ruta: str | None = None):
    _estado["fase"] = fase
    _estado["pct"] = round(pct)
    _estado["mensaje"] = mensaje
    if version is not None:
        _estado["version"] = version
    if ruta is not None:
        _estado["ruta"] = ruta


def _carpeta_descargas() -> pathlib.Path:
    c = config.carpeta_usuario() / "descargas"
    c.mkdir(parents=True, exist_ok=True)
    return c


def _bajar_a(url: str, f, total_global: int, ya: int, version: str) -> int:
    """Baja `url` escribiendo en `f`; devuelve los bytes leídos."""
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    leido = 0
    ultimo_aviso = 0.0
    with urllib.request.urlopen(pedido, timeout=60) as r:
        while True:
            trozo = r.read(512 * 1024)
            if not trozo:
                break
            f.write(trozo)
            leido += len(trozo)
            if time.time() - ultimo_aviso > 0.2:
                ultimo_aviso = time.time()
                acumulado = ya + leido
                pct = acumulado * 100 / total_global if total_global else 0
                _poner("descargando", pct,
                       f"Bajando shape101 {version}… {acumulado / 1e6:.0f} de {total_global / 1e6:.0f} MB"
                       if total_global else f"Bajando shape101 {version}… {acumulado / 1e6:.0f} MB")
    return leido


def _sha256(ruta: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _trabajo(ult: dict) -> None:
    version = ult["version"]
    try:
        nombre = ult["archivo"] or f"shape101-{version}-setup.exe"
        destino = _carpeta_descargas() / nombre
        parcial = destino.with_suffix(destino.suffix + ".parte")
        # Si ya está bajado y cuadra, no se vuelve a bajar.
        if destino.exists() and ult["sha256"] and _sha256(destino) == ult["sha256"]:
            _poner("listo", 100, f"shape101 {version} ya estaba bajado.", version, str(destino))
            return
        _poner("descargando", 0, f"Bajando shape101 {version}…", version, "")
        fuentes = ult["partes"] or [ult["url"]]
        total = ult["bytes"]
        ya = 0
        with open(parcial, "wb") as f:
            for u in fuentes:
                ya += _bajar_a(u, f, total, ya, version)
        if total and abs(ya - total) > 0:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(f"Se bajaron {ya} bytes y el sitio dice {total}: descarga incompleta.")
        _poner("comprobando", 100, "Comprobando que lo bajado esté íntegro…", version)
        if ult["sha256"]:
            huella = _sha256(parcial)
            if huella != ult["sha256"]:
                parcial.unlink(missing_ok=True)
                raise RuntimeError("Lo bajado no cuadra con la huella que publica Taller 101. No se instala. "
                                   "Inténtalo de nuevo más tarde.")
        parcial.replace(destino)
        _poner("listo", 100, f"shape101 {version} bajado y comprobado. Listo para instalar.", version, str(destino))
    except Exception as exc:
        _poner("error", 0, f"No se pudo bajar la actualización: {exc}", version, "")


def bajar() -> dict:
    """Arranca la descarga en un hilo. Devuelve el estado de inmediato."""
    global _hilo
    with _candado:
        if _hilo and _hilo.is_alive():
            return dict(_estado)
        ult = ultimo()
        if es_de_pruebas() or not ult or not mas_nueva(ult["version"], VERSION):
            _poner("nada", 0, "No hay versión nueva.")
            return dict(_estado)
        if not (ult["partes"] or ult["url"]):
            _poner("manual", 0, "Esta versión no trae instalador para bajar; se abre la página.", ult["version"])
            return {**_estado, "abrir": ult.get("pagina") or ""}
        # El estado se pone **antes** de arrancar el hilo: quien preguntó
        # justo ahora ve «descargando», no un «nada» de medio milisegundo.
        _poner("descargando", 0, f"Bajando shape101 {ult['version']}…", ult["version"], "")
        _hilo = threading.Thread(target=_trabajo, args=(ult,), daemon=True)
        _hilo.start()
        return dict(_estado)


def ruta_lista() -> str | None:
    """El instalador bajado y comprobado, si lo hay."""
    if _estado.get("fase") == "listo" and _estado.get("ruta") and pathlib.Path(_estado["ruta"]).exists():
        return _estado["ruta"]
    return None


def texto_bat(exe: pathlib.Path) -> str:
    """El .bat que espera dos segundos y abre el instalador (ver abajo)."""
    return ("@echo off\r\n"
            "rem shape101: espera a que el programa cierre y corre el instalador.\r\n"
            "ping -n 3 127.0.0.1 >nul\r\n"
            f'start "" "{exe}"\r\n')


def lanzar_instalador(ruta: str) -> bool:
    """Arranca el instalador aparte (sólo Windows). La app se cierra después.

    Va por un `.bat` de tres renglones junto al instalador: espera dos
    segundos (a que shape101 suelte sus archivos) y lo abre con `start`.

    **Por qué un .bat y no `cmd /c "…"`:** la 0.19.2 mandaba la orden como
    argumento de `cmd.exe` y Python, al armar la línea de comandos de Windows,
    escapaba las comillas de `start "" "ruta"` como `\"\"` — cmd las leía
    literales y Windows acababa buscando la ruta `\\`: «No se ha encontrado la
    ruta de acceso de la red» (Mike, 8-sep-2026). En un archivo por lotes no
    hay nadie que re-escape nada.
    """
    if sys.platform != "win32":
        return False
    p = pathlib.Path(ruta)
    if not p.exists():
        return False
    bat = p.with_name("instalar-shape101.bat")
    bat.write_text(texto_bat(p), encoding="mbcs" if sys.platform == "win32" else "utf-8")
    # `cmd /c <ruta.bat>`: la ruta es un solo argumento (con espacios, entre
    # comillas) y adentro no hay comillas que escapar. Sin ventana.
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
        cwd=str(p.parent),
    )
    return True
