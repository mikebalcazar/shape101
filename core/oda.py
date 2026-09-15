"""Instalar el ODA File Converter desde t101draw  ·  lo pidió Mike el 6-sep.

El ODA File Converter es lo que más rápido y más fiel convierte DWG. Es
gratuito, pero **no se puede meter en nuestro instalador**: ODA lo regala al
usuario final y no da derecho a redistribuirlo (por eso FreeCAD, QCAD y ezdxf
también piden que cada quien lo instale). Lo que sí se puede es hacerle el
camino corto al usuario: un botón que lo baja **de ODA** y corre su instalador.

Cómo se sabe cuál es la versión de hoy —y esto es lo que decidió Mike—: el
programa **no** apunta al link de ODA, que cambia con cada versión y que ODA
puede mover cuando quiera. Apunta a un link **nuestro**, fijo, con un JSON
chiquito (`PUNTERO`) que dice «la última es la 27.1 y se baja de aquí». Cuando
ODA saque versión nueva, Taller 101 actualiza ese JSON y todos los t101draw
instalados la ven sin cambiar nada. El JSON lleva el link, **no el archivo**:
el MSI sigue viniendo de opendesign.com, que es lo que la licencia permite.

Si nuestro link no contesta (sin internet, Netlify caído), se intenta leer la
página de ODA directamente buscando el nombre del MSI con una expresión regular.
Y si tampoco, se abre la página de ODA en el navegador y el usuario lo baja a
mano. En ningún caso deja de funcionar leer DWG: sin ODA sigue LibreDWG.

Flujo:

  1. `GET /api/oda`             → qué hay instalado y cuál es la última.
  2. `POST /api/oda/instalar`   → baja el MSI en un hilo (progreso en
                                  `/api/oda/estado`) y corre `msiexec`.
                                  El instalador de ODA es el que enseña su
                                  licencia y pide el permiso de Windows: no
                                  se instala nada a escondidas.
  3. t101draw lo detecta solo la próxima vez que convierte
     (`dwg.oda_disponible()` busca en Program Files\\ODA).

Dos candados, desde el 15-sep-2026 (barrido de seguridad de Jr.):

  · **El MSI sólo puede venir de opendesign.com, por https.** El puntero dice
    qué versión y qué liga, pero si la liga no es de ODA se ignora y se pasa
    a la siguiente fuente. Quien se hiciera del sitio del puntero (o lo
    interceptara) podría, como mucho, señalar otra versión del convertidor;
    nunca otro programa. Antes, la liga del puntero se corría tal cual.
  · **Si el puntero trae `sha256`, se comprueba.** El archivo bajado se
    compara con la huella antes de correr `msiexec`; si no cuadra, se borra y
    no se instala. El puntero puede no traerla (la fuente `oda`, leída de su
    página, nunca la trae): entonces manda el candado del dominio.
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

from . import config

#: El link fijo de Taller 101. Lo que hay detrás está en `build/sitio/` y se
#: publica en Netlify (sitio `t101draw`): `/oda.json` lo contesta una función
#: que lee la página de ODA en vivo —el link se actualiza solo— y
#: `/oda-fijo.json` es un archivo plano que Taller 101 edita a mano, por si la
#: función no está o ODA cambió el formato. Se prueban en ese orden.
PUNTERO = "https://t101draw.netlify.app/oda.json"
PUNTERO_FIJO = "https://t101draw.netlify.app/oda-fijo.json"

#: Por si el puntero no contesta: la página pública de ODA y el nombre que
#: lleva su MSI de Windows (64 bits, Qt6, VC16). Si ODA cambia el patrón,
#: queda el puntero; si cambia el puntero, queda la página.
PAGINA_ODA = "https://www.opendesign.com/guestfiles/oda_file_converter"
BAJAR_ODA = "https://www.opendesign.com/guestfiles/get?filename="
PATRON_MSI = re.compile(r"ODAFileConverter_QT6_vc16_amd64dll_(\d+(?:\.\d+)*)\.msi")

#: De dónde puede venir el MSI. Sólo de aquí, por https. Ver el docstring.
HOSTS_ODA = ("opendesign.com", "www.opendesign.com")

ESPERA_RED = 5          # segundos para el puntero y la página
AGENTE = f"t101draw/{config.VERSION} (Taller 101)"

# Lo que va pasando con la descarga, para que la interfaz lo enseñe.
_estado = {"fase": "nada", "pct": 0, "mensaje": "", "version": ""}
_hilo: threading.Thread | None = None
_candado = threading.Lock()


# --- Qué hay instalado ------------------------------------------------------

def instalado() -> dict | None:
    """`{ruta, version}` del ODA que ya está en la máquina, o None."""
    from . import dwg
    ruta = dwg.oda_disponible()
    if not ruta:
        return None
    # En Windows se instala en `Program Files\ODA\ODAFileConverter 27.1.0\`:
    # la versión es el nombre de la carpeta. En macOS no la dice nadie.
    m = re.search(r"ODAFileConverter[ _](\d+(?:\.\d+)*)", str(pathlib.Path(ruta).parent.name))
    return {"ruta": ruta, "version": m.group(1) if m else ""}


# --- Cuál es la última ------------------------------------------------------

def _leer_url(url: str, espera: int = ESPERA_RED) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return r.read()


def url_de_oda(url) -> bool:
    """¿Esta liga es de ODA y va por https? Es el candado que hace que el
    puntero pueda elegir versión, pero no programa."""
    try:
        partes = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return False
    host = (partes.hostname or "").lower()
    return partes.scheme == "https" and (host in HOSTS_ODA or host.endswith(".opendesign.com"))


def _huella_declarada(oda: dict, plataforma: str) -> str:
    """El sha256 que el puntero declara para esta plataforma, en minúsculas,
    o «» si no trae uno que parezca sha256 (64 hexadecimales)."""
    huellas = oda.get("sha256")
    h = huellas.get(plataforma) if isinstance(huellas, dict) else None
    h = str(h or "").strip().lower()
    return h if re.fullmatch(r"[0-9a-f]{64}", h) else ""


def _clave_plataforma() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "mac_arm" if platform.machine() == "arm64" else "mac_intel"
    return "linux"


def ultimo() -> dict:
    """`{version, url, fuente, sha256}` de la última versión que se puede bajar.

    `fuente` dice de dónde salió el dato: `taller101` (nuestro puntero),
    `oda` (leído de su página) o `ninguna` (sin red: `url` es la página de
    ODA para bajarlo a mano). `sha256` es la huella que declara el puntero,
    o «» si no la trae.

    Un puntero cuya liga no sea de opendesign.com se ignora como si no
    hubiera contestado: el puntero elige versión, no programa.
    """
    # 1. El puntero de Taller 101: el vivo y, si no, el fijo.
    plataforma = _clave_plataforma()
    for puntero in (PUNTERO, PUNTERO_FIJO):
        try:
            datos = json.loads(_leer_url(puntero).decode("utf-8"))
            oda = datos.get("oda") or {}
            url = oda.get(plataforma)
            if url and oda.get("version") and url_de_oda(url):
                return {"version": str(oda["version"]), "url": str(url), "fuente": "taller101",
                        "actualizado": oda.get("actualizado", ""),
                        "sha256": _huella_declarada(oda, plataforma)}
        except Exception:
            continue
    # 2. La página de ODA, buscando el nombre del MSI.
    if sys.platform == "win32":
        try:
            html = _leer_url(PAGINA_ODA).decode("utf-8", "replace")
            m = PATRON_MSI.search(html)
            if m:
                return {"version": m.group(1), "url": BAJAR_ODA + m.group(0), "fuente": "oda",
                        "actualizado": "", "sha256": ""}
        except Exception:
            pass
    # 3. Nada: que lo baje a mano.
    return {"version": "", "url": PAGINA_ODA, "fuente": "ninguna", "actualizado": "", "sha256": ""}


def _mas_nueva(a: str, b: str) -> bool:
    """¿`a` es más nueva que `b`? «27.1» vs «27.1.0» son la misma."""
    def partes(v):
        return [int(x) for x in re.findall(r"\d+", v or "")]
    pa, pb = partes(a), partes(b)
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    return pa > pb


def resumen(con_red: bool = True) -> dict:
    """Lo que enseña Ajustes: instalado, última, y si conviene actualizar."""
    inst = instalado()
    ult = ultimo() if con_red else {"version": "", "url": PAGINA_ODA, "fuente": "ninguna", "sha256": ""}
    return {
        "instalado": inst,
        "ultimo": ult,
        "hay_nueva": bool(inst and ult.get("version") and _mas_nueva(ult["version"], inst.get("version", ""))),
        "estado": dict(_estado),
        "se_puede_instalar": sys.platform == "win32" and ult["fuente"] != "ninguna",
    }


# --- Bajar e instalar -------------------------------------------------------

def estado() -> dict:
    return dict(_estado)


def _poner(fase: str, pct: float = 0, mensaje: str = "", version: str | None = None):
    _estado["fase"] = fase
    _estado["pct"] = round(pct)
    _estado["mensaje"] = mensaje
    if version is not None:
        _estado["version"] = version


def _carpeta_descargas() -> pathlib.Path:
    c = config.carpeta_usuario() / "descargas"
    c.mkdir(parents=True, exist_ok=True)
    return c


def _bajar(url: str, destino: pathlib.Path) -> None:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=30) as r, open(destino, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        leido = 0
        ultimo_aviso = 0.0
        while True:
            trozo = r.read(256 * 1024)
            if not trozo:
                break
            f.write(trozo)
            leido += len(trozo)
            if time.time() - ultimo_aviso > 0.2:
                ultimo_aviso = time.time()
                pct = leido * 100 / total if total else 0
                _poner("descargando", pct,
                       f"Bajando el ODA File Converter… {leido / 1e6:.0f} de {total / 1e6:.0f} MB"
                       if total else f"Bajando el ODA File Converter… {leido / 1e6:.0f} MB")
    if destino.stat().st_size < 5_000_000:
        raise RuntimeError("Lo que se bajó no parece el instalador de ODA (pesa menos de 5 MB).")


def _sha256(ruta: pathlib.Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1024 * 1024), b""):
            h.update(trozo)
    return h.hexdigest()


def _lanzar_instalador(msi: pathlib.Path) -> int:
    """Corre el instalador de ODA **con su ventana**: la licencia la acepta el
    usuario, y Windows pide su permiso. Espera a que termine."""
    if sys.platform != "win32":
        raise RuntimeError("El instalador automático es sólo para Windows.")
    p = subprocess.run(["msiexec", "/i", str(msi)], timeout=1800)
    return p.returncode


def _trabajo(url: str, version: str, sha256: str = "") -> None:
    try:
        # El candado del dominio se vuelve a cerrar aquí, aunque `ultimo()` ya
        # lo cerró: ésta es la función que corre un instalador, y no debe
        # fiarse de quien la llame.
        if not url_de_oda(url):
            raise RuntimeError("El instalador sólo se baja de opendesign.com; esta liga no es de ahí.")
        _poner("descargando", 0, "Bajando el ODA File Converter…", version)
        destino = _carpeta_descargas() / (pathlib.Path(url.split("filename=")[-1]).name or "ODAFileConverter.msi")
        _bajar(url, destino)
        if sha256:
            _poner("descargando", 100, "Comprobando la huella del instalador…")
            huella = _sha256(destino)
            if huella != sha256:
                destino.unlink(missing_ok=True)
                raise RuntimeError("La huella del instalador no cuadra con la que declara el puntero: no se instala.")
        _poner("instalando", 100, "Corriendo el instalador de ODA… acepta su licencia y el permiso de Windows.")
        codigo = _lanzar_instalador(destino)
        # 0 = instalado; 1602 = el usuario canceló; 3010 = instalado, pide reiniciar.
        if codigo in (0, 3010) and instalado():
            _poner("listo", 100, "ODA File Converter instalado. Los DWG ya se convierten con él.")
        elif codigo == 1602:
            _poner("cancelado", 0, "Se canceló la instalación.")
        else:
            _poner("error", 0, f"El instalador de ODA terminó con código {codigo} y no se encontró el programa.")
    except Exception as exc:
        _poner("error", 0, f"No se pudo instalar: {exc}")


def instalar() -> dict:
    """Arranca la descarga en un hilo. Devuelve el estado de inmediato."""
    global _hilo
    with _candado:
        if _hilo and _hilo.is_alive():
            return dict(_estado)
        ult = ultimo()
        if ult["fuente"] == "ninguna" or sys.platform != "win32":
            _poner("manual", 0, "No se pudo averiguar la versión. Se abre la página de ODA para bajarlo a mano.")
            return {**_estado, "abrir": PAGINA_ODA}
        _hilo = threading.Thread(target=_trabajo, args=(ult["url"], ult["version"], ult.get("sha256", "")), daemon=True)
        _hilo.start()
        return dict(_estado)


# --- ¿Conviene sugerirlo? ---------------------------------------------------

UMBRAL_SUGERIR_MB = 5


def sugerir_para(ruta: pathlib.Path) -> float | None:
    """Si vale la pena ofrecer el ODA al abrir este archivo: devuelve los MB, o None.

    Sólo para DWG de más de `UMBRAL_SUGERIR_MB`, sólo en Windows, sólo si no
    está el ODA, y **sólo una vez**: se apunta en preferencias que ya se
    ofreció. Un aviso que sale cada vez es un aviso que se aprende a cerrar sin
    leer.
    """
    if sys.platform != "win32" or ruta.suffix.lower() != ".dwg":
        return None
    try:
        mb = ruta.stat().st_size / 1e6
    except OSError:
        return None
    if mb < UMBRAL_SUGERIR_MB or instalado():
        return None
    from . import preferencias
    if preferencias.leer().get("oda_ofrecido"):
        return None
    preferencias.guardar({"oda_ofrecido": True})
    return round(mb)
