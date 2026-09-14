"""t010 · El puente con la suite: traer una cocina, regenerarla y entregarla.

Éste es el camino completo de features 6 y 69–74: llega un `.t101x` de Taller
101, cada mueble entra **como bloque** con su planta y su alzado, la corrida se
acota sola, se arma una hoja por mueble y se deja el paquete para SUPERVISOR.

La comprobación que de verdad importa está en el medio: **regenerar no se lleva
por delante lo que alguien anotó encima**. Un plano que hay que volver a anotar
entero cada vez que el mueble cambia de medida no se actualiza: se rehace, y
nadie lo rehace.
"""

from __future__ import annotations

import json

from core import entidades as ent
from core import t101x
from core.documento import Documento
from pruebas import comun

DESCRIPCION = "t101x: bloques, cotas, regenerar sin perder anotaciones, paquete"


PROYECTO = {
    "nombre": "Cocina Mondelez",
    "cliente": "Mondelez",
    "estandar": {},
    "gabinetes": [
        {"nombre": "B-01", "tipo": "base", "ancho": 900, "alto": 900, "prof": 600,
         "pos_x": 0, "pos_z": 0, "frentes": [{}, {}]},
        {"nombre": "B-02", "tipo": "base", "ancho": 600, "alto": 900, "prof": 600,
         "pos_x": 900, "pos_z": 0, "frentes": [{}]},
        {"nombre": "A-01", "tipo": "aereo", "ancho": 900, "alto": 700, "prof": 350,
         "pos_x": 0, "pos_z": 2000, "frentes": [{}, {}]},
    ],
}


def correr(r: comun.Reporte) -> None:
    with comun.carpeta() as tmp:
        ruta = tmp / "cocina.t101x"
        ruta.write_text(json.dumps(PROYECTO, ensure_ascii=False), encoding="utf-8")
        doc = _importar(r, ruta)
        _regenerar(r, doc, ruta, tmp)
        _paquete(r, doc, tmp)


def _importar(r: comun.Reporte, ruta) -> Documento:
    datos = t101x.leer(ruta)
    res = t101x.resumen(datos)
    r.igual(res["gabinetes"], 3, "el resumen cuenta los tres muebles")
    r.igual(res["bajos"], 2, "y sabe cuáles son bajos")
    r.igual(res["aereos"], 1, "y cuál es aéreo")

    doc = Documento.nuevo()
    with doc.transaccion("Importar de Taller 101"):
        hecho = t101x.generar(doc, datos, str(ruta))

    r.igual(hecho["gabinetes"], 3, "se dibujan los tres muebles")

    # --- Cada mueble es un bloque  ·  feature 70 --------------------------
    r.igual(sorted(doc.bloques), ["A-01", "B-01", "B-02"],
            "cada mueble entra como bloque, con su nombre")
    inserciones = [e for e in doc.lista() if e.tipo == "insercion"]
    r.igual(len(inserciones), 3, "y cada uno se inserta una vez")
    r.cierto(all(e.origen == t101x.ORIGEN for e in inserciones),
             "lo generado queda marcado como generado (es lo que permite rehacerlo)")

    # La posición en la cocina se respeta: X a la derecha, Z al frente.
    b02 = next(e for e in inserciones if e.bloque == "B-02")
    r.punto(b02.p, [900, 0], "el segundo mueble se inserta donde lo puso Taller 101")

    # --- Capas separadas  ·  feature 71 -----------------------------------
    r.cierto(t101x.CAPA_CUERPO in doc.capas and t101x.CAPA_FRENTES in doc.capas,
             "el cuerpo y los frentes van en capas distintas")
    capas_del_bloque = {e.capa for e in doc.bloques["B-01"].entidades}
    r.cierto(t101x.CAPA_FRENTES in capas_del_bloque,
             "y dentro del bloque los frentes están en la suya")

    # --- Acotado como se acota a mano  ·  feature 69 -----------------------
    cotas = [e for e in doc.lista() if e.tipo == "cota"]
    r.cierto(len(cotas) >= 4,
             "la corrida sale acotada: un ancho por mueble y el total",
             f"salieron {len(cotas)}")
    r.cierto(all(c.capa == t101x.CAPA_COTAS for c in cotas),
             "y todas las cotas en la capa COTAS")
    alturas = [c for c in cotas if abs(c.rotacion - 90) < 1e-9]
    r.igual(len(alturas), 2,
            "una sola cota de altura por cada altura distinta (900 y 700), "
            "no una por mueble")
    r.cierto(all(c.origen == t101x.ORIGEN for c in cotas),
             "las cotas generadas quedan marcadas, y **fuera** de los bloques")

    return doc


