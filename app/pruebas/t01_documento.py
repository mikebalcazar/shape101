"""Bloque 1 · el contrato del motor de shape101.

Prueba de aceptación escrita por el chat de shape101 **antes** de programar
(arranque §4). Comprueba tres cosas y nada más:

1. El **documento**: una pieza (nombre, material, espesor) más un historial de
   operaciones, que se guarda en un `.s101` y se reabre igual. Los bocetos van
   embebidos: un archivo suelto es un archivo que se pierde.
2. La **edición del historial**: cambiar una cota de abajo y regenerar; y que
   la caché por operación sólo vuelva a ejecutar lo que hace falta. P3 midió
   que regenerar 60 operaciones desde cero cuesta 10 s: por eso la caché es
   parte del contrato, no una mejora para después.
3. La **API local** (el mismo patrón que draw101: el documento vive en el
   servidor, no en el navegador).

Decisiones de Mike del 13-sep que aquí se comprueban: una pieza por documento,
mm con centésimas, material y espesor como dato de la pieza.

Si esta prueba pasa, el bloque 1 está hecho.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

from app.motor import servidor
from app.motor.documento import Documento
from poc import comun

DESCRIPCION = "documento .s101, edición del historial y API local"

ANCHO, FONDO, ESPESOR, RADIO = 900.0, 600.0, 18.0, 80.0


def rect(w, h):
    return [{"tipo": "polilinea", "cerrada": True,
             "puntos": [[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0]]}]


def circ(x, y, r):
    return [{"tipo": "circulo", "centro": [x, y], "radio": r}]


def ops_tablero(ancho=ANCHO, radio=RADIO):
    """Tablero con un barreno en medio: el caso de taller de la PoC."""
    return [
        {"op": "boceto", "plano": "XY", "entidades": rect(ancho, FONDO)},
        {"op": "extruir", "mm": ESPESOR},
        {"op": "restar", "entidades": circ(ancho / 2, FONDO / 2, radio), "mm": ESPESOR},
    ]


def volumen(ancho=ANCHO, radio=RADIO):
    return (ancho * FONDO - math.pi * radio ** 2) * ESPESOR


def pedir(url, datos=None, metodo=None):
    cuerpo = None if datos is None else json.dumps(datos).encode()
    peticion = urllib.request.Request(
        url, data=cuerpo, method=metodo or ("POST" if datos is not None else "GET"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=30) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


def correr(r: comun.Reporte):
    # 1 · el documento nuevo: una pieza con material y espesor
    doc = Documento.nuevo(nombre="Tablero", material="MDF", espesor_mm=18)
    r.igual(doc.pieza["nombre"], "Tablero", "el documento nuevo guarda el nombre de la pieza")
    r.igual(doc.pieza["material"], "MDF", "el documento nuevo guarda el material")
    r.casi(doc.pieza["espesor_mm"], 18.0, "el documento nuevo guarda el espesor en mm")
    r.igual(doc.unidades, "mm", "las unidades del documento son mm")
    r.igual(doc.decimales, 2, "las medidas se escriben con dos decimales (centésimas)")
    r.igual(doc.operaciones, [], "el documento nuevo nace sin operaciones")

    # 2 · agregar operaciones y regenerar
    for op in ops_tablero():
        doc.agregar(op)
    r.igual(len(doc.operaciones), 3, "el historial tiene las 3 operaciones")
    reg = doc.regenerar()
    r.exige(reg.solido is not None, "regenerar devuelve un sólido")
    r.casi(reg.solido.volume, volumen(), "el volumen es el de la fórmula (tablero − barreno)", 1e-2)
    caja = reg.solido.bounding_box()
    r.casi(caja.size.X, ANCHO, "el tablero mide 900 de ancho")
    r.casi(caja.size.Z, ESPESOR, "el tablero mide 18 de espesor")
    r.igual(len(reg.nombrador.caras), len(reg.solido.faces()), "todas las caras tienen nombre")
    r.cierto("arriba" in reg.nombrador.caras, "la cara de arriba se llama «arriba»")

    # 3 · el archivo .s101: se guarda, se reabre y da lo mismo
    with comun.carpeta() as d:
        ruta = d / "tablero.s101"
        doc.guardar(ruta)
        r.exige(ruta.exists(), "guardar deja el archivo .s101 en el disco")
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        r.igual(crudo["formato"], "shape101", "el archivo se declara formato shape101")
        r.igual(crudo["version"], 1, "el archivo declara versión 1 del formato")
        r.igual(crudo["unidades"], "mm", "el archivo declara mm")
        r.igual(crudo["decimales"], 2, "el archivo declara centésimas")
        r.igual(crudo["pieza"]["material"], "MDF", "el archivo guarda el material de la pieza")
        r.casi(crudo["pieza"]["espesor_mm"], 18.0, "el archivo guarda el espesor de la pieza")
        r.igual(len(crudo["operaciones"]), 3, "el archivo guarda las 3 operaciones")
        r.cierto(all("t101d" not in op for op in crudo["operaciones"]),
                 "los bocetos van embebidos: el .s101 no apunta a ningún archivo suelto")
        otro = Documento.abrir(ruta)
        r.igual(otro.pieza, doc.pieza, "reabierto, la pieza es la misma")
        r.igual(otro.operaciones, doc.operaciones, "reabierto, el historial es el mismo")
        r.casi(otro.regenerar().solido.volume, volumen(),
               "reabierto, el sólido da el mismo volumen", 1e-2)

    # 4 · cambiar una cota de abajo y regenerar
    doc.editar(0, {"op": "boceto", "plano": "XY", "entidades": rect(1000.0, FONDO)})
    doc.editar(2, {"op": "restar", "entidades": circ(500.0, FONDO / 2, RADIO), "mm": ESPESOR})
    reg2 = doc.regenerar()
    r.casi(reg2.solido.bounding_box().size.X, 1000.0, "tras cambiar la cota el tablero mide 1000")
    r.casi(reg2.solido.volume, volumen(1000.0),
           "tras cambiar la cota el volumen sigue la fórmula", 1e-2)
    r.cierto("arriba" in reg2.nombrador.caras, "«arriba» sigue existiendo tras cambiar la cota de abajo")

    # 5 · caché por operación: sólo se vuelve a ejecutar lo que hace falta
    doc.regenerar()                                     # deja el estado caliente
    doc.editar(2, {"op": "restar", "entidades": circ(500.0, FONDO / 2, 60.0), "mm": ESPESOR})
    reg3 = doc.regenerar()
    r.igual(len(reg3.tiempos), 1,
            "editar la última operación sólo vuelve a ejecutar esa (caché por operación)")
    r.cierto(reg3.tiempos and reg3.tiempos[0]["op"].startswith("2:"),
             "lo que se volvió a ejecutar es la operación 2, la editada")
    r.casi(reg3.solido.volume, volumen(1000.0, 60.0),
           "con el barreno de ⌀120 el volumen vuelve a ser el de la fórmula", 1e-2)
    doc.editar(0, {"op": "boceto", "plano": "XY", "entidades": rect(ANCHO, FONDO)})
    reg4 = doc.regenerar()
    r.igual(len(reg4.tiempos), 3, "editar la primera operación vuelve a ejecutar las 3")

    # 6 · centésimas: lo que se teclea se guarda redondeado a 0,01
    doc.agregar({"op": "empujar_cara", "cara": "arriba", "mm": 10.006})
    r.casi(doc.operaciones[-1]["mm"], 10.01,
           "una medida tecleada se guarda redondeada a centésimas", 1e-9)
    doc.borrar(len(doc.operaciones) - 1)
    r.igual(len(doc.operaciones), 3, "borrar quita la operación del historial")

    # 7 · una operación que no existe se rechaza y no deja el documento a medias
    antes = list(doc.operaciones)
    try:
        doc.agregar({"op": "no_existe"})
        doc.regenerar()
        r.cierto(False, "una operación desconocida se rechaza")
    except Exception as e:
        r.cierto("no_existe" in str(e), "una operación desconocida se rechaza diciendo cuál es",
                 f"el error dijo: {e}")
    doc.operaciones[:] = antes

    # 8 · la API local
    with comun.carpeta() as d, servidor.Servidor(puerto=0) as s:
        codigo, salud = pedir(s.url + "/api/salud")
        r.igual(codigo, 200, "el motor contesta /api/salud")
        r.igual(salud.get("ok"), True, "/api/salud dice que está vivo")
        pedir(s.url + "/api/documento/nuevo",
              {"nombre": "Tablero", "material": "MDF", "espesor_mm": 18})
        for op in ops_tablero():
            codigo, _ = pedir(s.url + "/api/operacion", {"op": op})
            r.igual(codigo, 200, f"la API acepta la operación «{op['op']}»")
        codigo, modelo = pedir(s.url + "/api/modelo")
        r.igual(codigo, 200, "la API devuelve el modelo")
        r.cierto(modelo["n_caras"] >= 6, "el modelo trae al menos las 6 caras del tablero")
        r.igual(len(modelo["caras"]), modelo["n_caras"], "viene una malla por cara, no una malla única")
        r.cierto(all(c.get("nombre") for c in modelo["caras"]), "cada cara de la malla trae su nombre")
        r.cierto(len(modelo["aristas"]) > 0, "el modelo trae las aristas para dibujarlas")
        codigo, doc_api = pedir(s.url + "/api/documento")
        r.igual(doc_api["pieza"]["material"], "MDF", "la API devuelve el documento con su material")
        for formato, nombre in (("step", "tablero.step"), ("stl", "tablero.stl"), ("gltf", "tablero.glb")):
            destino = d / nombre
            codigo, _ = pedir(s.url + "/api/exportar", {"formato": formato, "ruta": str(destino)})
            r.cierto(destino.exists() and destino.stat().st_size > 0,
                     f"exportar {formato.upper()} deja un archivo con contenido")
        guardado = d / "por-la-api.s101"
        pedir(s.url + "/api/documento/guardar", {"ruta": str(guardado)})
        r.cierto(guardado.exists(), "la API guarda el .s101 donde se le dice")
        codigo, _ = pedir(s.url + "/api/documento/abrir", {"ruta": str(guardado)})
        r.igual(codigo, 200, "la API reabre el .s101 que acaba de guardar")
        try:
            pedir(s.url + "/api/operacion", {"op": {"op": "no_existe"}})
            r.cierto(False, "la API rechaza una operación desconocida")
        except urllib.error.HTTPError as e:
            r.igual(e.code, 400, "la API rechaza una operación desconocida con 400")
        codigo, _ = pedir(s.url + "/api/salud")
        r.igual(codigo, 200, "el motor sigue contestando después del error")

    r.numero("B1 comprobaciones del contrato del motor", r.hechas, "")
