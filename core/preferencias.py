"""Preferencias de dibujo: rejilla, referencias, ortho, entrada dinámica.

Son del **usuario**, no del archivo: si alguien trabaja siempre con ortho
encendido y snap de 10 mm, eso tiene que seguir así mañana y con cualquier
plano. Por eso viven en `~/Taller 101/shape101/preferencias.json` y no dentro
del `.t101d`. Es la misma lección de Taller 101 con los materiales: el estándar
es del taller, no del proyecto.
"""

from __future__ import annotations

import json
import pathlib

from . import config

CARPETA = config.carpeta_usuario()
ARCHIVO = CARPETA / "preferencias.json"

# Los modos de referencia a objetos, con el nombre que verá el usuario.
MODOS_OSNAP = {
    "extremo": "Extremo",
    "medio": "Punto medio",
    "centro": "Centro",
    "cuadrante": "Cuadrante",
    "interseccion": "Intersección",
    "perpendicular": "Perpendicular",
    # 0.20.0 (Mike, 9-sep): proyectar el cursor sobre la perpendicular a una
    # entidad desde el punto anterior —aunque el pie caiga fuera del tramo— y
    # sobre el cruce de esa perpendicular con otra línea.
    "proyeccion": "Proyección perpendicular",
    "cercano": "Cercano",
    "nodo": "Nodo / inserción",
}

OMISION = {
    # Rejilla  ·  feature 12
    "rejilla": True,
    # Modo borrador (LibreCAD/QCAD «draft»): líneas de 1 px, sin patrones,
    # textos como cajas. Para navegar un plano pesado en una máquina floja.
    "borrador": False,
    "rejilla_paso": 10.0,          # mm
    "snap_rejilla": False,         # apagado: en un plano de obra estorba
    "snap_paso": 10.0,

    # Referencias a objetos  ·  feature 13
    "osnap": True,
    "osnap_modos": {
        "extremo": True, "medio": True, "centro": True, "cuadrante": True,
        "interseccion": True, "perpendicular": True, "proyeccion": True,
        "cercano": False, "nodo": True,
    },
    "osnap_apertura": 14,          # píxeles

    # Ortho  ·  feature 14
    "ortho": False,

    # Entrada dinámica  ·  feature 15
    "dinamica": True,

    # Un parpadeo casi imperceptible del lienzo cuando un comando cambió algo
    # (Mike, 9-sep-2026: «un mini mini mini flicker de casi nada para cuando el
    # comando sí se ejecuta bien; y cuando no, pues no pasa nada»).
    "parpadeo_comando": True,

    # Atajos propios  ·  feature 80.  {"Q": "CIRCULO", ...}
    "atajos": {},

    # Idioma de la interfaz: "en" (inglés, el de fábrica desde 0.19.0 — lo
    # pidió Mike el 6-sep-2026 pensando en vender fuera) o "es". Se cambia en
    # Ayuda → Configuración. Los comandos se aceptan en los dos idiomas siempre.
    "idioma": "en",

    # Vista
    "tema": "claro",
    "zoom_rueda": 1.15,

    # Cuando un clic cae encima de varias cosas, ¿sale el menú para elegir?
    # Encendido: en un plano de obra es lo normal que haya cuatro cosas bajo el
    # cursor, y la que gana por medio milímetro casi nunca es la que se quería.
    "menu_seleccion": True,

    # Ancho del panel de capas y propiedades, en píxeles  ·  punto 5.
    "panel_ancho": 340,

    # La última impresora que se usó, por su nombre de Windows  ·  punto 12.
    # En un taller es siempre la misma; recordarla ahorra un cuadro por hoja.
    "impresora": "",
    # El papel de la impresora: "HOJA" (del tamaño de la hoja) o A4, A3, CARTA…
    # La hoja se imprime **centrada en el papel**, no en los márgenes.
    "papel": "HOJA",

    # Los últimos dibujos abiertos, para la pantalla de inicio  ·  punto 10.
    # [{"ruta": "...", "nombre": "...", "cuando": "2026-09-01T10:22:00"}]
    "recientes": [],

    # Si ya se ofreció instalar el ODA File Converter (core/oda.py). Una vez.
    "oda_ofrecido": False,

    # Actualizaciones (core/actualizar.py): revisar solo al arrancar y una vez
    # al día; y qué versión pidió el usuario que no se le vuelva a ofrecer.
    "actualizaciones_auto": True,
    "version_ignorada": "",

    # Avisos de Taller 101 ya enseñados (core/avisos.py), por id.
    "avisos_leidos": [],

    # La última respuesta a cada pregunta numérica («Distancia del desfase»:
    # 60), por pregunta. La herramienta la ofrece por omisión la próxima vez.
    "ultimos_valores": {},

    # Dónde quedó la barra de herramientas. Es del usuario, no del plano:
    # dónde te gusta la barra no cambia porque abras otro dibujo.
    # anclaje: izquierda | derecha | arriba | abajo | flotante
    "barra": {"anclaje": "flotante", "x": 12, "y": 12},
}


def _fusionar(base: dict, encima: dict) -> dict:
    salida = dict(base)
    for k, v in (encima or {}).items():
        if k not in base:
            continue                       # llave de otra versión: se ignora
        if isinstance(base[k], dict) and isinstance(v, dict):
            # Los atajos los inventa el usuario, y los últimos valores llevan
            # la pregunta como llave: no se pueden filtrar contra una lista
            # fija de llaves como el resto.
            salida[k] = dict(v) if k in ("atajos", "ultimos_valores") else {
                **base[k], **{a: b for a, b in v.items() if a in base[k]}}
        elif isinstance(v, type(base[k])) or isinstance(base[k], float) and isinstance(v, int):
            salida[k] = v
    return salida


def leer() -> dict:
    """Nunca truena: un archivo de preferencias roto no debe impedir dibujar."""
    try:
        datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        return _fusionar(OMISION, datos)
    except Exception:
        return dict(OMISION)


RECIENTES_MAX = 12


def recordar(ruta, nombre: str = "") -> dict:
    """Apunta un dibujo en la lista de recientes y la devuelve ya recortada.

    La misma ruta no se repite: se sube al principio. Lo que se guarda es la
    ruta, no el contenido, así que un archivo que alguien movió aparece igual —
    la pantalla de inicio lo marca como no encontrado en vez de esconderlo, que
    es lo que ayuda a acordarse de dónde estaba.
    """
    ruta = str(ruta)
    actuales = leer().get("recientes") or []
    lista = [r for r in actuales
             if isinstance(r, dict) and str(r.get("ruta")) != ruta]
    import datetime as _dt
    lista.insert(0, {"ruta": ruta, "nombre": nombre or pathlib.Path(ruta).stem,
                     "cuando": _dt.datetime.now().isoformat(timespec="seconds")})
    return guardar({"recientes": lista[:RECIENTES_MAX]})


def guardar(cambios: dict) -> dict:
    actuales = _fusionar(leer(), cambios)
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        ARCHIVO.write_text(json.dumps(actuales, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    except OSError:
        pass          # sin permisos de escritura se sigue trabajando igual
    return actuales
