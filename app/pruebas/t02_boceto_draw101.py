"""Bloque 2 · bocetos dibujados en draw101.

Prueba de aceptación escrita antes de programar. Lo que fija:

1. shape101 lee un `.t101d` **sin draw101**: es un ZIP con `meta.json` y
   `documento.json`, y eso es todo lo que hace falta. En la máquina del taller
   draw101 puede no estar instalado.
2. **Las unidades del dibujo se respetan.** draw101 dibuja en mm, cm o m; sus
   coordenadas van en esa unidad. Un tablero dibujado en centímetros tiene que
   entrar a shape101 midiendo lo mismo que uno dibujado en milímetros. El
   `bulge` de una polilínea es adimensional y NO se escala.
3. **Qué entra y qué no**: geometría del modelo, en capa prendida. Las cotas,
   los textos, lo que vive en una hoja de impresión y lo apagado se cuentan y
   se reportan, pero no son el boceto.
4. **El `.s101` sigue siendo autosuficiente**: al agregar el boceto se embeben
   las entidades ya en milímetros y se anota de qué archivo vinieron. El
   documento guardado nunca apunta a un `.t101d` suelto.

Los dibujos de esta prueba se arman aquí mismo (el corredor no tiene draw101),
con el formato que escribe `core/proyecto.py`. Además, si el repositorio trae
muestras de verdad en `poc/muestras/*.t101d` —hechas por draw101—, se leen
todas: es la comprobación contra el escritor real.
"""
from __future__ import annotations

import json
import math
import pathlib
import urllib.error
import urllib.request
import zipfile

from app.motor import servidor, t101d
from app.motor.documento import Documento
from poc import comun

DESCRIPCION = "leer .t101d sin draw101, unidades y boceto embebido"

ANCHO, FONDO, ESPESOR, RADIO = 900.0, 600.0, 18.0, 80.0
MUESTRAS = pathlib.Path(__file__).resolve().parents[2] / "poc" / "muestras"


# --- dibujos de mentira, con el formato de verdad ---------------------------
def entidad(tipo, **campos):
    """Los campos que draw101 escribe en toda entidad, más los suyos."""
    base = {"id": campos.pop("id", "e1"), "capa": campos.pop("capa", "0"), "color": None,
            "grosor": None, "tipo_linea": None, "escala_tl": 1.0,
            "visible": campos.pop("visible", True), "handle_origen": "", "origen": "",
            "espacio": campos.pop("espacio", ""), "grupo": "", "tipo": tipo}
    base.update(campos)
    return base


def rect(w, h, **campos):
    return entidad("polilinea", puntos=[[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0]], cerrada=True, **campos)


def circulo(x, y, r, **campos):
    return entidad("circulo", centro=[x, y], radio=r, **campos)


def dibujo(ruta, entidades, unidades="mm", capas=None, nombre="Tablero", formato=1):
    """Escribe un .t101d como lo escribe draw101: ZIP con los dos JSON."""
    capas = capas if capas is not None else [{"nombre": "0", "visible": True}]
    meta = {"formato": formato, "app": "draw101", "guardado": "2026-09-13T12:00:00", "unidad": "mm"}
    doc = {"nombre": nombre, "unidades": unidades, "capas": capas, "bloques": [],
           "entidades": entidades, "layouts": []}
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False))
        z.writestr("documento.json", json.dumps(doc, ensure_ascii=False))
    return pathlib.Path(ruta)


def volumen(ancho=ANCHO, radio=RADIO):
    return (ancho * FONDO - math.pi * radio ** 2) * ESPESOR


def pedir(url, datos=None):
    cuerpo = None if datos is None else json.dumps(datos).encode()
    peticion = urllib.request.Request(url, data=cuerpo, method="POST" if datos is not None else "GET",
                                      headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=60) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


