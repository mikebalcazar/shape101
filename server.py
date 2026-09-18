"""API de shape101.

FastAPI en 127.0.0.1, igual que Taller 101: Electron levanta este proceso,
espera a `/api/salud` y carga la interfaz desde aquí. Sin Electron, el mismo
servidor sirve la interfaz en el navegador.

El documento vive **en el servidor**, no en el navegador. En un CAD el estado
es grande (un plano de obra son decenas de miles de entidades) y el historial
tiene que ser exacto; mandarlo completo en cada clic, como hace Taller 101 con
el proyecto de gabinetes, aquí no aguantaría.
"""

from __future__ import annotations

import gc
import json
import pathlib
import socket
import sys
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import capas as mod_capas
from core import actualizar as mod_actualizar, avisos as mod_avisos, config, unidades as mod_unidades, cotas as mod_cotas, licencias as mod_licencias, dibujo, geometria, papel, pdf_fondo, preferencias, proyecto, t101x
from core import unir as mod_unir
from core import agrupar as mod_agrupar
from core import oda as mod_oda
from core import version as mod_version
from core import progreso as mod_progreso
from core import entidades as ent_mod
from core.capas import Capa, NombreCapaInvalido
from core.documento import ESTILO_COTA_T101, CapaBloqueada, CapaEnUso, Documento
from core import dwg as mod_dwg
from core import idioma as mod_idioma
from core.dxf_lector import DWGNoDisponible, leer
from export import dxf as export_dxf
from export import pdf as export_pdf

RAIZ = pathlib.Path(__file__).resolve().parent
UI = RAIZ / "ui"

app = FastAPI(title=config.APP_NOMBRE)

# --- El kernel de sólidos se calienta en segundo plano --------------------
# Son 350 MB de bibliotecas que Windows lee, y su antivirus escanea, la
# primera vez que se importan: medio minuto medido por Mike en la 0.8.0 al
# extruir por primera vez. Aquí se importa al arrancar, en un hilo que no
# bloquea nada, para que cuando el usuario extruya ya esté cargado.
import threading as _hilos  # noqa: E402


def _calentar_kernel():
    import time as _t
    t0 = _t.perf_counter()
    try:
        import build123d  # noqa: F401
        print(f"[3d] kernel listo en {_t.perf_counter() - t0:.1f} s", flush=True)
    except Exception as e:  # sin kernel no hay 3D, pero el 2D sigue
        print(f"[3d] el kernel no cargó: {e}", flush=True)


_hilos.Thread(target=_calentar_kernel, name="calentar-kernel", daemon=True).start()


class Sesion:
    """Un documento abierto: el dibujo, de dónde salió y su candado."""

    def __init__(self):
        self.doc = Documento.nuevo()
        self.ruta: pathlib.Path | None = None
        self.informe: dict | None = None
        # En qué espacio se está dibujando: `""` el modelo, o el nombre de la
        # hoja. Es **del documento y no de la vista**: quien crea entidades es
        # el motor, y tiene que saber dónde ponerlas sin que cada herramienta
        # se lo mande. Ver `Entidad.espacio`.
        self.espacio: str = ""
        self.candado = threading.Lock()

    def resumen(self) -> dict:
        d = self.doc
        return {
            "nombre": d.nombre,
            "cliente": d.cliente,
            "ruta": str(self.ruta) if self.ruta else None,
            "sucio": d.sucio,
            "unidad": d.unidad,
            "capa_activa": d.capa_activa,
            "capas": [c.a_dict() for c in d.capas.values()],
            "tipos_linea": {k: v["desc"] for k, v in mod_capas.TIPOS_LINEA.items()},
            "grosores": config.GROSORES,
            "entidades": len(d.entidades),
            "extension": d.extension(self.espacio),
            "espacio": self.espacio,
            "unidades": d.unidades,
            "mm_por_unidad": d.mm_por_unidad(),
            "puede_deshacer": d.historial.puede_deshacer,
            "puede_rehacer": d.historial.puede_rehacer,
            "nombre_deshacer": d.historial.nombre_deshacer(),
            "nombre_rehacer": d.historial.nombre_rehacer(),
            "informe": self.informe,
            # Se calcula una vez al arrancar: preguntar por los motores en
            # cada refresco de estado sería lanzar un Node por clic.
            "dwg": _DWG,
            # Las pestañas viajan en cada resumen: así el nombre y el punto de
            # «sin guardar» de la pestaña no se quedan atrás respecto al título
            # de la ventana, que es de donde salen los errores tontos.
            "escritorio": ESCRITORIO.lista(),
            # El estilo de cota activo, para el panel «Cotas del documento»
            # (0.20.0): cambia por ESTILOCOTA y al entrar a una hoja (DIMSCALE).
            "estilo_cota": {**ESTILO_COTA_T101, **d.estilos_cota.get("T101", {})},
        }


# --- El recolector de basura de Python, domado ------------------------------
#
# Un plano de obra en memoria son cientos de miles de listas (cada vértice es
# una). El recolector cíclico de Python los vuelve a recorrer **todos** cada
# vez que se disparan sus umbrales —cada pocos miles de objetos nuevos—, y una
# operación que crea trazos nuevos los dispara varias veces: pausas de 300 ms
# que no son del programa sino del recolector. Dos medidas, las mismas que usa
# cualquier servidor con un modelo grande en memoria:
#   · umbrales altos: recolectar cada 50 000 objetos nuevos, no cada 700;
#   · `gc.freeze()` después de cargar un dibujo: lo cargado ya no se revisa.
# Medido: una operación sobre 2 000 entidades pasó de 1 000 ms a 500 ms sólo
# con esto (lo demás lo arreglan las cachés de documento.py).
gc.set_threshold(50000, 20, 20)


def _congelar_gc() -> None:
    gc.collect()
    gc.freeze()


#: Qué motores de DWG hay en esta máquina. Ver core/dwg.py.
_DWG = mod_dwg.estado()
_DWG["puede"] = bool(_DWG["oda"] or _DWG["empotrado"])


def _refrescar_dwg() -> None:
    """Volver a mirar qué motores hay: después de instalar el ODA, el pie tiene
    que decir «ODA File Converter» sin reiniciar el programa."""
    nuevo = mod_dwg.estado()
    nuevo["puede"] = bool(nuevo["oda"] or nuevo["empotrado"])
    _DWG.clear()
    _DWG.update(nuevo)


class Escritorio:
    """Los dibujos abiertos a la vez  ·  punto 14 de Mike.

    Hasta la 0.10.0 el servidor sostenía **un** documento, como AutoCAD LT.
    Mike pidió pestañas, y eso no es un botón: es que el motor sostenga varios.

    Lo que hace que el cambio no toque doscientas líneas es que el resto del
    servidor sigue diciendo `S.doc`. `S` dejó de ser el documento y pasó a ser
    un apuntador al **activo**: cada petición trabaja sobre la pestaña de
    enfrente, igual que antes, y sólo los endpoints de aquí abajo saben que hay
    más de una. El precio es el de siempre con un apuntador global —dos
    peticiones de pestañas distintas se pisarían— y se paga barato: la interfaz
    es de un solo usuario delante de una sola ventana.
    """

    MAX = 12          # más pestañas que eso no se leen, y cada una pesa

    def __init__(self):
        self.sesiones: list[Sesion] = [Sesion()]
        self.activo = 0

    @property
    def actual(self) -> Sesion:
        self.activo = min(max(self.activo, 0), len(self.sesiones) - 1)
        return self.sesiones[self.activo]

    def abrir_pestana(self) -> int:
        if len(self.sesiones) >= self.MAX:
            raise ValueError(f"No se pueden tener más de {self.MAX} dibujos abiertos")
        self.sesiones.append(Sesion())
        self.activo = len(self.sesiones) - 1
        return self.activo

    def cerrar(self, i: int) -> None:
        if not (0 <= i < len(self.sesiones)):
            raise IndexError("No existe ese dibujo")
        self.sesiones.pop(i)
        if not self.sesiones:              # nunca cero: se queda uno en blanco
            self.sesiones.append(Sesion())
        self.activo = min(self.activo if i > self.activo else self.activo - 1,
                          len(self.sesiones) - 1)
        self.activo = max(self.activo, 0)

    def lista(self) -> dict:
        return {
            "activo": self.activo,
            "documentos": [
                {"indice": i, "nombre": s.doc.nombre,
                 "ruta": str(s.ruta) if s.ruta else None,
                 "sucio": s.doc.sucio, "entidades": len(s.doc.entidades)}
                for i, s in enumerate(self.sesiones)
            ],
        }


ESCRITORIO = Escritorio()

#: ¿La vez pasada se cerró mal? Se decide al arrancar (ver core/proyecto.py).
SE_CAYO = proyecto.iniciar_sesion()


class _Activa:
    """Apunta siempre a la pestaña de enfrente.

    Existe para que `S.doc`, que sale unas doscientas veces en este archivo,
    siga significando lo mismo después de que el motor pasara a sostener varios
    dibujos. No hereda de `Sesion` a propósito: si mañana `Sesion` gana un
    campo, éste lo reenvía solo.
    """

    def __getattr__(self, nombre):
        return getattr(ESCRITORIO.actual, nombre)

    def __setattr__(self, nombre, valor):
        setattr(ESCRITORIO.actual, nombre, valor)