def _regenerar(r: comun.Reporte, doc: Documento, ruta, tmp) -> None:
    """Feature 72: el mueble cambia de medida en Taller 101 y el plano se
    actualiza sin perder lo que alguien escribió encima."""
    with doc.transaccion("Anotar a mano"):
        nota = doc.agregar(ent.Texto(p=[0, -1200], texto="REVISAR HERRAJE", altura=50))
        raya = doc.agregar(ent.Linea(p1=[0, -1100], p2=[1500, -1100]))
    r.igual(nota.origen, "", "lo que dibuja una persona no queda marcado como generado")

    # En Taller 101 el mueble creció.
    nuevo = json.loads(json.dumps(PROYECTO))
    nuevo["gabinetes"][1]["ancho"] = 750
    ruta.write_text(json.dumps(nuevo, ensure_ascii=False), encoding="utf-8")

    with doc.transaccion("Actualizar de Taller 101"):
        t101x.regenerar(doc)

    ids = {e.id for e in doc.lista()}
    r.cierto(nota.id in ids, "la anotación a mano sigue ahí después de regenerar")
    r.cierto(raya.id in ids, "y la raya que se trazó encima también")

    b02 = next(e for e in doc.lista()
               if e.tipo == "insercion" and e.bloque.startswith("B-02"))
    ancho = _ancho_del_bloque(doc, b02.bloque)
    r.casi(ancho, 750, "y el mueble ya mide lo que ahora dice Taller 101", 1.0)

    generadas = [e for e in doc.lista() if e.origen == t101x.ORIGEN]
    r.igual(len([e for e in generadas if e.tipo == "insercion"]), 3,
            "no se duplicaron los muebles al regenerar")


def _ancho_del_bloque(doc: Documento, nombre: str) -> float:
    xs = [p[0] for e in doc.bloques[nombre].entidades
          for p in _puntos_de(e)]
    return (max(xs) - min(xs)) if xs else 0.0


def _puntos_de(e) -> list:
    for campo in ("puntos",):
        if getattr(e, campo, None):
            return [[p[0], p[1]] for p in getattr(e, campo)]
    if getattr(e, "p1", None) and getattr(e, "p2", None):
        return [e.p1, e.p2]
    if getattr(e, "p", None):
        return [e.p]
    return []


def _paquete(r: comun.Reporte, doc: Documento, tmp) -> None:
    """Feature 73 y 74: una hoja por mueble y la carpeta para SUPERVISOR.

    Se arma con las mismas funciones del servidor, que es lo que corre la app.
    """
    import server
    server.S.doc = doc
    server.S.ruta = None
    server.S.espacio = ""

    hojas = _cuerpo(server.hojas_por_mueble())
    r.igual(len(doc.layouts), 3, "sale una hoja por mueble (feature 73)")
    r.cierto(all(L.get("ventanas") for L in doc.layouts),
             "y cada hoja trae su ventana, encuadrada sobre su mueble")

    carpeta = tmp / "para-supervisor"
    res = _cuerpo(server.paquete_supervisor(
        server.PaqueteEntrada(carpeta=str(carpeta))))

    r.cierto((carpeta / "manifiesto.json").exists(),
             "el paquete deja un manifiesto que dice qué es cada cosa")
    archivos = sorted(p.suffix for p in carpeta.iterdir())
    r.cierto(".dxf" in archivos, "deja el DXF, que es lo que se corta")
    r.cierto(".pdf" in archivos, "y el PDF, que es lo que se mira")

    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    r.igual(sorted(manifiesto["muebles"]), sorted(doc.bloques),
            "el manifiesto lista los muebles que van dentro")
    r.igual(len(manifiesto["hojas"]), 3, "y las hojas del paquete")
    r.cierto(manifiesto.get("origen_t101x", {}).get("ruta", "").endswith(".t101x"),
             "y de qué proyecto de Taller 101 salió todo")


def _cuerpo(res):
    if isinstance(res, dict):
        return res
    return json.loads(bytes(res.body).decode("utf-8"))