def correr(r: comun.Reporte):
    with comun.carpeta() as d:
        # 1 · un dibujo en milímetros
        en_mm = dibujo(d / "tablero-mm.t101d", [rect(ANCHO, FONDO), circulo(ANCHO / 2, FONDO / 2, RADIO, id="e2")])
        lec = t101d.leer(en_mm)
        r.igual(lec["unidades"], "mm", "el dibujo en mm se declara en mm")
        r.casi(lec["factor_mm"], 1.0, "en mm no hay que convertir nada")
        r.igual(len(lec["entidades"]), 2, "entran las 2 entidades del modelo")
        r.igual(lec["ignoradas"], 0, "no se ignoró nada")
        r.igual(lec["dibujo"], "Tablero", "se sabe cómo se llama el dibujo")

        # 2 · el MISMO tablero dibujado en centímetros tiene que medir lo mismo
        en_cm = dibujo(d / "tablero-cm.t101d",
                       [rect(ANCHO / 10, FONDO / 10), circulo(ANCHO / 20, FONDO / 20, RADIO / 10, id="e2")],
                       unidades="cm")
        lec_cm = t101d.leer(en_cm)
        r.igual(lec_cm["unidades"], "cm", "el dibujo en cm se declara en cm")
        r.casi(lec_cm["factor_mm"], 10.0, "un centímetro son 10 mm")
        poli = next(e for e in lec_cm["entidades"] if e["tipo"] == "polilinea")
        r.casi(poli["puntos"][1][0], ANCHO, "el tablero en cm llega midiendo 900 mm de ancho")
        circ = next(e for e in lec_cm["entidades"] if e["tipo"] == "circulo")
        r.casi(circ["radio"], RADIO, "el barreno en cm llega con su radio en mm")
        r.casi(circ["centro"][1], FONDO / 2, "el centro del barreno también se convierte")

        # 3 · en metros, lo mismo
        en_m = dibujo(d / "tablero-m.t101d", [rect(ANCHO / 1000, FONDO / 1000)], unidades="m")
        lec_m = t101d.leer(en_m)
        r.casi(lec_m["factor_mm"], 1000.0, "un metro son 1000 mm")
        r.casi(lec_m["entidades"][0]["puntos"][2][1], FONDO, "el tablero en metros llega midiendo 600 mm de fondo")

        # 4 · el bulge es adimensional: se escalan las coordenadas, no la curvatura
        con_bulge = dibujo(d / "bulge.t101d", [entidad(
            "polilinea", puntos=[[0, 0, 0.5], [10, 0, 0], [10, 10, 0], [0, 10, 0]], cerrada=True)], unidades="cm")
        pts = t101d.leer(con_bulge)["entidades"][0]["puntos"]
        r.casi(pts[1][0], 100.0, "el tramo de 10 cm llega midiendo 100 mm")
        r.casi(pts[0][2], 0.5, "el bulge NO se escala: sigue siendo 0,5")

        # 5 · lo que no es el boceto se cuenta y se deja fuera
        mezcla = dibujo(d / "mezcla.t101d", [
            rect(ANCHO, FONDO),
            entidad("cota", id="c1", p1=[0, 0], p2=[900, 0]),
            entidad("texto", id="t1", p=[10, 10], texto="Tablero"),
            circulo(100, 100, 10, id="h1", espacio="Hoja 1"),
            circulo(200, 200, 10, id="h2", visible=False),
            circulo(300, 300, 10, id="h3", capa="APAGADA"),
        ], capas=[{"nombre": "0", "visible": True}, {"nombre": "APAGADA", "visible": False}])
        lec_m2 = t101d.leer(mezcla)
        r.igual(len(lec_m2["entidades"]), 1, "sólo entra la geometría del modelo, en capa prendida")
        r.igual(lec_m2["ignoradas"], 5, "las otras 5 se cuentan como ignoradas")
        r.cierto("cota" in lec_m2["tipos_ignorados"] and "texto" in lec_m2["tipos_ignorados"],
                 "se dice que se ignoraron cotas y textos")
        r.cierto("hoja" in lec_m2["tipos_ignorados"], "se dice que algo vivía en una hoja de impresión")
        r.cierto("apagada" in lec_m2["tipos_ignorados"], "se dice que algo estaba apagado")

        # 6 · archivos que no sirven: error claro, nunca un rastro de Python
        for ruta, que in ((d / "no-existe.t101d", "un archivo que no existe"),
                          (d / "basura.t101d", "un archivo que no es un ZIP")):
            if "basura" in ruta.name:
                ruta.write_text("esto no es un zip", encoding="utf-8")
            try:
                t101d.leer(ruta)
                r.cierto(False, f"{que} se rechaza")
            except ValueError as e:
                r.cierto(ruta.name in str(e), f"{que} se rechaza diciendo de qué archivo se trata",
                         f"el error dijo: {e}")
        futuro = dibujo(d / "futuro.t101d", [rect(ANCHO, FONDO)], formato=9)
        try:
            t101d.leer(futuro)
            r.cierto(False, "un formato más nuevo se rechaza")
        except ValueError as e:
            r.cierto("draw101" in str(e), "un .t101d de una versión más nueva de draw101 se rechaza con su motivo")

        # 7 · agregar el boceto al documento: se embebe, no se referencia
        doc = Documento.nuevo(nombre="Tablero", material="MDF", espesor_mm=ESPESOR)
        doc.agregar({"op": "boceto", "t101d": str(en_cm)})
        op = doc.operaciones[0]
        r.cierto("t101d" not in op, "la operación guardada no se queda con la ruta del .t101d")
        r.igual(len(op["entidades"]), 2, "la operación guarda las entidades del dibujo")
        r.igual(op["origen"]["unidades"], "cm", "se anota en qué unidades venía el dibujo")
        r.igual(op["origen"]["dibujo"], "Tablero", "se anota de qué dibujo vino")
        doc.agregar({"op": "extruir", "mm": ESPESOR})
        reg = doc.regenerar()
        r.exige(reg.solido is not None, "el boceto de draw101 se vuelve un sólido")
        r.casi(reg.solido.bounding_box().size.X, ANCHO, "el sólido mide 900 de ancho aunque se dibujó en cm")
        r.casi(reg.solido.volume, volumen(), "el volumen es el del tablero con su barreno", 1e-2)
        r.cierto("arriba" in reg.nombrador.caras, "las caras se nombran igual que con un boceto tecleado")

        guardado = doc.guardar(d / "de-draw101.s101")
        crudo = guardado.read_text(encoding="utf-8")
        r.cierto('"t101d"' not in crudo, "el .s101 guardado no apunta a ningún .t101d suelto")
        otro = Documento.abrir(guardado)
        r.casi(otro.regenerar().solido.volume, volumen(), "reabierto sin el .t101d al lado, da lo mismo", 1e-2)

        # 8 · las dos formas juntas, o un dibujo sin geometría: se rechazan
        try:
            doc.agregar({"op": "boceto", "t101d": str(en_mm), "entidades": [rect(10, 10)]})
            r.cierto(False, "un boceto con entidades Y ruta se rechaza")
        except ValueError as e:
            r.cierto("no los dos" in str(e), "un boceto con entidades Y ruta se rechaza diciendo por qué")
        solo_cotas = dibujo(d / "solo-cotas.t101d", [entidad("cota", id="c1", p1=[0, 0], p2=[900, 0])])
        try:
            doc.agregar({"op": "boceto", "t101d": str(solo_cotas)})
            r.cierto(False, "un dibujo sin geometría se rechaza")
        except ValueError as e:
            r.cierto("solo-cotas.t101d" in str(e), "un dibujo sin geometría se rechaza nombrando el archivo",
                     f"el error dijo: {e}")

        # 9 · por la API
        with servidor.Servidor(puerto=0) as s:
            codigo, resumen = pedir(s.url + "/api/t101d", {"ruta": str(en_cm)})
            r.igual(codigo, 200, "la API dice qué trae un dibujo de draw101")
            r.igual(resumen["unidades"], "cm", "el resumen trae las unidades del dibujo")
            r.igual(len(resumen["entidades"]), 2, "el resumen trae las entidades ya en milímetros")
            pedir(s.url + "/api/documento/nuevo", {"nombre": "Tablero", "material": "MDF", "espesor_mm": ESPESOR})
            codigo, _ = pedir(s.url + "/api/operacion", {"op": {"op": "boceto", "t101d": str(en_cm)}})
            r.igual(codigo, 200, "la API acepta un boceto importado de draw101")
            codigo, modelo = pedir(s.url + "/api/operacion", {"op": {"op": "extruir", "mm": ESPESOR}})
            r.cierto(modelo["n_caras"] >= 6, "el modelo llega con sus caras")
            r.casi(modelo["caja"][0], ANCHO, "la caja del modelo dice 900 de ancho", 0.01)
            try:
                pedir(s.url + "/api/t101d", {"ruta": str(d / "no-existe.t101d")})
                r.cierto(False, "la API rechaza un dibujo que no existe")
            except urllib.error.HTTPError as e:
                r.igual(e.code, 400, "la API rechaza un dibujo que no existe con 400")
            codigo, _ = pedir(s.url + "/api/salud")
            r.igual(codigo, 200, "el motor sigue vivo después del error")

    # 10 · las muestras de verdad del repositorio, hechas por draw101
    reales = sorted(MUESTRAS.glob("*.t101d")) if MUESTRAS.is_dir() else []
    leidas = 0
    for m in reales:
        lec = t101d.leer(m)
        r.cierto(lec["unidades"] in ("mm", "cm", "m"), f"{m.name}: se lee su unidad")
        r.cierto(len(lec["entidades"]) > 0, f"{m.name}: trae geometría en el modelo")
        leidas += 1
    r.numero("B2 muestras de draw101 leídas con el lector propio", leidas, "archivos")
