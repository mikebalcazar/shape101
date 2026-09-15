"""t023 · El instalador del ODA: sólo de opendesign.com y con la huella que diga el puntero.

El botón «Instalar ODA» baja un MSI y lo corre con `msiexec`. Hasta la 0.3.0
corría la liga que dijera el puntero de Taller 101 tal cual, sin mirar de
dónde era ni qué traía: quien se hiciera del sitio del puntero podía instalar
lo que quisiera en la máquina de un usuario (barrido de seguridad, 15-sep).
Desde la 0.3.1 hay dos candados y esto comprueba que cierran:

  · una liga que no sea `https://…opendesign.com` se ignora en `ultimo()`
    (se pasa a la siguiente fuente) y, si de todos modos llegara a
    `_trabajo`, no se baja ni se corre nada;
  · si el puntero declara `sha256` y lo bajado no cuadra, se borra y no se
    instala; si cuadra, se instala.

No toca la red ni corre `msiexec`: se sustituyen `_leer_url`, `_bajar`,
`_lanzar_instalador` e `instalado` por dobles que anotan qué se les pidió.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from core import oda
from pruebas import comun

DESCRIPCION = "ODA: sólo opendesign.com por https, y sha256 del puntero antes de msiexec"

ODA_OK = "https://www.opendesign.com/guestfiles/get?filename=ODAFileConverter_QT6_vc16_amd64dll_27.1.0.msi"
AJENA = "https://t101draw.netlify.app/ODAFileConverter.msi"


def correr(r: comun.Reporte) -> None:
    _candado_del_dominio(r)
    _el_puntero_elige_version_no_programa(r)
    _la_huella_manda(r)


def _candado_del_dominio(r: comun.Reporte) -> None:
    r.cierto(oda.url_de_oda(ODA_OK), "la liga de ODA por https pasa")
    r.cierto(oda.url_de_oda("https://opendesign.com/x.msi"), "opendesign.com sin www también pasa")
    r.cierto(oda.url_de_oda("https://files.opendesign.com/x.msi"), "un subdominio de opendesign.com pasa")
    r.cierto(not oda.url_de_oda("http://www.opendesign.com/x.msi"), "por http no pasa, aunque sea ODA")
    r.cierto(not oda.url_de_oda(AJENA), "una liga ajena (el sitio del puntero) no pasa")
    r.cierto(not oda.url_de_oda("https://opendesign.com.malo.mx/x.msi"), "un dominio que sólo empieza igual no pasa")
    r.cierto(not oda.url_de_oda("https://malo.mx/?u=https://www.opendesign.com"), "ODA en la query no cuenta")
    r.cierto(not oda.url_de_oda(""), "la liga vacía no pasa")
    r.cierto(not oda.url_de_oda(None), "sin liga no pasa")


class _Red:
    """Un `_leer_url` de mentiras: contesta lo que se le programe por URL y
    anota qué se le pidió."""

    def __init__(self, respuestas: dict):
        self.respuestas = respuestas
        self.pedidas: list[str] = []

    def __call__(self, url, espera=0):
        self.pedidas.append(url)
        if url not in self.respuestas:
            raise OSError("no contesta")
        return json.dumps(self.respuestas[url]).encode("utf-8")


def _con_red(respuestas: dict, plataforma: str = "windows"):
    red = _Red(respuestas)
    original = (oda._leer_url, oda._clave_plataforma)
    oda._leer_url = red
    oda._clave_plataforma = lambda: plataforma
    return red, original


def _sin_red(original) -> None:
    oda._leer_url, oda._clave_plataforma = original


def _el_puntero_elige_version_no_programa(r: comun.Reporte) -> None:
    huella = "a" * 64
    # 1. El puntero vivo señala una liga ajena; el fijo, una de ODA con huella.
    red, orig = _con_red({
        oda.PUNTERO: {"oda": {"version": "99.0", "windows": AJENA}},
        oda.PUNTERO_FIJO: {"oda": {"version": "27.1", "windows": ODA_OK, "sha256": {"windows": huella.upper()}}},
    })
    try:
        u = oda.ultimo()
    finally:
        _sin_red(orig)
    r.igual(u["fuente"], "taller101", "el puntero fijo sí se usa")
    r.igual(u["version"], "27.1", "la versión es la del fijo, no la de la liga ajena")
    r.igual(u["url"], ODA_OK, "la liga es la de ODA")
    r.igual(u["sha256"], huella, "la huella viaja en minúsculas")
    r.igual(red.pedidas, [oda.PUNTERO, oda.PUNTERO_FIJO], "se leyó el vivo, se descartó, y se leyó el fijo")

    # 2. Los dos punteros señalan ligas ajenas y no hay página de ODA (fuera
    #    de Windows no se lee): queda «ninguna», o sea bajarlo a mano.
    _, orig = _con_red({
        oda.PUNTERO: {"oda": {"version": "99.0", "linux": AJENA}},
        oda.PUNTERO_FIJO: {"oda": {"version": "99.0", "linux": "http://www.opendesign.com/x.msi"}},
    }, plataforma="linux")
    try:
        u = oda.ultimo()
    finally:
        _sin_red(orig)
    r.igual(u["fuente"], "ninguna", "con puras ligas ajenas (o por http) no hay de dónde bajar")
    r.igual(u["url"], oda.PAGINA_ODA, "y se manda a la página de ODA")

    # 3. Un puntero bueno sin huella, o con una que no parece sha256: se acepta sin huella.
    _, orig = _con_red({oda.PUNTERO: {"oda": {"version": "27.1", "windows": ODA_OK, "sha256": {"windows": "abc"}}}})
    try:
        u = oda.ultimo()
    finally:
        _sin_red(orig)
    r.igual((u["fuente"], u["sha256"]), ("taller101", ""), "una huella que no es sha256 se ignora, la liga de ODA se acepta")


class _Instalador:
    """`_bajar`, `_lanzar_instalador` e `instalado` de mentiras."""

    def __init__(self, contenido: bytes):
        self.contenido = contenido
        self.bajadas: list[str] = []
        self.corridos: list[pathlib.Path] = []

    def bajar(self, url, destino):
        self.bajadas.append(url)
        pathlib.Path(destino).write_bytes(self.contenido)

    def lanzar(self, msi):
        self.corridos.append(pathlib.Path(msi))
        return 0

    def instalado(self):
        return {"ruta": "C:/ODA/ODAFileConverter.exe", "version": "27.1"} if self.corridos else None


def _con_instalador(contenido: bytes):
    inst = _Instalador(contenido)
    original = (oda._bajar, oda._lanzar_instalador, oda.instalado)
    oda._bajar, oda._lanzar_instalador, oda.instalado = inst.bajar, inst.lanzar, inst.instalado
    return inst, original


def _sin_instalador(original) -> None:
    oda._bajar, oda._lanzar_instalador, oda.instalado = original


def _la_huella_manda(r: comun.Reporte) -> None:
    contenido = b"MSI de mentiras " * 1000
    buena = hashlib.sha256(contenido).hexdigest()
    carpeta = oda._carpeta_descargas()

    # 1. La huella no cuadra: se borra y no se corre nada.
    inst, orig = _con_instalador(contenido)
    try:
        oda._trabajo(ODA_OK, "27.1", "f" * 64)
    finally:
        _sin_instalador(orig)
    e = oda.estado()
    r.igual(e["fase"], "error", "con la huella equivocada el estado es «error»")
    r.cierto("huella" in e["mensaje"], "y el mensaje dice que fue la huella", e["mensaje"])
    r.igual(inst.corridos, [], "no se corrió ningún instalador")
    r.igual([p.name for p in carpeta.glob("*.msi")], [], "el archivo bajado se borró")

    # 2. La huella cuadra: se instala.
    inst, orig = _con_instalador(contenido)
    try:
        oda._trabajo(ODA_OK, "27.1", buena)
    finally:
        _sin_instalador(orig)
    e = oda.estado()
    r.igual(e["fase"], "listo", "con la huella correcta queda «listo»")
    r.igual(len(inst.corridos), 1, "se corrió el instalador una vez")
    r.cierto(inst.corridos and inst.corridos[0].name.endswith(".msi"), "y fue el MSI bajado")

    # 3. Sin huella declarada (fuente `oda`): manda el candado del dominio y se instala.
    inst, orig = _con_instalador(contenido)
    try:
        oda._trabajo(ODA_OK, "27.1", "")
    finally:
        _sin_instalador(orig)
    r.igual((oda.estado()["fase"], len(inst.corridos)), ("listo", 1), "sin huella declarada se instala igual que antes")

    # 4. Una liga ajena que llegara hasta aquí: ni se baja ni se corre.
    inst, orig = _con_instalador(contenido)
    try:
        oda._trabajo(AJENA, "27.1", buena)
    finally:
        _sin_instalador(orig)
    e = oda.estado()
    r.igual(e["fase"], "error", "una liga ajena en _trabajo es «error»")
    r.igual((inst.bajadas, inst.corridos), ([], []), "y no se bajó ni se corrió nada")
    r.cierto("opendesign.com" in e["mensaje"], "el mensaje dice de dónde sí se baja", e["mensaje"])