S = _Activa()

# --- El 3D -----------------------------------------------------------------
# Las rutas de sólidos viven en su propio módulo: son otro oficio y, sobre
# todo, el kernel tarda casi tres segundos en cargar. Importarlas aquí no lo
# carga —`core/solido/rutas.py` lo importa dentro de cada función—, así que la
# app sigue abriendo igual de rápido para quien sólo va a dibujar en 2D.
from core.solido import rutas as rutas_3d  # noqa: E402

rutas_3d.enchufar(lambda: S.doc)
app.include_router(rutas_3d.router)


def _error(exc: Exception, codigo: int = 400):
    raise HTTPException(status_code=codigo, detail=str(exc))


# --- Respuestas grandes, sin pasar por el codificador de FastAPI ------------
# FastAPI recorre lo que se devuelve con `jsonable_encoder` antes de
# serializarlo: con los 51 MB de trazos del plano de Mondelez eso son **5.4
# segundos** de recorrer listas de números, más 1.1 s del `json.dumps`. El
# navegador se quedaba 22 s esperando al servidor y parecía que parseaba.
# Devolviendo una `Response` ya armada el codificador no interviene, y orjson
# serializa lo mismo en 0.2 s. Si orjson no está (una máquina de desarrollo
# sin él), se cae al json normal: más lento, pero igual de correcto.
try:
    import orjson as _orjson

    def _json(datos) -> Response:
        return Response(_orjson.dumps(datos, option=_orjson.OPT_SERIALIZE_NUMPY),
                        media_type="application/json")
except ImportError:                                   # pragma: no cover
    def _json(datos) -> Response:
        return JSONResponse(datos)


# =========================================================================
# Salud y estado
# =========================================================================

@app.get("/api/salud")
def salud():
    return {"ok": True, "app": config.APP_NOMBRE, "dxf": config.DXF_VERSION,
            "version": mod_version.VERSION, "fecha": mod_version.FECHA}


# --- ODA File Converter: instalarlo desde aquí  ·  core/oda.py -----------

@app.get("/api/oda")
def oda_resumen(red: bool = True):
    """Qué ODA hay instalado y cuál es la última versión (según el puntero de
    Taller 101). `red=false` no sale a internet: sólo lo local."""
    _refrescar_dwg()
    return mod_oda.resumen(con_red=red)


@app.post("/api/oda/instalar")
def oda_instalar():
    return mod_oda.instalar()


@app.get("/api/oda/estado")
def oda_estado():
    e = mod_oda.estado()
    if e.get("fase") == "listo":
        _refrescar_dwg()
    e["dwg"] = _DWG
    return e


@app.get("/api/version")
def version():
    """Qué versión corre y qué trajo. Lo lee el pie y el comando VERSION."""
    return {"version": mod_version.VERSION, "fecha": mod_version.FECHA,
            "bitacora": mod_version.BITACORA}


# --- Actualizaciones y avisos  ·  0.19.2 ------------------------------------

@app.get("/api/actualizacion")
def actualizacion(red: int = 1, forzar: int = 0):
    """Qué versión corre, cuál es la última en el sitio de Taller 101, y si conviene."""
    return mod_actualizar.resumen(con_red=bool(red), forzar=bool(forzar))


@app.post("/api/actualizacion/bajar")
def actualizacion_bajar():
    return mod_actualizar.bajar()


@app.get("/api/actualizacion/estado")
def actualizacion_estado():
    return mod_actualizar.estado()


class _Version(BaseModel):
    version: str = ""


@app.post("/api/actualizacion/ignorar")
def actualizacion_ignorar(entrada: _Version):
    return mod_actualizar.ignorar(entrada.version)


@app.post("/api/actualizacion/instalar")
def actualizacion_instalar():
    """Arranca el instalador bajado. La interfaz cierra la app después."""
    ruta = mod_actualizar.ruta_lista()
    if not ruta:
        raise HTTPException(409, "No hay un instalador bajado y comprobado.")
    if not mod_actualizar.lanzar_instalador(ruta):
        return {"lanzado": False, "ruta": ruta}
    return {"lanzado": True, "ruta": ruta}


@app.get("/api/avisos")
def avisos(red: int = 1, forzar: int = 0):
    return mod_avisos.resumen(con_red=bool(red), forzar=bool(forzar))


class _Ids(BaseModel):
    ids: list[str] | None = None


@app.post("/api/avisos/leidos")
def avisos_leidos(entrada: _Ids):
    return mod_avisos.marcar_leidos(entrada.ids)


class _Unidades(BaseModel):
    unidades: str
    escalar: bool = True


@app.post("/api/unidades")
def unidades_cambiar(entrada: _Unidades):
    """Unidad de trabajo del dibujo: mm, cm o m (comando UNIDADES)."""
    try:
        with S.candado:
            with S.doc.transaccion("Cambiar unidades"):
                r = mod_unidades.cambiar(S.doc, entrada.unidades, entrada.escalar)
    except ValueError as exc:
        _error(exc)
    return {**r, **S.resumen()}


@app.get("/api/ayuda/guia")
def ayuda_guia():
    """La guía de herramientas en PDF (build/hacer_guia.py), en el idioma en uso."""
    idioma = preferencias.leer().get("idioma", "en")
    carpeta = RAIZ / "assets" / "ayuda"
    ruta = carpeta / f"herramientas-{'es' if idioma == 'es' else 'en'}.pdf"
    if not ruta.exists():
        ruta = carpeta / "herramientas-es.pdf"
    if not ruta.exists():
        raise HTTPException(404, "La guía no está en este paquete")
    return {"ruta": str(ruta), "url": "/api/ayuda/herramientas.pdf"}


@app.get("/api/ayuda/herramientas.pdf")
def ayuda_guia_pdf():
    r = ayuda_guia()
    return FileResponse(r["ruta"], media_type="application/pdf", filename="shape101-herramientas.pdf")


@app.get("/api/licencias")
def licencias():
    """Lo ajeno que viaja dentro del programa y bajo qué licencia (Ayuda → Licencias)."""
    return {"componentes": mod_licencias.indice()}


@app.get("/api/licencias/{archivo}")
def licencia_texto(archivo: str):
    r = mod_licencias.texto(archivo)
    if r is None:
        raise HTTPException(404, "No hay ese aviso de licencia")
    return Response(content=r[0], media_type=r[1])


@app.get("/api/estado")
def estado():
    return S.resumen()


@app.get("/api/progreso")
def progreso_actual():
    """Qué está haciendo el motor, para el indicador de «trabajando»."""
    return mod_progreso.actual()


def _parche(ids) -> dict:
    """Lo que cambió y nada más, para que el lienzo no se rehaga entero.

    **Aquí estaba el problema de lentitud que reportó Mike.** Cada acción —
    borrar una línea incluso— pedía `/api/trazos`, que tesela el documento
    completo y lo manda por la red. En un plano de 1 850 entidades eso son
    9 500 trazos y **6 MB de JSON**: en la máquina de pruebas 1.1 segundos, y en
    una de taller tres a cinco. El borrado en sí tardaba 16 milisegundos.

    La cuenta que importa: el cliente ya tiene el dibujo entero pintado. Lo
    único que necesita saber es **qué entidades cambiaron y cómo quedaron**. Eso
    son unos kilobytes, no seis megas, y no crece con el tamaño del plano — que
    es la parte que de verdad arregla el problema, porque los planos de obra
    sólo se hacen más grandes.

    Devuelve `{quitar, poner, extension}`: `quitar` son los ids cuyos trazos hay
    que borrar del lienzo, y `poner` los trazos y la geometría nuevos de esos
    mismos ids. Una entidad borrada aparece en `quitar` y no en `poner`.
    """
    unicos = list(dict.fromkeys(ids))
    trazos_nuevos: list[dict] = []
    geom_nueva: list[dict] = []
    for id_ in unicos:
        e = S.doc.entidades.get(id_)
        if e is None:
            continue                       # se borró: basta con quitarla
        if getattr(e, "espacio", "") != S.espacio:
            continue          # está en otro espacio: aquí no se pinta
        capa = S.doc.capas.get(e.capa)
        if not e.visible or capa is None or not capa.visible:
            continue                       # está, pero no se ve
        trazos_nuevos.extend(dibujo.trazos_de(S.doc, e))
        geom_nueva.extend(geometria.primitivas_marcadas(S.doc, e))
    return {
        "quitar": unicos,
        "trazos": trazos_nuevos,
        "geometria": geom_nueva,
        "extension": S.doc.extension(S.espacio),
    }


class Ids(BaseModel):
    ids: list


@app.post("/api/entidades/varias")
def entidades_varias(entrada: Ids):
    """Las entidades completas de una lista de ids, en **una** petición.

    El panel de propiedades pedía `/api/entidad/{id}` una por una: con 5 000
    seleccionadas eran 5 000 peticiones y 1.7 segundos con la interfaz
    congelada, para enseñar «5 000 entidades». Aquí se contestan de golpe y en
    milisegundos. El tope de 20 000 es por si algo se descontrola, no un límite
    práctico: mover medio plano pasa por aquí.
    """
    salida = []
    for id_ in entrada.ids[:20000]:
        e = S.doc.entidades.get(id_)
        if e is not None:
            salida.append(e.a_dict())
    return {"entidades": salida, "total": len(entrada.ids)}


