"""Avisos de Taller 101 a quien usa shape101  ·  0.19.2.

Mike, 7-sep-2026: *«debemos tener alguna forma de mandar comunicación a los
usuarios del software… que el software siempre revise un registro por nueva
comunicación»*.

Así se hace hoy en día en programas chicos y medianos, y así se hace aquí:
**no hay servidor que empuje nada**; la app **lee un archivo** en el
repositorio `descargas` de Taller 101 (`avisos.json`, junto al `shape101.json`
de versiones; el mismo archivo sirve a nest101, campo `app`) al
arrancar y cada tantas horas, y enseña lo que no haya enseñado antes. Es lo
que hacen VS Code con sus «release notes», Blender con su barra de noticias o
cualquier app con «what's new»: un JSON en un CDN, cero infraestructura, y
para publicar un aviso basta editar el archivo y subirlo.

Cada aviso lleva `id` (único, no se repite nunca), `fecha`, `titulo`, `texto`,
opcionalmente `url` («leer más»), `nivel` (`info` o `importante`: el
importante sale en un cuadro al arrancar; el otro sólo marca el menú Ayuda y
lo dice la consola), `desde`/`hasta` (versiones de shape101 a las que aplica) y
`caduca` (fecha a partir de la cual ya no se enseña). Puede traer `en:
{titulo, texto}` para quien tenga la interfaz en inglés.

Lo leído se apunta en preferencias (`avisos_leidos`), por máquina.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request

from . import config, preferencias
from .actualizar import mas_nueva
from .version import VERSION

PUNTERO = os.environ.get("SHAPE101_AVISOS") or f"{config.URL_DESCARGAS}/avisos.json"
ESPERA_RED = 5
AGENTE = f"shape101/{VERSION} (Taller 101)"

_cache: dict = {"cuando": 0.0, "datos": None}


def _leer_url(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=ESPERA_RED) as r:
        return r.read()


def _aplica(a: dict, hoy: dt.date) -> bool:
    if not a.get("id") or not a.get("titulo"):
        return False
    # El archivo es de toda la familia *101: `app` dice a cuál va el aviso
    # ("shape101", "nest101", lista de ambas, o "todas" / ausente).
    app = a.get("app") or "todas"
    apps = [app] if isinstance(app, str) else list(app)
    if "todas" not in apps and config.APP_NOMBRE not in apps:
        return False
    if a.get("desde") and mas_nueva(str(a["desde"]), VERSION):
        return False
    if a.get("hasta") and mas_nueva(VERSION, str(a["hasta"])):
        return False
    if a.get("caduca"):
        try:
            if dt.date.fromisoformat(str(a["caduca"])[:10]) < hoy:
                return False
        except ValueError:
            pass
    return True


def traer(forzar: bool = False) -> list[dict] | None:
    """Los avisos vigentes para esta versión, o None si el sitio no contestó."""
    # 6 h: los trae el vigilante de core/actualizar.py en su hilo; la interfaz
    # no debe quedarse esperando a la red por un aviso.
    if not forzar and _cache["datos"] is not None and time.time() - _cache["cuando"] < 6 * 3600:
        return _cache["datos"]
    try:
        datos = json.loads(_leer_url(PUNTERO).decode("utf-8"))
    except Exception:
        return None
    hoy = dt.date.today()
    vigentes = []
    for a in (datos.get("avisos") or []):
        if not isinstance(a, dict) or not _aplica(a, hoy):
            continue
        vigentes.append({
            "id": str(a["id"]),
            "fecha": str(a.get("fecha") or ""),
            "titulo": str(a["titulo"]),
            "texto": str(a.get("texto") or ""),
            "url": str(a.get("url") or ""),
            "nivel": "importante" if a.get("nivel") == "importante" else "info",
            "en": a.get("en") if isinstance(a.get("en"), dict) else None,
        })
    vigentes.sort(key=lambda a: a["fecha"], reverse=True)
    _cache.update({"cuando": time.time(), "datos": vigentes})
    return vigentes


def resumen(con_red: bool = True, forzar: bool = False) -> dict:
    leidos = set(preferencias.leer().get("avisos_leidos") or [])
    avisos = (traer(forzar) if con_red else _cache["datos"]) or []
    for a in avisos:
        a["leido"] = a["id"] in leidos
    return {
        "avisos": avisos,
        "nuevos": sum(1 for a in avisos if not a["leido"]),
        "importantes_nuevos": [a for a in avisos if not a["leido"] and a["nivel"] == "importante"],
        "consulto": _cache["datos"] is not None,
    }


def marcar_leidos(ids: list[str] | None = None) -> dict:
    """Apunta como leídos esos ids (o todos los vigentes). Guarda a lo más 200."""
    actuales = list(preferencias.leer().get("avisos_leidos") or [])
    nuevos = list(ids) if ids else [a["id"] for a in (_cache["datos"] or [])]
    for i in nuevos:
        if i not in actuales:
            actuales.append(str(i))
    actuales = actuales[-200:]
    preferencias.guardar({"avisos_leidos": actuales})
    return {"ok": True, "leidos": len(actuales)}