@app.post("/api/entidades/resumen")
def entidades_resumen(entrada: Ids):
    """Qué es cada una de estas entidades, en corto.

    Lo pide el menú de «cuál de éstos» cuando hay varias cosas encimadas bajo el
    cursor: para escribir la lista hace falta el tipo y la capa, y el cliente
    sólo tiene trazos ya teselados, que no saben si vienen de una polilínea o de
    una cota.

    Va en una sola petición y no una por entidad: son cuatro o cinco, pero es la
    clase de cosa que se convierte en cuarenta el día que alguien pique en un
    nudo.
    """
    salida = []
    for id_ in entrada.ids[:40]:
        e = S.doc.entidades.get(id_)
        if e is None:
            continue
        d = {"id": id_, "tipo": e.tipo, "capa": e.capa}
        if e.tipo == "cota":
            d["detalle"] = mod_cotas.formato(
                mod_cotas.medida(S.doc, e),
                {**ESTILO_COTA_T101, **S.doc.estilos_cota.get(e.estilo, {})},
                e.texto)
        elif e.tipo in ("texto", "textom"):
            d["detalle"] = (e.texto or "")[:28]
        elif e.tipo == "insercion":
            d["detalle"] = e.bloque
        elif e.tipo == "cruda":
            d["detalle"] = e.dxftype
        elif e.tipo == "polilinea":
            d["detalle"] = f"{len(e.puntos)} vértices"
        elif e.tipo == "circulo":
            d["detalle"] = f"⌀ {e.radio * 2:.0f}"
        elif e.tipo == "linea":
            d["detalle"] = f"{((e.p2[0] - e.p1[0]) ** 2 + (e.p2[1] - e.p1[1]) ** 2) ** 0.5:.0f} mm"
        salida.append(d)
    return {"entidades": salida}


@app.get("/api/trazos")
def trazos():
    """Lo que se pinta y lo que se engancha, en la misma llamada.

    Van juntos a propósito: si el lienzo y el índice de referencias se piden
    por separado, hay un instante en que el osnap apunta a geometría que ya no
    está en pantalla, y el usuario ve el marcador pegado al aire.
    """
    with S.candado:
        return _json({
            "trazos": dibujo.trazos(S.doc, S.espacio),
            "geometria": geometria.indice(S.doc, S.espacio),
            "extension": S.doc.extension(S.espacio),
        })


@app.get("/api/bloques/definicion")
def bloque_definicion(nombre: str):
    """La definición de un bloque pesado, para instanciarlo en el lienzo
    cuando llega por parche una inserción cuyo bloque el navegador no tiene."""
    with S.candado:
        d = dibujo.definicion_bloque(S.doc, nombre)
    if d is None:
        _error(KeyError(f"No existe el bloque «{nombre}»"), 404)
    return _json(d)


# =========================================================================
# Preferencias de dibujo  ·  features 12, 13, 14, 15
# =========================================================================

@app.get("/api/preferencias")
def preferencias_leer():
    return {"preferencias": preferencias.leer(),
            "modos_osnap": preferencias.MODOS_OSNAP}


class CambioPrefs(BaseModel):
    cambios: dict


@app.post("/api/preferencias")
def preferencias_guardar(entrada: CambioPrefs):
    return {"preferencias": preferencias.guardar(entrada.cambios),
            "modos_osnap": preferencias.MODOS_OSNAP}


# =========================================================================
# Puente con Taller 101  ·  features 6 y 69 a 74
# =========================================================================

class ImportarT101x(BaseModel):
    ruta: str
    acotar: bool = True


@app.post("/api/t101x/resumen")
def t101x_resumen(entrada: RutaEntrada):
    try:
        return t101x.resumen(t101x.leer(entrada.ruta))
    except Exception as exc:
        _error(exc)


@app.post("/api/t101x/importar")
def t101x_importar(entrada: ImportarT101x):
    try:
        with S.candado:
            datos = t101x.leer(entrada.ruta)
            with S.doc.transaccion("Importar de Taller 101"):
                r = t101x.generar(S.doc, datos, entrada.ruta, entrada.acotar)
    except Exception as exc:
        _error(exc)
    return {**r, **S.resumen()}


@app.post("/api/t101x/regenerar")
def t101x_regenerar():
    try:
        with S.candado:
            with S.doc.transaccion("Regenerar desde Taller 101"):
                r = t101x.regenerar(S.doc)
    except Exception as exc:
        _error(exc)
    return {**r, **S.resumen()}


@app.post("/api/hojas_por_mueble")
def hojas_por_mueble():
    """Una hoja por mueble, cada una encuadrada sobre el suyo  ·  feature 73.

    El despiece pieza por pieza lo calcula Taller 101 y lo exporta en DXF;
    aquí se arma el plano **del mueble**, que es lo que se lleva al taller
    junto con la lista de corte.
    """
    creadas = []
    with S.candado:
        inserciones = [e for e in S.doc.entidades.values()
                       if e.tipo == "insercion" and e.origen == t101x.ORIGEN]
        if not inserciones:
            _error(ValueError("Este dibujo no trae muebles importados de Taller 101"))
        for ins in inserciones:
            caja = S.doc.caja_de(ins)
            if not caja:
                continue
            L = papel.layout_nuevo(ins.bloque, "A3")
            ux0, uy0, ux1, uy1 = papel.area_util(L)
            v = papel.ventana_nueva(
                ux0, uy0, ux1 - ux0, uy1 - uy0,
                [(caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2])
            # la escala se elige para que ESE mueble llene su hoja
            necesaria = max((caja[2] - caja[0]) / (v["ancho"] * 0.9),
                            (caja[3] - caja[1]) / (v["alto"] * 0.9), 1e-6)
            v["escala"] = float(next((e for e in papel.ESCALAS if e >= necesaria),
                                     papel.ESCALAS[-1]))
            L["ventanas"].append(v)
            L["rotulo"]["dibujo"] = ins.bloque
            S.doc.layouts.append(L)
            creadas.append(ins.bloque)
        S.doc.sucio = True
    return {"hojas": creadas, "layouts": S.doc.layouts}


class PaqueteEntrada(BaseModel):
    carpeta: str


@app.post("/api/paquete_supervisor")
def paquete_supervisor(entrada: PaqueteEntrada):
    """Deja en una carpeta lo que SUPERVISOR necesita  ·  feature 74.

    Un PDF para mirar, un DXF para cortar y un `manifiesto.json` que dice qué
    es cada cosa. Se entrega por carpeta y no por una llamada a SUPERVISOR
    porque SUPERVISOR todavía no tiene una puerta de entrada; el día que la
    tenga, lo que cambia es quién lee esta carpeta, no lo que hay dentro.
    """
    carpeta = pathlib.Path(entrada.carpeta)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        base = (S.doc.nombre or "plano").replace("/", "-")
        salidas = {}
        if S.doc.layouts:
            r = export_pdf.escribir(S.doc, carpeta / f"{base}.pdf")
            salidas["pdf"] = r["ruta"]
        res = export_dxf.escribir(S.doc, carpeta / f"{base}.dxf")
        salidas["dxf"] = str(carpeta / f"{base}.dxf")
        manifiesto = {
            "app": config.APP_NOMBRE,
            "dibujo": S.doc.nombre,
            "cliente": S.doc.cliente,
            "generado": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "entidades": len(S.doc.entidades),
            "hojas": [L["nombre"] for L in S.doc.layouts],
            "muebles": sorted({e.bloque for e in S.doc.entidades.values()
                               if e.tipo == "insercion"}),
            "origen_t101x": S.doc.origen_t101x,
            "archivos": salidas,
            "dxf_escritas": res.escritas,
        }
        (carpeta / "manifiesto.json").write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        _error(exc)
    return {"carpeta": str(carpeta), **manifiesto}


# =========================================================================
# Referencia externa y comparación  ·  features 77 y 78
# =========================================================================

CAPA_XREF = "REF-EXTERNA"


@app.post("/api/refext")
def refext(entrada: RutaEntrada):
    """Trae otro dibujo a una capa bloqueada  ·  feature 77.

    No se enlaza en vivo. Un plano que cambia solo mientras lo estás mirando es
    un plano en el que no se puede confiar: se trae cuando uno lo pide, y
    entonces se ve qué cambió.
    """
    ruta = pathlib.Path(entrada.ruta)
    if not ruta.exists():
        _error(FileNotFoundError(f"No existe {ruta}"), 404)
    try:
        otro = (proyecto.abrir(ruta) if ruta.suffix.lower() == config.EXT_PROYECTO
                else leer(ruta)[0])
        with S.candado:
            if CAPA_XREF not in S.doc.capas:
                S.doc.capa_agregar(Capa(CAPA_XREF, "#8A93A1", 13, "CONTINUOUS",
                                        imprime=False,
                                        descripcion=f"Referencia externa: {ruta.name}"))
            else:
                S.doc.capa_modificar(CAPA_XREF, {"bloqueada": False})
            n = 0
            with S.doc.transaccion(f"Referencia externa «{ruta.name}»"):
                # se quita la referencia anterior antes de traer la nueva
                for id_ in [e.id for e in S.doc.entidades.values()
                            if e.origen == "refext"]:
                    S.doc.borrar(id_)
                for nombre, bl in otro.bloques.items():
                    if nombre not in S.doc.bloques:
                        S.doc.bloque_agregar(bl)
                for e in otro.lista():
                    copia = ent_mod.de_dict({**e.a_dict(), "id": None,
                                             "capa": CAPA_XREF, "origen": "refext"})
                    copia.id = ent_mod.nuevo_id()
                    S.doc.agregar(copia)
                    n += 1
            S.doc.capa_modificar(CAPA_XREF, {"bloqueada": True})
    except Exception as exc:
        _error(exc)
    return {"entidades": n, "capa": CAPA_XREF, "ruta": str(ruta), **S.resumen()}


@app.post("/api/comparar")
def comparar(entrada: RutaEntrada):
    """Qué cambió entre este dibujo y otro archivo  ·  feature 78.

    Se comparan por **geometría**, no por id: los ids de dos archivos distintos
    nunca coinciden, y compararlos diría que todo cambió siempre.
    """
    ruta = pathlib.Path(entrada.ruta)
    if not ruta.exists():
        _error(FileNotFoundError(f"No existe {ruta}"), 404)
    try:
        otro = (proyecto.abrir(ruta) if ruta.suffix.lower() == config.EXT_PROYECTO
                else leer(ruta)[0])
    except Exception as exc:
        _error(exc)

    def huella(e):
        d = e.a_dict()
        for k in ("id", "handle_origen", "origen"):
            d.pop(k, None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)

    aqui = {}
    for e in S.doc.lista():
        aqui.setdefault(huella(e), []).append(e.id)
    alla = {}
    for e in otro.lista():
        alla.setdefault(huella(e), []).append(e.id)

    solo_aqui, ids_aqui, solo_alla, iguales = 0, [], 0, 0
    for h, ids in aqui.items():
        n_alla = len(alla.get(h, []))
        iguales += min(len(ids), n_alla)
        if len(ids) > n_alla:
            solo_aqui += len(ids) - n_alla
            ids_aqui.extend(ids[n_alla:])
    for h, ids in alla.items():
        n_aqui = len(aqui.get(h, []))
        if len(ids) > n_aqui:
            solo_alla += len(ids) - n_aqui

    detalle = []
    por_tipo = {}
    for id_ in ids_aqui:
        t = S.doc.entidades[id_].tipo
        por_tipo[t] = por_tipo.get(t, 0) + 1
    for t, n in sorted(por_tipo.items()):
        detalle.append(f"{n} {t}(s) de más aquí")
    if len(S.doc.capas) != len(otro.capas):
        detalle.append(f"capas: {len(S.doc.capas)} aquí, {len(otro.capas)} allá")

    return {"solo_aqui": solo_aqui, "solo_alla": solo_alla, "iguales": iguales,
            "ids_solo_aqui": ids_aqui[:500], "detalle": detalle}


# =========================================================================
# Bloques y biblioteca  ·  features 29 y 30
# =========================================================================

BIBLIOTECA = config.carpeta_usuario() / "bloques"


class BloqueNuevo(BaseModel):
    nombre: str
    ids: list
    base: list


@app.get("/api/bloques")
def bloques():
    """Los del dibujo y los del taller.

    La biblioteca es del **taller**, no del proyecto: una jaladera dibujada una
    vez tiene que estar en todas las cocinas. Es la misma lección que los
    materiales de Taller 101.
    """
    guardados = []
    if BIBLIOTECA.exists():
        for f in sorted(BIBLIOTECA.glob("*.json")):
            try:
                datos = json.loads(f.read_text(encoding="utf-8"))
                guardados.append({"nombre": datos.get("nombre", f.stem),
                                  "descripcion": datos.get("descripcion", ""),
                                  "entidades": len(datos.get("entidades", []))})
            except Exception:
                continue
    return {"documento": [{"nombre": b.nombre, "entidades": len(b.entidades),
                           "descripcion": b.descripcion}
                          for b in S.doc.bloques.values()],
            "biblioteca": guardados}


@app.post("/api/bloque")
def bloque_crear(entrada: BloqueNuevo):
    """Convierte lo seleccionado en un bloque y lo deja insertado en su sitio.

    Todo en una transacción: crear el bloque, quitar las entidades sueltas y
    poner la inserción. A medias quedaría un dibujo con las piezas duplicadas.
    """
    nombre = (entrada.nombre or "").strip()
    if not nombre:
        _error(ValueError("El bloque necesita un nombre"))
    if nombre in S.doc.bloques:
        _error(ValueError(f"Ya existe un bloque llamado «{nombre}»"))
    base = [float(entrada.base[0]), float(entrada.base[1])]

    with S.candado:
        piezas = [S.doc.entidades[i] for i in entrada.ids if i in S.doc.entidades]
        if not piezas:
            _error(ValueError("No hay nada seleccionado"))
        # las entidades del bloque se guardan relativas a su punto base
        from copy import deepcopy
        internas = []
        for e in piezas:
            copia = ent_mod.de_dict(deepcopy(e.a_dict()))
            copia.handle_origen = ""
            internas.append(copia)
        with S.doc.transaccion(f"Bloque «{nombre}»"):
            S.doc.bloque_agregar(ent_mod.Bloque(nombre=nombre, base=base,
                                                entidades=internas))
            for e in piezas:
                S.doc.borrar(e.id)
            ins = S.doc.agregar(ent_mod.Insercion(bloque=nombre, p=base,
                                                  capa=S.doc.capa_activa))
    return {"id": ins.id, **S.resumen()}


class InsertarBloque(BaseModel):
    nombre: str
    p: list
    escala: float = 1.0
    rotacion: float = 0.0
    desde_biblioteca: bool = False


@app.post("/api/insertar")
def bloque_insertar(entrada: InsertarBloque):
    with S.candado:
        if entrada.desde_biblioteca and entrada.nombre not in S.doc.bloques:
            f = BIBLIOTECA / f"{entrada.nombre}.json"
            if not f.exists():
                _error(FileNotFoundError(f"No está «{entrada.nombre}» en la biblioteca"), 404)
            datos = json.loads(f.read_text(encoding="utf-8"))
            S.doc.bloque_agregar(ent_mod.Bloque.de_dict(datos))
        if entrada.nombre not in S.doc.bloques:
            _error(KeyError(f"No existe el bloque «{entrada.nombre}»"), 404)
        with S.doc.transaccion(f"Insertar «{entrada.nombre}»"):
            ins = S.doc.agregar(ent_mod.Insercion(
                bloque=entrada.nombre, p=[float(entrada.p[0]), float(entrada.p[1])],
                escala=[entrada.escala, entrada.escala], rotacion=entrada.rotacion,
                capa=S.doc.capa_activa))
    return {"id": ins.id, **S.resumen()}


class GuardarBloque(BaseModel):
    nombre: str
    descripcion: str = ""


@app.post("/api/biblioteca")
def biblioteca_guardar(entrada: GuardarBloque):
    bl = S.doc.bloques.get(entrada.nombre)
    if bl is None:
        _error(KeyError(f"No existe el bloque «{entrada.nombre}»"), 404)
    BIBLIOTECA.mkdir(parents=True, exist_ok=True)
    datos = bl.a_dict()
    datos["descripcion"] = entrada.descripcion
    (BIBLIOTECA / f"{entrada.nombre}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"guardado": entrada.nombre, "carpeta": str(BIBLIOTECA)}


# --- PDF de fondo  ·  feature 7 -------------------------------------------

class PDFEntrada(BaseModel):
    ruta: str
    pagina: int = 1
    escala: float = 1.0
    origen: list = [0.0, 0.0]


@app.post("/api/pdf_paginas")
def pdf_paginas(entrada: RutaEntrada):
    try:
        return {"paginas": pdf_fondo.paginas(entrada.ruta)}
    except Exception as exc:
        _error(exc)


@app.post("/api/pdf_fondo")
def pdf_importar(entrada: PDFEntrada):
    try:
        with S.candado:
            with S.doc.transaccion("Importar PDF de fondo"):
                r = pdf_fondo.importar(S.doc, entrada.ruta, entrada.pagina,
                                       entrada.escala, entrada.origen)
    except pdf_fondo.PDFSinVectores as exc:
        _error(exc, 422)
    except Exception as exc:
        _error(exc)
    return {**r, **S.resumen()}


# --- Imagen de referencia  ·  feature 8 -----------------------------------

@app.get("/api/imagen_ref/{id_}")
def imagen_ref(id_: str):
    """Sirve el archivo de una imagen de referencia **del documento**.

    Sólo se sirve lo que una entidad del dibujo señala: la interfaz no puede
    pedir cualquier archivo del disco por esta puerta.
    """
    ent = S.doc.entidades.get(id_)
    if ent is None or ent.tipo != "imagen":
        _error(KeyError("No es una imagen del dibujo"), 404)
    ruta = pathlib.Path(ent.archivo)
    if not ruta.exists():
        _error(FileNotFoundError(f"No se encuentra {ruta}"), 404)
    return FileResponse(str(ruta))


# =========================================================================
# Hojas de impresión  ·  features 60 a 68
# =========================================================================

class LayoutNuevo(BaseModel):
    nombre: str = ""
    formato: str = "A3"
    # Recuadro del modelo [x0, y0, x1, y1] que la ventana debe enseñar
    # (VENTANAHOJA). Sin él, la ventana encuadra todo el dibujo.
    caja: list | None = None


class CambioLayout(BaseModel):
    cambios: dict


class CambioVentana(BaseModel):
    cambios: dict


def _layout(i: int) -> dict:
    if not (0 <= i < len(S.doc.layouts)):
        _error(IndexError("No existe esa hoja"), 404)
    return S.doc.layouts[i]


@app.get("/api/layouts")
def layouts():
    return {"layouts": S.doc.layouts, "formatos": papel.FORMATOS,
            "escalas": papel.ESCALAS}


@app.post("/api/layout")
def layout_nuevo(entrada: LayoutNuevo):
    """Una hoja nueva viene con una ventana ya encuadrada sobre el dibujo.

    Una hoja vacía obliga a inventar de cero el rectángulo y la escala, que es
    justo la parte que nadie quiere hacer. Encuadrada, se ajusta si hace falta.
    """
    with S.candado:
        nombre = _nombre_libre(entrada.nombre or f"{mod_idioma.t('Plano')} {len(S.doc.layouts) + 1}")
        L = papel.layout_nuevo(nombre, entrada.formato)
        ux0, uy0, ux1, uy1 = papel.area_util(L)
        v = papel.ventana_nueva(ux0, uy0, ux1 - ux0, uy1 - uy0, [0, 0])
        papel.encuadrar_ventana(S.doc, v, entrada.caja)
        L["ventanas"].append(v)
        S.doc.layouts.append(L)
        papel.escala_de_cotas(S.doc, L)
        S.doc.sucio = True
    return {"indice": len(S.doc.layouts) - 1, "layouts": S.doc.layouts}


@app.patch("/api/layout/{i}")
def layout_editar(i: int, entrada: CambioLayout):
    with S.candado:
        L = _layout(i)
        for k, v in entrada.cambios.items():
            if k == "rotulo" and isinstance(v, dict):
                L.setdefault("rotulo", {}).update(v)
            elif k == "nombre":
                # Lo dibujado sobre la hoja se identifica por el nombre de la
                # hoja, así que renombrarla tiene que arrastrarlo: si no, la
                # nota se queda apuntando a una hoja que ya no existe y
                # desaparece de la vista sin haberse borrado.
                antes, ahora = L.get("nombre", ""), _nombre_libre(str(v), i)
                if ahora != antes:
                    for e in S.doc.entidades.values():
                        if getattr(e, "espacio", "") == antes:
                            e.espacio = ahora
                    if S.espacio == antes:
                        S.espacio = ahora
                    S.doc.olvidar()
                L["nombre"] = ahora
            elif k == "formato":
                L[k] = v
            elif k in ("ancho", "alto"):
                # Sólo tienen sentido con formato CUSTOM, pero se guardan
                # siempre: quien vuelve de A3 a la medida no tiene por qué
                # volver a teclear sus números.
                L[k] = min(max(float(v), papel.CUSTOM_MIN), papel.CUSTOM_MAX)
            elif k == "tam_cotas":
                # Altura del texto de cota en mm de papel, **de esta hoja**
                # (Mike, 9-sep). Vacío o 0 = la del estilo.
                try:
                    tam = float(v) if v not in (None, "") else 0.0
                except (TypeError, ValueError):
                    tam = 0.0
                if tam > 0:
                    L["tam_cotas"] = min(max(tam, 0.5), 50.0)
                else:
                    L.pop("tam_cotas", None)
                S.doc.olvidar()
        # Cambiar de formato mueve el papel debajo de las ventanas. Las que
        # quedaron fuera del marco se recolocan: una ventana flotando en el
        # vacío no avisa de nada, sólo imprime una hoja en blanco. Y si es la
        # única ventana, ocupa el área útil entera (Mike, 9-sep-2026).
        cambio_papel = any(k in entrada.cambios for k in ("formato", "ancho", "alto"))
        _encajar_ventanas(L, crecer=cambio_papel)
        papel.escala_de_cotas(S.doc, L)
        S.doc.sucio = True
    return {"layouts": S.doc.layouts}


def _encajar_ventanas(L: dict, crecer: bool = False) -> None:
    """Que ninguna ventana se salga del área útil. Con `crecer`, la única
    ventana de la hoja se agranda hasta ocupar toda el área útil —sin invadir
    el pie de plano— que es lo que uno espera al cambiar el tamaño del papel
    (Mike, 9-sep-2026: «si cambio el tamaño de la hoja, en automático el
    viewport ocupe la mayor área posible sin ocupar el espacio del pie»)."""
    util_x0, util_y0, util_x1, util_y1 = papel.area_util(L)
    vs = L.get("ventanas") or []
    if crecer and len(vs) == 1:
        v = vs[0]
        v["x"], v["y"] = util_x0, util_y0
        v["ancho"], v["alto"] = util_x1 - util_x0, util_y1 - util_y0
        return
    for v in vs:
        v["ancho"] = max(20.0, min(v["ancho"], util_x1 - util_x0))
        v["alto"] = max(20.0, min(v["alto"], util_y1 - util_y0))
        v["x"] = min(max(v["x"], util_x0), util_x1 - v["ancho"])
        v["y"] = min(max(v["y"], util_y0), util_y1 - v["alto"])


class VentanaNueva(BaseModel):
    x: float | None = None
    y: float | None = None
    ancho: float | None = None
    alto: float | None = None
    escala: float | None = None
    centro: list | None = None


@app.post("/api/layout/{i}/ventana")
def ventana_nueva(i: int, entrada: VentanaNueva):
    """Una ventana más en la hoja (Mike, 9-sep-2026: «agregar viewports
    adicionales»). Sin medidas, ocupa el área útil; sin escala, la de la
    primera ventana; sin centro, el centro del dibujo."""
    with S.candado:
        L = _layout(i)
        ux0, uy0, ux1, uy1 = papel.area_util(L)
        vs = L.setdefault("ventanas", [])
        ancho = float(entrada.ancho or (ux1 - ux0))
        alto = float(entrada.alto or (uy1 - uy0))
        x = float(entrada.x if entrada.x is not None else ux0)
        y = float(entrada.y if entrada.y is not None else uy0)
        escala = float(entrada.escala or (vs[0].get("escala", 20) if vs else 20))
        ext = S.doc.extension()
        centro = entrada.centro or ([(ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2] if ext else [0, 0])
        v = papel.ventana_nueva(x, y, ancho, alto, centro, escala)
        vs.append(v)
        _encajar_ventanas(L)
        papel.escala_de_cotas(S.doc, L)
        S.doc.sucio = True
    return {"indice": len(vs) - 1, "layouts": S.doc.layouts}


@app.delete("/api/layout/{i}/ventana/{j}")
def ventana_borrar(i: int, j: int):
    with S.candado:
        L = _layout(i)
        vs = L.get("ventanas") or []
        if not (0 <= j < len(vs)):
            _error(IndexError("No existe esa ventana"), 404)
        vs.pop(j)
        papel.escala_de_cotas(S.doc, L)
        S.doc.sucio = True
    return {"layouts": S.doc.layouts}


@app.delete("/api/layout/{i}")
def layout_borrar(i: int):
    with S.candado:
        L = _layout(i)
        nombre = L.get("nombre", "")
        # Se va la hoja y se va lo que estaba dibujado en ella. Dejarlo
        # huérfano sería peor: no se vería en ninguna parte, seguiría pesando
        # en el archivo y reaparecería el día que alguien creara otra hoja con
        # el mismo nombre. Va dentro de una transacción para que un Ctrl+Z lo
        # devuelva.
        huerfanas = [e.id for e in S.doc.entidades.values()
                     if getattr(e, "espacio", "") == nombre]
        if huerfanas:
            with S.doc.transaccion(f"Borrar hoja «{nombre}»"):
                for id_ in huerfanas:
                    S.doc.borrar(id_)
        S.doc.layouts.pop(i)
        if S.espacio == nombre:
            S.espacio = ""
        S.doc.sucio = True
    return {"layouts": S.doc.layouts}


def _nombre_libre(nombre: str, salvo: int = -1) -> str:
    """Un nombre de hoja que no choque con otra.

    Dos hojas con el mismo nombre serían dos espacios con el mismo nombre, y lo
    dibujado en una saldría también en la otra.
    """
    base = (nombre or "Plano").strip() or "Plano"
    usados = {L.get("nombre", "") for j, L in enumerate(S.doc.layouts) if j != salvo}
    if base not in usados:
        return base
    n = 2
    while f"{base} ({n})" in usados:
        n += 1
    return f"{base} ({n})"


@app.patch("/api/layout/{i}/ventana/{j}")
def ventana_editar(i: int, j: int, entrada: CambioVentana):
    with S.candado:
        L = _layout(i)
        if not (0 <= j < len(L["ventanas"])):
            _error(IndexError("No existe esa ventana"), 404)
        v = L["ventanas"][j]
        if entrada.cambios.get("encuadrar"):
            papel.encuadrar_ventana(S.doc, v)
        if entrada.cambios.get("centrar"):
            # Centrar el dibujo en la ventana sin tocar la escala (Mike, 8-sep).
            ext = S.doc.extension()
            if ext:
                v["centro"] = [(ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2]
        for k, valor in entrada.cambios.items():
            if k in ("x", "y", "ancho", "alto", "escala", "rotacion"):
                v[k] = float(valor)
            elif k == "centro":
                v["centro"] = [float(valor[0]), float(valor[1])]
            elif k == "marco":
                v["marco"] = bool(valor)
        # Dentro del área útil siempre: al arrastrar un handle más allá del
        # marco, la ventana se detiene en el borde.
        if any(k in entrada.cambios for k in ("x", "y", "ancho", "alto")):
            _encajar_ventanas(L)
        papel.escala_de_cotas(S.doc, L)
        S.doc.sucio = True
    return {"layouts": S.doc.layouts}


@app.get("/api/layout/{i}/ventana/{j}/previa")
def ventana_previa(i: int, j: int):
    """Lo que la ventana `j` puede enseñar alrededor de su encuadre actual, para
    correr el dibujo **en vivo** al arrastrarlo (ver `papel.previa_ventana`)."""
    with S.candado:
        L = _layout(i)
        if not (0 <= j < len(L["ventanas"])):
            _error(IndexError("No existe esa ventana"), 404)
        trazos = papel.previa_ventana(S.doc, L, j)
    return _json({"trazos": trazos})


@app.get("/api/papel/{i}")
def papel_trazos(i: int):
    """El **fondo** de la hoja: el marco, el pie de plano y lo que se ve por
    las ventanas.

    Lo que el usuario dibujó sobre la hoja no viene aquí: eso lo pinta el
    lienzo normal a partir de `/api/trazos`, y así al poner una nota se repinta
    por parche en vez de rehacer la hoja entera. Al PDF sí va todo junto — ver
    `papel.trazos_papel`.
    """
    with S.candado:
        L = _layout(i)
        hoja = papel.trazos_papel(S.doc, L, propias=False)
        # Y la geometría del modelo vista por las ventanas, para poder
        # engancharse a lo que se ve al acotar sobre la hoja.
        geo = papel.geometria_ventanas(S.doc, L)
    return _json({**hoja, "layout": L, "indice": i, "geometria_ventanas": geo})


@app.get("/api/papel/{i}/svg")
def papel_svg(i: int):
    """La hoja como SVG en milímetros: es lo que se imprime y lo que enseña la
    vista previa (ver core/svg.py y `Papel.vistaPrevia` en ui/papel.js)."""
    from fastapi.responses import Response
    from core import svg as mod_svg
    with S.candado:
        L = _layout(i)
        texto = mod_svg.hoja_svg(S.doc, L)
    return Response(content=texto, media_type="image/svg+xml")


class EspacioActivo(BaseModel):
    #: `None` es el modelo; un entero, el índice de la hoja.
    indice: int | None = None


@app.post("/api/espacio")
def espacio_activar(entrada: EspacioActivo):
    """Cambia de espacio y devuelve lo que hay que pintar en el nuevo.

    Va en una sola llamada porque cambiar de espacio cambia **todo** lo que el
    lienzo tiene: los trazos, la geometría del osnap y la extensión. Pedirlo en
    tres pasos deja instantes en que se pinta un espacio con el índice del otro,
    y el osnap se engancha a cosas que no están ahí.
    """
    with S.candado:
        if entrada.indice is None:
            S.espacio = ""
        else:
            L = _layout(entrada.indice)
            S.espacio = L.get("nombre", "")
        return _json({
            "espacio": S.espacio,
            "trazos": dibujo.trazos(S.doc, S.espacio),
            "geometria": geometria.indice(S.doc, S.espacio),
            "extension": S.doc.extension(S.espacio),
        })


class Impresion(BaseModel):
    #: Sin ruta, el PDF va a una carpeta temporal. Es lo que hace falta para
    #: imprimir en papel (punto 12): el archivo es un paso intermedio, no algo
    #: que el usuario pidió tener.
    ruta: str | None = None
    layouts: list | None = None       # None = todas  ·  feature 67
    dpi: int = 150


@app.post("/api/imprimir")
def imprimir(entrada: Impresion):
    try:
        with S.candado:
            hojas = None if entrada.layouts is None else [
                S.doc.layouts[i] for i in entrada.layouts if 0 <= i < len(S.doc.layouts)]
            ruta = entrada.ruta
            if not ruta:
                import tempfile
                base = (S.doc.nombre or "plano").replace("/", "-").replace("\\", "-")
                ruta = str(pathlib.Path(tempfile.gettempdir()) /
                           f"shape101-{base}.pdf")
            r = export_pdf.escribir(S.doc, ruta, hojas)
    except Exception as exc:
        _error(exc)
    return r


@app.post("/api/imagen")
def imagen(entrada: Impresion):
    try:
        with S.candado:
            i = (entrada.layouts or [0])[0]
            r = export_pdf.imagen(S.doc, entrada.ruta, _layout(i), entrada.dpi)
    except HTTPException:
        raise
    except Exception as exc:
        _error(exc)
    return r


# =========================================================================
# Estilos de cota  ·  features 56, 57 y 59
# =========================================================================

class EstiloCota(BaseModel):
    nombre: str
    cambios: dict


@app.get("/api/estilos_cota")
def estilos_cota():
    return {"estilos": S.doc.estilos_cota, "activo": "T101"}


#: Qué se puede tocar del estilo, y de qué tipo. Lo que no esté aquí se
#: ignora: el estilo viaja al DXF como DIMSTYLE y una llave inventada lo
#: rompería en AutoCAD sin decir dónde.
_ESTILO_CAMPOS = {
    "altura_texto": float, "tam_flecha": float, "ext_linea": float,
    "hueco_origen": float, "factor_escala": float, "decimales": int,
    "sufijo": str, "flecha": str,
}


@app.post("/api/estilo_cota")
def estilo_cota_guardar(entrada: EstiloCota):
    """Cambiar el estilo cambia **todas** las cotas que lo usan, sin tocarlas
    una por una: es justo lo que un estilo existe para hacer.

    Por eso devuelve el parche de todas las cotas del plano y no de ninguna en
    concreto, y por eso tira la caché: la geometría de una cota depende del
    estilo, y servir la de antes deja el plano diciendo la medida nueva con las
    letras viejas.
    """
    with S.candado:
        est = dict(S.doc.estilos_cota.get(entrada.nombre) or {})
        est.setdefault("nombre", entrada.nombre)
        for k, v in entrada.cambios.items():
            tipo = _ESTILO_CAMPOS.get(k)
            if tipo is None:
                continue
            try:
                est[k] = tipo(v)
            except (TypeError, ValueError):
                _error(ValueError(f"Valor inválido para «{k}»"))
        if est.get("altura_texto", 1) <= 0 or est.get("factor_escala", 1) <= 0:
            _error(ValueError("La altura del texto y la escala tienen que ser "
                              "mayores que cero"))
        S.doc.estilos_cota[entrada.nombre] = est
        S.doc.olvidar()
        S.doc.sucio = True
        # Las inserciones entran también: un bloque puede llevar cotas dentro,
        # y ésas cambian aunque la entidad de arriba no sea una cota.
        parche = _parche([e.id for e in S.doc.entidades.values()
                          if e.tipo in ("cota", "insercion")])
        completo = dict(ESTILO_COTA_T101)
        completo.update(est)
    return {"estilos": S.doc.estilos_cota, "estilo": completo,
            "parche": parche, **S.resumen()}


# =========================================================================
# Archivo  ·  features 2, 4, 5
# =========================================================================

class RutaEntrada(BaseModel):
    ruta: str


class Nuevo(BaseModel):
    pestana: bool = False


@app.post("/api/nuevo")
def nuevo(entrada: Nuevo | None = None):
    if entrada and entrada.pestana:
        try:
            ESCRITORIO.abrir_pestana()
        except ValueError as exc:
            _error(exc)
        return S.resumen()
    with S.candado:
        S.doc = Documento.nuevo()
        S.ruta = None
        S.informe = None
    return S.resumen()


class Abrir(RutaEntrada):
    #: En pestaña nueva, sin tocar lo que ya estaba abierto. Lo pone la
    #: interfaz salvo cuando la pestaña de enfrente está en blanco y sin
    #: guardar: abrir ahí no pierde nada y evita dejar pestañas vacías.
    pestana: bool = False


@app.post("/api/abrir")
def abrir(entrada: Abrir):
    ruta = pathlib.Path(entrada.ruta)
    if not ruta.exists():
        _error(FileNotFoundError(f"No existe {ruta}"), 404)
    volver_a = ESCRITORIO.activo
    nueva = False
    if entrada.pestana:
        try:
            ESCRITORIO.abrir_pestana()
            nueva = True
        except ValueError as exc:
            _error(exc)
    try:
        with S.candado:
            if ruta.suffix.lower() == config.EXT_PROYECTO:
                S.doc = proyecto.abrir(ruta)
                S.informe = None
            else:
                S.doc, informe = leer(ruta)
                S.informe = informe.a_dict()
            S.ruta = ruta
    except Exception as exc:
        # Si la pestaña se abrió para esto, se cierra: dejar una pestaña vacía
        # detrás de un error es basura que el usuario tiene que limpiar.
        if nueva:
            ESCRITORIO.cerrar(ESCRITORIO.activo)
            ESCRITORIO.activo = volver_a
        if isinstance(exc, DWGNoDisponible):
            _error(exc, 501)
        _error(exc)
    preferencias.recordar(ruta, S.doc.nombre)
    _congelar_gc()
    r = S.resumen()
    # Un DWG grande sin ODA: se ofrece instalarlo, una sola vez (core/oda.py).
    mb = mod_oda.sugerir_para(ruta)
    if mb:
        r["sugerir_oda"] = mb
    return r


@app.post("/api/guardar")
def guardar(entrada: RutaEntrada):
    try:
        with S.candado:
            S.ruta = proyecto.guardar(S.doc, entrada.ruta)
    except Exception as exc:
        _error(exc)
    preferencias.recordar(S.ruta, S.doc.nombre)
    return S.resumen()


# --- Pestañas  ·  punto 14 ------------------------------------------------

@app.get("/api/documentos")
def documentos():
    return ESCRITORIO.lista()


class Pestana(BaseModel):
    indice: int


@app.post("/api/documentos/activar")
def documento_activar(entrada: Pestana):
    if not (0 <= entrada.indice < len(ESCRITORIO.sesiones)):
        _error(IndexError("No existe ese dibujo"), 404)
    ESCRITORIO.activo = entrada.indice
    return S.resumen()


@app.post("/api/documentos/cerrar")
def documento_cerrar(entrada: Pestana):
    """Cierra sin preguntar: quien pregunta es la interfaz, que es la que sabe
    si el usuario ya dijo que sí."""
    try:
        ESCRITORIO.cerrar(entrada.indice)
    except IndexError as exc:
        _error(exc, 404)
    return S.resumen()


@app.post("/api/exportar_dxf")
def exportar_dxf(entrada: RutaEntrada):
    """DXF o DWG, según la extensión  ·  features 4 y 3."""
    try:
        with S.candado:
            res = export_dxf.escribir(S.doc, entrada.ruta)
    except DWGNoDisponible as exc:
        _error(exc, 501)
    except Exception as exc:
        _error(exc)
    return {"ruta": entrada.ruta, **res.a_dict()}


# --- Autoguardado y recuperación  ·  feature 9 ---------------------------

@app.post("/api/autoguardar")
def autoguardar():
    with S.candado:
        copia = proyecto.autoguardar(S.doc, S.ruta)
    return {"copia": str(copia) if copia else None}


@app.get("/api/recuperables")
def recuperables():
    return {"copias": proyecto.recuperables()}


@app.post("/api/recuperar")
def recuperar(entrada: Abrir):
    """Abrir un autoguardado **como lo que era**: el dibujo queda apuntando a
    su archivo original (si era un .t101d) o sin ruta (si era un DWG o un
    dibujo nuevo), y marcado con cambios. Antes se abría como si fuera un
    archivo más, y Ctrl+S lo guardaba dentro de la carpeta de autoguardado."""
    copia = pathlib.Path(entrada.ruta)
    if not copia.exists():
        _error(FileNotFoundError(f"No existe {copia}"), 404)
    marca = copia.with_suffix(".origen")
    origen = marca.read_text(encoding="utf-8").strip() if marca.exists() else ""
    volver_a = ESCRITORIO.activo
    nueva = False
    if entrada.pestana:
        try:
            ESCRITORIO.abrir_pestana()
            nueva = True
        except ValueError as exc:
            _error(exc)
    try:
        with S.candado:
            S.doc = proyecto.abrir(copia)
            S.informe = None
            S.doc.sucio = True
            S.ruta = pathlib.Path(origen) if origen.lower().endswith(config.EXT_PROYECTO) else None
            if S.ruta is None and origen:
                S.doc.nombre = pathlib.Path(origen).stem
    except Exception as exc:
        if nueva:
            ESCRITORIO.cerrar(ESCRITORIO.activo)
            ESCRITORIO.activo = volver_a
        _error(exc)
    proyecto.descartar_recuperacion(copia)
    return S.resumen()


@app.post("/api/sesion/cerrar")
def sesion_cerrar():
    """Electron lo llama justo antes de matar el motor, cuando el usuario ya
    contestó si guarda o no. Después de esto no queda nada que recuperar."""
    proyecto.cerrar_sesion()
    return {"ok": True}


@app.get("/api/sesion")
def sesion_info():
    return {"se_cayo": SE_CAYO, "sucios": [d["nombre"] for d in ESCRITORIO.lista()["documentos"] if d["sucio"]]}


@app.post("/api/descartar_recuperacion")
def descartar(entrada: RutaEntrada):
    proyecto.descartar_recuperacion(entrada.ruta)
    return {"ok": True}


# =========================================================================
# Deshacer / rehacer  ·  feature 10
# =========================================================================

@app.post("/api/deshacer")
def deshacer():
    with S.candado:
        nombre = S.doc.deshacer()
        parche = None if S.doc.ultimo_toco_capas else _parche(S.doc.ultimos_tocados)
    return {"accion": nombre, "parche": parche, **S.resumen()}


@app.post("/api/rehacer")
def rehacer():
    with S.candado:
        nombre = S.doc.rehacer()
        # Si la transacción tocó capas, cambia de golpe qué se ve y qué no en
        # todo el dibujo: ahí el parche no alcanza y el cliente recarga.
        parche = None if S.doc.ultimo_toco_capas else _parche(S.doc.ultimos_tocados)
    return {"accion": nombre, "parche": parche, **S.resumen()}


# =========================================================================
# Capas  ·  features 45 a 49
# =========================================================================

class CapaEntrada(BaseModel):
    nombre: str
    color: str = "#FFFFFF"
    grosor: int = 25
    tipo_linea: str = "CONTINUOUS"
    visible: bool = True
    bloqueada: bool = False
    imprime: bool = True
    descripcion: str = ""


class CambioCapa(BaseModel):
    cambios: dict


@app.post("/api/capa")
def capa_nueva(entrada: CapaEntrada):
    try:
        with S.candado:
            S.doc.capa_agregar(Capa(**entrada.model_dump()))
    except (NombreCapaInvalido, ValueError) as exc:
        _error(exc)
    return S.resumen()


@app.patch("/api/capa/{nombre}")
def capa_editar(nombre: str, entrada: CambioCapa):
    """Cambiar una capa toca sólo **sus** entidades, no el dibujo entero.

    Apagar una capa en un plano de 48 capas es de lo que más se hace, y hasta
    ahora costaba lo mismo que abrir el archivo. El parche cuesta lo que pesa
    esa capa. Si le cambian el nombre, sí se recarga: el nombre viaja en cada
    trazo y cambia el índice completo.
    """
    try:
        with S.candado:
            if nombre not in S.doc.capas:
                _error(KeyError(f"No existe la capa «{nombre}»"), 404)
            afectadas = [e.id for e in S.doc.entidades.values() if e.capa == nombre]
            S.doc.capa_modificar(nombre, entrada.cambios)
            renombro = ("nombre" in entrada.cambios
                        and entrada.cambios["nombre"] != nombre)
            parche = None if renombro else _parche(afectadas)
    except HTTPException:
        raise
    except (NombreCapaInvalido, ValueError) as exc:
        _error(exc)
    return {"parche": parche, **S.resumen()}


@app.delete("/api/capa/{nombre}")
def capa_borrar(nombre: str):
    try:
        with S.candado:
            S.doc.capa_borrar(nombre)
    except (CapaEnUso, ValueError) as exc:
        _error(exc)
    return S.resumen()


@app.post("/api/capa_activa/{nombre}")
def capa_activa(nombre: str):
    with S.candado:
        if nombre not in S.doc.capas:
            _error(KeyError(f"No existe la capa «{nombre}»"), 404)
        S.doc.capa_activa = nombre
    return S.resumen()


# =========================================================================
# Entidades (lo mínimo que F0 necesita; las herramientas llegan en F2 y F3)
# =========================================================================

class PreviaRayado(BaseModel):
    rutas: list
    patron: str = "SOLID"
    escala: float = 1.0
    angulo: float = 0.0


@app.get("/api/rayados")
def rayados_lista():
    """Los patrones de rayado que ofrece la galería (core/rayado.py)."""
    from core import rayado as mod_rayado
    return {"patrones": mod_rayado.lista()}


@app.post("/api/rayado/previa")
def rayado_previa(entrada: PreviaRayado):
    """Las rayas (o el relleno) de un patrón dentro de un contorno, para la
    previa de la galería de RAYADO: se ve en el modelo antes de crear nada."""
    from core import rayado as mod_rayado
    patron = (entrada.patron or "SOLID").upper()
    if patron == "SOLID" or not mod_rayado.PATRONES.get(patron, ("", []))[1]:
        pols = [mod_rayado._teselar(r) for r in entrada.rutas if len(r) >= 2]
        return _json({"lineas": [], "poligonos": pols, "solido": True})
    with S.candado:
        lineas = mod_rayado.rayas(entrada.rutas, patron, entrada.escala, entrada.angulo,
                                  S.doc.mm_por_unidad())
    return _json({"lineas": lineas, "poligonos": [], "solido": False})


class NuevaEntidad(BaseModel):
    entidad: dict
    accion: str = "Dibujar"


@app.post("/api/entidad")
def entidad_nueva(entrada: NuevaEntidad):
    """Crea una entidad. La capa, si no viene, es la activa.

    El `id` lo pone el servidor siempre, aunque el navegador mande uno: los ids
    son la liga del historial y de las cotas asociativas, y no pueden depender
    de que dos pestañas o dos herramientas no se pisen.
    """
    datos = dict(entrada.entidad)
    datos.pop("id", None)
    datos.setdefault("capa", S.doc.capa_activa)
    # Nace donde se está dibujando. Sin esto, estando en una hoja la entidad
    # caía en el modelo con coordenadas de papel: se trazaba y no aparecía en
    # ninguna parte.
    datos["espacio"] = S.espacio
    # Una cota puesta sobre una hoja mide milímetros de papel. Para que anuncie
    # la medida de verdad se le pone la escala de la ventana donde cayó, sin
    # que nadie tenga que acordarse. Es el DIMLFAC de AutoCAD.
    if S.espacio and datos.get("tipo") == "cota" and not datos.get("factor_medida"):
        L = next((x for x in S.doc.layouts if x.get("nombre") == S.espacio), None)
        if L is not None:
            datos["factor_medida"] = papel.factor_de_medida(L, datos.get("puntos") or [], S.doc.mm_por_unidad())
    try:
        ent = ent_mod.de_dict(datos)
    except Exception as exc:
        _error(exc)
    try:
        with S.candado:
            with S.doc.transaccion(entrada.accion):
                # Las cotas siempre a su capa, sin importar la activa.
                mod_cotas.encapar(S.doc, ent)
                S.doc.agregar(ent)
            parche = _parche([ent.id])
    except CapaBloqueada as exc:
        _error(exc)
    return {"id": ent.id, "parche": parche, **S.resumen()}


class VariasEntidades(BaseModel):
    entidades: list
    accion: str = "Dibujar"


@app.post("/api/entidades")
def entidades_nuevas(entrada: VariasEntidades):
    """Varias entidades en **una sola** transacción.

    Un arreglo rectangular de 40 copias tiene que deshacerse con un Ctrl+Z, no
    con cuarenta.
    """
    ids = []
    try:
        with S.candado:
            with S.doc.transaccion(entrada.accion):
                for datos in entrada.entidades:
                    d = dict(datos)
                    d.pop("id", None)
                    d.setdefault("capa", S.doc.capa_activa)
                    ids.append(S.doc.agregar(ent_mod.de_dict(d)).id)
            parche = _parche(ids)
    except (CapaBloqueada, ValueError) as exc:
        _error(exc)
    return {"ids": ids, "parche": parche, **S.resumen()}


class Operacion(BaseModel):
    """Un cambio sobre varias entidades a la vez, en una transacción."""
    accion: str = "Editar"
    cambios: dict = {}          # id → {campo: valor}
    borrar: list = []
    agregar: list = []


class Unir(BaseModel):
    ids: list[str]
    tolerancia: float | None = None


@app.post("/api/unir")
def unir_entidades(entrada: Unir):
    """UNIR  ·  varias líneas y arcos sueltos en una sola polilínea.

    La geometría vive en `core/unir.py`; aquí sólo se envuelve en una
    transacción —para que un Ctrl+Z devuelva todas las piezas a la vez— y se
    arma el parche de lo que cambió.
    """
    try:
        with S.candado:
            with S.doc.transaccion("Unir"):
                r = mod_unir.unir(S.doc, entrada.ids,
                                  entrada.tolerancia or mod_unir.TOLERANCIA)
            parche = _parche(r["borradas"] + [c["id"] for c in r["creadas"]])
    except (CapaBloqueada, ValueError) as exc:
        _error(exc)
    return {**r, "parche": parche, **S.resumen()}


@app.post("/api/operacion")
def operacion(entrada: Operacion):
    ids = []
    tocadas: list[str] = []
    try:
        with S.candado:
            with S.doc.transaccion(entrada.accion):
                for id_, cambios in entrada.cambios.items():
                    if id_ in S.doc.entidades:
                        S.doc.modificar(id_, cambios)
                for id_ in entrada.borrar:
                    S.doc.borrar(id_)
                for datos in entrada.agregar:
                    d = dict(datos)
                    d.pop("id", None)
                    d.setdefault("capa", S.doc.capa_activa)
                    ids.append(S.doc.agregar(
                        mod_cotas.encapar(S.doc, ent_mod.de_dict(d))).id)
                # Las cotas pegadas a lo que se movió se mueven con ello, y
                # dentro de la MISMA transacción: un Ctrl+Z devuelve la pieza y
                # su cota a la vez, no una y luego la otra.
                mod_cotas.limpiar_ligas(S.doc, entrada.borrar)
                tocadas = mod_cotas.actualizar_ligadas(
                    S.doc, list(entrada.cambios.keys()) + list(entrada.borrar))
            afectadas = (list(entrada.cambios.keys()) + list(entrada.borrar)
                         + ids + tocadas)
            parche = _parche(afectadas)
    except (CapaBloqueada, ValueError, AttributeError) as exc:
        _error(exc)
    return {"ids": ids, "parche": parche, **S.resumen()}


class CambioEntidad(BaseModel):
    cambios: dict


@app.patch("/api/entidad/{id_}")
def entidad_editar(id_: str, entrada: CambioEntidad):
    try:
        with S.candado:
            if id_ not in S.doc.entidades:
                _error(KeyError("No existe esa entidad"), 404)
            with S.doc.transaccion("Cambiar propiedades"):
                S.doc.modificar(id_, entrada.cambios)
                tocadas = mod_cotas.actualizar_ligadas(S.doc, [id_])
            parche = _parche([id_] + tocadas)
    except HTTPException:
        raise
    except (CapaBloqueada, AttributeError) as exc:
        _error(exc)
    return {"parche": parche, **S.resumen()}


class GrupoEntrada(BaseModel):
    ids: list


@app.post("/api/grupo")
def grupo_hacer(entrada: GrupoEntrada):
    """GRUPO: estas entidades se agarran juntas de aquí en adelante."""
    try:
        with S.candado:
            with S.doc.transaccion("Agrupar"):
                nombre = mod_agrupar.agrupar(S.doc, entrada.ids)
            ids = mod_agrupar.miembros(S.doc, nombre)
            parche = _parche(ids)
    except (ValueError, CapaBloqueada) as exc:
        _error(exc)
    return {"grupo": nombre, "ids": ids, "parche": parche, **S.resumen()}


@app.post("/api/desagrupar")
def grupo_deshacer(entrada: GrupoEntrada):
    try:
        with S.candado:
            with S.doc.transaccion("Desagrupar"):
                ids = mod_agrupar.desagrupar(S.doc, entrada.ids)
            parche = _parche(ids)
    except CapaBloqueada as exc:
        _error(exc)
    return {"ids": ids, "parche": parche, **S.resumen()}


@app.post("/api/explotar")
def explotar(entrada: GrupoEntrada):
    """EXPLOTAR: bloques, polilíneas, rayados, cotas y entidades ajenas, en
    sus partes. Una sola transacción: un Ctrl+Z lo devuelve todo."""
    try:
        with S.candado:
            with S.doc.transaccion("Explotar"):
                r = mod_agrupar.explotar(S.doc, entrada.ids)
            parche = _parche(r["quitados"] + r["nuevos"])
    except CapaBloqueada as exc:
        _error(exc)
    return {**r, "parche": parche, **S.resumen()}


@app.delete("/api/entidad/{id_}")
def entidad_borrar(id_: str):
    try:
        with S.candado:
            with S.doc.transaccion("Borrar"):
                S.doc.borrar(id_)
                mod_cotas.limpiar_ligas(S.doc, [id_])
            parche = _parche([id_])
    except CapaBloqueada as exc:
        _error(exc)
    return {"parche": parche, **S.resumen()}


@app.get("/api/entidad/{id_}")
def entidad_ver(id_: str):
    ent = S.doc.entidades.get(id_)
    if ent is None:
        _error(KeyError("No existe esa entidad"), 404)
    return ent.a_dict()


# =========================================================================
# Interfaz
# =========================================================================

# Va al final a propósito: montado en la raíz atrapa todo lo que no case con
# una ruta de /api. Y se monta en la raíz —no en /ui— para que el index.html
# encuentre `styles.css` y `app.js` con rutas relativas.
app.mount("/", StaticFiles(directory=str(UI), html=True), name="ui")


def puerto_libre(desde: int = 8780) -> int:
    for p in range(desde, desde + 200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("No hay puertos libres")


if __name__ == "__main__":
    import uvicorn

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    abrir_navegador = "--abrir" in sys.argv
    puerto = int(args[0]) if args else puerto_libre()
    url = f"http://127.0.0.1:{puerto}"
    print(f"{config.APP_NOMBRE} en {url}", flush=True)

    if abrir_navegador:
        # El navegador se abre un momento después, cuando el servidor ya
        # responde. Abrirlo antes enseña un error y asusta.
        def _abrir():
            import webbrowser
            webbrowser.open(url)
        threading.Timer(1.5, _abrir).start()

    # La consulta de versión nueva y avisos va en un hilo desde ya, no cuando
    # la interfaz la pida (Mike, 9-sep-2026: tardaba o no avisaba).
    mod_actualizar.iniciar_vigilancia()
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")
